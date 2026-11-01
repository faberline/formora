# Failed candidate f22e3e86c

This candidate did not pass. The complete decoded logs are stored as gzip files.
The manifests record their byte counts and SHA-256 hashes.

The Intel Mac full contract job stopped at the memory replay. Both the focused
17-case replay and the full 2,496-case replay had 78 world-coordinate violations.
The full replay checked 1,617,408 components against both sealed Blender captures.
The separate Intel CLI diagnostic also failed cases 921 and 923.
Its 73 probes are a diagnostic subset, not the full contract.

The scalar source control and the actual differences were frozen in
`baseline/static-usd-macos-axis-angle/acos-diagnostic.json` before the arithmetic
repair. The input quaternion has an exact matrix-to-quaternion scalar of 0.5.
Both native source captures require half-angle bits `0x3f860a92`.
The failed Intel result had bits `0x3f860a91`. All printed paired, separate and
wider sine/cosine probes agreed at the failed angles.

All four capacity jobs failed. The first initialization set a work limit of one.
Later executor workers reported a limit of four and failed the profile assertion.
Linux, Windows and ARM Mac passed only their first capacity sample. Intel Mac
passed no sample: its first 100k sample also exceeded the unchanged two-second
pipeline limit at 2.156925538 seconds. An assertion repair alone does not prove
that this cold sample will pass. No failed sample is counted as a pass.

The source inputs, source exceptions, coordinate tolerance, workload, timing
boundaries, timing limits and six required samples remain unchanged.
Skipped model steps after the Intel replay failure remain unrun.
