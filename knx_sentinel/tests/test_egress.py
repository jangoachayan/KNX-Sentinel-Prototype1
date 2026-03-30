import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from knx_sentinel.egress import InfluxDBProvider, MQTTProvider

class TestEgress(unittest.IsolatedAsyncioTestCase):
    def test_influxdb_line_formatting(self):
        provider = InfluxDBProvider("http://localhost", "token", "org", "bucket")
        tags = {"site": "NYC", "tag with space": "value,comma"}
        fields = {"temp": 22.5, "count": 10}
        timestamp = 1234567890000000000

        line = provider._format_line("sensor_data", tags, fields, timestamp)

        self.assertIn("sensor_data", line)
        self.assertIn("site=NYC", line)
        self.assertIn("tag\\ with\\ space=value\\,comma", line)
        self.assertIn("temp=22.5", line)
        self.assertIn("count=10i", line)
        self.assertIn(str(timestamp), line)

    async def test_influxdb_send_metric_enqueues(self):
        provider = InfluxDBProvider("http://localhost", "token", "org", "bucket")
        await provider.send_metric("sensor_data", {"site": "NYC"}, {"val": 1.0}, 1234567890000000000)
        self.assertEqual(provider._buffer.qsize(), 1)

    async def test_influxdb_retry_on_failure(self):
        provider = InfluxDBProvider("http://localhost", "token", "org", "bucket")

        call_count = 0

        def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 503
            mock_resp.text = AsyncMock(return_value="unavailable")
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=False)
            return mock_resp

        with patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = fake_post
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            with patch('asyncio.sleep', new_callable=AsyncMock):
                await provider._send_with_retry("measurement field=1i 0")

        self.assertEqual(call_count, 4)  # exhausts all retries

    async def test_influxdb_no_retry_on_client_error(self):
        provider = InfluxDBProvider("http://localhost", "token", "org", "bucket")

        call_count = 0

        def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 401
            mock_resp.text = AsyncMock(return_value="unauthorized")
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=False)
            return mock_resp

        with patch('aiohttp.ClientSession') as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.post = fake_post
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            await provider._send_with_retry("measurement field=1i 0")

        self.assertEqual(call_count, 1)  # stops immediately on 401

    async def test_mqtt_payload(self):
        provider = MQTTProvider("localhost", 1883, "knx")
        provider.client = MagicMock()
        provider.connected = True
        
        tags = {"site_id": "site1"}
        fields = {"val": 123}
        
        await provider.send_metric("test_metric", tags, fields, 1000)
        
        provider.client.publish.assert_called()
        args = provider.client.publish.call_args
        topic = args[0][0]
        payload = args[0][1]
        
        self.assertEqual(topic, "knx/site1/test_metric")
        self.assertIn('"val": 123', payload)

if __name__ == '__main__':
    unittest.main()
