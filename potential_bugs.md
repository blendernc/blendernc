# Potential bugs in `blendernc/`

Findings from a re-read of every module, test and CI script in the working
tree on 2026-11-13 (branch `Blender5.2`, including uncommitted changes).
Each entry names the file and line, how it fails, and the smallest fix.
Design and quality notes live in `improvements.md`.

## Confirmed by reading the code

- **CI never fails on test failures.** `tests/build-test.sh:59` exits 1
  only when `test_exit` *and* `test_nolib_exit` are non-zero. There are no
  `*.test_nolib.py` files, so the first run always succeeds and the script
  exits 0 whatever `run_tests.py` reports. Change `&&` to `||` (or drop the
  nolib pass).
- **`decorators.is_linked` crashes instead of cancelling.**
  `decorators.py:30-34`: `self` is the operator, which has no
  `BNC_datastructs`, `outputs` or `inputs`; the else branch raises
  `AttributeError` the moment a grid is baked with no linked inputs. The
  panel now bakes on every variable change (`utils.py:433`), so selecting a
  variable before X and Y are chosen hits this path. Clear the *node*'s data
  item and outputs, and report through the operator.
- **`utils.update_variable_UI` uses unbound names.** `utils.py:425-439`:
  `selected` and `action` are only assigned inside `if var_node:`, so a
  missing variable node raises `UnboundLocalError` at line 438. `texture_node`
  and `grid_node` are also passed to `create_link` without a `None` check.
- **The texture node is never unlinked from the grid.** `utils.py:439`
  calls `delete_link(..., "Object", "Object")`, but `delete_link`
  (`node_utils.py:266`) only removes a link when `output_name == "No var"`.
  On deselect the Variable link goes away and the Object link stays.
- **`utils.suggested_stride` returns 0 and steps in tens.** `utils.py:483-491`:
  for any surface size up to 1000 it returns `stride - 1 == 0`; the
  `IntProperty(min=1)` clamp hides it. Above 1000 the stride jumps by 10, so
  a 1001-wide grid is cut to 100 points. It also uses `min(sizes)`, so a
  100 by 10000 grid gets stride 1. `max(1, ceil(max(sizes) / 1000))` is
  probably what was meant.
- **`DatacubeResolution.update` recurses and double-records.**
  `nodes.py:573-579`: assigning `self.step = stride` inside `update` fires
  the property's `update=lambda: self.update()`, which records the stride
  and refreshes downstream nodes; the outer call then does both again. The
  nested call also takes the `else` branch and logs "Using manually set
  step" although the step was just suggested. Compute the stride without
  assigning, or guard with a re-entrancy flag.
- **`utils.update_step_UI` reverts the user's edit through recursion.**
  `utils.py:468-476`: when `suggested_step` is on, writing `self.step` from
  inside its own update callback triggers a second call that then bakes
  the grid. Harmless loop today, but the user's typed value is silently
  overwritten; disable the field, or turn `suggested_step` off on edit.
  `step_node` is also dereferenced without a `None` check.
- **`DatacubeSelect` forwards a stale variable name.** `nodes.py:278-280`
  sets the output `default_value` only when it creates the socket. It only
  works today because `has_datastructs` deletes the `init`-created socket
  first; once linked, a new upstream variable is never forwarded.
  `DatacubeSubsample` (`nodes.py:494`) does it right.
- **`DatacubeSelect` cannot select an index.** `nodes.py:281` hard-codes
  `value = 0`; the node needs an `IntProperty`. Its docstring at
  `nodes.py:246-248` still describes the old `"<var>_<coord>_<index>,"`
  format.
- **Collections modified while iterated.** `decorators.py:280`
  (`has_datastructs`), `node_utils.py:264` (`delete_link`) and
  `node_utils.py:280` (`disconnect_links`) remove items from the collection
  they loop over, so every other socket or link survives. Iterate over
  `list(...)` or use `self.outputs.clear()` as `is_linked` does.
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
- **`bNC_update_attributes` has no input guards.** `handlers.py:32-38`: an
  empty Object socket gives `None.data`, an empty Variable gives
  `dataset[""]`, and a non-mesh object makes `add_attribute` return `None`
  which `write_point_attribute` dereferences. The handler runs on every
  frame change, so one half-connected node breaks playback. The
  `if not anim_text_nodes` check at line 28 is also always false because
  `get_all_nodes_by_idname` returns a generator.
- **`DatacubeTexture._write_texture` lacks the same guards.**
  `nodes.py:405-409`: `obj.data` can be `None` (an Empty) and
  `get_data_from_datastruct` raises `KeyError` when the variable is not in
  the dataset any more.
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
- **`_create_UI_nodes` never re-appends the coordinate section.**
  `decorators.py:236`: `Panel.is_extended()` is true as soon as *any* draw
  function is appended, so once the resolution section exists the
  variable/coords section is not restored after a `remove`. Check
  membership in `panel.draw._draw_funcs`, or always `remove` then `append`.

## Likely, worth a test before fixing

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
