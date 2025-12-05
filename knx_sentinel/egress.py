import abc
import logging
import json
import time
import aiohttp
import asyncio
# paho-mqtt is synchronous, so we run it in executor or use a wrapper. 
# For simplicity in this prototype, we'll use the standard client and loop.start() if available, 
# or just run blocking publish in executor.
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class EgressProvider(abc.ABC):
    @abc.abstractmethod
    async def send_metric(self, measurement, tags, fields, timestamp=None):
        pass

class InfluxDBProvider(EgressProvider):
    def __init__(self, host, token, org, bucket):
        self.host = host
        self.token = token
        self.org = org
        self.bucket = bucket
        self.url = f"{host}/api/v2/write?org={org}&bucket={bucket}&precision=ns"
        self.headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8"
        }

    async def send_metric(self, measurement, tags, fields, timestamp=None):
        """Sends data to InfluxDB using Line Protocol."""
        if timestamp is None:
            timestamp = time.time_ns()
            
        # Format Line Protocol
        # measurement,tag1=val1 field1=val1 timestamp
        
        tag_str = ",".join([f"{self._escape_tag(k)}={self._escape_tag(str(v))}" for k, v in tags.items()])
        field_str = ",".join([f"{self._escape_tag(k)}={self._format_field(v)}" for k, v in fields.items()])
        
        line = f"{measurement}"
        if tag_str:
            line += f",{tag_str}"
        line += f" {field_str} {timestamp}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.url, data=line, headers=self.headers) as resp:
                    if resp.status not in (200, 204):
                        text = await resp.text()
                        _LOGGER.error(f"InfluxDB Write Failed: {resp.status} - {text}")
                    else:
                        _LOGGER.debug(f"InfluxDB Write Success: {line}")
            except Exception as e:
                _LOGGER.error(f"InfluxDB Connection Error: {e}")

    def _escape_tag(self, value):
        return value.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

    def _format_field(self, value):
        if isinstance(value, int):
            return f"{value}i"
        elif isinstance(value, str):
            return f'"{value}"'
        return str(value)

class MQTTProvider(EgressProvider):
    def __init__(self, broker, port, topic_prefix, client_id="knx_sentinel"):
        self.broker = broker
        self.port = port
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client(client_id=client_id)
        # In a real app, we'd handle connection loop properly
        self.connected = False
        
    async def start(self):
        # Run connect in executor to avoid blocking asyncio loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._connect)
        self.client.loop_start()

    def _connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.connected = True
            _LOGGER.info(f"Connected to MQTT Broker {self.broker}")
        except Exception as e:
            _LOGGER.error(f"MQTT Connection Error: {e}")

    async def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    async def send_metric(self, measurement, tags, fields, timestamp=None):
        if not self.connected:
            return

        if timestamp is None:
            timestamp = int(time.time())

        payload = {
            "measurement": measurement,
            "tags": tags,
            "fields": fields,
            "timestamp": timestamp
        }
        
        # Topic: prefix/site_id/measurement (site_id is in tags)
        site_id = tags.get("site_id", "default")
        topic = f"{self.topic_prefix}/{site_id}/{measurement}"
        
        # Publish is blocking in paho, but loop_start handles network loop. 
        # publish() returns an info object, it's non-blocking for queuing.
        info = self.client.publish(topic, json.dumps(payload))
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
             _LOGGER.error(f"MQTT Publish Failed: {info.rc}")
        else:
             _LOGGER.debug(f"MQTT Publish Success: {topic}")
