import os
from typing import NotRequired, TypedDict


class OAuthProviderConfig(TypedDict):
    client_id: str
    client_secret: NotRequired[str]
    oauth_authorize_url: str
    oauth_token_url: str
    scope: str
    account_api_url: str


oauth_config: dict[str, OAuthProviderConfig] = {
    "lichess": {
        "client_id": os.getenv("LICHESS_CLIENT_ID", "pychess"),
        "oauth_authorize_url": "https://lichess.org/oauth",
        "oauth_token_url": "https://lichess.org/api/token",
        "scope": "",
        "account_api_url": "https://lichess.org/api/account",
    },
    "lishogi": {
        "client_id": os.getenv("LISHOGI_CLIENT_ID", "pychess"),
        "client_secret": os.getenv("CLIENT_SECRET", "secret"),
        "oauth_authorize_url": "https://lishogi.org/oauth",
        "oauth_token_url": "https://lishogi.org/api/token",
        "scope": "",
        "account_api_url": "https://lishogi.org/api/account",
    },
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "pychess"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "secret"),
        "oauth_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "oauth_token_url": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/userinfo.profile openid",
        "account_api_url": "https://www.googleapis.com/oauth2/v2/userinfo",
    },
    "discord": {
        "client_id": os.getenv("DISCORD_CLIENT_ID", "pychess"),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET", "secret"),
        "oauth_authorize_url": "https://discord.com/oauth2/authorize",
        "oauth_token_url": "https://discord.com/api/oauth2/token",
        "scope": "identify",
        "account_api_url": "https://discordapp.com/api/users/@me",
    },
}
