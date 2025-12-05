import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from knx_sentinel.egress import InfluxDBProvider, MQTTProvider

class TestEgress(unittest.IsolatedAsyncioTestCase):
    async def test_influxdb_formatting(self):
        provider = InfluxDBProvider("http://localhost", "token", "org", "bucket")
        
        tags = {"site": "NYC", "tag with space": "value,comma"}
        fields = {"temp": 22.5, "count": 10}
        timestamp = 1234567890000000000
        
        # Mock aiohttp
        mock_post = MagicMock()
        mock_post.__aenter__.return_value.status = 204
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post
        mock_session.__aenter__.return_value = mock_session
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await provider.send_metric("sensor_data", tags, fields, timestamp)
            
            # Verify payload
            # Expected: sensor_data,site=NYC,tag\ with\ space=value\,comma temp=22.5,count=10i 1234567890000000000
            call_args = mock_session.post.call_args
            data = call_args[1]['data']
            
            self.assertIn("sensor_data", data)
            self.assertIn("site=NYC", data)
            self.assertIn("tag\\ with\\ space=value\\,comma", data)
            self.assertIn("temp=22.5", data)
            self.assertIn("count=10i", data)
            self.assertIn(str(timestamp), data)

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
