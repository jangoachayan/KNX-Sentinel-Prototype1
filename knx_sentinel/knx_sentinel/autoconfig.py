import logging

_LOGGER = logging.getLogger(__name__)

class AutoConfigurator:
    def __init__(self, ha_client):
        self.ha_client = ha_client

    async def discover_entities(self):
        """
        Queries HA Registry and returns a list of entities to monitor.
        """
        if self.ha_client.ws is None:
            _LOGGER.warning("HA WebSocket not connected; skipping entity discovery")
            return []

        try:
            await self.ha_client.ws.send_json({
                "id": 99,
                "type": "config/entity_registry/list"
            })

            result_msg = None
            async for msg in self.ha_client.ws:
                from aiohttp import WSMsgType
                import json as _json
                if msg.type == WSMsgType.TEXT:
                    data = _json.loads(msg.data)
                    if data.get("id") == 99:
                        result_msg = data
                        break

            if result_msg is None or not result_msg.get("success"):
                _LOGGER.error(f"Entity registry fetch failed: {result_msg}")
                return []

            entities = []
            for entry in result_msg.get("result", []):
                profile = self.analyze_entity(entry)
                if profile is not None:
                    entities.append({"entity_id": entry["entity_id"], "profile": profile})

            _LOGGER.info(f"Auto-discovered {len(entities)} KNX entities")
            return entities

        except Exception as e:
            _LOGGER.error(f"Error during entity discovery: {e}")
            return []

    @staticmethod
    def analyze_entity(entity_entry):
        """
        Analyzes a single entity entry and assigns a profile.
        """
        platform = entity_entry.get("platform")
        domain = entity_entry.get("entity_id", "").split(".")[0]
        device_class = entity_entry.get("original_device_class") or entity_entry.get("device_class")
        unit = entity_entry.get("unit_of_measurement")

        if platform != "knx":
            return None

        if domain == "sensor":
            if device_class == "voltage":
                return {"method": "range", "min": 207, "max": 253}
            elif device_class == "temperature":
                return {"method": "z_score", "threshold": 3.0}
            elif device_class == "illuminance":
                return {"method": "solar_check"}
        
        return None
