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

## Candidate c1f0f87 follow-up

Linux run41301056657/job124831867208 passed the frozen normal arithmetic witness,
all four revision3 model flows through CLI and official MCP, and the signed-matrix/
UV/corner-normal/face-material fixture on both interfaces. Its transfer bundle
4eec3251d84d08d1ea1409f4660d737bdcd7f52d51c24df3e015ba976d419114 retains raw native
scene UTF-8 as well as USD. All eight source/output digests match the CI manifest.
Windows also reached the capacity step. Hosted macOS compiled the consumer with
minimum macOS14 target and checked iOS17 API availability, then reached capacity.
These observations do not make a failing whole job pass.

Actual RealityKit reruns on the four corrected files all exited0 (PIDs5557,5699,
5888,6041). Complete oriented triangles, numeric material values, semantic parents,
Y-up conversion and whole-bounds bottom-centre pivot now pass1e-6. Actual reports
are bound to waited process PIDs and input digests. The five actually loaded Apple
corruptions were rejected again. Native Formora Metal reruns used byte-exact CI
mother files. Of64 captured views,56 are byte-identical to the previously directly
inspected images. The other8 were viewed directly. The review record retains each
digest and method. This is finite controller QA, not independent final acceptance.

All six Linux capacity samples failed speed while full content comparison passed.
100k core:1.149103052,1.170461662,1.208502211 seconds (limit0.25s).
100k full pipeline:3.522837498,3.396361995,3.438243432 seconds (limit2s).
200k core:2.392929971,2.256033950,2.317162971 seconds (limit0.5s).
200k full pipeline:6.838689525,6.708970614,6.727934908 seconds (limit4s).
All raw failures and records remain under candidate-c1f0f87. The next optimization
keeps Scene::validate inside the core clock. Flat faces do not use smoothing fans
or derived edge IDs; a private validated-flat resolver uses the same existing f32
normal functions and explicit-normal precedence. An exact-value memory test checks
it against the unchanged full resolver on frozen triangle/polygon fixtures,
including loose geometry, degenerate faces and explicit normals. Smooth faces
fall back to the full resolver. The export's sets/index lookups use hash tables;
serialization order still comes from the source BTreeMaps. Deterministic bytes
remain checked. Full capacity comparisons use array operations for every element;
they do not sample or omit data, change tolerance, or move validation out of clocks.
The first optimization is unmeasured until the next actual CI sample.

The retained first Linux contract run dd1f4ac ended with122 rotation failures in
4992 checks. The first is rotation_snap_0097 world_vertices/v000026/y:
source -6.924999713897705 versus Rust -6.92500114440918. This is an inherited
cross-platform numerical defect, not a new accepted source exception. The next
bounded diagnostic retains the full actual failed state for cases97/99/139 and
the first affected range. It is explicitly not full acceptance. The full4992-check
commands and1e-6 limit remain. No rotating matrix algorithm was changed on a guess.

## Frozen cross-platform trig correction

The bounded Linux diagnostic (run41302871368/job124837267656) reproduced exactly
three failures among53 selected CLI cases:97,99,139. Its complete actual states
are frozen under baseline/static-usd-rotation-diagnostic. For97/99 the evaluated
cursor matrices are byte-equivalent numeric values to the source-backed passing
ARM records, but one assigned Euler channel is1.570796251296997 instead of the
Blender source's1.5707963705062866. Case139 has the same cursor matrix too, but
its third assigned Euler channel differs by one f32 step. The original source
fixture SHA-256 and exact expected channel bits were frozen at42c814170 before
implementation. No source exception or tolerance was added.

The Euler conversion now evaluates atan2 on the same input f32 values in f64,
then quantizes once to f32. It keeps the same branch/normalization/lock rules and
stored channel format. A pure-memory gimbal helper test passes the frozen bits
3fc90fdb/bfc90fdb/00000000, including nearby atan2 boundaries. This preserves the
source on ARM; actual Linux diagnosis and full three-platform regression must
still qualify the correction. No whole-suite pass is claimed from this unit test.

All CI checkouts now select the exact PR head SHA. The new static-USD workflow
runs on the PR event once per update to avoid duplicate identical work; original
full-contract push/PR triggers and every required test command remain. Capacity
runs even when an earlier independent new check fails, so a failure still leaves
speed evidence. Earlier failed steps keep the whole job red. No continue-on-error
was introduced. The rejection helper's expected missing-asset message was fixed
to the existing Scene validator's exact wording; the product error did not change.

## Candidate 748f0ac measurements

Run41304474636: Linux job124841939567 and Windows job124841939449 passed all
four editable-model CLI/MCP flows, attribute checks and rejection controls. Both
jobs FAILED capacity speed. Every capacity sample passed full content comparison.
The four exported model byte digests still exactly match candidate-c1f0f87, whose
actual Apple/GPU evidence is archived separately with its own binary provenance.
Linux core100k:0.602045377,0.621301165,0.621221043s; pipeline100k:
3.006418972,2.712679357,2.498783856s. Linux core200k:
1.181101870,1.178840053,1.125763959s; pipeline200k:
4.999736062,4.993146061,4.751715020s.
Windows core100k:0.867343600,0.809427600,0.787358900s; pipeline100k:
3.516000000,3.094000000,3.063000000s. Windows core200k:
1.616188400,1.553710800,1.569625700s; pipeline200k:
6.719000000,5.985000000,6.047000000s.
Limits remain0.25/2s per100k and0.5/4s per200k. No timing pass is claimed.

The Linux diagnostic job124841939464 passed all53 selected CLI rotation probes.
This is diagnosis only. It cannot replace the full4992-check source suite or
current-head three-platform checks. Complete decoded logs are gzip archived in
candidate-748f0ac, with uncompressed byte counts and SHA-256 in its manifest.

Eleven superseded runs created by this issue86 branch AFTER task admission were
explicitly cancelled to free CI slots. The audit retains every run/job snapshot,
cancel request and completed/cancelled readback under own-superseded-ci-cleanup.
All cancelled, skipped or unrun checks remain NONPASSING. Original pre-task runs,
the two public reruns41136886204/41136867265 and source workloads were excluded.
No completed run or log was deleted. The three current748 runs were retained.

The next candidate streams arrays into one string buffer, reuses faces within
the immutable validated projection, and uses hash lookups for flat-normal input
positions and resolved face normals. Bit-identical adjacent normal text can be
reused; signed zero is distinguished. Output ordering and complete validation
remain unchanged. Diagnostic phase times remain inside the original complete
core clock and do not define separate pass criteria. Runner metadata is recorded
outside the clocks. Capacity is unmeasured until fresh CI.

Added CI coverage uses the existing frozen concave-polygon fixture on BOTH
interfaces: reject its loose/isolated components without creating output, then
explicitly edit the native asset and preserve its eight corners, normal payload,
two UV layers and IDs. It also checks UTF-8/escaped names and an unrelated camera
sibling outside the selected subtree. These additions have only syntax checks
locally; functional execution remains CI-only. No original fixture was changed.
