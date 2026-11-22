from __future__ import annotations

from collections.abc import Awaitable, Callable
from ipaddress import IPv6Address, ip_address

from aiohttp import web
from settings import CLIENT_IP_MODE

_CLIENT_IP_KEY = web.RequestKey[str | None]("client_ip")


def _canonical_ip(value: str) -> str:
    # Zone IDs identify local interfaces, not Internet clients, and must not
    # create additional identities for the same IPv6 address.
    if "%" in value:
        raise ValueError("Scoped client address")
    address = ip_address(value.strip())
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(address)


def get_client_ip(request: web.Request) -> str | None:
    """Resolve once per request using the deployment's configured trust boundary."""
    if _CLIENT_IP_KEY in request:
        return request[_CLIENT_IP_KEY]

    client_ip: str | None
    if CLIENT_IP_MODE == "heroku":
        # Preserve repeated fields in wire order. Heroku appends the connecting
        # address on the right; everything before it can be attacker supplied.
        forwarded_for = ",".join(request.headers.getall("X-Forwarded-For", []))
        candidate = forwarded_for.rsplit(",", maxsplit=1)[-1]
        try:
            client_ip = _canonical_ip(candidate)
        except ValueError as exc:
            # Never search an untrusted prefix for an alternative address.
            raise web.HTTPBadRequest(text="Invalid forwarded client address") from exc
    else:
        try:
            client_ip = _canonical_ip(request.remote or "")
        except ValueError:
            client_ip = None

    request[_CLIENT_IP_KEY] = client_ip
    return client_ip


@web.middleware
async def client_ip_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    get_client_ip(request)
    return await handler(request)
