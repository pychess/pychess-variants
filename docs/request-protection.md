# Anonymous browsing admission

`server/request_protection.py` rejects excess anonymous public-page requests
before the page handler, locale setup, database queries, and template rendering.
It returns HTTP 429 immediately; requests do not wait for a free slot.

The browsing limits are shared across the selected routes, query strings, user
agents, and anonymous sessions. A rotating-address crawler still consumes the
same application budget. Having a materialized anonymous session does not grant
an exemption.

| Budget | Default | Configuration |
| --- | --- | --- |
| Anonymous browsing per client IP | 30 admissions in 30 seconds | `_ANON_HTML_IP_LIMIT` |
| Anonymous browsing across all IPs | 120 admissions in 60 seconds | `ANON_HTML_REQUESTS_PER_MINUTE` |
| Executing anonymous browsing handlers | 12 | `ANON_HTML_MAX_INFLIGHT` |

The environment settings are positive integers read at process startup. Budgets
are per web process; multiple Heroku dynos each have their own budget. The global
history is a fixed deque bounded by the admission count, independent of the
per-IP bucket map. The 60-second window survives idle periods and map saturation.
The shared budget is checked before allocating per-IP state for browsing traffic.
Executing-handler slots are released in `finally`, including on exceptions and
cancellation.

The per-route limiter's cleanup also retains each bucket until its actual rate
window expires. Its 15-second cleanup cadence must not reset longer budgets.

The route allowlist covers GET/HEAD requests for the lobby, blogs, videos, variant
rules, standalone analysis/editor pages, public browsing/list pages, and site
documentation. It uses the resolved route template, so neither a forged `Accept`
header nor a game ID resembling a page name changes the classification.

Registered sessions, game pages, invites, embeds, correspondence analysis, live
tournament/simul/Study pages, websockets, SSE streams, APIs, Fishnet, static assets,
login/OAuth, and metrics do not consume this new browsing budget. Their existing
controls still apply. Anonymous profile rendering retains its separate global
120-per-minute and 30-inflight budgets.

Blocked responses have `Cache-Control: no-store` and `Retry-After`: 1 second for
concurrency, 30 seconds for the per-IP budget, or 60 seconds for the shared rate
budget. Warning logs distinguish `bucket=anon_html` and
`bucket=anon_html_global`, with `reason=rate` or `reason=concurrency` for the latter.
Global block logs are sampled by bucket/reason rather than address to avoid log
amplification under a distributed flood.

After deployment, compare representative traffic periods for these warnings,
request latency, Heroku CPU and memory, and legitimate browsing failures. Adjust
the environment settings if needed. These are admission limits for the selected
HTTP handlers; they do not establish that every cause of a Heroku crash is fixed.
