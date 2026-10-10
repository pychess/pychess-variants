import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import web
from aiohttp_session import Session
from session_security import session_expiry_timeout, session_matches_user
from settings import MAX_AGE


class SessionLifetimeTestCase(unittest.IsolatedAsyncioTestCase):
    def identity(self, *, anon=False):
        return SimpleNamespace(username="alice", enabled=True, anon=anon, auth_version=0)

    def session(self, *, timestamp=100):
        return Session(
            None,
            new=False,
            data={"created": 100, "session": {"user_name": "alice", "authenticated_at": timestamp}},
        )

    async def test_registered_connection_uses_remaining_not_renewed_lifetime(self):
        with patch("session_security.datetime") as clock, patch("session_security.MAX_AGE", 10):
            clock.now.return_value.timestamp.return_value = 109.98
            with self.assertRaises(TimeoutError):
                async with session_expiry_timeout(self.session(), self.identity()):
                    await asyncio.Event().wait()

    async def test_anonymous_connection_has_no_registered_login_deadline(self):
        async with session_expiry_timeout(self.session(), self.identity(anon=True)) as timeout:
            self.assertIsNone(timeout.when())

    async def test_one_year_policy_keeps_month_old_login_valid_without_renewing_it(self):
        self.assertEqual(365 * 24 * 3600, MAX_AGE)
        session = self.session()
        user = self.identity()
        with patch("session_security.datetime") as clock:
            clock.now.return_value.timestamp.return_value = 100 + 31 * 24 * 3600
            self.assertTrue(session_matches_user(session, user))
            async with session_expiry_timeout(session, user) as timeout:
                self.assertAlmostEqual(
                    timeout.when() - asyncio.get_running_loop().time(),
                    MAX_AGE - 31 * 24 * 3600,
                    delta=1,
                )
            clock.now.return_value.timestamp.return_value = 100 + MAX_AGE
            self.assertFalse(session_matches_user(session, user))

    async def test_invalid_expired_or_revoked_connection_is_rejected_before_entering(self):
        with patch("session_security.datetime") as clock, patch("session_security.MAX_AGE", 10):
            clock.now.return_value.timestamp.return_value = 110
            for timestamp in (100, 111, "invalid", True):
                with self.subTest(timestamp=timestamp), self.assertRaises(web.HTTPUnauthorized):
                    session_expiry_timeout(self.session(timestamp=timestamp), self.identity())
            clock.now.return_value.timestamp.return_value = 105
            user = self.identity()
            user.auth_version = 1
            with self.assertRaises(web.HTTPUnauthorized):
                session_expiry_timeout(self.session(), user)
