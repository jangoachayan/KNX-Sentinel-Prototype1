import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class BusLoadMonitor:
    def __init__(self):
        self._counter = 0
        self._lock = asyncio.Lock()

    async def process_event(self, event):
        """Increments the telegram counter."""
        async with self._lock:
            self._counter += 1

    async def get_and_reset(self):
        """Returns the current count and resets it to zero."""
        async with self._lock:
            count = self._counter
            self._counter = 0
        return count
