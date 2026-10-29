# Procedural generation evidence

These results cover the finite component scope of issue #34. They do not prove full feature or milestone acceptance.

`cases/` contains Rust-generated geometry queried through real CLI and official MCP processes.
The adapter sends primitive parameters, not reference geometry. It uses the retained Blender 5.2.3 data only for comparison.
The original reference data and attribution remain under `baseline/reference/blender-5.2.3/`.

There are 20 original primitive cases and seven boundary geometry subchecks per interface.
The boundary data came from context cases, but no selection or creation-origin claims are copied into the candidates.
Full context acceptance remains unrun. Undefined source UV components remain explicitly marked, not called zero numeric error.

The independent-runtime report records a macOS sandbox that denied all source repository reads.
A denial control confirmed that even a reference fixture could not be read.
A copied binary generated four shapes with parameters not present in the reference corpus.

The native Metal record checks every shape before and after parameter changes, and compares a new-process reload.
The first individual cube-growth probe hit the neighboring plane. That assertion failed and is not accepted evidence.
The probe was moved above that plane and the full capture reran without changing its assertions.
