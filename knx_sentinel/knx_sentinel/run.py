import asyncio
import logging
import signal
import sys
import os
from knx_sentinel.ha_client import HAWebSocketClient
from knx_sentinel.bus_monitor import BusLoadMonitor
from knx_sentinel.anomaly_engine import AnomalyEngine
from knx_sentinel.autoconfig import AutoConfigurator
from knx_sentinel.diagnostics import DiagnosticsEngine
from knx_sentinel.egress import InfluxDBProvider, MQTTProvider


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stdout
)
_LOGGER = logging.getLogger(__name__)

import json

def load_config():
    """Loads configuration from /data/options.json or env vars."""
    options_path = "/data/options.json"
    config = {}
    
    if os.path.exists(options_path):
        try:
            with open(options_path, "r") as f:
                options = json.load(f)
                _LOGGER.info(f"Loaded configuration from {options_path}")
                
                # Map options to internal structure
                config = {
                    "client_id": options.get("client_id", "default_client"),
                    "site_id": options.get("site_id", "default_site"),
                    "mode": options.get("mode", "influxdb_cloud"),
                    "influxdb": {
                        "host": options.get("influxdb", {}).get("host"),
                        "token": options.get("influxdb", {}).get("token"),
                        "org": options.get("influxdb", {}).get("org"),
                        "bucket": options.get("influxdb", {}).get("bucket")
                    },
                    "mqtt": {
                        "broker": options.get("mqtt", {}).get("broker"),
                        "port": options.get("mqtt", {}).get("port", 1883),
                        "topic_prefix": options.get("mqtt", {}).get("topic_prefix", "knx")
                    },
                    "anomaly_detection": options.get("anomaly_detection", {}),
                    "lat": float(options.get("latitude", 0.0)),
                    "lon": float(options.get("longitude", 0.0)),
                }
        except Exception as e:
            _LOGGER.error(f"Failed to load options.json: {e}")
            sys.exit(1)
    else:
        _LOGGER.info("Using environment variables for configuration")
        config = {
            "client_id": os.getenv("CLIENT_ID", "default_client"),
            "site_id": os.getenv("SITE_ID", "default_site"),
            "mode": os.getenv("EGRESS_MODE", "influxdb"),
            "influxdb": {
                "host": os.getenv("INFLUX_HOST", "http://localhost:8086"),
                "token": os.getenv("INFLUX_TOKEN", "token"),
                "org": os.getenv("INFLUX_ORG", "org"),
                "bucket": os.getenv("INFLUX_BUCKET", "bucket")
            },
            "mqtt": {
                "broker": os.getenv("MQTT_BROKER", "localhost"),
                "port": int(os.getenv("MQTT_PORT", 1883)),
                "topic_prefix": os.getenv("MQTT_PREFIX", "knx")
            },
            "anomaly_detection": {},
            "lat": float(os.getenv("LATITUDE", 0.0)),
            "lon": float(os.getenv("LONGITUDE", 0.0)),
        }
    return config

async def main():
    _LOGGER.info("Starting KNX Sentinel...")
    
    config = load_config()
    
    # Initialize Egress
    if config["mode"] == "mqtt":
        egress = MQTTProvider(
            config["mqtt"]["broker"], 
            config["mqtt"]["port"], 
            config["mqtt"]["topic_prefix"]
        )
        await egress.start()
    else:
        egress = InfluxDBProvider(
            config["influxdb"]["host"],
            config["influxdb"]["token"],
            config["influxdb"]["org"],
            config["influxdb"]["bucket"]
        )
        await egress.start()

    # Initialize Components
    bus_monitor = BusLoadMonitor()
    anomaly_engine = AnomalyEngine()
    diagnostics_engine = DiagnosticsEngine(lat=config["lat"], lon=config["lon"])
    client = HAWebSocketClient()
    autoconfig = AutoConfigurator(client)
    if config["lat"] == 0.0 and config["lon"] == 0.0:
        _LOGGER.warning("Latitude/longitude not configured; solar diagnostics will use 0,0 (equator)")

    # Pre-register sensors from manual config (these take precedence over auto-discovery)
    ad_config = config.get("anomaly_detection", {})
    if ad_config.get("enabled", True):
        for sensor in ad_config.get("sensors", []):
            entity_id = sensor.get("entity_id")
            if not entity_id:
                continue
            profile = {"method": sensor.get("method", "z_score")}
            if "threshold" in sensor:
                profile["threshold"] = sensor["threshold"]
            if "min" in sensor:
                profile["min"] = sensor["min"]
            if "max" in sensor:
                profile["max"] = sensor["max"]
            anomaly_engine.register_sensor(entity_id, profile)
            _LOGGER.info(f"Registered sensor from config: {entity_id} -> {profile}")
    
    # Common Tags
    common_tags = {
        "client_id": config["client_id"],
        "site_id": config["site_id"]
    }
    
    # Define Event Callback
    async def handle_event(event):
        # 1. Bus Load Counting
        await bus_monitor.process_event(event)

        # 2. Sensor Processing
        data = event.get("data", {})
        destination = data.get("destination")  # Group Address
        value = data.get("value")

        if destination and value is not None:
            entity_id = f"sensor.knx_{destination.replace('/', '_')}"
            anomaly_engine.register_sensor(entity_id)

            profile = anomaly_engine.profiles.get(entity_id, {})

            if profile.get("method") == "solar_check":
                # Route illuminance sensors to physics-based diagnostics
                try:
                    fault = diagnostics_engine.check_solar_sensor(entity_id, float(value))
                    if fault:
                        tags = common_tags.copy()
                        tags["entity_id"] = entity_id
                        tags["type"] = "diagnostic"
                        fields = {
                            "lux": float(value),
                            "solar_elevation": fault.get("elevation", 0.0),
                        }
                        await egress.send_metric("knx_diagnostics", tags, fields)
                except Exception as e:
                    _LOGGER.error(f"Solar check error for {entity_id}: {e}")
            else:
                # Statistical anomaly detection
                anomaly = anomaly_engine.process_value(entity_id, value)
                if anomaly:
                    tags = common_tags.copy()
                    tags["entity_id"] = entity_id
                    tags["type"] = "anomaly"
                    fields = {
                        "value": float(value),
                        "z_score": anomaly.get("z_score", 0.0),
                        "threshold": anomaly.get("threshold", 0.0),
                    }
                    await egress.send_metric("knx_diagnostics", tags, fields)

    client.set_callback(handle_event)

    # Setup Signal Handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        _LOGGER.info("Signal received, stopping...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start Client Task
    client_task = asyncio.create_task(client.start())

    # Wait for HA connection then run auto-discovery
    try:
        await asyncio.wait_for(client.connected_event.wait(), timeout=10)
        discovered = await autoconfig.discover_entities()
        for item in discovered:
            anomaly_engine.register_sensor(item["entity_id"], item["profile"])
        _LOGGER.info(f"Auto-discovery complete: {len(discovered)} entities registered")
    except asyncio.TimeoutError:
        _LOGGER.warning("Timed out waiting for HA connection; skipping auto-discovery")
    
    # Start Aggregation Loop (Background Task)
    async def aggregation_loop():
        while not stop_event.is_set():
            try:
                await asyncio.sleep(60)
                
                # 1. Bus Load
                count = await bus_monitor.get_and_reset()
                _LOGGER.info(f"Bus Load: {count} telegrams/min")
                
                tags = common_tags.copy()
                tags["metric_type"] = "bus_load"
                fields = {"telegrams_per_min": count}
                await egress.send_metric("knx_metrics", tags, fields)
                
                # 2. Heartbeat
                hb_tags = common_tags.copy()
                hb_tags["metric_type"] = "heartbeat"
                await egress.send_metric("agent_status", hb_tags, {"online": 1})
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in aggregation loop: {e}")

    agg_task = asyncio.create_task(aggregation_loop())
    
    # Wait for stop signal
    await stop_event.wait()
    
    # Shutdown
    agg_task.cancel()
    if hasattr(egress, "stop"):
        await egress.stop()
    await client.stop()
    try:
        await client_task
        await agg_task
    except asyncio.CancelledError:
        pass
        
    _LOGGER.info("KNX Sentinel stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
