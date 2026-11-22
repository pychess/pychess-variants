import unittest
from typing import cast
from unittest.mock import AsyncMock, call, patch

from aiohttp.web_ws import WebSocketResponse
from websocket_utils import (
    _RECEIVE_TIMEOUT_SECS,
    _WS_HEARTBEAT_SECS,
    _ws_json_loads,
    ws_send_json,
    ws_send_json_many,
    ws_send_json_many_ordered,
    ws_send_str,
    ws_send_str_many,
)
from ws_structs import LOBBY_TYPED_DECODERS


class WebSocketUtilsTestCase(unittest.IsolatedAsyncioTestCase):
    def test_heroku_websocket_heartbeat_is_faster_than_idle_timeout(self):
        ws = WebSocketResponse(receive_timeout=_RECEIVE_TIMEOUT_SECS, heartbeat=_WS_HEARTBEAT_SECS)
        self.assertLess(_WS_HEARTBEAT_SECS, 55)
        self.assertEqual(ws._heartbeat, _WS_HEARTBEAT_SECS)
        self.assertEqual(ws._receive_timeout, _RECEIVE_TIMEOUT_SECS)

    async def test_ws_send_json_connection_reset_returns_false_without_error_log(self):
        ws = cast(WebSocketResponse, AsyncMock())
        ws.send_str.side_effect = ConnectionResetError

        with patch("websocket_utils.log.error") as error:
            ok = await ws_send_json(ws, {"type": "ping"})

        self.assertFalse(ok)
        error.assert_not_called()

    async def test_ws_send_str_connection_reset_returns_false_without_error_log(self):
        ws = cast(WebSocketResponse, AsyncMock())
        ws.send_str.side_effect = ConnectionResetError

        with patch("websocket_utils.log.error") as error:
            ok = await ws_send_str(ws, "ping")

        self.assertFalse(ok)
        error.assert_not_called()

    async def test_ws_send_json_many_returns_count_of_successful_sends(self):
        ws1 = cast(WebSocketResponse, AsyncMock())
        ws2 = cast(WebSocketResponse, AsyncMock())
        ws2.send_str.side_effect = ConnectionResetError

        sent = await ws_send_json_many([ws1, ws2], {"type": "ping"})

        self.assertEqual(sent, 1)
        ws1.send_str.assert_awaited_once_with('{"type":"ping"}')
        ws2.send_str.assert_awaited_once_with('{"type":"ping"}')

    async def test_ws_send_json_many_ordered_preserves_order_per_socket(self):
        ws1 = cast(WebSocketResponse, AsyncMock())
        ws2 = cast(WebSocketResponse, AsyncMock())

        sent = await ws_send_json_many_ordered(
            [ws1, ws2],
            [
                {"type": "duels"},
                {"type": "game_update"},
                {"type": "tstatus"},
            ],
        )

        self.assertEqual(sent, 6)
        expected = [
            call('{"type":"duels"}'),
            call('{"type":"game_update"}'),
            call('{"type":"tstatus"}'),
        ]
        self.assertEqual(ws1.send_str.await_args_list, expected)
        self.assertEqual(ws2.send_str.await_args_list, expected)

    async def test_ws_send_json_many_ordered_stops_after_socket_failure(self):
        ws = cast(WebSocketResponse, AsyncMock())
        ws.send_str.side_effect = [None, ConnectionResetError]

        sent = await ws_send_json_many_ordered(
            [ws],
            [
                {"type": "duels"},
                {"type": "game_update"},
                {"type": "tstatus"},
            ],
        )

        self.assertEqual(sent, 1)
        self.assertEqual(ws.send_str.await_count, 2)

    async def test_ws_send_str_many_ignores_none_socket(self):
        ws = cast(WebSocketResponse, AsyncMock())
        sent = await ws_send_str_many([None, ws], "ping")

        self.assertEqual(sent, 1)
        ws.send_str.assert_awaited_once_with("ping")

    def test_ws_json_loads_typed_decoder_message_type_for_struct(self):
        payload = (
            '{"type":"create_ai_challenge","profileid":"Random-Mover","variant":"chess",'
            '"rm":true,"fen":"","color":"r","minutes":5,"increment":0,'
            '"byoyomiPeriod":0,"level":1,"chess960":false}'
        )

        decoded = _ws_json_loads(payload, LOBBY_TYPED_DECODERS)

        self.assertEqual(decoded.get("type"), "create_ai_challenge")
