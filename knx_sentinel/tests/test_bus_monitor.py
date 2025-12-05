import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from knx_sentinel.ha_client import HAWebSocketClient
from aiohttp import WSMsgType

class TestHAWebSocketClient(unittest.IsolatedAsyncioTestCase):
    async def test_connect_auth_subscribe(self):
        """Test successful connection, authentication, and subscription."""
        client = HAWebSocketClient(token="test_token")
        
        # Mock aiohttp session and ws
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        mock_ws = AsyncMock()
        
        # Setup mock responses for receive_json
        # 1. auth_required
        # 2. auth_ok
        # 3. subscription success
        mock_ws.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
            {"id": 1, "type": "result", "success": True, "result": None}
        ]
        
        # Mock async iterator for messages (empty to exit loop immediately or one event)
        # We'll simulate one event then stop
        mock_ws.__aiter__.return_value = [
            MagicMock(type=WSMsgType.TEXT, data='{"type": "event", "event": {"data": "test"}}')
        ]
        
        mock_session.ws_connect.return_value.__aenter__.return_value = mock_ws
        
        # Patch aiohttp.ClientSession
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Start client in a task
            task = asyncio.create_task(client.start())
            
            # Give it a moment to run
            await asyncio.sleep(0.1)
            
            # Stop client
            await client.stop()
            await task
            
            # Verify calls
            mock_session.ws_connect.assert_called_with(client.url)
            
            # Verify Auth sent
            mock_ws.send_json.assert_any_call({
                "type": "auth",
                "access_token": "test_token"
            })
            
            # Verify Subscribe sent
            mock_ws.send_json.assert_any_call({
                "id": 1,
                "type": "subscribe_events",
                "event_type": "knx_event"
            })

    async def test_backoff_logic(self):
        """Test that the client waits longer after failures."""
        client = HAWebSocketClient()
        
        # Mock session to raise exception
        mock_session = MagicMock()
        mock_session.ws_connect.side_effect = OSError("Connection refused")
        
        with patch('aiohttp.ClientSession', return_value=mock_session), \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            # Side effect: return None for first 2 calls, raise Error on 3rd to break loop
            mock_sleep.side_effect = [None, None, ValueError("Stop Loop")]
            
            # Run client
            try:
                await client.start()
            except ValueError:
                pass
            
            # Verify sleep calls
            # 1st fail -> sleep(1)
            # 2nd fail -> sleep(2)
            # 3rd fail -> sleep(4) -> Raises ValueError
            self.assertEqual(mock_sleep.call_count, 3)
            
            args = [call.args[0] for call in mock_sleep.call_args_list]
            self.assertEqual(args, [1, 2, 4])

if __name__ == '__main__':
    unittest.main()
