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
macOS job124841939280 also passed every four-model/attribute/rejection stage and
FAILED speed with all content comparisons passing. Core100k:
0.990737229,0.996916540,1.037603198s; pipeline100k:
4.859936158,4.135733809,4.029481645s. Core200k:
2.010822300,2.142661951,2.050301894s; pipeline200k:
8.032487012,8.526337768,8.014650010s. Its complete log and digest are also archived.
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

## Candidate 3739abe and the next repair

Linux static job124848530964 in run41306725508 passed the entire new gate,
including both concave-polygon interfaces and all six capacity samples.
Core100k:0.194760426,0.200629028,0.198621060s; pipeline100k:
1.725147736,1.503380839,1.497608275s. Core200k:
0.455053676,0.403875342,0.407471900s; pipeline200k:
3.088072533,3.030057990,2.995378536s. All model USD byte digests remain identical
to the actual Apple-tested c1 files. This is Linux evidence, not three-platform
acceptance. Complete log, six samples and model hashes are archived.

Windows job124848531123 passed every model/attribute/rejection stage but FAILED
all six speed samples while all full content comparisons passed. Core100k:
0.337948200,0.331343700,0.326717500s; pipeline100k:
3.062,2.813,2.812s. Core200k:0.673272000,0.699411400,0.658301000s;
pipeline200k:5.516,6.047,5.468s. Its complete log and samples are archived too.
The next repair keeps the same work and limits. It borrows face/UV slices,
uses membership hashes during complete mesh validation, and avoids a temporary
owned JSON value tree when a fresh CLI process reads the complete native scene.
Both CLI serialization and the MCP value query share the same full-read builder.
Filtered reads keep their existing validation and errors. A memory-only test
checks complete scene values, revision, filtered errors and an independent cursor
matrix. Diagnostic export/reopen/compare phase times stay inside the full clock.

The fast float formatter is the same locked zmij1.0.23 already used by serde_json.
The first scalar differential test failed at f32 bits48a951a4: zmij printed
346765.12 while Display printed346765.13. Both round-trip, but byte preservation
still matters. Exact decimal-halfway values and exponent spellings therefore
retain Display. The unchanged differential test, with the first failure explicitly
retained, now passes over4000 finite patterns across the f32 range plus boundary cases.
All seven memory-only USD tests and the full-read helper test pass on Rust1.85.

Contract review found a gap: the frozen v1 text requires control-byte escaping,
but the first implementation rejected all control characters. This is a product
defect, not a reason to narrow the contract. Additive reference/source bytes were
frozen at25a3c2beb612a7e3525ef0c30644c6d03e51c087 BEFORE its repair. They use the
same2095faf OpenUSD pin: string grammar, Quote and TfEscapeStringReplaceChar.
Two-digit hex escapes preserve ASCII controls, including NUL and following text;
quote/backslash escaping and multibyte UTF-8 remain exact. Both-interface CI now
requires the actual OpenUSD-parsed name to equal the frozen input containing all
ASCII controls, DEL, C1 characters, Chinese and an emoji. Local memory helpers
check lexical bytes only; actual OpenUSD acceptance remains unrun until new CI.

No source numeric rule, original sealed input, sample, threshold or full-regression
command changed. New capacity/current-head CI and independent acceptance remain
required. These repairs do not establish release or milestone acceptance.

Full Linux contract job124841939518, run41304474642 at748f0ac, completed FAILURE:
50 failed CLI/MCP records out of4992 checks. The first is rotation_snap_0037,
world vertex v000026/y: -8.879652976989746 versus -8.879651069641113. Thus the
53-probe diagnostic success did not establish the full trig correction. The
complete decoded log/digest and the actual first20 failure records are retained.
The bounded diagnostic now includes these20 IDs alongside the previous53 and
prints the actual first three failed states. It remains diagnosis, not acceptance.
No further rotation algorithm change is made before obtaining that actual state.

## Portable scalar repair and further allocation reduction

Run41308623799/job124854140435 reproduced20 failures among73 selected CLI
probes and retained full actual states37/39/205. Source-backed target Euler values
in37 are[-0.15624983608722687,-0.14847351610660553,0.06427420675754547]; the
rounded f64 attempt produced[-0.15624982118606567,-0.14847350120544434,...]. A
memory-only scene/matrix helper reproduced this failure on Apple M1 Max too.
The native host atan2f returned the frozen source values for these scalar inputs;
the rounded f64 function did not. This failure is not a tolerance exception.

Apple's published Libm approximation at17a5f9daa3f5679f7536b26f133b40cc078753c3
also reproduces those scalar values. Its source bytes, exact coefficient bits,
independent Blender expected values and actual failed states were frozen separately
atc62742a83c49693d074ba3df5e91a9cf02778500 BEFORE replacing the f64 attempt.
The new Rust function uses the fixed factored polynomial and quadrant rules,
including signed zero, followed by one f32 conversion. It calls neither host
atan2f nor host f64 atan2. It has no case-ID branches or fitted product references.
The source pin is evidence for a published approximation, not proof of the
current macOS26 library's build identity; the pinned ARM source file is empty.
Three memory-only tests now pass: scalar pairs/quadrants/signed zero, old source97
gimbal bits, and complete source Euler channels in37/39/205. Actual73-probe and
full4992 three-platform checks remain required; no whole-suite pass is claimed.

The complete logs and all capacity samples for3739 macOS, f1 Linux/Windows and
0e50 Linux/Windows are archived separately. All content comparisons passed.
f1 Linux passed5 of6 samples: one100k core took250082524ns, above250000000ns.
That sample and whole-job failure remain. 0e50 Linux passed all6 at the same
product code; Windows still failed speed. macOS3739 failed every sample, with
substantial host-time variation. No failed sample is discarded as noise or averaged
away. Existing limits, three samples and complete clocks remain unchanged.

Further optimization streams valid ASCII ID arrays without per-ID string copies.
The immutable flat resolver evaluates every face using the same existing f32
normal functions and precedence, borrowing explicit corner data and using stack
storage for triangles. It no longer owns per-face ID/corner copies or a second
flat normal lookup table. The unchanged differential helper still compares every
normal against the full resolver on the frozen fixtures. Smooth faces retain the
full resolver. The diagnostic normal_setup phase now measures setup only; per-face
flat arithmetic stays in mesh_write, inside the unchanged complete core clock.

Typed JSON map reads retain duplicate rejection and sorted data while avoiding a
redundant key clone. The capacity comparator uses full native Vt string-array
equality and gathers every authored corner with its independent source indices.
It still checks every ID, corner, normal, point, material and transform. It never
uses exported points to create the expected normals. None of that validation
moves outside the clocks. Release builds use thin LTO and one codegen unit, with
optimized memory helpers added to CI. Runtime capacity still requires real samples.
The12 selected memory-only helpers also passed locally under the actual Rust1.85
optimized release profile on Apple M1 Max (7 USD,1 flat-normal differential,1 read,
3 rotation). This is not a CLI/MCP, capacity, GPU or whole-product acceptance run.

Four additional superseded own full-contract runs were cancelled after readbacks
confirmed current0e50 head. The full before/request/final-cancelled records are in
candidate-0e50f407/own-superseded-ci-cleanup-02.json.gz with its digest and readable
four-run manifest. All4 final states were independently reread completed/cancelled.
Together with cleanup01,15 own obsolete runs were cancelled. All remain NONPASSING.
Original pre-task/public runs, retained748 cross-platform evidence, f1 static
capacity jobs and current0e50 jobs were excluded. No CI log was deleted.

## Candidate c340be9a9: two static CI passes, macOS speed failure

Run41311306246/jobs124862094400 (Linux) and124862094180 (Windows) passed the
entire static gate: all four CLI/MCP model flows, attribute/name/polygon cases,
negative controls,12 optimized memory helpers and all6 capacity samples per OS.
The73-case Linux diagnostic job124862094356 passed with zero failures. In the
full contract run41311306212, Linux's entire raw rotation step completed SUCCESS
at2026-11-01T14:20:31Z and proceeded to nonidentity delta tests. The full job was
still running at capture; no whole-job or three-platform acceptance is claimed.

macOS static job124862094433 passed every content check and12 optimized helpers,
but FAILED all6 combined timing samples. Core100k:
259806821,281714684,206710813ns; pipeline100k:
5718785204,3705526765,2276011547ns. Core200k:
436657134,518855779,433810451ns; pipeline200k:
5525377493,7676356628,5255962912ns. Every complete content comparison passed.
No cold sample is discarded, exempted or averaged away. Complete decoded logs,
all sample records and their hashes are retained under candidate-c340be9a9.

Fresh physical evidence uses the c340 Rust1.85 preview binary, SHA-256
b9e814844bbd8a2297cba69f444bf2fffed65532366dc471de56499aa75580d6,
on actual macOS26.5.2/Apple M1 Max. Its32 native renders and4 Apple load/capture
processes were actually waited to exit0. Every model passed actual Apple numeric
geometry, material, semantic hierarchy, axis and bottom-centre checks. All64 PNGs
are byte-identical to the separately inspected c1 images. The new identity,36
process receipts, raw Apple reports and every frame digest are archived; the
committed-image-reference list maps each exact model/engine/view to existing
committed PNG bytes and its review entry. This is finite controller QA, not
independent or whole-product acceptance. No local authoring/export/capacity CLI
test was run; the local CLI exception was physical render only.

Cleanup03 requested cancellation only for six superseded own candidate runs.
Four old full-contract runs actually cancelled; two static runs had already
completed failure and were retained. All6 final states were independently reread.
The archived full before/request/final records and manifest show19 total own
obsolete cancellations across the three cleanups. Original pre-task/public runs
and currentc340 were excluded. Cancelled, skipped and unrun checks never pass.

The next projection uses one source vertex-index table and one complete dense
corner array for used-vertex checks, USD indices and normal lookups. It retains
all original IDs, topology, arithmetic and full scene validation. The CLI's saved
file wrapper decodes once and then calls the same export core as MCP. Complete
Scene::validate stays inside project/core and before any output; only its identical
extra pre-core call is removed. Scene::load for other commands remains unchanged.
The seven USD memory tests and flat-normal differential pass in debug and release.

Verifier JSON inputs and official orjson3.13.0 CPython3.12 wheel digests were frozen
ataaf61de5838e751d185248f0a18c59b1ea93277d before changing its decoder. The
verifier captures complete raw pipe bytes and parses the complete native reply
without a redundant Unicode decode/encode cycle. The independent source-input
interpreter still uses standard json. The new CI corpus requires identical values,
types and f64 bits, including signed zero, u64 maximum, UTF-8 and escaped controls;
it also rejects malformed/nonfinite/invalid UTF-8 input. Only prebuilt wheels are
used; the native Rust toolchain remains1.85. These Python changes have syntax
checks locally; actual equivalence and full functional runs are CI-only.

OpenUSD and NumPy imports remain INSIDE the original pipeline clock. New diagnostic
import/Stage.Open times do not subtract anything from that clock or change pass
criteria. No data check moves outside it. All6 samples,250/500ms core limits and
2000/4000ms full pipeline limits remain. This next optimization is unmeasured until
new current-head CI. All failed and still-unrun required gates remain incomplete.

## Candidate 17b83893c: complete content passes, Intel macOS speed failure

Static run41317842134 passed its entire Linux job124881570328 and Windows
job124881570531. Both passed the independent JSON value/type/f64-bit corpus,
all four CLI/MCP model flows, attributes/polygons/control names, negative controls,
12 optimized memory helpers and all6 fixed capacity samples. Linux100k core:
91605864,88903980,97182428ns; pipeline:1077614000,896938792,855787775ns.
Linux200k core:179507861,180403295,194701997ns; pipeline:
1630740043,1634667817,1649882144ns. Windows100k core:
136573600,130448700,130783400ns; pipeline:1953000000,1719000000,1734000000ns.
Windows200k core:285809300,253982200,257595000ns; pipeline:
3422000000,3250000000,3359000000ns. All8 model/source digests exactly match
the c340 physical evidence. No current binary is claimed as that physical binary.

Intel macOS job124881570484 passed every content/negative/helper stage, then
FAILED all6 combined speed samples. Core100k:266977977,416995239,209761145ns;
pipeline100k:8930316235,4554596099,3137341260ns. Core200k:
2282079366,601119543,350286488ns; pipeline200k:
8761226519,5341542325,7691785431ns. Every data comparison passed. First sample
OpenUSD import alone took2359956811ns, stage open1370889514ns and NumPy import
665535680ns. These times remain inside the unchanged2000000000ns total limit.
They are not exemptions. Host contention, memory pressure or a library startup
cause is not established from wall time alone.

Complete logs, every sample and model digest are archived in candidate-17b83893c.
Also archived are older c340 full-contract Linux/Windows SUCCESS jobs124862094136
and124862094079, including4992 raw rotations and3584 nonidentity-delta checks
per platform. c340 macOS and exact17b full-contract jobs remain running at capture.
They are not passes. No additional CI was cancelled.

The next verifier releases each complete reopened scene only AFTER full equality,
inside the existing pipeline clock. Previously it kept the large decoded query
alive during USD parsing and the next native export. Every original comparison
still runs. CPU totals and cumulative peak RSS are diagnostic, not new criteria;
Windows reports unavailable resource diagnostics explicitly. Per-module USD import
times refine the existing aggregate without prewarming or subtracting any time.
Only Python syntax checks ran locally; actual behavior remains CI-only.

Add macos-15 Apple Silicon alongside the existing macos-15-intel job. The official
runner labels/hardware are recorded in baseline/static-usd-host-diagnostic.json.
This adds the architecture used by the actual physical evidence. Intel remains
required, with all original commands and limits. The new job has the same complete
checks and all6 samples; a Silicon pass cannot cancel an Intel failure. Apple
minimum target stays macOS14/iOS17, compiled for the actual runner architecture.
Neither hardware choice, unrun checks nor resource diagnostics can pass this gate.
