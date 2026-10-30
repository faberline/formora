# Primitive regeneration in an active edit context

The real recipe proof at Rust implementation 224a4360 reached a successful
merge, undo and replay. Regeneration then failed with:
`edit objects require persistent mesh editing state`.
The native CLI server returned this error at call 27 and later exited zero.
The proof controller exited one. This is a failed required gate.

Freeze these rules before changing product code:

- Regeneration must work while any edit object uses the target shared asset.
  Keep all entities, shared asset identity and the entire object context.
- Generate fresh geometry and attributes from the retained or new primitive.
  Preserve the creation frame and the existing generator rules.
- For an asset still used by an edit object, keep its prior selection modes
  and preview setting. Give the new geometry empty selected and hidden sets,
  empty history and no active face. Old component IDs must not leak into it.
- If no edit object uses the asset, keep the existing fresh-generation result
  exactly. Do not add an editing record in that case.
- Keep the recipe unedited after successful regeneration. A later real merge
  must mark it edited. Empty merge operations must not mark it edited.
- Failure, including a late batch error or bad budget, must preserve the scene,
  revision and undo stack. Undo and replay must restore real mesh data.
- Cover all ten existing generators, all three selection modes, both preview
  settings, a shared user that is the only active edit object, changed primitive
  parameters, actual CLI/MCP, save and fresh reload.
- Retain the original numeric and performance limits. Re-run all required
  prior gates on the repaired build. Failed or unrun checks cannot pass.

The first recipe controller also had a setup error before any merge.
It selected an edit object before creating editing state.
That failed controller and trace remain separate.
The second controller fixed only that setup and saved raw calls and terminal.
Its exact regeneration failure remains a product failure.
Its later whole-asset equality would have required editing=None while an edit
object still used that asset. This is not a valid scene. Before the fix,
replace that later expectation with the explicit fresh editing rule above.
Keep its original geometry, recipe, entity, atomicity and undo checks.
This does not accept issue #72, its follow-up, a PR or any milestone.
