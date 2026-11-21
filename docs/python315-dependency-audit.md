# Python 3.15 dependency audit

Checked on 2026-11-11 against PyPI and CPython 3.15.2 on Linux x86_64 with the GIL enabled.

## Result

Local Python 3.15 development is feasible without changing Heroku's Python 3.14
runtime. The existing `requires-python = ">=3.14"` already permits 3.15; keep
`.python-version` at 3.14 and explicitly select 3.15 for a separate local environment.
Heroku reads the committed version pin, independently of the local interpreter.
See [Heroku's runtime selection documentation](https://devcenter.heroku.com/articles/python-runtimes).

The production lockfile cannot be installed unchanged on 3.15. The audit identified
these two dependencies for special handling; availability of source code alone does
not guarantee a successful build:

| Package | Current and latest PyPI release | Finding | Required action |
| --- | --- | --- | --- |
| [py4swiss](https://pypi.org/project/py4swiss/0.3.1/#files) | 0.3.1 | No compatible wheel or source distribution on PyPI. The [GitHub v0.3.1 source archive](https://github.com/Moritz72/py4swiss/releases/tag/v0.3.1) builds and installs successfully on 3.15.2. All 26 project Swiss pairing tests pass with it. | Use the GitHub release archive for local 3.15, or publish compatible PyPI artifacts upstream. |
| [minify-html](https://pypi.org/project/minify-html/0.18.1/#files) | 0.18.1 | A PyPI source distribution exists, but its build fails on 3.15.2 because PyO3 0.27.1 supports Python only through 3.14. Repository searches found no application imports or callers. | Removed from pyproject.toml and uv.lock. |

The minify-html build reports:

```text
error: the configured Python version (3.15) is newer than PyO3's maximum supported version (3.14)
```

No environment variable was used to bypass PyO3's compatibility check.
Application code, runtime pins, CI, and Docker images are unchanged. The only production
dependency change is removal of unused minify-html from `pyproject.toml` and `uv.lock`.
Local setup instructions and a separate dependency override file implement the reviewed approach.

## Engine packages

- The local `~/pyffish-wheels` directory contains **pyffish 0.0.91**, including standard
  CPython 3.15 and free-threaded wheels for Linux x86_64, macOS x86_64/ARM64, and Windows x86_64.
  The standard Linux wheel installs and imports on CPython 3.15.2, reports `(0, 0, 91)`,
  and enumerates 121 variants. Other platforms and free-threaded builds were not executed.
  The project's current pin and latest PyPI release are still **0.0.90**; publishing 0.0.91
  will require updating the pin and lockfile during migration.
- [pyffish-alice 0.0.3](https://pypi.org/project/pyffish-alice/0.0.3/#files) has no 3.15 wheel
  on PyPI, and the provided wheel directory contains no Alice wheels. Its existing PyPI source
  distribution **builds and imports successfully on 3.15.2** and exposes the Alice variant.
  Publish 3.15 wheels as well if deployment should avoid compiling the engine.

## Dependency updates needed for local 3.15

These locked native dependencies lack a compatible Linux wheel, but newer releases on PyPI
provide one. The versions below are verified candidates, not claims about the first release
supporting 3.15. They satisfy the current direct dependency constraints in a fresh resolution.

| Dependency | Locked version | Verified candidate |
| --- | --- | --- |
| [cffi](https://pypi.org/project/cffi/2.1.1/) | 2.0.0 | 2.1.1 |
| [greenlet](https://pypi.org/project/greenlet/3.5.6/) (Playwright) | 3.2.4 | 3.5.6 |
| [MarkupSafe](https://pypi.org/project/MarkupSafe/3.0.4/) | 3.0.2 | 3.0.4 |
| [NumPy](https://pypi.org/project/numpy/2.5.4/) (rustworkx) | 2.3.2 | 2.5.4 |
| [pydantic-core](https://pypi.org/project/pydantic-core/2.50.4/) (py4swiss) | 2.41.5 | 2.50.4, together with [Pydantic 2.14.3](https://pypi.org/project/pydantic/2.14.3/) |

Pydantic pins its core version exactly, so update the pair together.
PyYAML 6.0.2 and the latest 6.0.3 both lack a compatible Linux wheel but build and import on
3.15.2. http-ece 1.2.1 is source-only and also installs and imports successfully.

## Checks performed

- Queried version-specific PyPI JSON metadata and release files for all **91 registry packages**
  in the original `uv.lock`, including all **26 runtime** and **11 development** direct dependencies.
  These counts and the inventory below include minify-html, which was subsequently removed.
  All locked `Requires-Python` constraints admit 3.15.2; this alone does not establish runtime support.
- Compared wheel tags against regular CPython 3.15 on this Linux x86_64 host, accepting compatible
  `abi3` and interpreter-independent wheels as well as `cp315-cp315` wheels.
  **80 of 91 locked packages have a compatible wheel.** Pure Python fallbacks count as available
  even where an older release lacks a native accelerator wheel.
- Queried the latest PyPI releases for every package without a matching locked wheel.
- Verified the unpinned build requirement `setuptools>=75.0`: latest **84.2.1** has a compatible
  universal wheel and allows 3.15.2.
- Installed an isolated CPython **3.15.2** under `/tmp`, using `uv==0.13.7` through `uvx`.
  The existing system uv 0.11.7 only knows 3.15.0a8; its interpreter catalog must be updated
  before relying on `uv python install 3.15` to install the stable release.
- Reproduced py4swiss's PyPI resolver failure and minify-html's PyPI source-build failure.
  Subsequently built py4swiss successfully from its GitHub v0.3.1 archive with SHA-256
  `b612c7e7ce979c6708624fff4b1c29530f5c2c3260413b728693c3a920bc1363`.
- Resolved and installed **85 packages** for the remaining runtime/development requirements,
  excluding py4swiss, minify-html, and the two engine packages. Added `pydantic>=2.11.9`
  explicitly to exercise py4swiss's dependency chain. Tested pyffish and pyffish-alice separately.
  This fresh resolution updates transitives; it does not validate the existing lockfile unchanged.
- Passed **39 dependency imports**, an aiohttp local HTTP request/response, a cryptography
  encrypt/decrypt roundtrip, Pydantic validation, msgspec JSON roundtrip, and Playwright driver
  startup.
- Confirmed Ruff 0.17.4 accepts `py315`, and `python -m profiling.sampling --help` works.
  The new sampling profiler is documented in the
  [Python 3.15 documentation](https://docs.python.org/3.15/library/profiling.sampling.html).
- [Heroku supports Python 3.15](https://devcenter.heroku.com/articles/python-support);
  the deployment platform itself is not a blocker.

The application checks below use a separate local 3.15 environment with pyffish 0.0.91,
the py4swiss GitHub release archive, pyffish-alice built from PyPI source, refreshed
transitives, and minify-html omitted. These checks do not validate installing the
unchanged dependency set from PyPI or the existing lockfile on 3.15.

| Application verification on 3.15.2 | Result |
| --- | --- |
| Unittest shard 1 | 868 tests passed |
| Unittest shard 2 | 881 tests run: 880 passed, 1 skipped |
| pytest-only Simul suite | 40 tests passed |
| Playwright lobby page (`tests/test_e2e.py`) | Passed with the bundled Chromium browser |
| `uv pip check` | All 88 installed packages compatible |

Both unittest shards together cover the full unittest discovery set. Other Playwright
workflows were not run. The suites emit existing application warnings and deprecation
warnings; no application source changes were needed for these tests to pass.

The new sampling profiler successfully ran all 26 Swiss pairing tests and wrote a
collapsed-stack profile with 2,066 samples. This verifies profiler functionality;
it is not a performance benchmark.

## Complete locked-package inventory

Each package link points to the exact audited PyPI release. “Wheel” means an installable
artifact exists for regular CPython 3.15 on this Linux host, not that the maintainer explicitly
classifies or tests 3.15. “Python wheel” includes platform-specific executable distributions
such as Ruff and Playwright. Packages enabled only on other platforms or by extras are included.

| Package | Locked version | Dependency | Linux CPython 3.15 artifact / action |
| --- | --- | --- | --- |
| [aiohappyeyeballs](https://pypi.org/project/aiohappyeyeballs/2.6.1/) | 2.6.1 | Transitive / extra | Python wheel |
| [aiohttp](https://pypi.org/project/aiohttp/3.14.5/) | 3.14.5 | Direct runtime | CPython 3.15 wheel |
| [aiohttp-cors](https://pypi.org/project/aiohttp-cors/0.8.1/) | 0.8.1 | Direct runtime | Python wheel |
| [aiohttp-jinja2](https://pypi.org/project/aiohttp-jinja2/1.6/) | 1.6 | Direct runtime | Python wheel |
| [aiohttp-session](https://pypi.org/project/aiohttp-session/2.12.1/) | 2.12.1 | Direct runtime | Python wheel |
| [aiohttp-sse](https://pypi.org/project/aiohttp-sse/3.0/) | 3.0 | Direct runtime | Python wheel |
| [aiohttp-swagger3](https://pypi.org/project/aiohttp-swagger3/0.10.0/) | 0.10.0 | Direct runtime | Python wheel |
| [aiosignal](https://pypi.org/project/aiosignal/1.4.0/) | 1.4.0 | Transitive / extra | Python wheel |
| [annotated-types](https://pypi.org/project/annotated-types/0.7.0/) | 0.7.0 | Transitive / extra | Python wheel |
| [attrs](https://pypi.org/project/attrs/25.3.0/) | 25.3.0 | Transitive / extra | Python wheel |
| [audioop-lts](https://pypi.org/project/audioop-lts/0.2.2/) | 0.2.2 | Transitive / extra | Stable ABI wheel |
| [betza-visualizer](https://pypi.org/project/betza-visualizer/0.1.1/) | 0.1.1 | Direct runtime | Python wheel |
| [brotli](https://pypi.org/project/brotli/1.2.1/) | 1.2.1 | Direct runtime | CPython 3.15 wheel |
| [certifi](https://pypi.org/project/certifi/2026.10.19/) | 2026.10.19 | Transitive / extra | Python wheel |
| [cffi](https://pypi.org/project/cffi/2.0.0/) | 2.0.0 | Transitive / extra | Refresh lock to 2.1.1 for wheel |
| [cfgv](https://pypi.org/project/cfgv/3.4.0/) | 3.4.0 | Transitive / extra | Python wheel |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.4.7/) | 3.4.7 | Transitive / extra | Python wheel |
| [colorama](https://pypi.org/project/colorama/0.4.6/) | 0.4.6 | Transitive / extra | Python wheel |
| [cryptography](https://pypi.org/project/cryptography/50.0.2/) | 50.0.2 | Direct runtime | Stable ABI wheel |
| [discord-py](https://pypi.org/project/discord-py/2.7.1/) | 2.7.1 | Direct runtime | Python wheel |
| [distlib](https://pypi.org/project/distlib/0.4.4/) | 0.4.4 | Transitive / extra | Python wheel |
| [dnspython](https://pypi.org/project/dnspython/2.9.2/) | 2.9.2 | Direct runtime | Python wheel |
| [fastjsonschema](https://pypi.org/project/fastjsonschema/2.19.1/) | 2.19.1 | Transitive / extra | Python wheel |
| [filelock](https://pypi.org/project/filelock/4.2.1/) | 4.2.1 | Transitive / extra | Python wheel |
| [frozenlist](https://pypi.org/project/frozenlist/1.7.0/) | 1.7.0 | Transitive / extra | Python wheel |
| [greenlet](https://pypi.org/project/greenlet/3.2.4/) | 3.2.4 | Transitive / extra | Refresh lock to 3.5.6 for wheel |
| [http-ece](https://pypi.org/project/http-ece/1.2.1/) | 1.2.1 | Transitive / extra | Source-only; installation and import pass |
| [identify](https://pypi.org/project/identify/2.6.13/) | 2.6.13 | Transitive / extra | Python wheel |
| [idna](https://pypi.org/project/idna/3.15/) | 3.15 | Transitive / extra | Python wheel |
| [iniconfig](https://pypi.org/project/iniconfig/2.1.0/) | 2.1.0 | Transitive / extra | Python wheel |
| [jinja2](https://pypi.org/project/jinja2/3.1.6/) | 3.1.6 | Direct runtime | Python wheel |
| [linkify-it-py](https://pypi.org/project/linkify-it-py/2.1.0/) | 2.1.0 | Transitive / extra | Python wheel |
| [markdown-it-py](https://pypi.org/project/markdown-it-py/4.2.0/) | 4.2.0 | Transitive / extra | Python wheel |
| [markupsafe](https://pypi.org/project/markupsafe/3.0.2/) | 3.0.2 | Transitive / extra | Refresh lock to 3.0.4 for wheel |
| [mdit-py-plugins](https://pypi.org/project/mdit-py-plugins/0.6.1/) | 0.6.1 | Transitive / extra | Python wheel |
| [mdurl](https://pypi.org/project/mdurl/0.1.2/) | 0.1.2 | Transitive / extra | Python wheel |
| [minify-html](https://pypi.org/project/minify-html/0.18.1/) | 0.18.1 | Direct runtime | Blocked: source build rejects Python 3.15 |
| [mongomock](https://pypi.org/project/mongomock/4.3.0/) | 4.3.0 | Transitive / extra | Python wheel |
| [mongomock-motor](https://pypi.org/project/mongomock-motor/0.0.36/) | 0.0.36 | Direct dev | Python wheel |
| [motor](https://pypi.org/project/motor/3.7.1/) | 3.7.1 | Direct dev | Python wheel |
| [msgspec](https://pypi.org/project/msgspec/0.22.0/) | 0.22.0 | Direct runtime | CPython 3.15 wheel |
| [multidict](https://pypi.org/project/multidict/6.6.4/) | 6.6.4 | Transitive / extra | Python wheel |
| [nodeenv](https://pypi.org/project/nodeenv/1.9.1/) | 1.9.1 | Transitive / extra | Python wheel |
| [numpy](https://pypi.org/project/numpy/2.3.2/) | 2.3.2 | Transitive / extra | Refresh lock to 2.5.4 for wheel |
| [objgraph](https://pypi.org/project/objgraph/3.7.0/) | 3.7.0 | Direct dev | Python wheel |
| [packaging](https://pypi.org/project/packaging/26.3/) | 26.3 | Transitive / extra | Python wheel |
| [platformdirs](https://pypi.org/project/platformdirs/4.4.0/) | 4.4.0 | Transitive / extra | Python wheel |
| [playwright](https://pypi.org/project/playwright/1.64.1/) | 1.64.1 | Direct dev | Python wheel |
| [pluggy](https://pypi.org/project/pluggy/1.6.0/) | 1.6.0 | Transitive / extra | Python wheel |
| [pre-commit](https://pypi.org/project/pre-commit/4.7.0/) | 4.7.0 | Direct dev | Python wheel |
| [propcache](https://pypi.org/project/propcache/0.3.2/) | 0.3.2 | Transitive / extra | Python wheel |
| [py-vapid](https://pypi.org/project/py-vapid/1.9.4/) | 1.9.4 | Transitive / extra | Python wheel |
| [py4swiss](https://pypi.org/project/py4swiss/0.3.1/) | 0.3.1 | Direct runtime | No PyPI artifact; GitHub release source build and Swiss tests pass |
| [pycparser](https://pypi.org/project/pycparser/2.22/) | 2.22 | Transitive / extra | Python wheel |
| [pydantic](https://pypi.org/project/pydantic/2.12.5/) | 2.12.5 | Transitive / extra | Python wheel; update to 2.14.3 with core |
| [pydantic-core](https://pypi.org/project/pydantic-core/2.41.5/) | 2.41.5 | Transitive / extra | Refresh Pydantic/core pair to 2.14.3 / 2.50.4 |
| [pyee](https://pypi.org/project/pyee/13.0.0/) | 13.0.0 | Transitive / extra | Python wheel |
| [pyffish](https://pypi.org/project/pyffish/0.0.90/) | 0.0.90 | Direct runtime | Local 0.0.91 wheel passes import smoke check; unpublished |
| [pyffish-alice](https://pypi.org/project/pyffish-alice/0.0.3/) | 0.0.3 | Direct runtime | No wheel; PyPI source build and import pass |
| [pygments](https://pypi.org/project/pygments/2.20.0/) | 2.20.0 | Transitive / extra | Python wheel |
| [pymongo](https://pypi.org/project/pymongo/4.19.0/) | 4.19.0 | Direct runtime | CPython 3.15 wheel |
| [pyopenssl](https://pypi.org/project/pyopenssl/26.4.0/) | 26.4.0 | Direct runtime | Python wheel |
| [pyrefly](https://pypi.org/project/pyrefly/1.4.1/) | 1.4.1 | Direct dev | Python wheel |
| [pytest](https://pypi.org/project/pytest/9.2.0/) | 9.2.0 | Direct dev | Python wheel |
| [pytest-aiohttp](https://pypi.org/project/pytest-aiohttp/1.1.1/) | 1.1.1 | Direct dev | Python wheel |
| [pytest-asyncio](https://pypi.org/project/pytest-asyncio/1.3.0/) | 1.3.0 | Transitive / extra | Python wheel |
| [python-discovery](https://pypi.org/project/python-discovery/1.6.1/) | 1.6.1 | Transitive / extra | Python wheel |
| [python-gettext](https://pypi.org/project/python-gettext/5.0/) | 5.0 | Direct runtime | Python wheel |
| [pytz](https://pypi.org/project/pytz/2025.2/) | 2025.2 | Transitive / extra | Python wheel |
| [pywebpush](https://pypi.org/project/pywebpush/2.5.0/) | 2.5.0 | Direct runtime | Python wheel |
| [pyyaml](https://pypi.org/project/pyyaml/6.0.2/) | 6.0.2 | Transitive / extra | No wheel; source build and import pass |
| [rapidfuzz](https://pypi.org/project/rapidfuzz/3.14.6/) | 3.14.6 | Direct runtime | CPython 3.15 wheel |
| [requests](https://pypi.org/project/requests/2.34.2/) | 2.34.2 | Transitive / extra | Python wheel |
| [rfc3339-validator](https://pypi.org/project/rfc3339-validator/0.1.4/) | 0.1.4 | Transitive / extra | Python wheel |
| [rich](https://pypi.org/project/rich/15.0.0/) | 15.0.0 | Transitive / extra | Python wheel |
| [ruff](https://pypi.org/project/ruff/0.17.4/) | 0.17.4 | Direct dev | Python wheel |
| [rustworkx](https://pypi.org/project/rustworkx/0.18.1/) | 0.18.1 | Direct runtime | Stable ABI wheel |
| [sentinels](https://pypi.org/project/sentinels/1.1.1/) | 1.1.1 | Transitive / extra | Python wheel |
| [six](https://pypi.org/project/six/1.17.0/) | 1.17.0 | Transitive / extra | Python wheel |
| [sortedcollections](https://pypi.org/project/sortedcollections/2.1.0/) | 2.1.0 | Direct runtime | Python wheel |
| [sortedcontainers](https://pypi.org/project/sortedcontainers/2.4.0/) | 2.4.0 | Transitive / extra | Python wheel |
| [tenacity](https://pypi.org/project/tenacity/9.2.1/) | 9.2.1 | Direct runtime | Python wheel |
| [textual](https://pypi.org/project/textual/8.2.8/) | 8.2.8 | Direct dev | Python wheel |
| [tqdm](https://pypi.org/project/tqdm/4.70.1/) | 4.70.1 | Direct dev | Python wheel |
| [typing-extensions](https://pypi.org/project/typing-extensions/4.15.0/) | 4.15.0 | Transitive / extra | Python wheel |
| [typing-inspection](https://pypi.org/project/typing-inspection/0.4.2/) | 0.4.2 | Transitive / extra | Python wheel |
| [tzdata](https://pypi.org/project/tzdata/2026.6/) | 2026.6 | Direct runtime | Python wheel |
| [uc-micro-py](https://pypi.org/project/uc-micro-py/2.0.0/) | 2.0.0 | Transitive / extra | Python wheel |
| [urllib3](https://pypi.org/project/urllib3/2.8.0/) | 2.8.0 | Transitive / extra | Python wheel |
| [virtualenv](https://pypi.org/project/virtualenv/21.14.13/) | 21.14.13 | Transitive / extra | Python wheel |
| [yarl](https://pypi.org/project/yarl/1.25.1/) | 1.25.1 | Transitive / extra | CPython 3.15 wheel |

## Local development setup

Follow [the local setup instructions](python315-development.md).
The [local overrides](../requirements/python315-overrides.in) select pyffish 0.0.91
and the py4swiss release archive. Once pyffish is published, the same override can
resolve it from PyPI instead of a wheel directory. The unused minify-html dependency
has been removed.

The separate local environment leaves `.python-version`, the Python requirement,
Ruff/Pyrefly runtime targets, CI, Docker, and other production dependencies at their
existing 3.14-compatible settings. Local installation resolves newer transitive versions
without updating the production lockfile.
Do not use an ordinary `uv sync --python 3.15` against the current lockfile and expect
it to work. A separate local resolution is needed for the transitive updates above.

For commands in an activated, prepared local environment, use plain `python`, or
`uv run --active --no-sync --python 3.15` to avoid synchronizing production pins into it.
That invocation was verified with the repository's `.python-version` still set to 3.14.
Retain 3.14-compatible application syntax and the existing `py313` formatting target.
