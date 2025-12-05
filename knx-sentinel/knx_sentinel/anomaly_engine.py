from collections import deque
import logging
from knx_sentinel.math_kernel import MathKernel

_LOGGER = logging.getLogger(__name__)

class AnomalyEngine:
    def __init__(self, config=None):
        self.config = config or {}
        self.buffers = {} # entity_id -> deque
        self.profiles = {} # entity_id -> profile dict
        self.default_maxlen = 60

    def register_sensor(self, entity_id, profile=None):
        """Registers a sensor for monitoring."""
        if entity_id not in self.buffers:
            self.buffers[entity_id] = deque(maxlen=self.default_maxlen)
            self.profiles[entity_id] = profile or {"method": "z_score", "threshold": 3.0}
            _LOGGER.info(f"Registered sensor {entity_id} for anomaly detection")

    def process_value(self, entity_id, value):
        """
        Processes a new value for a sensor.
        Returns an anomaly dict if detected, else None.
        """
        if entity_id not in self.buffers:
            return None

        try:
            val = float(value)
        except (ValueError, TypeError):
            return None

        buffer = self.buffers[entity_id]
        buffer.append(val)
        
        profile = self.profiles[entity_id]
        method = profile.get("method", "z_score")

        if method == "z_score":
            return self._check_z_score(entity_id, val, buffer, profile)
        elif method == "range":
            return self._check_range(entity_id, val, profile)
        
        return None

    def _check_z_score(self, entity_id, value, buffer, profile):
        if len(buffer) < 30:
            return None # Insufficient data

        mean = MathKernel.calculate_mean(buffer)
        std_dev = MathKernel.calculate_std_dev(buffer)
        
        if std_dev == 0:
            return None

        z_score = MathKernel.calculate_z_score(value, mean, std_dev)
        threshold = profile.get("threshold", 3.0)

        if abs(z_score) > threshold:
            _LOGGER.warning(f"Anomaly detected for {entity_id}: Value={value}, Z-Score={z_score:.2f}")
            return {
                "type": "anomaly",
                "subtype": "z_score",
                "entity_id": entity_id,
                "value": value,
                "z_score": z_score,
                "threshold": threshold
            }
        return None

    def _check_range(self, entity_id, value, profile):
        min_val = profile.get("min")
        max_val = profile.get("max")
        
        if min_val is not None and value < min_val:
            return {
                "type": "anomaly",
                "subtype": "range_low",
                "entity_id": entity_id,
                "value": value,
                "limit": min_val
            }
        
        if max_val is not None and value > max_val:
             return {
                "type": "anomaly",
                "subtype": "range_high",
                "entity_id": entity_id,
                "value": value,
                "limit": max_val
            }
            
        return None
