import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from knx_sentinel.diagnostics import DiagnosticsEngine


class TestDiagnosticsEngine(unittest.TestCase):
    def setUp(self):
        # New York City coordinates
        self.engine = DiagnosticsEngine(lat=40.71, lon=-74.00)

    def test_solar_fault_detected(self):
        # Patch solar elevation to a high value (sun is up)
        with patch('knx_sentinel.diagnostics.MathKernel.calculate_solar_elevation', return_value=45.0):
            ts = datetime(2024, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
            result = self.engine.check_solar_sensor("sensor.outdoor_lux", lux_value=2, timestamp=ts)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "diagnostic")
        self.assertEqual(result["subtype"], "solar_mismatch")
        self.assertEqual(result["entity_id"], "sensor.outdoor_lux")
        self.assertAlmostEqual(result["elevation"], 45.0)
        self.assertEqual(result["lux"], 2)

    def test_no_fault_when_sun_low(self):
        # Sun below threshold — lux being low is expected
        with patch('knx_sentinel.diagnostics.MathKernel.calculate_solar_elevation', return_value=5.0):
            ts = datetime(2024, 6, 21, 6, 0, 0, tzinfo=timezone.utc)
            result = self.engine.check_solar_sensor("sensor.outdoor_lux", lux_value=2, timestamp=ts)

        self.assertIsNone(result)

    def test_no_fault_when_lux_normal(self):
        # Sun high, lux also high — sensor is fine
        with patch('knx_sentinel.diagnostics.MathKernel.calculate_solar_elevation', return_value=45.0):
            ts = datetime(2024, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
            result = self.engine.check_solar_sensor("sensor.outdoor_lux", lux_value=50000, timestamp=ts)

        self.assertIsNone(result)

    def test_uses_current_time_when_no_timestamp(self):
        fixed_time = datetime(2024, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
        with patch('knx_sentinel.diagnostics.datetime') as mock_dt, \
             patch('knx_sentinel.diagnostics.MathKernel.calculate_solar_elevation', return_value=5.0) as mock_elev:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            self.engine.check_solar_sensor("sensor.test", lux_value=100)
            mock_elev.assert_called_once()


if __name__ == '__main__':
    unittest.main()
