# Blender 5.2.3: an unwritten axis for all-axis rotation constraints

Formora issue: [#52](https://github.com/faberline/formora/issues/52).
Human-approved handling: reject the input and preserve the complete scene.
The policy was approved on 2026-10-29. It applies to rotation with
`constraint_axis = [true, true, true]`.

The frozen source is commit `e13b728c6880d3084d9d57c30031ed5df8b39dee`.
The frozen macOS executable has SHA-256
`de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
The original seven cases are `transform_0693`, `transform_0701`,
`transform_0709`, `transform_0717`, `transform_0725`, `transform_0733` and
`transform_0741`. Both original source captures and every earlier product
failure remain in the repository.

## Source cause

`applyRotation` declares `float3 axis_final` without an initializer.
The vector's default constructor is defaulted. Its float storage members
have no initializers. The rotation-axis wrapper invokes the constraint
callback when `CON_APPLY` and `applyRot` are set. That branch does not assign
the axis before the callback.

The callback's axis mask contains bit values 2, 4 and 8. It handles the
six masks with one or two bits. The mask with all three bits is 14. No switch
case assigns the output for that mask. Both axis and object callbacks use
this implementation. The resulting axis is not a defined rotation axis.
An observed coordinate result cannot supply the missing definition.

The frozen native instructions confirm the path. `applyRotation` passes
the local stack address at `sp + 4` to the wrapper without initializing it.
The wrapper branches to the callback with that same output pointer.
Both callbacks return for mask 14 before their axis stores. The complete
relevant instruction ranges are retained in the source-probe evidence.

Relevant frozen files:

- [Rotation caller](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/transform/transform_mode_rotate.cc).
- [Rotation-axis wrapper](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/transform/transform_mode.cc).
- [Constraint callbacks](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/transform/transform_constraints.cc).
- [Constraint flag definitions](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/transform/transform.hh).
- [Vector storage and default constructor](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/blenlib/BLI_math_vector_types.hh).

## Reproducible evidence

Run the initialized-sentinel probe from the repository root:

```sh
python3 tools/undefined_rotation_source_probe.py /private/tmp/formora-rotation-proof-new
```

It refuses an existing output directory. It compiles the unchanged callback
body with minimal dependency declarations. It sets an initialized axis to
`[41, -43, 47]`. All eight callback masks are tested. The six defined
constraint cases copy their expected basis vector. The three-axis mask
preserves the sentinel. The probe never reads uninitialized memory.

The probe forces `CON_APPLY` for every isolated callback invocation. Its
zero-mask result does not make an unconstrained rotation invalid. The real
wrapper uses a separate initialized-axis path when constraints are disabled.
Formora retains that valid all-false input.

`docs/evidence/undefined-rotation/source-probe` contains the source body,
compiler command, binary, output, symbols and native disassembly. Complete
vector-constructor source is retained under `defect-sources`, with its Git
blob and SHA-256. That additional header supports the source review. It was
not a dependency stub or input to the callback probe.

## Formora behavior

Formora returns this exact error before deriving a mesh transform:

```text
mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior
```

It publishes no success receipt. Scene data, revision, saved bytes and undo
history remain unchanged. A batch containing this request rolls back fully.
The restriction appears in the agent schema. All-false, single-axis and
plane rotation masks remain valid. Translation and resize keep their
existing behavior.

The fourteen interface checks for the seven affected source inputs require
that explicit rejection. Their records declare that no numerical match to
the undefined source output is claimed. They remain part of the full suite.
The other 2,392 raw results are unchanged. Position, normal and UV thresholds
remain 1e-6. No other failure receives this policy.
