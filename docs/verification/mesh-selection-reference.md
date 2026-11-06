# Mesh selection reference baseline

Scope: [issue #38](https://github.com/faberline/formora/issues/38), part of #14 and milestone 0.0.
This change adds ten pending contracts for later 0.2 implementation.
It does not implement or accept Formora selection.

## Fixed source and coverage

The reference remains Blender 5.2.3 LTS, build `e13b728c6880`, with the existing executable digest.
The official manual family remains 5.2.

- [Select All by Trait](https://docs.blender.org/manual/en/5.2/modeling/meshes/selecting/all_by_trait.html):
  non-manifold selection, loose geometry, interior faces, faces by sides, poles and ungrouped vertices.
- [Selection introduction](https://docs.blender.org/manual/en/5.2/modeling/meshes/selecting/introduction.html):
  ordinary mode conversion, combined modes, expansion and contraction.

Complete HTML bytes are retained under `baseline/sources/`.
Their Blender contributor attribution and CC BY-SA 4.0 notices remain intact.
Ten existing source entries now refer to individual contracts.
The introduction page itself stays pending because its other tools remain uncovered.
All 9,047 original source IDs, old artifact pins, exclusions and product versions remain unchanged.
Both full inventory flags remain incomplete.
The catalog has 23 pending features. Pending sources fall from 9,036 to 9,026.
These counts describe registration, not product completion.

## Inputs and real reference results

The initial matrix and comparison constraints were committed as `5bb8056` before the adapter.
Explicit reference probes then identified unchanged mode requests.
The [final contract](../contracts/mesh-selection-baseline.md) records them separately from rejections.
No requests were dropped from the 530-run matrix.

The fixture has 52 vertices, 70 edges and 34 faces. It includes manifold and non-manifold parts,
an internal face, isolated parts, inconsistent winding, hidden geometry and coincident vertices
with distinct IDs. It also has two UV layers, two material slots, seams, smoothing and weights.
Custom integer attributes retain the authored logical IDs. Coordinates do not determine identity.

Both complete captures and the comparison are retained:

- [First manifest](../../baseline/reference/blender-5.2.3/mesh-selection/manifest.json).
- [Second manifest](../../baseline/reference/blender-5.2.3/mesh-selection-repeat/manifest.json).
- [Reproduction report](../../baseline/reference/blender-5.2.3/mesh-selection-reproduction.json).

Both fresh processes executed all 530 requests. Their IDs, UTC start times, launch arguments,
executable digests, input digests and adapter digests are recorded.
All per-run results reproduce exactly. The process manifests remain distinct.
Each run records before/after geometry, UVs, materials, seams, weights, hidden IDs,
selected IDs, mode mask, ordered history, active face and operation result.
UV layer order is explicit, so the active index has an unambiguous meaning.
Every initial state is also checked directly against authored JSON, including UVs and weights.

| Reference result | Count | Meaning |
| --- | ---: | --- |
| FINISHED | 480 | Operation completed; selection can still be empty |
| CANCELLED | 30 | Mode request makes no change; the entire state stays equal |
| POLL_REJECTED | 20 | Invalid domain or missing weights; the entire state stays equal |

Sixteen rejections use edge/face mode for the vertex-only ungrouped operation.
Four use vertex mode with absent or empty groups. Zero weight remains distinct from missing membership.
Unexpected errors fail the batch. Failed batches publish no partial reference directory.
The launcher uses `--python-exit-code 1` to make script errors fail the process.

## Independent verification

Each capture also passes 152 independent predicates. These use the authored topology to check
mode masks, face sides, vertex degree, loose parts and four edge-use classifications.
They do not invoke the reference operator. The other cases still require full-state reproduction.
The 152 checks do not imply that every case has a separate mathematical oracle.

Mutation tests reject wrong IDs even when counts match. They also reject changed positions,
edge endpoints, winding, UV corners, materials, seams, hidden flags, weights, mode, history,
active faces and outcomes. Duplicate JSON keys, missing runs and wrong input digests fail.
A self-consistent fake face selection also fails its independent predicate.

An initial authoring test found tuples in memory where JSON has arrays.
The builder now returns arrays. Existing input bytes and reference results did not change.
A result-schema review also added rejection of unknown statuses with null outcomes.
The final tests pass both checks.

## Local checks and open gates

This branch starts from main `5761e68`. It is independent of pending PRs #33, #35 and #37.
It does not remove their work. Integration must retain every required CI step.
On macOS arm64 with Rust 1.85.0, format, Clippy, 71 Rust tests and 46 Python tests passed.
The existing official MCP regression passed.
The baseline checker reports structurally valid data with zero problems.
Strict mode still exits 2 because full review remains incomplete.
See the [local record](../evidence/mesh-selection-baseline/local-checks.json).

The new CI step compares recorded reference results. It does not run product selection.
Required three-platform CI, integration and independent acceptance remain open.
Earlier Actions jobs could not start because of GitHub account billing limits.

Product selection, persistence, undo, preview, performance and three-platform product execution remain unrun.
Full numeric domains, larger capacity, multi-object and other selection functions retain their original scope.
No feature or milestone is accepted by this finite reference suite.
