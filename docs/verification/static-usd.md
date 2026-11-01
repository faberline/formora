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

## Candidate be5f67 follow-up

All three static USD CI jobs actually passed the four-model CLI/MCP stage before
failing the capacity comparison. Run41299157370 jobs124826300894 (macOS),
124826301018 (Windows),124826301082 (Linux). Each stage checked complete native
scene equality, deterministic USD bytes between CLI and official MCP, geometry,
material bindings/numeric values and hierarchy, plus semantic corruption controls.
This is not whole-job success. The log transfer bundle SHA-256 was
63ee322ec69fa266ee2488cf010e112cb8b72217499e4c1a5ea23a062dffadad.
All four downloaded USD byte digests exactly match the CLI/MCP CI manifests.
The transfer reconstructed mother JSON from complete objects, so its field order
and byte digest differ from the original native save. No byte-identity claim is
made for those transferred mother files. Subsequent bundles also retain the raw
saved UTF-8 to permit an exact byte comparison.

Actual RealityKit load and ARView captures for all four models completed with
exit0 on Apple M1 Max/macOS26.5.2. Actual PhysicallyBasedMaterial properties,
oriented triangle corners and semantic parents matched. Each model has eight
RealityKit views and eight Formora Metal views, all64 inspected by the controller.
The first two Formora capture rounds were dark; they remain archived. The third
uses proper existing light-intensity units and shows the material roles/surfaces.
No Blender process or upstream exporter made these assets.

The additional whole-bounds pivot check correctly FAILED the first rock/radio
assets. Rock's edited vertex changes its whole XY centre to x=0.0075m. Radio's
front detail changes its whole centre to y=-0.00625m. These are authoring defects,
not acceptable pivot exceptions. The original data and Apple failing comparisons
remain under candidate-be5f67. Additive native set_transform recipes were frozen
separately at44dd937d7cce7ff5768963cb5834f799f16ea64f before wiring the corrected
recipe flow. They move every affected part by the independently calculated offset.
The exporter does not recentre or change geometry. The corrected assets must pass
actual CI and Apple loading again. The initial create/edit fixtures are unchanged.

Actual Apple corruption controls loaded all five wrong files successfully, then
rejected wrong axis, wrong units, wrong material, missing geometry and wrong parent.
Loader failure alone was not used as semantic detection evidence. Original
geometry/material matches do not cancel the newly exposed pivot failures.

The capacity comparison's first numerical failure was reproduced from authored
triangle104 alone: (104,0,0.06),(105,0,0),(104,1,0.05). Independent IEEE f32 sequential
Newell gives y=0.009982731193304062, exactly the CI output. Independent f64 cross
gives y=0.009981551179720135; their difference is1.1800135839273168e-6. The pre-code
contract fixes the existing preview's f32 normal resolution. The initial comparator
incorrectly applied f64 cross to that capacity payload. The correction implements
the frozen input-only f32 arithmetic with NumPy, including each rounding step;
it does not read product output as a reference. Both old values, the failed run
and the unchanged1e-6 tolerance remain. Capacity timing has NOT passed. Every
sample now records validation failure and actual timings before reporting failure.
Full validation stays inside the same clocks; no sample count, workload or limit
was reduced. Normal reference arithmetic is checked separately from product speed.

The first new Windows full-contract run got beyond the normal helper, then failed
when remaining_scale_regression hashed the path without .exe. The same entry-point
error exists in the later required runtime drivers. They now resolve the actual
executable before running or hashing it. All original commands and comparisons
remain, and raw rotation errors are printed early as well as retained in reports.
