# Multi-data source work

Issue #77. Native execution is unrun. No product extension is implemented.

The authoring drafts contain 13,440 context rows and three independently
specified mesh assets. Counts and rows are inputs, not passed test cases.
The capture adapter and independent checker are still required.

`tools/generate_multi_mesh_merge_cases.py` builds the fixture without reading
native captures or product results. `authoring-drafts/` preserves the earlier
context-only and full-data drafts and the pinned source-reading notes.
The final fixture removes temporary readiness markers; execution status
belongs in separate capture manifests and terminal receipts.

Follow `docs/contracts/mesh-merge-multi-data-baseline.md`.
Do not change the existing 1,024-case baseline or claim complete feature,
issue, CI, integration or milestone acceptance from this authoring step.
