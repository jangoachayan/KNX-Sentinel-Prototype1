import asyncio
import json
import logging
import os
import aiohttp
from aiohttp import ClientError, WSMsgType

_LOGGER = logging.getLogger(__name__)

class HAWebSocketClient:
    def __init__(self, supervisor_url="ws://supervisor/core/websocket", token=None):
        self.url = supervisor_url
        self.token = token or os.getenv("SUPERVISOR_TOKEN")
        self.running = False
        self.session = None
        self.ws = None
        self.event_callback = None
        self._reconnect_delay = 1

    def set_callback(self, callback):
        """Sets the callback function for incoming KNX events."""
        self.event_callback = callback

    async def start(self):
        """Starts the WebSocket client loop."""
        self.running = True
        self.session = aiohttp.ClientSession()
        _LOGGER.info(f"Starting HA WebSocket Client connecting to {self.url}")
        
        while self.running:
            try:
                async with self.session.ws_connect(self.url) as ws:
                    self.ws = ws
                    self._reconnect_delay = 1 # Reset delay on connection
                    _LOGGER.info("Connected to Home Assistant Core")
                    
                    await self._authenticate_and_subscribe()
                    await self._listen()
                    
            except (ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.warning(f"Connection failed: {err}")
            except Exception as e:
                _LOGGER.error(f"Unexpected error: {e}", exc_info=True)
            
            if self.running:
                _LOGGER.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def stop(self):
        """Stops the client."""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        _LOGGER.info("HA WebSocket Client stopped")

    async def _authenticate_and_subscribe(self):
        """Handles the auth handshake and subscription."""
        # Wait for auth_required
        msg = await self.ws.receive_json()
        if msg.get("type") != "auth_required":
            _LOGGER.error(f"Unexpected message during auth: {msg}")
            return

        # Send auth
        await self.ws.send_json({
            "type": "auth",
            "access_token": self.token
        })

        # Wait for auth_ok
        msg = await self.ws.receive_json()
        if msg.get("type") != "auth_ok":
            _LOGGER.error(f"Authentication failed: {msg}")
            # If auth fails, we might want to stop or retry. 
            # For now, we'll raise an exception to trigger reconnect loop (though auth fail usually is permanent)
            raise ConnectionError("Authentication failed")

        _LOGGER.info("Authentication successful")

        # Subscribe to knx_event
        # We use a fixed ID for simplicity, or we could increment.
        await self.ws.send_json({
            "id": 1,
            "type": "subscribe_events",
            "event_type": "knx_event"
        })
        
        # Wait for subscription confirmation
        msg = await self.ws.receive_json()
        if not msg.get("success"):
             _LOGGER.error(f"Subscription failed: {msg}")

        _LOGGER.info("Subscribed to knx_event")

    async def _listen(self):
        """Listens for incoming messages."""
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "event":
                    event = data.get("event", {})
                    if self.event_callback:
                        # Dispatch to callback (fire and forget or await?)
                        # Ideally await if we want backpressure, or create task.
                        # For a monitor, we probably want to process it.
                        try:
                            if asyncio.iscoroutinefunction(self.event_callback):
                                await self.event_callback(event)
                            else:
                                self.event_callback(event)
                        except Exception as e:
                            _LOGGER.error(f"Error in event callback: {e}")
            elif msg.type == WSMsgType.ERROR:
                _LOGGER.error('WebSocket connection closed with exception %s', self.ws.exception())
