from aiohttp import web


def page_number(request: web.Request) -> int:
    try:
        return max(1, int(request.query.get("page", "1")))
    except ValueError:
        return 1


def page_href(request: web.Request, page: int) -> str:
    query = request.rel_url.query.copy()
    query.popall("page", None)
    if page > 1:
        query["page"] = str(page)
    return str(request.rel_url.with_query(query))
