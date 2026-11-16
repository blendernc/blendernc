# Possible improvements for `blendernc/`

Findings from a re-read of every module, test, doc and CI file on
2026-11-13 (branch `Blender5.2`, working tree including uncommitted
changes). It covers design, robustness, cleanup, tests and docs; the
crashes and wrong results found in the same review have all been fixed.
Line numbers refer to the current tree.

## 1. Work in progress to finish

- **"Apply Material" does nothing.** `operators.BlenderNCBakeFromAttribute`
  (`operators.py:175-181`) is a stub with no docstring, yet the panel shows
  it as "Apply Material" (`panels_draw.py:69`). Either wire it to the
  `Datacube Texture` node or hide the button until it works.
- **The panel bakes on every variable change.** `utils.update_variable_UI`
  still rebakes the grid when a variable is picked, although the variable
  only affects the texture unless it is linked to Z. It now skips the bake
  when no coordinate is linked; baking from the coords and step callbacks
  only would remove the redundant work.
- **`DatacubeSlice` is still a placeholder** (`nodes.py:211-240`),
  registered but hidden from the menu.
- **Texture sub-menu id.** `menus.BlenderNCNodeAnimate` now shows "Texture"
  but keeps `bl_idname` `..._animate` and its class name; rename for
  consistency once nothing else references it.
- **Quickstart text is out of date.** `docs/source/quickstart_guide.rst:64`
  still tells users to click "Animate datacube"; the panel offers
  "Steps for coords" and "Apply Material" now.
- **Datacube Volume follow-ups** (added 2026-11-16 with the node).
  - Curvilinear (2-D) and unevenly spaced coordinates fall back to index
    space (`volume_utils.voxel_transform`). Resampling onto a regular grid,
    or writing an affine/frustum VDB transform, would place them correctly.
  - The vertical axis always counts voxels × `vertical_scale`. An evenly
    spaced depth or pressure coordinate could set the spacing, as x/y do.
  - Descending coordinates (latitude from 90 to -90) give a negative
    object scale. Flipping the array instead would keep the scale positive.
  - VDB files live on disk next to the .blend file; nothing packs them, and
    nothing removes a node's folder when the node is deleted.
  - The field range is computed over the whole variable at bake time, which
    loads all of a large lazily read cube once, and it ignores the scene's
    "Lock range" setting.
  - `get_animate_dims` lists dims from the unsliced variable, so a dim
    dropped by a Select node is still offered (and refused at bake).
  - "Current frame" mode only follows `frame_change_pre`/`render_pre`;
    render farms without BlenderNC need "Bake all frames".

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
  `update_step_UI`. The panel already draws the node's `suggested_step`
  directly; drawing its `step` the same way would remove the mirror.

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

- **Some assertions still compare sorted arrays**, so a transposed field
  would pass them: `assert_frame_attribute` and `test_xy_variable_as_z`.
  `test_field_values_follow_vertices_for_both_dim_orders` already compares
  in mesh order with `field_at_vertices`; the older tests could use it too.
- No test opens a dataset whose variable dims are `(x, y)` ordered, has
  2-D coordinates, or has more than one import node.
- The UI panel path is covered by `tests/ui_panel.test.py` for one 2-D
  dataset; it does not yet exercise a file change, Z linking or the
  "Apply Material" button.
- `tests/build-test.sh` still runs a `test_nolib` pass that matches no
  files; drop it or add the tests it was meant to run.
- Pure helpers could run under `pytest` without Blender once split out of
  `utils.py` (section 3); the slicing codec and
  `extract_dimensions_of_grid` are still untested.
- `test_file_missing` only asserts that nothing raises; it should check
  that the data item is cleared and the import node disconnected (the
  TODO in the test says so).

## 7. Documentation

- `docs/source/modules/` has pages for `utils`, `blendernc`, `handlers`,
  `operators`, `panels`, `sockets` and `nodes`, but none for `decorators`,
  `node_utils`, `menus`, `nodetree`, `properties` or `panels_draw`, so
  half of the numpydoc docstrings are not rendered.
- Nothing documents the panel's step field and suggestion toggle.
- The Datacube Volume section of `in_depth_guide.rst` has commented-out
  image placeholders (marked TODO) waiting for UI screenshots.
- `docs/source/modules/` has no page for the new `volume_utils` module.
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
