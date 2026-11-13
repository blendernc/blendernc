# Potential bugs in `blendernc/`

Findings from a re-read of every module, test and CI script in the working
tree on 2026-11-13 (branch `Blender5.2`, including uncommitted changes).
Each entry names the file and line, how it fails, and the smallest fix.
Design and quality notes live in `improvements.md`. The ten highest-impact
entries were fixed on 2026-11-13; they are listed at the end.

## Confirmed by reading the code

- **`extract_dimensions_of_grid` returns `(ny, ny)` for two 2-D coords.**
  `utils.py:956-958`: with exactly two 2-D coordinates `second_index` is 0,
  so both values come from the first axis. The mixed branch at line 953
  also raises `IndexError` with one 1-D and two 2-D coordinates.
- **Dimension order is assumed, never checked.** `field_to_point_values`
  (`utils.py:1015`) and `stack_2D_coords` (`utils.py:915`) hard-code
  `transpose(1, 0)`, which is right for `(y, x)` variables only. A dataset
  with `(x, y)` ordered dims passes the size check in `texture_field_error`
  and produces a scrambled texture. Transpose by dimension name using the
  grid's X and Y coordinates, and see the test note in `improvements.md`.
- **`DatacubeImport.free` drops a dataset others still use.**
  `nodes.py:86-91` pops the shared cache entry by basename; a second import
  node, or downstream nodes holding a copy of the same `filename`, then
  fail with `KeyError`. Reference-count or key the cache per node.
- **Dataset cache keyed by basename.** `nodes.py:83` splits on `"/"` and
  `utils.py:91` uses `os.path.basename`, so two files with the same name
  in different folders collide, and the node variant is not Windows-safe.
- **`load_dataset` has no engine.** `utils.py:76`: the file filter offers
  `*.grib` and `*.zarr` but `xr.open_mfdataset` is called without
  `engine="cfgrib"` or `engine="zarr"`, so neither opens. Datasets are
  never closed either.
- **`file_exists` raises inside a property update.** `decorators.py:302`:
  on a node, a typo in `datacube_file` produces a `FileNotFoundError`
  traceback in the console instead of a message. (The UI panel path is
  spared only because `check_if_node_tree_exists` returns early for it.)
- **Handlers appended unconditionally.** `blendernc.py:83-84` and
  `106-107`: reloading the extension registers `bNC_update_attributes`
  twice, and `unregister` raises `ValueError` if a handler is already gone.
- **Hard-coded socket indices.** `operators.py:126-127` and `164-169` use
  `inputs[2]`, `inputs[3]`, `inputs[0]`, `inputs[2]` on geometry nodes;
  look them up by name (`"Vertices X"`, `"Vertices Y"`, `"Name"`).
- **Active object is not restored.** `operators.py:129` sets the active
  object for `modifier_apply` and no longer restores it (the earlier
  restore was removed). Use `context.temp_override(object=obj)`.
- **`look_up_object_and_mesh` trusts the mesh name.** `utils.py:1138-1140`:
  when a mesh of that name exists but its object was deleted, `obj` is
  `None` and the operator fails on `obj.modifiers`.
- **Links removed from inside `update()`.** `decorators.py:121` deletes a
  link while Blender is dispatching node updates; the API documents tree
  edits in `update` as unsafe. Defer with a timer or flag the socket.
- **Enum item strings are not kept alive.** `utils.py:303-308` and
  `358-363` build fresh tuples on every draw. Blender warns that `items`
  callbacks must keep the returned strings referenced or the enum can show
  garbage. Cache the last list on the module.
- **`Import_OT_mfdataset.execute` assumes `context.area`.**
  `operators.py:67`: outside background mode but invoked from a script,
  `context.area` is `None`.

## Fixed on 2026-11-13

Verified by `tests/synthetic_grid.test.py` and the new
`tests/ui_panel.test.py`, which drives the panel properties end to end.

- **CI exit logic** (`tests/build-test.sh`): `&&` became `||`, so a failing
  `run_tests.py` now fails the job.
- **`decorators.is_linked`** looks the node up by name, clears *its* data
  item and outputs, reports through the operator, and cancels cleanly when
  the node is missing.
- **`utils.update_variable_UI`** returns early when the tree or variable
  node is missing, checks the grid and texture nodes before linking, only
  bakes when the grid has a linked coordinate, and calls `grid.update()` so
  the `Object` socket exists before it is linked. `_bake_ui_grid` holds the
  shared bake step.
- **`node_utils.delete_link`** now removes the link into a named input
  unconditionally; the "No var" policy moved to `update_coords_links_UI`.
  Deselecting the variable therefore unlinks both texture inputs, and the
  texture node removes its attribute.
- **`utils.suggested_stride`** returns `max(1, ceil(max(sizes) / 1000))`,
  with the budget named `MAX_SURFACE_SAMPLES`.
- **`DatacubeResolution`**: the `step` property's callback is a no-op while
  `suggested_step` is on, so `update()` can assign the suggestion without
  re-entering itself; sizes come from `dataset.sizes`; the misleading log
  line is gone. (An ID-property write was tried first and does not reach
  the RNA value on nodes in Blender 5.2.)
- **`utils.update_step_UI`** switches the node to manual, pushes the step
  once and rebakes; no self-assignment, no recursion. The panel shows the
  `suggested_step` toggle and the current step.
- **`DatacubeSelect`** gained an `index` property (clamped to the
  coordinate size), always forwards the input variable name, and refreshes
  downstream nodes. Its docstring describes the current record format.
- **Collections modified while iterated**: `has_datastructs` uses
  `outputs.clear()`; `delete_link` and `disconnect_links` iterate over
  `list(node_tree.links)`.
- **Input guards**: the frame handler skips nodes with no object, a
  non-mesh object, no dataset or an unknown variable instead of raising,
  and the always-false generator check is gone; `DatacubeTexture` shows a
  message for the same cases.
- **Downstream refresh** (found while testing): `DatacubeCoords` and
  `DatacubeVariable` now call the shared `refresh_downstream()` like the
  other forwarding nodes, so a stride set on the resolution node reaches
  the grid before the panel bakes it.
- **Panel sections** are toggled through `panels_draw.show_section`, which
  removes before appending, so `_create_UI_nodes` no longer relies on
  `Panel.is_extended()` and the coordinate section comes back after a
  file change.
