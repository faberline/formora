# Local merge checks at 224a4360

This is local evidence for issue #72 and draft PR #75.
It does not accept the issue or a milestone.
All eleven milestones stay open.

## Exact builds

Rust implementation: `224a4360276511f48d023a2f6f39190010dae731`.
The default executable has SHA-256
`5bf40a3c99843bd7b9395d3d712f605756284cd44aa07c2925661b7c7bd5c3c2`.
The release library has SHA-256
`86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea`.
The preview executable has SHA-256
`5fe37fe3ce8c556e4cd5c01fe27f086fd422e5de8ad3a765de4c428b0ee15f7f`.
Evidence-only commits do not change these builds.

## Completed local checks

- Actual Rust 1.85 passed all 297 tests with all features and targets.
  Zero tests were ignored.
  Clippy passed with warnings denied.
  Formatting, debug build and release build passed.
- All 215 Python tests passed.
  The earlier three fixture-path failures remain recorded.
  Only captured-path selection changed in those tests.
  The original rejection checks remain.
- Both original native Blender captures passed the unchanged full source check.
  They contain 1,024 cases: 920 changed, 88 unchanged and 16 rejected enum inputs.
- All 2,048 actual CLI and official MCP requests passed.
  A separate audit checked every raw request, response, saved scene and receipt.
  It compared each case to both original native captures.
  The seven full-report corruption checks rejected false evidence.
  Eleven API and nine physical corruption checks also passed on current raw cases.
- All 30 new merge timing samples passed.
  The maximum core time was 162.519709 ms against 250 ms.
  The maximum operation/save/reload time was 188.243291 ms against 2,000 ms.
  All 30 saved outputs also passed the original physical source checks.
- All 177 retained timing samples passed their original limits.
  Their separate physical source checks are still running.
- Nine native Rust tests passed with both source trees and prior answer paths denied.
  These are native API tests, not CLI or MCP evidence.
- Nineteen native protocol calls proved real failed-save rollback, undo and replay.
  A fresh denied-source process loaded the saved result.
  The real save error was `Is a directory (os error 21)`.
- The new merge Metal proof passed before, after and fresh-process renders.
  It changed 16,155 pixels.
  After and reloaded PNG bytes are equal.
  The geometric projection and direct PNG pixel checks also passed.
- Seven retained source-denied suites passed.
  Five retained recipe, seven-action and invalid-input suites passed.
  Forty-eight fresh-process CLI RNG cases and six exact Euler-order checks passed.
  Four retained native Metal proofs passed.

## Evidence storage

`completed-proofs-gzip-01/archive-manifest.json` binds every copied output to its
original file, byte count and SHA-256.
Large JSON and stdout files use lossless gzip with a fixed timestamp.
The packer checked every decompressed digest against the original file.
Native files under `/private/tmp` remain intact.
The extra uncompressed `completed-proofs-01/` directory is local only.
It is not part of the published evidence set.
Later source, GPU, RNG and complete retained API reports need a second archive.

## Preserve these failures

The first full timing trial passed timing but failed history comparison.
The next trial passed physical source comparison but failed the fixed timing limit.
Its maximum core time was 365.706166 ms.
Its maximum pipeline time was 458.655625 ms.
The later code change preserves UV values that the operation does not use.
It also removes duplicate full-mesh work.
The native workload, clocks, validation and limits did not change.

The first full API run failed its input-stability gate.
Sparse checkout had removed a required contract file.
The full checkout was restored before the later complete runs.
This failed run remains failed.

The first retained timing attempt could not query hardware or host load.
Those 138 native timing samples had not started.
The 39 samples that did run passed and were kept.
The second attempt ran only the unstarted 138 samples.
It used the same drivers, hardware checks and limits.

The first small-gate controller did not create the local output parent.
Seven source-denied suites passed.
Five local suites stopped before native work.
Their retry created a fresh parent and ran the same tests.
The original controller report remains failed.

## Required work still open

The retained 14,326 CLI/MCP requests and asset regressions are running.
Their full raw audit is unrun.
The retained 177 physical source comparisons are running.
Three-platform CI, dependency integration and independent Codex acceptance are unpassed.
The full parameter, data and capacity domains remain required follow-up work.
The source feature catalog is still pending review.
`complete_products` remains empty.
