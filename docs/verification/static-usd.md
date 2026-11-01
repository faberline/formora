# Native static USD gate #86

Incomplete. Candidate builds on unmerged PR #81. Do not close #86 or a milestone.
Contract/input freeze: c5bd012519bf60361e2488b6f57608f32aa79ad7.
First exporter candidate: dd1f4acbecb9e968e70d6e2653e17e6daf637d1a.

Five new pure-memory Rust USD tests passed under actual rustc 1.85.0. All-feature
library clippy passed under actual clippy 0.1.85 after putting that toolchain bin
first on PATH. `rustup run ... cargo clippy` alone selected Homebrew clippy 0.1.96
and failed on an inherited manual_div_ceil warning. That failure is retained here;
no inherited algorithm or lint standard was changed. Default rustc 1.96.1 tests
also passed the first three tests. The initial 1e20 coordinate test failed because
automatic normals overflowed before precision checking; precision checking now
runs before normal generation. Full library tests include a filesystem session
lock test, so the local run was filtered to the five verified memory-only tests.
Full CLI/MCP/regression/filesystem checks run only in CI.

Apple witness: `tools/apple-static-usd/Inspect.swift` compiled with Swift 6.3.3,
Swift language mode 5, SDK 26.5, minimum arm64 macOS14 target. Actual runtime was
macOS26.5.2 build25F84, Apple M1 Max. The independent pre-exporter tetrahedron loaded
through RealityKit.Entity.load(contentsOf:). Its actual mesh buffers, parent
transforms and asymmetric axis lengths match the fixed reference, max error
2.384185791015625e-7 <=1e-6. Its actual process PID78784 was waited to exit0.
Eight actual ARView GPU captures and their camera matrices/digests are retained.
This witness has no authored material. RealityKit returns opaque AnyMaterial and
renders it magenta. It is a geometry/axis witness, NOT a material or four-model
quality pass. Inspect.swift records unavailable material numeric values explicitly;
that cannot satisfy a required authored-material comparison.

First physical attempt PID76909 exited-5: Apple CoreRE asserted no default Metal
device under restricted execution. Second attempt PID77320 exited1 on unsupported
default AnyMaterial. Both receipts are retained. Third attempt ran with physical
GPU access, recorded the unsupported default material as diagnostic, and completed.
The first success does not erase the failures. Original distance-source receipt
native01 PID46068 exit0 and check01 PID77511 exit1 were inspected before this run;
the old source checker failed missing capture/manifest.json. No source process was
restarted and no original sealed input was changed.

First CI static jobs on Linux/Windows failed because the new comparison helper
tried float(Gf.Vec3f). The repair follows the independent expected array shape;
it retains all values and the same tolerance. No product pass is claimed from
that failed run. The new exporter returned real USDA before this helper failure.
All original CI checks remain. Old public reruns41136886204/41136867265 completed
failure on all three platforms; Windows lacked .exe in the normal-query helper,
Linux/macOS failed raw rotation comparisons. Their records are preserved.

Pending: exact-current-head three-platform CI, all four models through CLI/MCP,
Apple authored material/geometry/hierarchy checks, four-model GPU quality review,
capacity three samples each at100k/200k, failure controls and independent acceptance.
Minimum OS compile evidence does not mean execution on macOS14 or iOS17 hardware.
