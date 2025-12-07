import asyncio
import logging
import json
import os
from aiohttp import web

_LOGGER = logging.getLogger(__name__)

class WebServer:
    def __init__(self, config):
        self.config = config
        self.runner = None
        self.site = None
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_post('/api/config', self.handle_update_config)
        self.app.router.add_static('/static', path=os.path.join(os.path.dirname(__file__), 'static'), append_version=True)

    async def start(self):
        _LOGGER.info("Starting Web Server...")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Ingress port is usually provided by HA, but for local dev/testing we use config
        # When running as Add-on with Ingress, HA handles the port mapping dynamically, 
        # but the app inside the container usually listens on the port specified in config.yaml (8099)
        port = 8099 
        self.site = web.TCPSite(self.runner, '0.0.0.0', port)
        await self.site.start()
        _LOGGER.info(f"Web Server started on port {port}")

    async def stop(self):
        _LOGGER.info("Stopping Web Server...")
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    async def handle_index(self, request):
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        if os.path.exists(template_path):
            return web.FileResponse(template_path)
        return web.Response(text="Configuration Page Not Found", status=404)

    async def handle_get_config(self, request):
        # Return safe config (masking tokens if needed in real app)
        return web.json_response(self.config)

    async def handle_update_config(self, request):
        try:
            data = await request.json()
            _LOGGER.info(f"Received config update: {data}")
            # In a real add-on, we might write to /data/options.json or call HA Supervisor API
            # For now, we update the in-memory config and acknowledge
            
            # Update specific keys
            for key in ['client_id', 'site_id']:
                if key in data:
                    self.config[key] = data[key]
            
            return web.json_response({"status": "ok", "message": "Configuration updated (memory only)"})
        except Exception as e:
            _LOGGER.error(f"Failed to update config: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)
