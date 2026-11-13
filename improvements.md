# Possible improvements for `blendernc/`

Findings from a re-read of every module, test, doc and CI file on
2026-11-13 (branch `Blender5.2`, working tree including uncommitted
changes). Crashes and wrong results are listed separately in
`potential_bugs.md`; this file covers design, robustness, cleanup, tests
and docs. Line numbers refer to the current tree.

## 1. Work in progress to finish

- **"Apply Texture" does nothing.** `operators.BlenderNCBakeFromAttribute`
  (`operators.py:175-181`) is a stub with no docstring, yet the panel shows
  it as "Apply Texture" (`panels_draw.py:69`). Either wire it to the
  `Datacube Texture` node or hide the button until it works.
- **The panel bakes on every variable change.** `utils.update_variable_UI`
  calls `create_grid_from_coords` (`utils.py:433`) although the variable
  only affects the texture unless it is linked to Z. Bake from the coords
  and step callbacks only, and let the texture node react to the link.
- **`DatacubeSlice` is still a placeholder** (`nodes.py:211-240`),
  registered but hidden from the menu.
- **Texture sub-menu id.** `menus.BlenderNCNodeAnimate` now shows "Texture"
  but keeps `bl_idname` `..._animate` and its class name; rename for
  consistency once nothing else references it.
- **Quickstart text is out of date.** `docs/source/quickstart_guide.rst:64`
  still tells users to click "Animate datacube"; the panel offers
  "Steps for coords" and "Apply Texture" now.

## 2. Robustness

- **Shared mutable cache on a class attribute.** `BNC_data.dict`
  (`properties.py:25`) is one `defaultdict` for every node in every file;
  `initialize_BNC_datastructs` (`decorators.py:195`) assigns `item.dict`
  on a transient `PropertyGroup` wrapper, so the per-item assignment has no
  lasting effect. A small cache module (`get`, `put`, `drop`, keyed by the
  full path, with reference counts) would make the lifetime explicit.
- **Enum `items` callbacks create data.** `_get_ui_node` (`utils.py:354`)
  calls `create_blenderncnodetree`, so drawing a drop-down can create a
  node group. Look the tree up with `bpy.data.node_groups.get` in read
  paths.
- **Output sockets accumulate.** `DatacubeCoords.update` (`nodes.py:117`)
  and `DatacubeVariable.update` (`nodes.py:161`) add sockets and never
  remove ones that no longer exist in the dataset, so switching files
  leaves dead outputs and links.
- **`panels_draw.draw_var_and_coords` assumes nodes exist.**
  `panels_draw.py:26-30` dereferences the "Datacube Coords" node without a
  `None` check, so deleting it raises on every redraw while the section is
  appended.
- **`get_grid_coords` has no missing-key handling.** `utils.py:673`:
  `dataset[socket.default_value]` raises `KeyError` if the coordinate was
  renamed or the dataset unloaded.
- **`_clear_default_values` matches on `bl_label`.** `decorators.py:69`
  compares `input_socket.bl_label != "Object"`; `isinstance(socket,
  bpy.types.NodeSocketObject)` is the stable test.
- **`basic_nodes` and `locations` must stay in step.** `node_utils.py:3-32`
  are two parallel module constants; `create_nodes` now uses
  `zip(strict=True)`, so adding a node to one without the other raises at
  panel creation. Put the location inside each `basic_nodes` entry.

## 3. Design and architecture

- **`decorators.py` contains UI logic.** `_create_UI_nodes`
  (`decorators.py:204-239`) builds the node tree, toggles panel draw
  functions and reads scene properties; it belongs with the operators or
  a `ui.py` module.
- **`check_if_node_tree_exists` does three unrelated things**
  (`decorators.py:242-262`) depending on `bl_idname`: for the UI property
  group it builds nodes and never calls the wrapped function; for the
  import operator it builds nodes and continues; for nodes it only
  resolves names. Three explicit helpers would make the call sites
  readable.
- **`create_nodes` mutates a module constant.** It writes `"node"` back
  into the mapping it is given, which for `basic_nodes` is module state, so
  stale node references survive across trees and reloads. Return a new
  mapping.
- **`delete_link` encodes caller policy.** The `output_name == "No var"`
  test (`node_utils.py:266`) belongs in `update_coords_links_UI`;
  `delete_link` should simply remove the link into a named input. This is
  also what makes the Object link to the texture node impossible to remove
  (see `potential_bugs.md`).
- **`utils.py` mixes pure helpers with `bpy` code.** `name_match`,
  `find_common_name`, the slicing codec, `get_surface_dims`,
  `get_2D_coords` and its handlers, `stack_2D_coords`,
  `extract_dimensions_of_grid`, `find_coord_matches`, `suggested_stride`
  and `texture_field_error` need no Blender. A `bpy`-free module would
  allow fast `pytest` unit tests and shrink the 1170-line file.
- **`utils.py` imports `panels_draw`** (`utils.py:14`) and `properties.py`
  imports `utils`, while `decorators.py` imports `panels_draw` and
  `node_utils`; the UI callbacks (`update_*_UI`, `_get_ui_node`) would sit
  better in a `ui.py` next to `panels_draw.py`.
- **`get_possible_coordinates_UI` depends on the layout of `get_dims`.**
  `utils.py:404-406` pops the separator and overwrites the header; a
  parameter on `get_dims` would remove the coupling.
- **The datacube path lives in three places** (`datacube_file` on the
  node, `datacube_file` on the scene properties, `datafile` on the data
  item) and is synced by hand in `Import_OT_mfdataset.execute` and
  `DatacubeImport.update`.
- **Two step properties.** `BlenderNC_UI_Properties.step`
  (`properties.py:56`) mirrors `DatacubeResolution.step` through
  `update_step_UI`; the panel could draw the node's property directly.

## 4. Dead code and cleanup

- `blendernc/__init__.py:41`: `bpy.context.preferences.addons.get(...)`
  does nothing. The root `__init__.py:54-57` `__main__` block registers
  and immediately unregisters.
- `properties.py:35`: `datacube_file` is described as "Folder with assets
  blend files".
- `blendernc.py:28-32`: trailing spaces in the operators import, and
  `nodes.py:533`, `nodes.py:571`, `utils.py:485-491`, `properties.py:56`,
  `panels_draw.py:66` are not `black`-formatted. Run `black` and `isort`
  before committing; both have workflows.
- `nodes.py:533` `suggested_step` has a space before the colon.
- `register`/`unregister` return `{"FINISHED"}` (`blendernc.py:94,115`),
  which Blender ignores for registration functions.
- Public names kept for compatibility: `get_2D_coords`,
  `bNC_update_attributes` (registered handler) and `BNC_datastructs`
  (stored in .blend files). Rename only with a migration.
- Repository hygiene: `develop.blend1` and `resolution.blend1` are Blender
  backup files and `develop.blend` / `resolution.blend` are binaries in
  git; add `*.blend1` to `.gitignore`. `.coveragerc` still omits the
  removed `addon_updater`. `pyproject.toml` says `requires-python >= 3.13`
  while `blender_manifest.toml` allows Blender 4.2 (Python 3.11), and the
  manifest's `wheels = []` is empty although `wheels/` is populated by
  `update_wheels.py`.

## 5. Blender API usage

- `bNCdatacubeSocket` subclasses `NodeSocketFloat` (`sockets.py:11`) but
  carries no float; subclass `bpy.types.NodeSocket` and implement
  `draw_color_simple` (classmethod) for Blender 4.x and later.
- `BlenderNCNodeTree.poll` always returns `True` (`nodetree.py:26`), so
  the editor type appears in every file.
- `add_custom_node_to_menu` (`menus.py:121-124`) injects the menu into
  every node editor; restrict it to `BlenderNCNodeTree`.
- `BlenderNCNodeImport` and `BlenderNCNodeSelection` both add the
  `DatacubeVariable` node under different labels (`menus.py:47,81`).
- `bpy.ops.object.modifier_apply` (`operators.py:130,170`) depends on the
  active object and mode; `context.temp_override(object=obj)` is safer and
  works in background mode.

## 6. Testing

- **Assertions compare sorted arrays**, so a transposed or scrambled field
  passes: `assert_frame_attribute` and the texture tests in
  `tests/synthetic_grid.test.py` sort both sides, and
  `test_xy_variable_as_z` sorts the Z values. Compare against the expected
  array in mesh order (build it with the same `meshgrid` the operator
  uses). This is the one test that would catch the dimension-order
  assumption listed in `potential_bugs.md`.
- No test opens a dataset whose variable dims are `(x, y)` ordered, has
  2-D coordinates, or has more than one import node.
- The UI panel path (`update_variable_UI`, `update_step_UI`,
  `_create_UI_nodes`) has no coverage at all, and three of the confirmed
  bugs live there.
- `tests/build-test.sh` runs a `test_nolib` pass that matches no files,
  and its exit logic hides failures (see `potential_bugs.md`).
- Pure helpers could run under `pytest` without Blender once split out of
  `utils.py` (section 3); `suggested_stride`, the slicing codec and
  `extract_dimensions_of_grid` are all untested today.
- `test_file_missing` only asserts that nothing raises; it should check
  that the data item is cleared and the import node disconnected (the
  TODO in the test says so).

## 7. Documentation

- `docs/source/modules/` has pages for `utils`, `blendernc`, `handlers`,
  `operators`, `panels`, `sockets` and `nodes`, but none for `decorators`,
  `node_utils`, `menus`, `nodetree`, `properties` or `panels_draw`, so
  half of the numpydoc docstrings are not rendered.
- `docs/source/terminal.rst` documents `BlenderNCNodeTexture` but not
  `BlenderNCNodeResolution.suggested_step`, and nothing documents the
  panel's step field.
- Type hints are absent throughout; adding them to the pure helpers would
  let `autodoc_typehints = "description"` do useful work.

## Resolved since the first pass

Kept for traceability; all verified against the current tree.

- `extract_dimensions_of_grid` no longer builds an unhashable key.
- `get_var` no longer indexes an empty variable list.
- `slicing` records use `|` separators with a wildcard target, so names
  with underscores work and `ssh` no longer matches `ssh_anom`.
- `find_coord_matches` returns a consistent list of tuples and the frame
  handler matches on `data.dims`, clamps the frame and skips variables with
  no animated dimension.
- Vertex ordering on a rectangular grid is verified by edge checks in
  `tests/synthetic_grid.test.py` (but see section 6 on sorted comparisons).
- `docs/source/modules/` no longer references removed modules.
- Dead code, commented-out blocks, shadowed builtins and camelCase locals
  were cleaned up in `4ba59ea` and `7cbb0ea`.
