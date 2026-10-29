# Rust mesh selection verification

Scope: issue #40. The fixed contract is commit `673a7a4`.
The implementation candidate is `7848233`.
The branch includes pending PRs #33, #35, #37 and #39.
This does not integrate those changes into main.
Every full feature and milestone acceptance gate remains open.

## Measured local results

The [evidence manifest](../evidence/mesh-selection-core/manifest.json) pins candidate `7848233`.
The [local check log](../evidence/mesh-selection-core/local/manifest.json) records the actual tool versions.
All 101 Rust tests and 47 Python tests passed.
Format, Clippy and the official MCP regression passed.
The strict baseline remains incomplete: exit 2, 9,047 sources, 9,026 pending sources
and all 23 catalog features pending. It is not a product pass.

All [1,060 selection comparisons](../evidence/mesh-selection-core/cases/report.json) passed
through CLI and the official MCP SDK with the Rust 1.85 executable.
The [138 primitive generation regressions](../evidence/mesh-selection-core/primitive-regression.json)
and [57 polygon payload regressions](../evidence/mesh-selection-core/polygon-payload-regression.json) also passed.
These use the original topology checks and numeric limits.

All [30 release measurements](../evidence/mesh-selection-core/performance/report.json) passed.
The maximum core time was 44.706 ms. The maximum select/save/reload time was 386.964 ms.
Existing triangle, polygon and primitive performance checks also passed their original limits.
Their full outputs are retained under `local/`.

The [Metal capture](../evidence/mesh-selection-core/gpu/manifest.json) passed all three domains.
Vertex, edge and face selection changed 25, 464 and 53,824 pixels, respectively.
Every reload was byte-identical. Hidden captures had zero visible surface pixels.
Codex inspected the edge and face captures.
The [isolated runtime](../evidence/mesh-selection-core/independent-runtime.json) passed all ten new inputs.
These finite local results do not replace any remaining integration or platform gate.

## Compiler qualification correction

An audit found that the earlier local command form `rustup run 1.85.0 cargo ...`
still resolved child tools through Homebrew PATH.
The observed compiler cache identifies Rust 1.96.1.
Clippy reported 0.1.96 and rustfmt reported 1.9.0.
Those earlier finite functional outputs do not prove minimum-version compatibility.
Correction comments were posted on PRs #33, #35, #37 and #39.
Their required CI and integrated acceptance remain open.

The current checks use absolute `RUSTC` and `RUSTDOC` paths.
They put the matching toolchain bin directory first in PATH.
They also use a fresh target directory.
The retained tool versions and compiler cache must identify Rust 1.85.0,
Cargo 1.85.0, Clippy 0.1.85 and rustfmt 1.8.0-stable.
The local check driver rejects a different version.

Actual Rust 1.85 Clippy found an existing comparison-chain lint in cube UV generation.
The code now uses an equivalent ordered match.
The UV values and branch conditions are unchanged.
The original geometry and numeric comparisons remain required.

## Fixed functional checks

The runtime adapter builds requests from the authored selection fixture.
It sends topology, attributes, logical IDs and seed operations.
It does not send captured before/after selection answers to Rust.
The runtime computes each result from the request.

Each of CLI and official MCP executes all 530 cases.
The source outcomes are 480 completed, 30 unchanged and 20 rejected per interface.
Every selection ID, mode, history entry, active face and hidden component is compared.
Geometry, UV layer order, materials, smoothing, seams and group weights are also compared.
The frozen reference comparer is unchanged.
Only the expected rejected operation's raw API text is normalized to its semantic code.
Both raw messages remain in the candidate and source data.
No state field or unexpected error is normalized.
This API does not promise bpy error-message compatibility.

The adapter checks a fresh process reload for every case.
Successful operations are undone and reapplied in the live session.
Rejected operations preserve file bytes.
The CLI rejects undo when no successful operation has entered that session's history.
MCP undo after a rejection returns to the earlier setup entry.
The CLI also repeats the selector through the one-shot command route.

New Rust tests cover typed legacy face identity, stable derived edge IDs,
read-only topology queries, old-file output, duplicate IDs, invalid references,
zero-weight membership, missing versus empty weight layers, shared instances,
ordered receipts, stale revisions, batch rollback, failed persistence and undo.
They also cover additive no-match behavior, mode conversion of isolated vertices,
hidden crossing polygons and render markers that do not change surface picking.

## Fixed performance and Metal checks

Each of the ten functions/conversions uses its frozen performance parameters.
The sample has 10,201 vertices, 20,200 edges and 10,000 quad faces.
It preserves the specified two UV layers, material slots, smooth flags, seams and weights.
Each function runs three times in release on Apple M1 Max/macOS.
The limits remain 100 ms for core selection and 2,000 ms for select/save/reload.
Raw monotonic timestamps, input/output hashes and saved-scene hashes are retained.

The actual Metal capture uses an isolated square for each selection domain.
Vertex markers, selected edges and selected face tint must change its pixels.
The hidden face must disappear.
A fresh process reload must produce a byte-identical PNG.
Saved geometry and authored attributes must remain unchanged.
Pixel area uses each image's own background pixel.
The draw and empty-clear paths can differ by one background channel value on Metal.
That difference must not be counted as object area.
The manifest records the executable, source, shader, requests, outputs and capture scripts.

The isolated runtime check copies the executable outside the repository.
It denies repository reads with the macOS sandbox.
A control read of a real selection fixture must fail.
Ten new inputs test the selectors and mode conversions through actual Rust commands.
They preserve coincident vertex identities and distinguish zero weights from missing membership.
Their requests and responses are retained.

## Reproduce

First set the toolchain paths and run the local check driver.
The toolchain directory must contain the actual Rust 1.85 binaries.
Set `CARGO_HOME` and `RUSTUP_HOME` only when using a separate cache.
Install `tools/requirements-mcp.txt` before SDK checks.

```sh
python3 tools/local_selection_checks.py /absolute/toolchain/bin /absolute/target /absolute/new-local-evidence
python3 tools/selection_runtime_smoke.py /absolute/target/debug/formora /absolute/new-selection-evidence
python3 tools/selection_gpu_evidence.py /absolute/target/debug/formora /absolute/new-gpu-evidence
python3 tools/selection_independent.py /absolute/target/debug/formora /absolute/new-independent-evidence
```

Build `selection_performance` with the same pinned paths and `--release`.
Run `tools/selection_performance_evidence.py` with that example executable and a new output directory.
The performance wrapper rejects a different native hardware model.

## Remaining gates

The strict baseline still exits 2. That is an incomplete baseline, not product acceptance.
Its original sources, feature scope, tolerances and version pins remain unchanged.
All dependency integrations, required three-platform CI and independent acceptance
of the integrated candidate remain required before issue closure.
GitHub previously refused to start jobs because of account billing or spending limits.
The final PR must retain its fresh check results. Local passes cannot replace unrun CI.

Full numeric domains, degenerate interior costs, multi-object operations,
screen-space tools, UV synchronization, native window input, Windows/Linux GPU
and full modeling parity remain open.
All 11 milestones remain open with no invented deadlines.
