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

_INFLUX_MAX_BUFFER = 200
_INFLUX_MAX_RETRIES = 4
_INFLUX_RETRY_BASE = 2  # seconds

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
        self._buffer = asyncio.Queue(maxsize=_INFLUX_MAX_BUFFER)
        self._flush_task = None

    async def start(self):
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

    async def send_metric(self, measurement, tags, fields, timestamp=None):
        """Enqueues a metric for delivery to InfluxDB."""
        if timestamp is None:
            timestamp = time.time_ns()
        line = self._format_line(measurement, tags, fields, timestamp)
        try:
            self._buffer.put_nowait(line)
        except asyncio.QueueFull:
            _LOGGER.warning("InfluxDB buffer full; dropping oldest metric")
            try:
                self._buffer.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._buffer.put_nowait(line)

    async def _flush_loop(self):
        while True:
            line = await self._buffer.get()
            await self._send_with_retry(line)

    async def _send_with_retry(self, line):
        delay = _INFLUX_RETRY_BASE
        for attempt in range(1, _INFLUX_MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.url, data=line, headers=self.headers) as resp:
                        if resp.status in (200, 204):
                            _LOGGER.debug(f"InfluxDB Write Success: {line}")
                            return
                        text = await resp.text()
                        _LOGGER.error(f"InfluxDB Write Failed ({resp.status}): {text}")
                        if resp.status in (400, 401, 403):
                            return  # non-retriable client errors
            except Exception as e:
                _LOGGER.error(f"InfluxDB Connection Error (attempt {attempt}): {e}")
            if attempt < _INFLUX_MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
        _LOGGER.error(f"InfluxDB: dropping metric after {_INFLUX_MAX_RETRIES} failed attempts")

    def _format_line(self, measurement, tags, fields, timestamp):
        tag_str = ",".join([f"{self._escape_tag(k)}={self._escape_tag(str(v))}" for k, v in tags.items()])
        field_str = ",".join([f"{self._escape_tag(k)}={self._format_field(v)}" for k, v in fields.items()])
        line = f"{measurement}"
        if tag_str:
            line += f",{tag_str}"
        line += f" {field_str} {timestamp}"
        return line

    def _escape_tag(self, value):
        return value.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

    def _format_field(self, value):
        if isinstance(value, int):
            return f"{value}i"
        elif isinstance(value, str):
            return f'"{value}"'
        return str(value)

_MQTT_RECONNECT_BASE = 2   # seconds
_MQTT_RECONNECT_MAX = 60   # seconds

class MQTTProvider(EgressProvider):
    def __init__(self, broker, port, topic_prefix, client_id="knx_sentinel"):
        self.broker = broker
        self.port = port
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client(client_id=client_id)
        self.connected = False
        self._reconnect_delay = _MQTT_RECONNECT_BASE
        self._stopping = False

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self._reconnect_delay = _MQTT_RECONNECT_BASE
            _LOGGER.info(f"Connected to MQTT Broker {self.broker}")
        else:
            _LOGGER.error(f"MQTT Connect failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if self._stopping:
            return
        _LOGGER.warning(f"MQTT disconnected (rc={rc}); scheduling reconnect in {self._reconnect_delay}s")
        time.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, _MQTT_RECONNECT_MAX)
        try:
            self.client.reconnect()
        except Exception as e:
            _LOGGER.error(f"MQTT Reconnect failed: {e}")

    async def start(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._connect)
        self.client.loop_start()

    def _connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
        except Exception as e:
            _LOGGER.error(f"MQTT Connection Error: {e}")

    async def stop(self):
        self._stopping = True
        self.client.loop_stop()
        self.client.disconnect()

    async def send_metric(self, measurement, tags, fields, timestamp=None):
        if not self.connected:
            _LOGGER.debug("MQTT not connected; dropping metric")
            return

        if timestamp is None:
            timestamp = int(time.time())

        payload = {
            "measurement": measurement,
            "tags": tags,
            "fields": fields,
            "timestamp": timestamp
        }

        site_id = tags.get("site_id", "default")
        topic = f"{self.topic_prefix}/{site_id}/{measurement}"

        info = self.client.publish(topic, json.dumps(payload))
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error(f"MQTT Publish Failed: {info.rc}")
        else:
            _LOGGER.debug(f"MQTT Publish Success: {topic}")
