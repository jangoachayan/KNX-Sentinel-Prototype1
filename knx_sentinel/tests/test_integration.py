import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from knx_sentinel.anomaly_engine import AnomalyEngine
from knx_sentinel.bus_monitor import BusLoadMonitor
from knx_sentinel.egress import InfluxDBProvider


class TestEventFlowIntegration(unittest.IsolatedAsyncioTestCase):
    """
    End-to-end tests for the core event processing pipeline:
    KNX event -> BusMonitor -> AnomalyEngine -> EgressProvider
    """

    def _make_event(self, destination, value):
        return {"data": {"destination": destination, "value": value}}

    async def test_normal_event_increments_bus_load(self):
        monitor = BusLoadMonitor()
        for _ in range(5):
            await monitor.process_event(self._make_event("1/1/1", 20.0))
        count = await monitor.get_and_reset()
        self.assertEqual(count, 5)

    async def test_anomaly_detected_and_egressed(self):
        engine = AnomalyEngine()
        engine.register_sensor("sensor.knx_1_1_1", {"method": "z_score", "threshold": 2.0})

        sent_metrics = []

        async def fake_send(measurement, tags, fields, timestamp=None):
            sent_metrics.append({"measurement": measurement, "tags": tags, "fields": fields})

        egress = MagicMock()
        egress.send_metric = fake_send

        # Seed 30 values around 20
        for i in range(30):
            engine.process_value("sensor.knx_1_1_1", 20.0 + (i % 2) * 0.1)

        # Simulate event handler logic (mirroring run.py handle_event)
        async def handle_event(event, bus_monitor, anomaly_engine, egress_provider, common_tags):
            await bus_monitor.process_event(event)
            data = event.get("data", {})
            destination = data.get("destination")
            value = data.get("value")
            if destination and value is not None:
                entity_id = f"sensor.knx_{destination.replace('/', '_')}"
                anomaly_engine.register_sensor(entity_id)
                anomaly = anomaly_engine.process_value(entity_id, value)
                if anomaly:
                    tags = common_tags.copy()
                    tags["entity_id"] = entity_id
                    tags["type"] = "anomaly"
                    fields = {
                        "value": float(value),
                        "z_score": anomaly.get("z_score", 0.0),
                        "threshold": anomaly.get("threshold", 0.0)
                    }
                    await egress_provider.send_metric("knx_diagnostics", tags, fields)

        monitor = BusLoadMonitor()
        common_tags = {"client_id": "test", "site_id": "s1"}

        # Send a spike — should trigger anomaly
        spike_event = self._make_event("1/1/1", 999.0)
        await handle_event(spike_event, monitor, engine, egress, common_tags)

        self.assertEqual(len(sent_metrics), 1)
        self.assertEqual(sent_metrics[0]["measurement"], "knx_diagnostics")
        self.assertIn("entity_id", sent_metrics[0]["tags"])
        self.assertGreater(sent_metrics[0]["fields"]["z_score"], 2.0)

    async def test_normal_value_does_not_egress_anomaly(self):
        engine = AnomalyEngine()
        engine.register_sensor("sensor.knx_2_2_2", {"method": "z_score", "threshold": 3.0})

        sent_metrics = []

        async def fake_send(measurement, tags, fields, timestamp=None):
            sent_metrics.append(measurement)

        egress = MagicMock()
        egress.send_metric = fake_send

        # Seed 30 values with natural variance (mean ~22, std_dev ~2)
        base = [20.0, 21.0, 22.0, 23.0, 24.0, 21.5, 22.5, 20.5, 23.5, 22.0]
        for i in range(30):
            engine.process_value("sensor.knx_2_2_2", base[i % len(base)])

        # A value close to the mean — well within 3 std devs
        result = engine.process_value("sensor.knx_2_2_2", 22.1)
        self.assertIsNone(result)
        self.assertEqual(len(sent_metrics), 0)

    async def test_range_profile_fires_on_out_of_bounds(self):
        engine = AnomalyEngine()
        engine.register_sensor("sensor.knx_voltage", {"method": "range", "min": 207, "max": 253})

        anomaly = engine.process_value("sensor.knx_voltage", 300.0)
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly["subtype"], "range_high")

        anomaly_low = engine.process_value("sensor.knx_voltage", 100.0)
        self.assertIsNotNone(anomaly_low)
        self.assertEqual(anomaly_low["subtype"], "range_low")

    async def test_configurable_threshold_respected(self):
        # Tighter threshold (1.5) should fire sooner than default (3.0)
        engine = AnomalyEngine()
        engine.register_sensor("sensor.strict", {"method": "z_score", "threshold": 1.5})

        # Seed 30 values with slight variance
        for i in range(30):
            engine.process_value("sensor.strict", 20.0 + (i % 2) * 0.5)

        # A moderate spike that would pass threshold=3.0 but fails at 1.5
        result = engine.process_value("sensor.strict", 23.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["threshold"], 1.5)

    async def test_bus_load_resets_after_read(self):
        monitor = BusLoadMonitor()
        for _ in range(10):
            await monitor.process_event({})
        first = await monitor.get_and_reset()
        second = await monitor.get_and_reset()
        self.assertEqual(first, 10)
        self.assertEqual(second, 0)


if __name__ == '__main__':
    unittest.main()
