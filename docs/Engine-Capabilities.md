# Engine and variant capability boundaries

PyChess must not treat "this variant has engine support" as one global boolean.
Different features execute in different places and may support different variant
sets. A variant can therefore be playable against a server engine while still being
unavailable to the browser analysis engine.

## Capability axes

| Capability | Execution path | Source of truth | Alice Chess |
| --- | --- | --- | --- |
| Play vs AI | Server -> fairyfishnet | An active worker capable of the requested variant | Supported when an Alice-capable worker is active |
| Server-side game/Study analysis | Server -> fairyfishnet | An active worker capable of the requested variant | Supported when an Alice-capable worker is active |
| Browser analysis | Browser engine worker | The loaded browser engine's advertised UCI variants | Unsupported |
| Local native analysis | Paired loopback Python bridge | Explicit per-adapter capabilities plus page permissions | Supported with a configured Alice native engine |
| Computer Practice | Browser engine worker | Local-analysis capability plus Practice restrictions | Unsupported |
| PGN legality/replay | Browser rules/replay module | The parser/replay implementation for the variant | Supported; this does **not** imply local engine search support |

The first two rows are dynamic deployment capabilities: availability can change as
workers connect, disconnect, or lose an optional engine. Browser support is a
separate property of the client engine bundle.

## Server fairyfishnet capabilities

`server/fishnet.py` keeps the variants that require an explicitly advertised worker
engine in `OPTIONAL_FISHNET_VARIANTS`. Older workers remain eligible for ordinary
Fairy-Stockfish variants, but are never considered capable of an optional variant.

Workers advertise optional variants in the fishnet request payload, for example:

```json
"capabilities": {
  "variants": ["alice"]
}
```

The server records recent capability advertisements separately from general worker
liveness. `has_available_fishnet_worker(..., variant=...)` is the availability gate
for variant-specific Play-AI and server-analysis work. Shared queue acquisition also
checks the requesting worker's capabilities so an ordinary worker can skip an Alice
job without consuming it.

An optional-engine variant must not fall through to the legacy Fairy-Stockfish BOT
websocket when no capable fishnet worker exists. Lack of an Alice-capable worker means
Alice server-engine work is unavailable at that moment; it does not mean the game or
variant itself is unsupported.

## Browser/WASM engine support

`AnalysisController.variantSupportedByFSF` refers specifically to the browser engine
loaded by the analysis page. It is set from that engine's `UCI_Variant` advertisement
and gates local infinite analysis and other browser searches.

Do not use `variantSupportedByFSF` to decide whether a server-side fishnet request can
be made. The server owns that decision because only it knows which fishnet worker
capabilities are currently available.

Likewise, successful client-side rules handling or PGN replay is not evidence of
browser engine-search support. Alice PGN import can use Alice-capable replay/rules
code while Alice browser/WASM search remains unavailable. Local native analysis uses
its separate paired adapter and does not imply Practice support.

## Feature rules

When adding or changing engine support for a variant:

1. Decide separately whether the variant supports Play-AI, server analysis, local
   browser analysis, Practice, and PGN replay.
2. For server work, add a worker capability when the standard Fairy-Stockfish worker
   cannot perform the job; do not widen a browser-engine allowlist as a substitute.
3. For browser work, rely on the actual loaded engine's advertised variants and any
   feature-specific restrictions (for example Practice's two-board exclusion).
4. Keep UI messages specific to the failing path: "no capable server worker" and
   "not supported by the browser engine" are different conditions.
5. Test the negative combinations as well as the positive path. In particular, a
   variant may intentionally have server AI/analysis enabled while local analysis is
   disabled.

Alice is the current reference case for this split: Alice-Stockfish is an optional
fairyfishnet engine for Play-AI and server analysis, while the normal browser
Fairy-Stockfish/WASM engine does not support Alice search.

## Local native analysis

Each paired external app configures one UCI executable. Its capabilities contain
one name, one set of resource limits and its supported variant list. The optional
`engine.variantRestrictions` map narrows Chess960/custom-rule support for specific
advertised variants without selecting another executable or changing resource limits.

An advertised Alice capability is qualified with a native search and validated with
`pyffish-alice`; neither successful PGN replay nor an engine's ordinary custom-rules
flag enables it. The bridge reports `variantRestrictions.alice` with `chess960: false`
and `customRules: false`. Alice uses compact looking-glass FEN and coordinate move
tokens. Page/Study/anti-cheat restrictions still apply, and Practice retains its
browser engine ownership.

See [the integration reference](external-engine.md) for frontend ownership and
links to the local application design, protocol and compatibility documentation.

## Engine BOT profile identity

An external BOT can include an optional `engine` object in its existing authenticated
`GET /api/stream/event` capability header:

```json
{"version":1,"variants":["alice"],"engine":{"name":"Alice-Stockfish 1.0","author":"Belzedar94 and the Stockfish developers (see AUTHORS file)"}}
```

The header remains `X-PyChess-Bot-Capabilities`, version 1. The BOT client reads these
values from the UCI `id name` and `id author` handshake. This is descriptive metadata;
it does not affect variant eligibility or replace the BOT account's username.

The server accepts a nonempty engine name, normalizes whitespace, and limits names
to 128 characters and author credits to 256 characters. Unknown engine fields are
ignored. Missing or malformed optional identity does not prevent the BOT connecting.
The last reported identity is stored as `botEngine` on that BOT's user document and
rendered as escaped text in the profile's player summary, including while offline.
A later advertisement replaces the identity; older clients without an `engine`
field retain the last reported details. Clients must not send paths, options, tokens,
or other private configuration in this object.
