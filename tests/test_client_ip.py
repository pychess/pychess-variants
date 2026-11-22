import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from client_ip import get_client_ip
from request_protection import RequestProtectionState
from security_evasion import collect_client_signals


class ClientIPTestCase(unittest.TestCase):
    @patch("client_ip.CLIENT_IP_MODE", "heroku")
    def test_uses_rightmost_address_across_repeated_header_fields(self):
        for headers in (
            {"X-Forwarded-For": "203.0.113.10, 198.51.100.44"},
            {"X-Forwarded-For": "unknown, forged, 198.51.100.44"},
            [
                ("X-Forwarded-For", "203.0.113.10, 203.0.113.20"),
                ("x-forwarded-for", " 198.51.100.44 "),
            ],
        ):
            with self.subTest(headers=headers):
                request = make_mocked_request("GET", "/", headers=headers)
                self.assertEqual(get_client_ip(request), "198.51.100.44")

    @patch("client_ip.CLIENT_IP_MODE", "heroku")
    def test_rejects_missing_or_malformed_trusted_address(self):
        for candidate in (
            "",
            "unknown",
            "not-an-ip",
            "198.51.100.44:8080",
            "[2001:db8::1]",
            "2001:db8::1%eth0",
            "198.051.100.44",
        ):
            with self.subTest(candidate=candidate):
                request = make_mocked_request(
                    "GET", "/", headers={"X-Forwarded-For": f"203.0.113.10, {candidate}"}
                ).clone(remote="192.0.2.1")
                with self.assertRaises(web.HTTPBadRequest):
                    get_client_ip(request)

        for headers in ({}, {"X-Forwarded-For": ""}):
            with self.subTest(headers=headers):
                request = make_mocked_request("GET", "/", headers=headers)
                with self.assertRaises(web.HTTPBadRequest):
                    get_client_ip(request)

        request = make_mocked_request(
            "GET",
            "/",
            headers=[("X-Forwarded-For", "198.51.100.44"), ("X-Forwarded-For", "")],
        )
        with self.assertRaises(web.HTTPBadRequest):
            get_client_ip(request)

    @patch("client_ip.CLIENT_IP_MODE", "heroku")
    def test_canonicalizes_ipv4_and_ipv6(self):
        for candidate, expected in (
            (" 198.51.100.44 ", "198.51.100.44"),
            ("2001:0DB8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
            ("::ffff:198.51.100.44", "198.51.100.44"),
        ):
            with self.subTest(candidate=candidate):
                request = make_mocked_request("GET", "/", headers={"X-Forwarded-For": candidate})
                self.assertEqual(get_client_ip(request), expected)

    @patch("client_ip.CLIENT_IP_MODE", "direct")
    def test_direct_connections_ignore_all_forwarding_headers(self):
        request = make_mocked_request(
            "GET",
            "/",
            headers={
                "X-Forwarded-For": "203.0.113.10, invalid",
                "Forwarded": "for=203.0.113.20",
                "X-Real-IP": "203.0.113.30",
            },
        ).clone(remote="2001:0DB8::1")
        self.assertEqual(get_client_ip(request), "2001:db8::1")

    @patch("client_ip.CLIENT_IP_MODE", "direct")
    def test_missing_peer_uses_shared_unknown_budget_without_ip_signals(self):
        request = make_mocked_request("GET", "/", headers={"X-Forwarded-For": "203.0.113.10"})
        self.assertIsNone(get_client_ip(request))
        self.assertEqual(RequestProtectionState().client_key(request), "unknown")
        self.assertIsNone(collect_client_signals(request).ip_hash)

    @patch("client_ip.CLIENT_IP_MODE", "heroku")
    def test_prefix_rotation_does_not_change_signals(self):
        signals = []
        for prefix in ("203.0.113.10", "203.0.113.20", "invalid"):
            request = make_mocked_request(
                "GET",
                "/",
                headers={
                    "X-Forwarded-For": f"{prefix}, 198.51.100.44",
                    "User-Agent": "SecurityTestUA/1.0",
                },
            )
            signals.append(collect_client_signals(request))
        self.assertIsNotNone(signals[0].ip_hash)
        self.assertIsNotNone(signals[0].ipfp_hash)
        self.assertEqual(signals[0], signals[1])
        self.assertEqual(signals[0], signals[2])

    @patch("client_ip.CLIENT_IP_MODE", "heroku")
    def test_consumers_reuse_the_resolved_address(self):
        request = make_mocked_request(
            "GET", "/", headers={"X-Forwarded-For": "203.0.113.10, 198.51.100.44"}
        )
        self.assertEqual(get_client_ip(request), "198.51.100.44")
        with patch("client_ip._canonical_ip", side_effect=AssertionError("resolved twice")):
            self.assertEqual(RequestProtectionState().client_key(request), "198.51.100.44")
            self.assertIsNotNone(collect_client_signals(request).ip_hash)
            self.assertEqual(get_client_ip(request), "198.51.100.44")
