from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp_jinja2
import jinja2
from aiohttp import web
from const import LANGUAGES
from settings import (
    NNUE_DOWNLOAD_ROOT,
    SOURCE_VERSION,
    STATIC_ROOT,
    URI,
    local_static_url,
    static_url,
)

from lang import LOCALE


def setup_templates(app: web.Application) -> None:
    """Configure the shared async Jinja environment used by HTML views."""
    aiohttp_jinja2.setup(
        app,
        enable_async=True,
        extensions=["jinja2.ext.i18n"],
        loader=jinja2.FileSystemLoader("templates"),
        autoescape=jinja2.select_autoescape(["html"]),
    )


def configure_template_environment(
    app: web.Application, translations: Mapping[str, Any], *, dev: bool
) -> None:
    """Install request-local translations and shared template globals."""

    # https://github.com/aio-libs/aiohttp-jinja2/issues/187#issuecomment-2519831516
    class _Translations:
        @staticmethod
        def gettext(message: str) -> str:
            return translations[LOCALE.get()].gettext(message)

        @staticmethod
        def ngettext(singular: str, plural: str, num: int) -> str:
            return translations[LOCALE.get()].ngettext(singular, plural, num)

    env: Any = aiohttp_jinja2.get_env(app)
    env.install_gettext_translations(_Translations, newstyle=True)

    env.globals["static"] = static_url
    env.globals["local_static"] = local_static_url
    env.globals["js"] = "/static/pychess-variants.js%s" % SOURCE_VERSION
    env.globals["dev"] = dev
    env.globals["app_name"] = "PyChess"
    env.globals["languages"] = LANGUAGES
    env.globals["asseturl"] = STATIC_ROOT
    env.globals["nnue_download_root"] = NNUE_DOWNLOAD_ROOT
    env.globals["home"] = URI
