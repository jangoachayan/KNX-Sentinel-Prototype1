import math
from datetime import datetime, timezone

class MathKernel:
    @staticmethod
    def calculate_mean(data):
        """Calculates the arithmetic mean of a list of numbers."""
        if not data:
            return 0.0
        return sum(data) / len(data)

    @staticmethod
    def calculate_variance(data):
        """Calculates the variance of a list of numbers."""
        if not data or len(data) < 2:
            return 0.0
        mean = MathKernel.calculate_mean(data)
        return sum((x - mean) ** 2 for x in data) / len(data)

    @staticmethod
    def calculate_std_dev(data):
        """Calculates the standard deviation."""
        return math.sqrt(MathKernel.calculate_variance(data))

    @staticmethod
    def calculate_z_score(value, mean, std_dev):
        """Calculates the Z-Score of a value."""
        if std_dev == 0:
            return 0.0
        return (value - mean) / std_dev

    @staticmethod
    def calculate_linear_regression_slope(x_values, y_values):
        """
        Calculates the slope (m) of the linear regression line y = mx + c
        using the Least Squares Method.
        """
        n = len(x_values)
        if n != len(y_values) or n < 2:
            return 0.0

        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_xx = sum(x * x for x in x_values)

        denominator = (n * sum_xx - sum_x ** 2)
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    @staticmethod
    def calculate_solar_elevation(lat, lon, utc_time):
        """
        Calculates solar elevation in degrees using the Grena/PSA algorithm.
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            utc_time: datetime object in UTC
        
        Returns:
            Elevation in degrees
        """
        # 1. Calculate Julian Day (JD)
        # Grena algorithm uses a simplified JD calculation valid for 2000-2050
        # But we can use a standard one for robustness or the one from the prompt.
        # Prompt formula: JD=367*Y-int(7*(Y+int((M+9)/12))/4)+int(275*M/9)+D+1721013.5+hour/24
        
        Y = utc_time.year
        M = utc_time.month
        D = utc_time.day
        h = utc_time.hour + utc_time.minute / 60.0 + utc_time.second / 3600.0
        
        jd = 367 * Y - int(7 * (Y + int((M + 9) / 12)) / 4) + int(275 * M / 9) + D + 1721013.5 + h / 24.0
        
        # 2. Calculate Right Ascension (RA) and Declination (delta)
        # Using Grena's algorithm simplified series (PSA)
        # t = (JD - 2451545.0) / 36525.0 # Julian Centuries
        # This part in the prompt was "Compute Right Ascension (RA) and Declination (delta) using simplified trigonometric series."
        # I will use a standard implementation of Grena 1 or similar suitable for python
        
        # Implementation based on Grena (2012) "Five new algorithms for the computation of sun position..."
        # Algorithm 1 is sufficient.
        
        t = (jd - 2451545.0) / 36525.0
        
        # Sun mean longitude
        L = (280.460 + 36000.771 * t) % 360.0
        
        # Sun mean anomaly
        G = math.radians(357.528 + 35999.050 * t)
        
        # Ecliptic longitude
        lambda_sun = math.radians(L + 1.915 * math.sin(G) + 0.020 * math.sin(2 * G))
        
        # Obliquity of the ecliptic
        epsilon = math.radians(23.439 - 0.013 * t)
        
        # Right Ascension (alpha) and Declination (delta)
        # alpha = atan2(cos(epsilon) * sin(lambda_sun), cos(lambda_sun)) 
        # delta = asin(sin(epsilon) * sin(lambda_sun))
        
        sin_lambda = math.sin(lambda_sun)
        cos_lambda = math.cos(lambda_sun)
        sin_epsilon = math.sin(epsilon)
        cos_epsilon = math.cos(epsilon)
        
        alpha = math.atan2(cos_epsilon * sin_lambda, cos_lambda)
        delta = math.asin(sin_epsilon * sin_lambda)
        
        # 3. Local Hour Angle (H)
        # Greenwich Mean Sidereal Time (GMST) in degrees
        # GMST = 18.697374558 + 24.06570982441908 * D_UT (days since J2000)
        # Alternative simple formula:
        # Theta_G = 280.46061837 + 360.98564736629 * (jd - 2451545.0)
        
        theta_g = (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360.0
        
        # Local Sidereal Time
        theta = theta_g + lon
        
        # Hour Angle (H) = theta - alpha (in degrees)
        # alpha is in radians, convert to degrees
        H = math.radians(theta) - alpha
        
        # 4. Elevation (E)
        # sin(El) = sin(phi)sin(delta) + cos(phi)cos(delta)cos(H)
        phi = math.radians(lat)
        
        sin_el = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(H)
        el_rad = math.asin(sin_el)
        
        return math.degrees(el_rad)
