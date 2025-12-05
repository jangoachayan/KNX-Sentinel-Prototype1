import unittest
import math
from datetime import datetime, timezone
from knx_sentinel.math_kernel import MathKernel

class TestMathKernel(unittest.TestCase):
    def test_mean(self):
        data = [1, 2, 3, 4, 5]
        self.assertEqual(MathKernel.calculate_mean(data), 3.0)
        self.assertEqual(MathKernel.calculate_mean([]), 0.0)

    def test_variance(self):
        data = [1, 2, 3, 4, 5]
        # Mean = 3. Variance = ((4+1+0+1+4)/5) = 2.0
        self.assertAlmostEqual(MathKernel.calculate_variance(data), 2.0)
        self.assertEqual(MathKernel.calculate_variance([1]), 0.0)

    def test_std_dev(self):
        data = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(MathKernel.calculate_std_dev(data), math.sqrt(2.0))

    def test_z_score(self):
        # Mean=3, StdDev=1.414
        # Z for 5 = (5-3)/1.414 = 1.414
        self.assertAlmostEqual(MathKernel.calculate_z_score(5, 3, 1.41421356), 1.41421356)
        self.assertEqual(MathKernel.calculate_z_score(5, 3, 0), 0.0)

    def test_slope(self):
        # y = 2x + 1
        x = [1, 2, 3, 4, 5]
        y = [3, 5, 7, 9, 11]
        self.assertAlmostEqual(MathKernel.calculate_linear_regression_slope(x, y), 2.0)
        
        # Horizontal line y = 5, slope 0
        y_flat = [5, 5, 5, 5, 5]
        self.assertEqual(MathKernel.calculate_linear_regression_slope(x, y_flat), 0.0)

    def test_solar_elevation(self):
        # Test case: Noon at Equator on Equinox (approx)
        # March 20, 2024 12:00 UTC, Lat 0, Lon 0
        dt = datetime(2024, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        el = MathKernel.calculate_solar_elevation(0, 0, dt)
        # Should be close to 90 degrees
        # Note: Exact value depends on specific year/time, but should be high
        print(f"Equinox Elevation: {el}")
        self.assertTrue(el > 85.0)

        # Test case: Midnight
        dt_night = datetime(2024, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        el_night = MathKernel.calculate_solar_elevation(0, 0, dt_night)
        print(f"Midnight Elevation: {el_night}")
        self.assertTrue(el_night < -80.0)

if __name__ == '__main__':
    unittest.main()
