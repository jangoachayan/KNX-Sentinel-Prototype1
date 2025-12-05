import unittest
import asyncio
from knx_sentinel.bus_monitor import BusLoadMonitor
from knx_sentinel.anomaly_engine import AnomalyEngine
from knx_sentinel.autoconfig import AutoConfigurator

class TestLogicCore(unittest.IsolatedAsyncioTestCase):
    async def test_bus_monitor(self):
        monitor = BusLoadMonitor()
        await monitor.process_event({})
        await monitor.process_event({})
        await monitor.process_event({})
        
        count = await monitor.get_and_reset()
        self.assertEqual(count, 3)
        
        count_after = await monitor.get_and_reset()
        self.assertEqual(count_after, 0)

    def test_anomaly_engine_z_score(self):
        engine = AnomalyEngine()
        engine.register_sensor("sensor.temp", {"method": "z_score", "threshold": 2.0})
        
        # Feed 30 steady values (mean=20, std_dev=0)
        for _ in range(30):
            engine.process_value("sensor.temp", 20)
            
        # Feed one slightly different to create variance (std_dev > 0)
        # If we keep it 0, z-score is 0.
        engine.process_value("sensor.temp", 21) 
        
        # Now we have a mean slightly > 20 and some variance.
        # Let's feed a spike.
        res = engine.process_value("sensor.temp", 100)
        
        # Should be detected
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "anomaly")
        self.assertEqual(res["subtype"], "z_score")

    def test_autoconfig_analysis(self):
        # Test Voltage
        entry = {"platform": "knx", "entity_id": "sensor.voltage", "device_class": "voltage"}
        profile = AutoConfigurator.analyze_entity(entry)
        self.assertEqual(profile["method"], "range")
        self.assertEqual(profile["min"], 207)

        # Test Non-KNX
        entry_bad = {"platform": "mqtt", "entity_id": "sensor.voltage"}
        profile_bad = AutoConfigurator.analyze_entity(entry_bad)
        self.assertIsNone(profile_bad)

if __name__ == '__main__':
    unittest.main()
