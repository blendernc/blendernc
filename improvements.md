# Possible improvements for `blendernc/`

Findings from a re-read of every module, test, doc and CI file on
2026-11-13 (branch `Blender5.2`), re-checked on 2026-11-17 (branch
`voxel` at `5dff8cb`). The section 1 work and the two crash fixes done on
2026-11-17 are listed under "Resolved" at the end. It covers design,
robustness, cleanup, tests and docs. Line numbers refer to the working tree
after that work.


## 1. Work in progress to finish

- **Datacube Variable**
  - BlenderNCNodeVariable should create all the outputs of the variables
    (similar to datacube coords) rather
    than having a list from which the user selects individually variables. This
    requires the Panel to link the output node of the selected variable in the
    panel with the Datacube Texture variable input. If the list of variables
    is larger than 10, use the enumeration property and only have a single output
    that corresponds to the variable selected.
- **Datacube coords**
  - When a new input dataset is connected the coordinates are appended, the
    exppected interaction would be for all the coordinates to be replaced.
- **Datacube Animation**
  - Add Apply Material button to make it easier to visualize the selected
    variable.
  - Add also the custom properties of max and min for the first loaded frame.
  - Use similar assignment of texture as the texture node.
- **Datacube Volume follow-ups** (left after the 2026-11-17 work).
  - Nothing packs the VDB files into the .blend file. In an unsaved file
    they go to Blender's temporary folder, and the node only warns (the
    chosen behaviour); nothing moves them when the file is first saved.
  - Curvilinear resampling (`volume_utils.curvilinear_placement`,
    `volume_utils.py:537`) is nearest neighbour at the source resolution,
    and it treats longitude as a plain number: a grid that crosses the
    dateline (179° to -179°) is resampled over the whole -180 to 180 range.
  - Unevenly spaced vertical levels stay one voxel per level
    (`vertical_placement`, `volume_utils.py:470`), so such a volume does
    not line up with a grid whose Z is that coordinate.
  - Releasing "Lock range" recomputes the texture ranges
    (`utils.update_lock_range`, `utils.py:1480`) but not the volume
    ranges, which wait for the next bake.
  - A node's VDB sub-folder is named after its tree and itself
    (`vdb_directory`, `volume_utils.py:693`); renaming either leaves the
    old folder behind.
  - Add more property types, for example temperature, and velocities. In
    the case of velocities, we will need a supplementary node that merges
    u,v, and w velocities to then pass it as a vector.

## 2. Robustness

- **Shared mutable cache on a class attribute.** `BNC_data.dict`
  (`properties.py:26`) is one `defaultdict` for every node in every file;
  `initialize_BNC_datastructs` (`decorators.py:287`) assigns `item.dict`
  on a transient `PropertyGroup` wrapper, so the per-item assignment has no
  lasting effect. A small cache module (`get`, `put`, `drop`, keyed by the
  full path, with reference counts) would make the lifetime explicit.
- **Read paths create data.** `_get_ui_node` (`utils.py:484-487`) and both
  panel draw functions (`panels_draw.py:37, 83`) call
  `create_blenderncnodetree`, so drawing a drop-down or the panel can
  create a node group. Look the tree up with `bpy.data.node_groups.get` in
  read paths.
- **`create_blenderncnodetree` ignores the tree type.** It returns any
  group with the requested name (`node_utils.py:127-128`).
  `assign_modifier_to_object` (`utils.py:1708`) asks for a geometry tree
  named after the grid object, so a grid object called "BLENDERNC" (or
  after any other node group) gets the wrong kind of tree for its
  modifier, and the bake fails. Check `bl_idname`, and pick a new name
  when the existing group has another type.
- **Output sockets accumulate.** `DatacubeCoords.update`
  (`nodes.py:160-170`) and `DatacubeVariable.update` (`nodes.py:209-216`)
  add sockets and never remove ones that no longer exist in the dataset,
  so switching files leaves dead outputs and links.
- **`panels_draw.draw_var_and_coords` assumes nodes exist.**
  `panels_draw.py:41-45` dereferences the "Datacube Coords" node without
  a `None` check, so deleting it raises on every redraw while the section
  is appended.
- **`get_grid_coords` has no missing-key handling.** `utils.py:1018`
  passes the socket value to `get_data_from_datastruct`, which indexes
  `dataset[var_name]` (`utils.py:948`). A renamed coordinate raises
  `KeyError`, and an unloaded dataset raises `TypeError`.
- **`_clear_default_values` matches on `bl_label`.** `decorators.py:74`
  compares `input_socket.bl_label != "Object"`; `isinstance(socket,
  bpy.types.NodeSocketObject)` is the stable test.
- **Node mappings and their locations must stay in step.** `basic_nodes`
  and `locations` (`node_utils.py:7-36`) are parallel module constants, as
  are `COLORBAR_MATERIAL_NODES` and `COLORBAR_MATERIAL_LOCATIONS`
  (`shader_utils.py:248-264`); `texture_material` and `volume_material`
  extend `RANGE_NODE_LOCATIONS` by hand (`shader_utils.py:89, 337`).
  `create_nodes` uses `zip(strict=True)`, so a node added to one list but
  not the other raises. Put the location inside each entry.
- **Grid and Volume nodes run operators from `update`.**
  `DatacubeGrid.update` and `DatacubeVolume.update` call `bpy.ops` to
  rebake (`nodes.py:294, 811`); the operator creates objects, applies
  modifiers and calls `update()` again. `decorators.py:171-174` notes that
  Blender is still walking the tree during `update` and moves link edits
  to a timer for that reason. Rebakes could be deferred the same way.

## 3. Design and architecture

- **Selections do not reach a grid baked from coordinates.** Select,
  Slice and Subsample records travel down the Variable chain. A Datacube
  Grid whose X and Y come from a Coords node only sees them through a
  linked Z, so the texture of a sliced variable does not fit the grid
  (the Texture node says to bake the grid from the variable's
  coordinates). Volumes are unaffected: they read their coordinates from
  the sliced variable.
- **`decorators.py` contains UI logic.** `_create_UI_nodes`
  (`decorators.py:296-330`) builds the node tree, toggles panel draw
  functions and reads scene properties; it belongs with the operators or
  in a `ui.py` module.
- **`check_if_node_tree_exists` does three unrelated things**
  (`decorators.py:356-374`), depending on `bl_idname`. For the UI property
  group it builds nodes and never calls the wrapped function. For the
  import operator it resolves the node through `_use_import_node`. For
  nodes it only resolves names. `_use_import_node` and the Apply Material
  operator, which now resolves its own defaults, show the explicit style
  the remaining branches could follow.
- **`create_nodes` mutates its input.** It writes `"node"` into each
  entry and may add a `"NodeGroupOutput"` entry (`node_utils.py:185,
  194`). `_create_UI_nodes` passes the module constant `basic_nodes`
  (`decorators.py:319`), so stale node references survive across trees
  and reloads. The material helpers build a fresh mapping on each call,
  and `colorbar_material` and `_new_colormap_group` copy theirs first
  (`shader_utils.py:297`, `shader_nodes.py:39`). Returning a new mapping
  would make those copies unnecessary.
- **`utils.py` mixes pure helpers with `bpy` code.** `name_match`,
  `find_common_name`, `dataset_engine`, the slicing codec and
  `_merge_selector`, `clamp_index_range`, `value_index_range`,
  `format_coord_value`, `get_surface_dims`, `get_2D_coords` and its
  handlers, `grid_dims`, `stack_2D_coords`, `extract_dimensions_of_grid`,
  `find_coord_matches`, `suggested_stride`, `field_to_point_values`,
  `field_range` and `texture_field_error` need no Blender, nor do
  `axis_spacing`, `nearest_positions`, `axis_placement`,
  `curvilinear_placement`, `volume_layout` and `frame_array` in
  `volume_utils.py`. A `bpy`-free module would allow fast `pytest` unit
  tests and shrink `utils.py`, which has grown to 1712 lines.
- **`utils.py` imports `panels_draw`** (`utils.py:22`), while
  `properties.py` imports `utils` and `decorators.py` imports
  `panels_draw` and `node_utils`. The UI callbacks (`update_*_UI`,
  `_get_ui_node`, `sync_texture_section`) would sit better in a `ui.py`
  next to `panels_draw.py`. That module, or `node_utils.py` next to
  `UI_NODE_TREE`, could also own the `UI_*_NODE` labels; they live in
  `utils.py` now, so `panels_draw.py` repeats the literals "BLENDERNC",
  "Datacube Coords" and "Datacube Resolution" (`panels_draw.py:37, 41,
  83-84`).
- **`get_possible_coordinates_UI` depends on the layout of `get_dims`.**
  `utils.py:539-541` drops the separator and overwrites the header; a
  parameter on `get_dims` would remove the coupling.
- **The datacube path lives in three places** (`datacube_file` on the
  node, `datacube_file` on the scene properties, `datafile` on the data
  item) and is synced by hand in `Import_OT_mfdataset.execute`
  (`operators.py:83-89`), `_create_UI_nodes` (`decorators.py:327`) and
  `DatacubeImport.update` (`nodes.py:119-131`).
- **Two step properties.** `BlenderNC_UI_Properties.step`
  (`properties.py:57`) mirrors `DatacubeResolution.step` through
  `update_step_UI` (`utils.py:666-680`). The panel already draws the
  node's `suggested_step` directly (`panels_draw.py:87`); drawing its
  `step` the same way would remove the mirror.

## 4. Dead code and cleanup

- `blendernc/__init__.py:41`: `bpy.context.preferences.addons.get(...)`
  does nothing. The root `__init__.py:54-57` `__main__` block registers
  and immediately unregisters.
- `properties.py:36`: `datacube_file` is described as "Folder with assets
  blend files".
- `register`/`unregister` return `{"FINISHED"}` (`blendernc.py:156,
  184`), which Blender ignores for registration functions.
- `DatacubeResolution.draw_buttons` reads `datastruct.dict` directly
  instead of calling `get_dataset` (`nodes.py:999`).
- `find_common_name` keeps the camelCase `commonName` and `S`
  (`utils.py:303-314`). `name_match` ends with a branch that only
  `pass`es (`utils.py:273-274`). `get_datacube_path` has a Google-style
  docstring among numpydoc ones (`utils.py:58-64`).
- `is_single_input_linked`'s docstring says the update runs only when an
  input is linked, but it always runs it (`decorators.py:254-255`).
- `draw_var_and_coords` builds a `coords` list only to count it
  (`panels_draw.py:42-46`).
- Public names kept for compatibility: `get_2D_coords`,
  `bNC_update_attributes` (registered handler) and `BNC_datastructs`
  (stored in .blend files). Rename only with a migration.
- Repository hygiene: `.coveragerc` still omits the removed
  `addon_updater`. `blender_manifest.toml:10` says
  `blender_version_min = "4.2.0"`, but `bl_info` and the docs say 5.2,
  the bundled wheels are built for Python 3.13 (`pyproject.toml` has
  `requires-python >= 3.13`), and `handlers.py` uses the slotted-action
  API. Set it to `5.2.0`. `docs/source/modules/blendernc.blendernc.rst`
  is tracked although `.gitignore` lists it.

## 5. Blender API usage

- `bNCdatacubeSocket` subclasses `NodeSocketFloat` (`sockets.py:12`) but
  carries no float; subclass `bpy.types.NodeSocket`, as `bNCAnySocket`
  does, and implement `draw_color_simple` (classmethod) for Blender 4.x
  and later.
- `BlenderNCNodeTree.poll` always returns `True` (`nodetree.py:17-26`),
  so the editor type appears in every file.
- `BlenderNCNodeImport` and `BlenderNCNodeSelection` both add the
  `DatacubeVariable` node under different labels (`menus.py:31, 64`).

## 6. Testing

- **Some assertions still compare sorted arrays**, so a transposed field
  would pass them: `assert_frame_attribute`, `test_xy_variable_as_z` and
  `test_xy_static_texture` (`synthetic_grid.test.py:288-329`).
  `test_field_values_follow_vertices_for_both_dim_orders` already compares
  in mesh order with `field_at_vertices`; the older tests could use it too.
- `tests/ui_panel.test.py` covers a single 2-D dataset: it never changes
  file, and links Z only in the failing-bake case.
- `tests/build-test.sh:24-27, 59` still runs a `test_nolib` pass that
  matches no files; drop it or add the tests it was meant to run.
- Pure helpers could run under `pytest` without Blender once split out of
  `utils.py` (section 3). The slicing codec, `find_common_name` and
  `extract_dimensions_of_grid` have no direct tests; the volume and slice
  helpers are tested through the nodes, and only `nearest_positions` on
  its own.

## 7. Documentation

- `docs/source/modules/` has pages for `utils`, `blendernc`, `handlers`,
  `messages`, `operators`, `panels`, `sockets` and `nodes`, but none for
  `decorators`, `node_utils`, `menus`, `nodetree`, `properties`,
  `panels_draw`, `volume_utils`, `shader_utils` or `shader_nodes`, so
  about half of the numpydoc docstrings are not rendered.
- The user guides do not mention the Colormap shader node or the Debug
  node. The node editor's Settings panel ("Lock range") is only mentioned
  in the Datacube Volume section, not for textures.
- `in_depth_guide.rst` has five commented-out image placeholders (marked
  TODO) for the Datacube Slice and Datacube Volume sections, waiting for
  UI screenshots.
- Type hints are absent throughout; adding them to the pure helpers would
  let `autodoc_typehints = "description"` do useful work.

## Resolved since the first pass

Kept for traceability; all verified against the tree on 2026-11-17.

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

Resolved between 2026-11-13 and 2026-11-17:

- "Apply Material" builds and assigns a material instead of being a stub.
- The quickstart guide describes the step field, the "Suggest step"
  toggle and "Apply Material"; the "Animate datacube" instruction is gone.
- `add_custom_node_to_menu` only adds the BlenderNC menu in
  `BlenderNCNodeTree` editors.
- Modifiers are applied through `context.temp_override`
  (`operators._apply_modifier`), so a bake keeps the active object and
  works in background mode.
- `test_file_missing` checks that the data item is cleared and the import
  node disconnected.
- Tests now cover `(x, y)`-ordered variables, 2-D coordinates and several
  import nodes (`synthetic_grid.test.py`, `custom_tree.test.py`).
- `black --check` passes on the whole repository and `ruff` finds no
  unused imports or names; the trailing spaces and the stray space in
  `suggested_step :` are gone.
- `develop.blend`, `resolution.blend` and their `.blend1` backups are no
  longer tracked and are listed in `.gitignore`.
- The manifest's empty `wheels = []` is intended: `build_extension.yml`
  fills it at build time with `update_wheels.py`.

Resolved on 2026-11-17 (section 1, and what it touched):

- **Apply Material.** The operator has a docstring and resolves its own
  defaults: no properties means the panel's "Datacube Texture" node. The
  Datacube Texture node has the same button, enabled once its texture is
  written. The variable's material goes into the first slot instead of
  a new slot per click. The material is built by
  `shader_utils.texture_material`, which shares the Attribute + Min/Max +
  Map Range block with `volume_material` (`_range_nodes`). A missing node,
  object or texture is reported instead of raising (was a crash). The
  `create_Shader_nodes` helper and the `basic_shader_nodes` /
  `VOLUME_MATERIAL_*` constants are gone.
- **The panel no longer rebakes on a variable change.**
  `DatacubeGrid.needs_bake` compares the object name, the linked
  coordinates (`baked_coords`) and the slicing, so only the coordinate
  drop-downs and the step rebake the grid. A variable change relinks the
  texture and swaps the material directly (`_follow_variable_material`).
  This also fixes the material lagging one variable behind, since the old
  rebake ran before the texture was relinked.
- **A failed panel bake no longer raises** out of the property callback:
  `_bake_ui_grid` catches the `RuntimeError` (was a crash).
- **`DatacubeSlice`** keeps a range along a 1-D coordinate, by index
  (First/Last) or by value (Minimum/Maximum), shows what it keeps, and is
  listed as "Slice Range" in the Selection menu. `record_selector` merges
  a range with a stride on the same dimension, so Slice, Subsample and
  Resolution combine in any order.
- **Texture sub-menu** renamed to `BlenderNCNodeTexture` /
  `NODE_MT_category_blendernc_texture`.
- **Datacube Volume.** Unevenly spaced and curvilinear horizontal
  coordinates are resampled onto a regular grid by nearest neighbour, and
  the node, status bar and log say so. Descending coordinates are flipped.
  An evenly spaced vertical coordinate sets the voxel height, with CF
  `positive = "down"` pointing down, and Vertical scale multiplies it.
  Deleting the node deletes its VDB folder once no Volume reads from it.
  An unsaved file shows a warning on the node. "Lock range" keeps the
  stored range, and the range takes one pass over a lazy array instead of
  two. "Animate along" lists the dims left after slicing.
- **Dropped:** playing "Current frame" volumes without BlenderNC
  installed is not a supported setup.
- `Material.use_nodes`, deprecated in Blender 5.2, is no longer set.
- `DatacubeVariable.update` uses `NO_SELECTION` instead of `"No var"`.
- Tests: Apply Material from the panel and from a node, the variable
  change without a rebake, a failed panel bake, eleven Slice tests
  (`tests/slice.test.py`) and thirteen new Volume tests for placement,
  range, dims and files.
