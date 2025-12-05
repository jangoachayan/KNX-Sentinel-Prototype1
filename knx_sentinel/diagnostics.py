import logging
from datetime import datetime, timezone
from knx_sentinel.math_kernel import MathKernel

_LOGGER = logging.getLogger(__name__)

class DiagnosticsEngine:
    def __init__(self, lat=0.0, lon=0.0):
        self.lat = lat
        self.lon = lon

    def check_solar_sensor(self, entity_id, lux_value, timestamp=None):
        """
        Validates a light sensor against calculated solar elevation.
        Returns a fault dict if inconsistent.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        elevation = MathKernel.calculate_solar_elevation(self.lat, self.lon, timestamp)
        
        # Rule: If Sun is high (> 10 deg) and Lux is low (< 10), potential fault
        # (Assuming outdoor sensor, not obstructed)
        if elevation > 10.0 and lux_value < 10:
            _LOGGER.warning(f"Solar Check Fault for {entity_id}: Elevation={elevation:.1f}, Lux={lux_value}")
            return {
                "type": "diagnostic",
                "subtype": "solar_mismatch",
                "entity_id": entity_id,
                "elevation": elevation,
                "lux": lux_value
            }
        return None

    # Placeholder for HVAC test
    async def run_hvac_test(self, entity_id, ha_client):
        pass
