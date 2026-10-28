# Polygon asset evidence

This directory records the finite scope of issue #32. It does not prove a product milestone.

`payloads/` contains Formora outputs after importing the existing Blender 5.2.3 reference payloads,
saving and querying them through new CLI processes. The test adapter does not generate primitives.
The payload data, including the Suzanne mesh, derive from Blender's GPL-licensed reference data.
See the retained [source attribution](../../../baseline/reference/blender-5.2.3/README.md)
and [GPL text](../../../baseline/reference/blender-5.2.3/GPL-license.txt).
The source inputs remain under `baseline/reference/blender-5.2.3/mesh-primitives/`.
The output report pins each input and result by SHA-256.

The U-shaped native GPU scene is an independently authored test fixture.
Its manifest records pixel probes, commands, binary/source hashes, and failed render behavior.
The first evidence script read a failure from stderr, but the CLI returns JSON on stdout.
That script assertion failed. The corrected capture was rerun in a new directory and is the one stored here.
