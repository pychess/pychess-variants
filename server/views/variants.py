import json
import os

import aiohttp_jinja2
from aiohttp import web
from catalogued.variants import (
    catalogued_variant_client_doc_for_name,
    catalogued_variant_rule_context,
    community_catalogued_variants_page,
    find_catalogued_variant_doc,
)
from fairy.cwda import cwda_betza_diagram_groups
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from variants import VARIANT_ICONS, VARIANTS

from lang import get_locale_ext
from views import get_user_context


def _positive_page(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _community_page_href(request: web.Request, page: int | None) -> str:
    if page is None:
        return ""
    query = dict(request.rel_url.query)
    query["page"] = str(page)
    return str(request.rel_url.with_query(query))


@aiohttp_jinja2.template("variants.html")
async def variants(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)

    app_state = get_app_state(request.app)
    variant = request.match_info.get("variant")
    catalogued_doc = None
    if (
        variant is not None
        and variant not in VARIANTS
        and variant not in {"terminology", "community"}
    ):
        catalogued_doc = await find_catalogued_variant_doc(
            app_state, variant, user.username if not user.anon else None
        )
        if catalogued_doc is None:
            variant = "chess"

    context["variants"] = context["category_variants"]
    context["groups"] = context["category_variant_groups"]
    context["icons"] = VARIANT_ICONS

    if variant == "community":
        community_variants = await community_catalogued_variants_page(
            app_state,
            q=request.rel_url.query.get("q", ""),
            author=request.rel_url.query.get("author", ""),
            sort=request.rel_url.query.get("sort", "updated"),
            page=_positive_page(request.rel_url.query.get("page")),
            favorite_names=(
                user.catalogued_variant_favorites if not user.anon and not user.bot else None
            ),
            favorites_only=request.rel_url.query.get("favorites") == "1",
        )
        context["community_variants"] = community_variants
        context["community_prev_href"] = _community_page_href(
            request, community_variants["prev_page"]
        )
        context["community_next_href"] = _community_page_href(
            request, community_variants["next_page"]
        )
        context["title"] = "Community variants • PyChess"
        return context

    if catalogued_doc is not None:
        catalogued_client_doc = catalogued_variant_client_doc_for_name(
            app_state, variant, user.username if not user.anon else None
        )
        if catalogued_client_doc is not None:
            catalogued_variants = json.loads(str(context.get("catalogued_variants") or "[]"))
            if not any(item.get("name") == variant for item in catalogued_variants):
                catalogued_variants.append(catalogued_client_doc)
                context["catalogued_variants"] = json_dumps(catalogued_variants)

        context["catalogued_variant"] = catalogued_variant_rule_context(catalogued_doc)
        context["title"] = f"{context['catalogued_variant']['displayName']} • PyChess"
        return context

    locale = get_locale_ext(context)

    # try translated docs file first
    if variant == "terminology":
        item = "docs/terminology%s.html" % locale
    else:
        item = "docs/" + ("terminology" if variant is None else variant) + "%s.html" % locale
    item_path = os.path.abspath(os.path.join("templates", item))

    # if there is no translated use the untranslated one
    if not os.path.exists(item_path):
        if variant == "terminology":
            item = "docs/terminology.html"
        else:
            item = "docs/" + ("terminology" if variant is None else variant) + ".html"
        item_path = os.path.abspath(os.path.join("templates", item))

    if not os.path.exists(item_path):
        raise web.HTTPNotFound()
    context["variant"] = item
    if variant == "cwda":
        context["cwda_army_diagrams"] = cwda_betza_diagram_groups()

    return context
