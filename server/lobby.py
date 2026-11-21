from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from aiohttp.web_ws import WebSocketResponse
from seek import get_seeks
from websocket_utils import ws_send_json_many

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
    from ws_types import LobbyCountMessage, LobbySeeksMessage
# from logger import log


class Lobby:
    def __init__(self, app_state: PychessGlobalAppState) -> None:
        self.app_state: PychessGlobalAppState = app_state
        self.lobbysockets: dict[
            str, set[WebSocketResponse]
        ] = {}  # one dict only! {user.username: user.tournament_sockets, ...}
        # Cache the last broadcast count so we can skip the broadcast when the
        # online count hasn't actually changed (e.g. a page-refresh causes a
        # rapid leave+join that triggers two calls but net count is the same).
        self._last_u_cnt: int = -1

    # below methods maybe best in separate class eventually
    async def lobby_broadcast(self, response: Mapping[str, object]) -> None:
        # log.debug("lobby_broadcast: %r to %r", response, self.lobbysockets)
        all_sockets: list[WebSocketResponse] = []
        for ws_set in tuple(self.lobbysockets.values()):
            all_sockets.extend(tuple(ws_set))
        await ws_send_json_many(all_sockets, response)

    async def lobby_broadcast_u_cnt(self) -> None:
        cnt = self.app_state.online_count()
        if cnt == self._last_u_cnt:
            return
        self._last_u_cnt = cnt
        response: LobbyCountMessage = {"type": "u_cnt", "cnt": cnt}
        await self.lobby_broadcast(response)

    async def lobby_broadcast_ap_cnt(self) -> None:
        response: LobbyCountMessage = {"type": "ap_cnt", "cnt": self.app_state.auto_pairing_count()}
        await self.lobby_broadcast(response)

    async def lobby_broadcast_seeks(self, usernames: Iterable[str] | None = None) -> None:
        """Refresh all lobby users, or only the named users for a private challenge."""
        recipients = (
            tuple(self.lobbysockets.items())
            if usernames is None
            else tuple(
                (username, sockets)
                for username in dict.fromkeys(usernames)
                if (sockets := self.lobbysockets.get(username))
            )
        )
        if not recipients:
            return
        # We will need all the seek users blocked info
        for seek in tuple(self.app_state.seeks.values()):
            await self.app_state.users.get(seek.creator.username)

        for username, ws_set in recipients:
            ws_user = await self.app_state.users.get(username)
            compatible_seeks = get_seeks(ws_user, self.app_state.seeks.values())
            response: LobbySeeksMessage = {"type": "get_seeks", "seeks": compatible_seeks}
            await ws_send_json_many(ws_set, response)

    async def handle_user_closes_lobby(self, user: User) -> None:
        # todo: maybe get rid of lobbysockets at some point and use app_state.users.loobby_sockets instead.
        #       On this event we could clean-up also app_state.users etc. if user is considered no longer online
        # online user counter will be updated in quit_lobby also!
        if len(user.lobby_sockets) == 0 and user.username in self.lobbysockets:
            del self.lobbysockets[user.username]

    async def close_lobby_sockets(self) -> None:
        for ws_set in tuple(self.lobbysockets.values()):
            for ws in tuple(ws_set):
                await ws.close()
