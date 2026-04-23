import unittest
import json
import os
import tempfile
from unittest.mock import patch
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from knx_sentinel.web import WebServer


class TestWebServer(AioHTTPTestCase):
    async def get_application(self):
        self.config = {
            "client_id": "test_client",
            "site_id": "test_site",
            "mode": "influxdb_cloud"
        }
        server = WebServer(self.config)
        return server.app

    async def test_get_config(self):
        resp = await self.client.get("/api/config")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["client_id"], "test_client")
        self.assertEqual(data["site_id"], "test_site")

    async def test_update_config_memory(self):
        # No /data/options.json in test env — in-memory update only
        with patch('os.path.exists', return_value=False):
            resp = await self.client.post(
                "/api/config",
                data=json.dumps({"client_id": "new_client", "site_id": "new_site"}),
                headers={"Content-Type": "application/json"}
            )
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(self.config["client_id"], "new_client")
        self.assertEqual(self.config["site_id"], "new_site")

    async def test_update_config_persists_to_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"client_id": "old_client", "site_id": "old_site", "mode": "mqtt"}, f)
            tmp_path = f.name

        try:
            with patch('os.path.exists', return_value=True), \
                 patch('builtins.open', unittest.mock.mock_open(
                     read_data=json.dumps({"client_id": "old_client", "site_id": "old_site"})
                 )), \
                 patch('os.replace') as mock_replace, \
                 patch('json.dump') as mock_dump:

                resp = await self.client.post(
                    "/api/config",
                    data=json.dumps({"client_id": "persisted_client"}),
                    headers={"Content-Type": "application/json"}
                )

            self.assertEqual(resp.status, 200)
            mock_replace.assert_called_once()
            mock_dump.assert_called_once()
            written = mock_dump.call_args[0][0]
            self.assertEqual(written["client_id"], "persisted_client")
        finally:
            os.unlink(tmp_path)

    async def test_update_config_ignores_unknown_keys(self):
        with patch('os.path.exists', return_value=False):
            resp = await self.client.post(
                "/api/config",
                data=json.dumps({"mode": "mqtt", "client_id": "c1"}),
                headers={"Content-Type": "application/json"}
            )
        self.assertEqual(resp.status, 200)
        # 'mode' should not have been updated (not in allowed keys)
        self.assertEqual(self.config.get("mode"), "influxdb_cloud")
        self.assertEqual(self.config["client_id"], "c1")

    async def test_update_config_bad_json(self):
        resp = await self.client.post(
            "/api/config",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp.status, 500)
        data = await resp.json()
        self.assertEqual(data["status"], "error")


if __name__ == '__main__':
    unittest.main()
