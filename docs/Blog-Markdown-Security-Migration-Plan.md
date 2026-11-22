# PyChess blog Markdown security migration

**Status:** Planning — no code or database changes applied  
**Security advisory:** [GHSA-px6q-99f9-q825](https://github.com/pychess/pychess-variants/security/advisories/GHSA-px6q-99f9-q825)  
**Target repository:** `pychess/pychess-variants`  
**Target collection:** `ublog_post2` (new); preserve `ublog_post` unchanged  
**Working reference:** Production `ublog_post.json` export (55 documents; 50 live) and the uploaded PyChess/Lichess source snapshots

## Goal

Eliminate stored and reflected cross-site scripting enabled by the blog's arbitrary raw HTML/iframe handling and same-origin image proxy, while retaining useful blog features: Markdown, chess diagrams, SVG images, video/study embeds, and links to PyChess's versioned jsDelivr static assets. Move toward Lichess's safer authoring model: **escape author-supplied HTML; create approved embeds in trusted rendering code; embed images only from approved hosts.**

This is a redesign, not merely the advisory's one-line SVG-denylist fix. **The earlier `pychess-blog-svg-iframe-xss-fix.patch` is superseded by this plan and should not be applied alongside the future migration patch without reconciliation.**

## Original vulnerability and required invariants

The advisory identifies two independently important issues:

1. A blog post may contain raw `<iframe>` HTML. Client sanitization permits arbitrary same-origin iframe URLs without a sandbox. An iframe targeting `/blogs/image?url=...` can display active SVG content in the PyChess origin, executing attacker JavaScript as a reader.
2. The unauthenticated `/blogs/image` endpoint proxies arbitrary third-party SVG unchanged with `image/svg+xml`. **Even without any iframe**, a victim following a direct proxy URL can execute untrusted SVG as a top-level, same-origin document.

The fix is complete only if all of the following hold:

- Authors cannot inject active HTML, event handlers, arbitrary iframes, scripts, unsafe URL schemes, or script-capable same-origin content.
- The image proxy is removed **or** made independently safe for direct navigations; disabling iframe parsing alone is insufficient.
- Application-created embeds use a tightly validated provider/path allowlist. Their safety does not rely on accepting arbitrary user HTML.
- External SVGs used as images remain external-origin `<img>` resources, not documents laundered into the PyChess origin.
- The new rules are enforced for every reader, including previews, edits, listings and old posts.

## Agreed product decisions

- Adopt **Lichess-style Markdown semantics and its image-host whitelist** as a starting point. Verify the exact current host rules in the bundled Lichess source before implementing; add PyChess-specific requirements.
- Add trusted PyChess paths (`/static/images/`, `/static/docs/`, `/static/icons/` and any other validated existing static paths), and the **versioned `cdn.jsdelivr.net/gh/pychess/pychess-variants@<revision>/static/...`** repository tree. Accept only the intended host and exact repository/path boundaries; never trust all jsDelivr URLs.
- Preserve approved image hosts already used by blog posts, notably `i.imgur.com`; arbitrary external hosts should degrade to links, as in Lichess. Treat host redirects, protocol, Unicode hostnames, query strings and URL normalization carefully.
- Support approved external SVG images via direct HTTPS `<img>` references, subject to host allowlisting and browser/CSP policy. Do not feed SVG to a same-origin image proxy.
- Disallow **author-supplied** iframe HTML. Provide automatic URL-based YouTube and Lichess study embeds, plus PyChess game/study embeds when defined and tested. Trusted renderer-generated embeds may internally use sandboxed iframes.
- Migrate **all existing blog documents** from `ublog_post` to **new** `ublog_post2`, leaving the old collection **untouched permanently**. New posts and all subsequent reads/edits/deletions use only `ublog_post2`.
- Run the conversion once during server initialization, from a helper called by `PychessGlobalAppState.init_from_db()`; no separate production migration command required.
- The operator will validate the conversion locally against the production MongoDB export prior to deployment. A production rollback after migration is **not** an expected workflow, but data integrity and failure handling are still required.

## Production-content migration scope

The supplied production export contains **55 documents (50 live, 5 non-live)**. Earlier inventory found raw HTML images, paragraphs/alignment, line breaks, a small number of video/study iframes, SVG diagrams, Imgur links and some inline base64 image data. Re-run the inventory reproducibly from `ublog_post.json` during implementation: count constructs, enumerate actual hostnames and flag unsupported patterns with post IDs. Do not rely solely on the earlier conversational counts.

Conversions to implement and verify:

| Legacy content | New representation |
| --- | --- |
| `<img src=... width=... height=...>` | Markdown image plus narrowly validated width/height extension, preserving dimensions where feasible |
| `<p align="center">`, `<div align="center">` | Minimal, explicitly supported alignment syntax/CSS or a documented visual approximation |
| `<br>` | Markdown-compatible hard break |
| `<a href=...>` | Markdown link, with URL validation |
| `<b>`, headings and ordinary paragraphs | Standard Markdown |
| YouTube `<iframe>` | Recognized, validated YouTube URL; renderer creates the approved embed |
| Lichess study `<iframe>` | Recognized, validated study URL; renderer creates the approved embed |
| PyChess chess/analysis embeds, if present | Approved application link/URL-driven embed |
| `data:` bitmap images in old posts | Convert to controlled static media only if a safe destination is available, otherwise report for manual handling; never silently drop |
| Unrecognized/unsafe HTML | Flag for review; do not silently retain executable markup |

Retain identifiers, slugs, author, publication state, timestamps, metadata, likes, discussion references and other application fields. Keep original relative static asset links relative; do not hard-code the current `STATIC_ROOT` revision (`1.11.78`) into migrated posts.

## Implementation milestones

### [ ] 1. Baseline audit and fixtures

- [ ] Read repository `AGENTS.md` and relevant `.agents/skills/lichess` and `pychess-testing` guidance.
- [ ] Enumerate all `ublog_post` read/write/index/count usages, Markdown entry points, preview paths, `/blogs/image` consumers and static-asset URL handling.
- [ ] Audit all 55 exported documents; produce a per-post report of image hosts, raw tags, iframe destinations, media sizing, and conversion exceptions.
- [ ] Capture representative original/expected rendered output for legacy posts, including SVG, Imgur, YouTube and Lichess studies.

**Done when:** every affected code path and unsupported legacy construct is known.

### [ ] 2. Secure Markdown renderer and embed rules

- [ ] Escape raw HTML at Markdown parsing time; retain output sanitization as defense in depth.
- [ ] Port/replicate Lichess-style external-image allowlisting, with narrowly scoped PyChess static and jsDelivr rules.
- [ ] Ensure external approved SVGs load directly in `<img>`; relative PyChess static assets still work with production `STATIC_ROOT`.
- [ ] Implement URL-to-embed handlers for YouTube and Lichess studies; define any additional PyChess embed URL shapes precisely.
- [ ] Introduce a minimal validated image-size/alignment Markdown extension only where legacy conversion requires it.
- [ ] Review CSP and renderer-generated iframe sandbox/permissions for functionality and origin separation.
- [ ] Apply identical rendering policy to preview, published posts, listings and other consumers.

**Done when:** raw `<iframe>` HTML never creates an iframe; allowed ordinary media still renders.

### [ ] 3. Remove the image-proxy attack surface

- [ ] Trace `/blogs/image` consumers and remove its use by blog rendering.
- [ ] Remove the endpoint if no other feature needs it; otherwise reject active formats independently and set safe content-type/content-disposition/CSP/nosniff behavior, including for direct navigation.
- [ ] Test direct URL attacks with SVG and disguised payloads; ensure unrelated static SVG rendering is unaffected.

**Done when:** no attacker-controlled script-capable bytes can be served as an active document from the PyChess origin via the proxy.

### [ ] 4. One-time `ublog_post` → `ublog_post2` conversion

- [ ] Implement a deterministic, testable Python converter in its own module.
- [ ] Add a startup phase in `server/pychess_global_app_state.py`, before blog requests are served.
- [ ] Use stable original `_id` values and retain all non-Markdown metadata.
- [ ] Make copying restartable: idempotent writes keyed by `_id`, explicit validation and completion state; **never** use `count_documents()==0` as the only success signal.
- [ ] After completion, never re-import old posts on subsequent restarts, even if a new post is deleted from `ublog_post2`.
- [ ] Detect an incomplete or failed conversion and **fail startup rather than silently serving an incomplete database**; log IDs and failure causes.
- [ ] Update legacy bootstrap behavior and every blog read/write/index/count operation to use `ublog_post2` after migration.
- [ ] Ensure local/test fresh databases work without `ublog_post` and no new writes go to the old collection.
- [ ] Handle concurrent startup workers safely if the deployment configuration changes.

**Done when:** `ublog_post` remains byte-for-byte unchanged, `ublog_post2` contains all expected posts exactly once, and subsequent restarts do not repeat migration.

### [ ] 5. Testing and local acceptance

- [ ] Run the converter against the real 55-document Mongo export in an isolated test database; compare record counts, IDs, metadata and post-by-post converted content.
- [ ] Verify both live and non-live posts and existing URLs/slugs.
- [ ] Test restart, interrupted migration, concurrent startup, post edits, deletes and no-resurrection behavior.
- [ ] Test malicious SVG iframe input, direct SVG proxy navigation, bypass encodings, unexpected URL redirects, and disallowed image hosts.
- [ ] Check external SVG diagrams, PyChess jsDelivr SVG and images, Imgur images, image dimensions, YouTube and Lichess study embeds in a real browser.
- [ ] Run focused JS tests, typecheck, lint, Markdown checks; Python tests, Ruff and Pyrefly according to `AGENTS.md`.
- [ ] Save a readable per-post conversion report, identify visual differences, and resolve unexpected losses **before** deployment.

**Done when:** tests are green and all known legacy posts have either faithful conversion or explicitly accepted differences.

### [ ] 6. Deployment and post-deploy checks

- [ ] Deploy the renderer, proxy fix, collection routing and startup migration **together** (no mixed-mode window).
- [ ] Confirm startup migration completion log and document totals in `ublog_post2`.
- [ ] Confirm production server reads/writes `ublog_post2` and leaves `ublog_post` unchanged.
- [ ] Smoke-test old blog URLs, CDN assets, approved external images and video/study embeds.
- [ ] Check security-relevant logs for anomalous `/blogs/image` requests; consider prior exploitation separately from code remediation.
- [ ] Keep the original collection as a historical snapshot; document that it does **not** reflect future edits or new posts.

## Known design cautions

1. **Startup timing:** 55 conversions should be inexpensive, but 1–2 seconds is an estimate, not a guaranteed upper bound; remote MongoDB latency and indexes also matter.
2. **Completion marker:** Keep a durable migration completion record (in a suitable metadata collection or equivalent) written only after verifying the destination. Avoid source replays that resurrect deleted posts.
3. **Operational errors:** Migration failure must never silently fall back to the unsafe renderer or accidentally serve a half-populated `ublog_post2`.
4. **Cross-origin security:** Direct `<img>` SVG is script-inert in normal image context, but authors must not be able to turn it into an iframe/object or same-origin active document. Apply a restrictive CSP where practical.
5. **Lichess parity:** Match the security *principles*, not necessarily every implementation detail. Verify approved hostnames from the actual bundled Lichess source; constrain PyChess-specific jsDelivr exceptions narrowly.
6. **Existing screenshots and diagrams:** Test aspect ratios, centering and dimensions rather than assuming Markdown image replacement is visually equivalent.
7. **Backend validation:** New post creation/editing should not trust client-side sanitization to ensure content safety. The reader must always be safe, including when data comes directly from MongoDB.

## Progress log

| Stage | Status | Notes |
| --- | --- | --- |
| Advisory reviewed | Done | Unsandboxed same-origin iframe and active SVG proxy identified; direct URL attack also matters |
| Architectural direction agreed | Done | Lichess-style Markdown/image whitelist; PyChess CDN exception |
| Migration strategy agreed | Done | Separate `ublog_post2`; one-time server startup conversion; preserve original |
| Content inventory | Preliminary | Supplied 55-post export available; reproducible detailed audit still required |
| Code implementation | Not started | Prior SVG/iframe patch not applied |
| Offline migration tests | Not started | Run against production export |
| Production deployment | Not started | Deploy only after local acceptance |

## Suggested implementation commits

1. `docs: plan secure blog Markdown and ublog_post2 migration`
2. `security: replace raw blog HTML with restricted Markdown embeds`
3. `security: retire unsafe blog image proxy and whitelist image hosts`
4. `feat: migrate legacy blogs to ublog_post2 at startup`
5. `test: verify blog conversion and XSS regressions against export`

These can be combined or split differently as implementation warrants, but each stage should have focused tests and a clear acceptance gate.
