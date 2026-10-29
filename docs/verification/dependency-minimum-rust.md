# Actual Rust 1.85 checks for pending dependencies

The [audit manifest](../evidence/dependency-minimum-rust/manifest.json) records four exact candidates.
Each candidate was checked in a clean worktree.
The driver pins the compiler and documentation compiler by absolute path.
It puts the same toolchain directory first in PATH.
It rejects versions other than Rust 1.85.0, Cargo 1.85.0, Clippy 0.1.85 and rustfmt 1.8.0-stable.
The retained compiler cache also identifies Rust 1.85.0.

These records replace the earlier local minimum-version qualification.
The earlier command form could resolve Homebrew child tools despite `rustup run 1.85.0`.
Its observed compiler cache identified Rust 1.96.1.
The old functional captures remain historical evidence.
They do not establish minimum-version compatibility.

| PR | Exact candidate | Rust tests | Python tests | Additional local checks |
|---|---|---:|---:|---|
| #33 | `554e2f9eb6d164b144f492ca49b4f13cfbdfe03c` | 79 | 32 | 57 payload round trips, two fixed asset performance samples, Metal concave-face and failed-output protection |
| #35 | `92b4746e80a007e26f47d09362df45eda98d3179` | 85 | 33 | 54 CLI/MCP generation comparisons, 57 payload round trips, fixed performance samples, four Metal shapes, four isolated unseen inputs |
| #37 | `a2131e0ebffadae192643dc54dfaae1c5199eb0c` | 90 | 33 | 138 CLI/MCP generation comparisons, 57 payload round trips, fixed performance samples, four Metal shapes, eight isolated unseen inputs |
| #39 | `8628d7b07cfad626cb8d9db46f520f25cee1e3b2` | 71 | 46 | 530 recorded selection pairs, 152 independent predicates per capture, 530 authored initial-state checks per capture |

Format, Clippy with all features and targets, full Rust tests, full Python tests,
the all-feature build and the official MCP regression passed for every row.
Test counts are checked against the fixed expectation for each candidate.
No failed, skipped or unrun test is counted as passed.
The #39 selection check verifies recorded source data. It does not execute product selection.

All original geometry checks and numeric limits remain unchanged.
The 1e-6 geometry limit remains fixed.
The release performance examples retain their original hardware samples and limits.
Native rendering used Apple M1 Max through Metal.
Each native capture records its exact executable, shader, requests, source and image hashes.
The generation isolation checks denied every repository read to the copied executable.
Their control read of a real source fixture failed as required.

## Compatibility repair and dependency history

Actual Rust 1.85 Clippy rejected the old cube UV comparison chain.
Commit `92b4746` replaces that chain with an equivalent ordered match.
The conditions and UV values are unchanged.
The fixed primitive comparisons passed after the change.

PR #37 now contains that repair through merge commit `a2131e0`.
PR #41 contains the updated dependency history through merge commit `357f1d5`.
Every product source hash still matches the published selection evidence.
There is no product source diff from PR #41 candidate `a6c3f4e` after that dependency merge.
The existing 1,060 selection results therefore retain their source qualification.
The four dependency audits do not replace selection tests or integrated acceptance.

## Evidence locations

Each `prNN/local/` directory contains the raw commands, stdout, stderr,
compiler cache, executable hash, tracked input hashes and generated comparison data.
Each available `prNN/gpu/` directory contains the native captures and their manifest.
The isolation reports retain actual requests and output checks.
Each `prNN/ci-unrun.json` contains the exact-head Actions runs, jobs and annotations.
All files are pinned by the top-level audit manifest.

The retained driver can reproduce the local checks from the exact candidate:

```sh
python3 docs/evidence/dependency-minimum-rust/audit.py /absolute/repository /absolute/rust-1.85-toolchain/bin /absolute/target /absolute/new-output --pr 35 --head 92b4746e80a007e26f47d09362df45eda98d3179
```

Install `tools/requirements-mcp.txt` before SDK checks.
Use a clean checkout of the requested commit.
The driver refuses a different HEAD or a dirty worktree.
Use the original native capture tools for that commit after the build.
The compiler paths must also remain pinned for release performance builds.

## Gates that remain open

The strict baseline check exits 2 for each candidate.
That expected exit confirms an incomplete baseline. It is not a product pass.
The two exact-head Actions runs for each PR contain six jobs with empty step lists.
All 24 jobs were refused because of GitHub account billing or spending limits.
No CI test ran. No rerun was requested during this audit.

The account administrator must resolve Billing & plans before those required checks can run.
All required three-platform CI, dependency integration and independent acceptance remain open.
Issues #32, #34, #36 and #38 remain open under `agy:done` for that acceptance.
All 11 milestones retain their full scope and remain open.
