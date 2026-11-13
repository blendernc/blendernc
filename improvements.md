# Possible improvements for `blendernc/`

Findings from a read-through of every module in the `blendernc` package.
Grouped by priority; line numbers refer to the current `Blender5.2` branch.

## 1. Likely bugs

- **`utils.extract_dimensions_of_grid` crashes on mixed 1-D/2-D coordinates.**
  In the `else` branch, `dims.get(list(key[0]))` turns the coordinate name
  into a list of characters and then uses it as a dict key, which raises
  `TypeError: unhashable type: 'list'`. It should be `dims[key[0]][0]`.
  The `len(dims) == 2` branch also takes `[0]` of both shapes, so two 2-D
  coordinates of shape `(ny, nx)` yield `(ny, ny)` instead of `(nx, ny)`.
- **`handlers.bNC_update_attributes` returns instead of clamping.** When the
  frame is outside the animated coordinate's range, `frame` is clamped and
  then the function `return`s, so the clamped value is never used and every
  remaining Animate Texture node is skipped. Use `continue` or drop the
  `return`.
- **`handlers.bNC_update_attributes` has no guards.** `object.data` fails when
  the Object socket is empty, `add_attribute` returns `None` for non-mesh
  objects and the next line dereferences it, and
  `[... if coord not in matched_coords][0]` raises `IndexError` when every
  coordinate matches the vertex count.
- **`decorators.has_datastructs` removes outputs while iterating.**
  `for output in self.outputs: self.outputs.remove(output)` skips every
  other socket. `is_linked` already does it right with `self.outputs.clear()`.
- **`slicing` records break on names with underscores.** Records are written
  as `"<var>_<coord>_<index>,"` and parsed with `split("_")`, so a coordinate
  such as `time_counter` or a variable such as `nav_lon` cannot be decoded.
  `get_data_from_datastruct` also matches records with `var_name in s`, a
  substring test, so a record for `ssh` applies to `ssh_anom` too. In
  `nodes.DatacubeSelect.update` the index `value` is hard-coded to `0`, so
  the node cannot actually pick an index, and the record is keyed by the
  variable only, so the grid coordinates are never sliced to match.
- **`utils.get_var` fails on datasets with no data variables.**
  `datacubedata[variables[0]]` raises `IndexError` when `variables` is empty
  (coordinate-only files, or a `str_filter` that matches nothing).
- **`utils.find_coord_matches` returns an inconsistent shape.** `np.squeeze`
  yields a 0-d array, a 1-d array of names or a 2-d array depending on how
  many combinations match. The handler then uses `in` on it, which behaves
  differently in each case. Return a plain `list[tuple[str, ...]]`.
- **Dataset cache is keyed by basename only.** `create_datastruct` and
  `DatacubeImport.update` use `datacube_file.split("/")[-1]` as the key, so
  two files with the same name in different folders collide, and the split
  is not Windows-safe. Use `os.path.basename` and key by the full path.
- **Vertex ordering on non-square grids is unverified.** `stack_2D_coords`
  flattens as `(nx, ny, 3)` (y fastest) while `extract_dimensions_of_grid`
  feeds `Vertices X = nx`, `Vertices Y = ny` to the Mesh Grid node, whose
  vertices are ordered x fastest. On square grids this is an invisible
  transpose; on rectangular grids it may scramble positions. A test with a
  rectangular dataset would settle it.

## 2. Robustness

- **`file_exists` raises inside a property `update` callback.**
  `create_datastruct` is the `update` of two `StringProperty` fields, so a
  typo in the path produces a `FileNotFoundError` traceback in the console
  rather than a user-facing message. Report through `self.report` or log and
  clear the data item instead.
- **Hard-coded socket indices in `operators.Import_OT_CreateGrid.execute`.**
  `MeshGrid_node.inputs[2]`, `inputs[3]`, `inputs[0]` and `inputs[2]` on the
  named-attribute nodes will silently break when Blender reorders sockets.
  Look sockets up by name (`"Vertices X"`, `"Vertices Y"`, `"Name"`).
- **`bpy.ops.object.modifier_apply` depends on view-layer state.** The
  operator swaps the active object twice and never restores selection. A
  `context.temp_override(object=obj)` block is safer and works in
  background mode.
- **Enum `items` callbacks have side effects.** `get_possible_variables_UI`
  and `get_possible_coordinates_UI` call `create_blenderncnodetree("BLENDERNC")`,
  which creates a node group as a side effect of drawing a drop-down. The
  Blender docs also warn that strings returned by an `items` callback must
  be kept referenced by Python, or the enum can show garbage or crash; cache
  the returned list on the module.
- **`panels_draw.draw_var_and_coords` assumes nodes exist.** It dereferences
  `node_tree.nodes.get("Datacube Coords")` without a `None` check, so
  deleting that node while the panel is extended raises every redraw.
- **`utils.get_grid_coords` has no missing-key handling.** Both
  `datastruct.dict[datastruct.filename]` and `dataset[socket.default_value]`
  raise `KeyError` if the dataset was unloaded or the coordinate renamed.
- **`load_dataset` always uses `xr.open_mfdataset` with no engine.** The file
  filter advertises `*.grib` and `*.zarr`, but GRIB needs `engine="cfgrib"`
  and Zarr stores need `engine="zarr"`; neither is passed. Datasets are also
  never closed, so file handles leak until Blender exits.
- **`blendernc.register` appends handlers unconditionally.** Reloading the
  extension appends a second `bNC_update_attributes`, and `unregister`
  raises `ValueError` if a handler is already gone. Check membership first.

## 3. Design and architecture

- **Global mutable cache on a class attribute.** `BNC_data.dict` is a
  `defaultdict` shared by every node in every file. `initialize_BNC_datastructs`
  assigns `item.dict = defaultdict()` but `PropertyGroup` instances are
  recreated on each access, so this only ever touches the class attribute.
  A dedicated cache module (e.g. `datasets.py` with `get`, `put`, `drop`)
  would make the lifetime explicit and testable.
- **`decorators.py` contains UI logic.** `_create_UI_nodes` builds the node
  tree, toggles panel draw functions and reads scene properties; it belongs
  with the operators or a `ui.py` module, not next to generic decorators.
- **`check_if_node_tree_exists` does three unrelated things** depending on
  `bl_idname`: for the UI property group it builds nodes and never calls the
  wrapped function; for the import operator it builds nodes and continues;
  for nodes it just resolves names. Split into explicit helpers so the
  control flow is visible at the call site.
- **`node_utils.create_nodes` mutates its argument and module state.** It
  writes `"node"` and `"name"` back into the dict it is given, which for
  `basic_nodes` is a module-level constant, so stale node references survive
  across node trees and reloads. Return a new mapping instead.
- **`delete_link` encodes caller policy.** The `output_name == "No var"` test
  belongs in `update_coords_links_UI`; `delete_link` should simply remove the
  link to a named input.
- **Pure helpers are mixed with `bpy` code in `utils.py`.** `name_match`,
  `findCommonName`, `get_2D_coords` and its handlers, `stack_2D_coords`,
  `extract_dimensions_of_grid`, `build_enum_prop_list` and
  `find_coord_matches` need no Blender at all. Moving them to a module that
  does not import `bpy` would allow fast `pytest` unit tests outside Blender.
- **`get_possible_coordinates_UI` depends on the layout of `get_dims`.**
  `items.pop(1)` and `items[0] = ...` assume a header plus separator at the
  front; a parameter on `get_dims` would remove the coupling.
- **Datacube path is stored in three places** (`datacube_file` on the node,
  `datacube_file` on the scene properties, and `datafile` on the data item)
  and kept in sync by hand in `Import_OT_mfdataset.execute` and
  `DatacubeImport.update`. One source of truth would simplify the update
  callbacks.

## 4. Dead code and cleanup

Most of this section was applied on 2026-11-13: unused symbols, commented-out
code, the `operations` field, shadowed builtins, `isinstance` in
`file_exists`, the early return in `does_link_exists`, module-level
`difflib`, named loggers, and the local camelCase names. What remains:

- `nodes.DatacubeSlice` is still a placeholder. It is registered but hidden
  from the "Selection" menu until `update` does something.
- Public names left as they are to avoid breaking callers and saved files:
  `get_2D_coords` (imported by `operators.py`), `bNC_update_attributes`
  (registered handler) and the `BNC_datastructs` property (stored in
  .blend files). Rename these only with a deliberate migration.

## 5. Blender API usage

- `bNCdatacubeSocket` subclasses `NodeSocketFloat` although it carries no
  float; subclass `bpy.types.NodeSocket` directly and implement
  `draw_color_simple` (classmethod) for Blender 4.x.
- `BlenderNCNodeTree.poll` always returns `True`; returning `True` only when
  the add-on is usable (or dropping the override) avoids an empty editor
  type in every file.
- `add_custom_node_to_menu` injects the menu into every node editor. The
  commented-out `tree_type` check suggests restricting it to
  `BlenderNCNodeTree` (and `GeometryNodeTree`) was intended.
- `BlenderNCNodeImport` and `BlenderNCNodeSelection` both add the
  `DatacubeVariable` node under different labels.
- `register` and `unregister` return `{"FINISHED"}`, which Blender ignores
  for registration functions.

## 6. Testing

- No tests cover `get_2D_coords`, `extract_dimensions_of_grid`,
  `stack_2D_coords`, `find_coord_matches`, `findCommonName` or
  `bNC_update_attributes`. Several of the bugs in section 1 live there.
- `tests/*.test.py` each spin up Blender; a plain `pytest` suite for the pure
  helpers (after the split suggested in section 3) would run in CI in
  seconds and catch regressions in the array logic.
- `test_file_missing` only asserts that nothing raises; it should also check
  that the data item is cleared and the import node is disconnected (the
  TODO in the test already says so).
- Add a rectangular-grid fixture to validate vertex ordering end to end.

## 7. Documentation

- `docs/source/modules/` still references removed modules (`blendernc.image`,
  `blendernc.get_utils`, `blendernc.preferences`, `blendernc.core`,
  `blendernc.nodes.math`) and has no pages for `utils`, `node_utils`,
  `nodetree`, `menus`, `properties` or `translations`, so the new numpydoc
  docstrings are not yet rendered.
- Type hints are absent throughout; adding them to the pure helpers would
  let `autodoc_typehints = "description"` in `conf.py` do useful work.
