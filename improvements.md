# Possible improvements for `blendernc/`

Findings from a re-read of every module, test, doc and CI file on
2026-11-13 (branch `Blender5.2`), re-checked on 2026-11-17 (branch
`voxel` at `5dff8cb`). The section 1 work and the two crash fixes done on
2026-11-17 are listed under "Resolved" at the end. It covers design,
robustness, cleanup, tests and docs. Line numbers refer to the working tree
after that work.


## 1. Work in progress to finish

- **Datacube Volume follow-ups** (left after the 2026-11-17 work).
  - Nothing packs the VDB files into the .blend file. In an unsaved file
    they go to Blender's temporary folder, and the node only warns (the
    chosen behaviour); nothing moves them when the file is first saved.
  - Curvilinear resampling (`volume_utils.curvilinear_placement`,
    `volume_utils.py:544`) is nearest neighbour at the source resolution,
    and it treats longitude as a plain number: a grid that crosses the
    dateline (179° to -179°) is resampled over the whole -180 to 180 range.
  - "Lock range" (on by default) keeps the stored range when the
    variable changes, for textures (`utils.write_field_range`) and
    volumes (`volume_utils.bake_range`) alike, so a new variable is
    coloured with the old one's range. The lock could store which
    variable the range belongs to and only hold it for that variable.
  - Releasing "Lock range" recomputes the texture ranges
    (`utils.update_lock_range`, `utils.py:1500`) but not the volume
    ranges, which wait for the next bake.
  - A node's VDB sub-folder is named after its tree and itself
    (`vdb_directory`, `volume_utils.py:744`); renaming either leaves the
    old folder behind.
  - Add more property types, for example temperature, and velocities. In
    the case of velocities, we will need a supplementary node that merges
    u,v, and w velocities to then pass it as a vector.

## 2. Robustness

- **Shared mutable cache on a class attribute.** `BNC_data.dict`
  (`properties.py:26`) is one `defaultdict` for every node in every file;
  `initialize_BNC_datastructs` (`decorators.py:282`) assigns `item.dict`
  on a transient `PropertyGroup` wrapper, so the per-item assignment has no
  lasting effect. A small cache module (`get`, `put`, `drop`, keyed by the
  full path, with reference counts) would make the lifetime explicit.
- **Read paths create data.** `_get_ui_node` (`ui.py:128-131`) and both
  panel draw functions (`panels_draw.py:42, 80`) call
  `create_blenderncnodetree`, so drawing a drop-down or the panel can
  create a node group. Look the tree up with `bpy.data.node_groups.get` in
  read paths.
- **`create_blenderncnodetree` ignores the tree type.** It returns any
  group with the requested name (`node_utils.py:136-137`).
  `assign_modifier_to_object` (`utils.py:681`) asks for a geometry tree
  named after the grid object, so a grid object called "BLENDERNC" (or
  after any other node group) gets the wrong kind of tree for its
  modifier, and the bake fails. Check `bl_idname`, and pick a new name
  when the existing group has another type.
- **`get_grid_coords` has no missing-key handling.** `utils.py:398`
  passes the socket value to `get_data_from_datastruct`, which indexes
  `dataset[var_name]` (`utils.py:358`). A renamed coordinate raises
  `KeyError`, and an unloaded dataset raises `TypeError`.
- **`_clear_default_values` matches on `bl_label`.** `decorators.py:63`
  compares `input_socket.bl_label != "Object"`; `isinstance(socket,
  bpy.types.NodeSocketObject)` is the stable test.
- **Node mappings and their locations must stay in step.** `basic_nodes`
  and `locations` (`node_utils.py:16-45`) are parallel module constants, as
  are `COLORBAR_MATERIAL_NODES` and `COLORBAR_MATERIAL_LOCATIONS`
  (`shader_utils.py:248-264`); `texture_material` and `volume_material`
  extend `RANGE_NODE_LOCATIONS` by hand (`shader_utils.py:89, 336`).
  `create_nodes` uses `zip(strict=True)`, so a node added to one list but
  not the other raises. Put the location inside each entry.
- **Grid and Volume nodes run operators from `update`.**
  `DatacubeGrid.update` and `DatacubeVolume.update` call `bpy.ops` to
  rebake (`nodes.py:366, 963`); the operator creates objects, applies
  modifiers and calls `update()` again. `decorators.py:160-163` notes that
  Blender is still walking the tree during `update` and moves link edits
  to a timer for that reason. Rebakes could be deferred the same way.

## 3. Design and architecture

- **Selections do not reach a grid baked from coordinates.** Select,
  Subsample, and a Slice of a data variable, record along the Variable
  chain. A Datacube Grid whose X and Y come from a Coords node only sees
  them through a linked Z, so the texture of a subsampled variable does not
  fit the grid (the Texture node says to bake the grid from the variable's
  coordinates). A Slice fed a datacube or a coordinate, and Resolution,
  reach the grid; Subsample could take a datacube the same way. Volumes
  are unaffected: they read their coordinates from the sliced variable.
- **`decorators.py` contains UI logic.** `_create_UI_nodes`
  (`decorators.py:302-336`) builds the node tree, toggles panel draw
  functions and reads scene properties; it belongs with the operators or
  in a `ui.py` module.
- **`check_if_node_tree_exists` does three unrelated things**
  (`decorators.py:362-380`), depending on `bl_idname`. For the UI property
  group it builds nodes and never calls the wrapped function. For the
  import operator it resolves the node through `_use_import_node`. For
  nodes it only resolves names. `_use_import_node` and the Apply Material
  operator, which now resolves its own defaults, show the explicit style
  the remaining branches could follow.
- **`create_nodes` mutates its input.** It writes `"node"` into each
  entry and may add a `"NodeGroupOutput"` entry (`node_utils.py:185,
  194`). `_create_UI_nodes` passes the module constant `basic_nodes`
  (`decorators.py:325`), so stale node references survive across trees
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
  tests and shrink `utils.py`, which has grown to 1822 lines.
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
  `utils.py:561-563` drops the separator and overwrites the header; a
  parameter on `get_dims` would remove the coupling.
- **The datacube path lives in three places** (`datacube_file` on the
  node, `datacube_file` on the scene properties, `datafile` on the data
  item) and is synced by hand in `Import_OT_mfdataset.execute`
  (`operators.py:83-89`), `_create_UI_nodes` (`decorators.py:333`) and
  `DatacubeImport.update` (`nodes.py:124-136`).
- **Two step properties.** `BlenderNC_UI_Properties.step`
  (`properties.py:57`) mirrors `DatacubeResolution.step` through
  `update_step_UI` (`utils.py:686-700`). The panel already draws the
  node's `suggested_step` directly (`panels_draw.py:83`); drawing its
  `step` the same way would remove the mirror.

## 4. Dead code and cleanup

- Public names kept on purpose: `get_2D_coords`, `bNC_update_attributes`
  (registered handler) and `BNC_datastructs` (stored in .blend files).
  Rename them only with a migration.

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
- `tests/unit/test_core.py` runs `blendernc.core` under `pytest`
  without Blender (35 tests). `get_2D_coords`, `stack_2D_coords`,
  `extract_dimensions_of_grid`, `vertical_placement`,
  `curvilinear_placement` and `frame_array` still have no direct unit
  tests; the Blender tests cover them through the nodes.

## 7. Documentation

- `docs/source/modules/` has pages for `core`, `utils`, `ui`,
  `blendernc`, `handlers`, `messages`, `operators`, `panels`, `sockets`
  and `nodes`, but none for
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


## 8. CI

- The unit tests of `blendernc.core` (`python -m pytest`, configured in
  `pyproject.toml`; needs numpy, xarray, scipy and pytest) do not run in
  CI yet; `.github/workflows/test.yml` only runs the Blender tests.
- ci(pre-commit.ci) always fails the Lint Commit. Brainstorm a way to fix it,
  either ignore it in the commitlint test, or change simplify the message of
  pre-commit.ci.

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
- **The volume no longer rebakes on a variable change.** Like the grid, it
  is placed again only when its coordinates change:
  `volume_utils.placement_key` digests the layout, the sizes and the
  coordinate values of the volume's axes, stored as `baked_placement`.
  When the tree changes and the key is unchanged (another variable, another
  index of a Select over time), `bake_volume(..., keep_placement=True)`
  rewrites the values only: it reuses the cached placement, swaps the
  material and reports no notes.
- **The volume keeps the user's transform.** The node records the placement
  it applied last (`placed_location`, `placed_scale`), and
  `volume_utils.place_object` applies the user's move, rotation and scale
  on top of the new one, for every bake, the "Bake Volume" button and
  Vertical scale included. Volumes baked before have no recorded placement
  and are placed afresh once.
- **Coords and Variable outputs follow the dataset.**
  `node_utils.sync_string_outputs` makes a node's outputs one string socket
  per name: outputs still listed keep their links, the others are removed
  (was: appended forever, the "Output sockets accumulate" item). Datacube
  Coords and Datacube Variable use it, and `create_datastruct` refreshes
  the nodes after an Import node whose file changed (they kept reading the
  released dataset). The Variable node has one output per variable up to
  `MAX_VARIABLE_OUTPUTS` (10); with more, a drop-down and a single
  `"Variable"` output, kept when another variable is picked.
  `DatacubeVariable.pick` returns the output carrying a variable, which the
  panel links to the Datacube Texture node in either mode.
- **Datacube Animate Texture works like Datacube Texture.** Both derive from
  `nodes.PointTextureNode`: the attribute is written as soon as the node
  updates (for the animation, the frame shown), `written` and `message`
  are kept, a new or unlinked variable removes the old attribute, a refused
  variable is reported on the node and logged, and the node has the "Apply
  Material" button. The animation stores the range of the first frame it
  loads (honouring "Lock range"); `write_frame`, called by
  `bNC_update_attributes` on every frame, leaves it alone. The animated
  dimension is found by `utils.animation_dim`, preferring the dims the grid
  was baked on. "Lock range", `grid_material` and the operator accept both
  node types (`TEXTURE_NODE_IDNAMES`).
- **Section 3 design work.** The panel's callbacks, the tree it builds
  (`build_ui_tree`, was `decorators._create_UI_nodes`) and
  `use_import_node` live in `ui.py`; `utils.py` no longer imports
  `panels_draw`, and the `UI_*_NODE` labels sit in `node_utils.py` next to
  `UI_NODE_TREE`, used by `panels_draw.py` too.
  `check_if_node_tree_exists` is gone: the panel path calls
  `update_datacube_file_UI`, the Import node loads its own path
  (`DatacubeImport.load`), and the import operator resolves its node
  explicitly. The panel's import node is only ever given the panel's path,
  so the operator sets that path for it instead of writing both.
  `create_nodes` returns a new mapping and leaves its input alone. The
  panel's axis items come from `coordinate_items`, not from editing
  `get_dims` output. The panel draws the Resolution node's step, and the
  scene's `step` mirror, `update_step_UI` and the panel-step handler are
  gone (keyframes on the old panel step are dropped; keys on the node's
  step are applied by `bNC_apply_animated_steps`). The helpers that need
  no Blender moved to `blendernc.core` (`dataset`, `slicing`, `grid`,
  `fields`, `volume`); `utils.py` went from 1822 to about 680 lines and
  `volume_utils.py` from about 1080 to about 500. `blendernc/__init__.py`
  imports the add-on only when registering, so `blendernc.core` imports
  without Blender, and `tests/unit/test_core.py` tests it under `pytest`.
- **Section 4 cleanup.** The no-op `preferences.addons.get(...)` in
  `blendernc/__init__.py` and the root `__main__` block (which registered
  and unregistered at once) are gone. The panel path describes a datacube
  file or pattern, not "Folder with assets blend files". `register` and
  `unregister` return nothing. The Resolution node reads its dataset with
  `get_dataset`. `find_common_name` uses snake_case and a `zip` over
  consecutive names (same results), `name_match` lost its `pass` branch,
  and `get_datacube_path` has a numpydoc docstring.
  `is_single_input_linked` says what it does. `draw_var_and_coords`
  counts the Coords outputs without building a list, and no longer fails
  when the node is missing (was in section 2). The manifest asks for
  Blender 5.2.0. The removed `addon_updater` is no longer excluded in
  `.coveragerc`, `.pre-commit-config.yaml`, `.codeclimate.yml`, the lint
  workflow or mocked in `docs/source/conf.py`.
- **Dropped:** playing "Current frame" volumes without BlenderNC
  installed is not a supported setup.
- `Material.use_nodes`, deprecated in Blender 5.2, is no longer set.
- `DatacubeVariable.update` uses `NO_SELECTION` instead of `"No var"`.
- Tests: Apply Material from the panel and from a node, the variable
  change without a rebake, a failed panel bake, eleven Slice tests
  (`tests/slice.test.py`) and twenty-one new Volume tests for placement,
  range, dims, files, refreshing the values and keeping the user's
  transform.

Resolved on 2026-11-25:

- **Datacube Slice slices a datacube too.** Its input
  (`bNCVariableOrDatacubeSocket`, still named `"Variable"` for scripts)
  takes a variable or a datacube, and the output is of the same type. The
  node decides which links it keeps (`DatacubeSlice.accepts_link`, read by
  `decorators._accepts_link`), so nodes saved with a string input take
  datacubes too. The range is recorded the same way; after a datacube it
  reaches the Coords and Variable nodes after the Slice, so a grid baked
  from those coordinates is cropped like the variable and the texture fits
  it. A linked 1-D coordinate is sliced along itself: the node stores it in
  `datacube_coords`, starting from its full range, and hides the
  drop-down. Tests in `tests/slice.test.py`: the output following the
  input, other links removed, a node saved with a string input, a
  coordinate sliced along itself, a grid cropped by a sliced coordinate,
  the range reaching variables and coordinates, a cropped grid and texture
  rebaked when the range widens, and Resolution combining in either order.
- **The grid no longer drops the slicing of its first inputs.**
  `is_single_input_linked` copied each linked input's data item in turn,
  so the grid kept the last input's `slicing` only: a range on the X
  coordinate was lost when Y came from a Coords node before the Slice, or
  Z from a variable that never went through it. The decorator now hands
  every input's `slicing` to `DatacubeGrid.merge_input_slicings`, which
  uses `core.merge_slicings`: records shared before a branch are kept
  once, then what each input added after it, in socket order. Other
  nodes keep the last input's, so a texture still reads its variable's
  slicing. Two new tests in `tests/slice.test.py`.

Resolved on 2026-11-26:

- **Uneven vertical levels sit at their true depth.** OpenVDB voxels share
  one height, so `core.volume.vertical_placement` interpolates uneven,
  distinct levels linearly onto even steps between the top and bottom
  levels (`depth_interpolation`, applied by `Placement.apply` through
  `interpolate_levels`). Next to a missing level the nearer level is used,
  and `frame_array` now fills missing data after the placement, so
  background values are never blended in. The count follows the finest
  spacing, capped at twice the levels (`vertical_voxel_count`,
  `MAX_LEVEL_FACTOR`). The node's new "Vertical" (True depth, the default,
  or One voxel per level) and "Vertical voxels" (0 = automatic) settings
  are part of its signature and of `placement_key`, so changing them
  rebakes and places the volume again. Tests in `tests/unit/test_core.py`
  and `tests/volume.test.py`.
- **Volume files hold a mask grid, on a zero background.** Missing data
  is written as inactive voxels, but Blender's render-time interpolation
  blended the voxels next to it with the background (the field minimum),
  which gave values inside the colour range that are not in the data (a
  fringe along land and the sea floor). Now each file holds
  `<variable>_mask` too (`core.volume.mask_grid_name`), 1 where there is
  data, and the material's Principled Volume uses it as Density Attribute,
  so missing data has no density for any variable range. The values bleed
  two voxels into missing data (`core.volume.bleed_missing`, mean of valid
  face neighbours, `BLEED_VOXELS`), so the edges blend real values only;
  beyond, voxels are empty at zero (`volume_utils.BACKGROUND`). Infinite
  values count as missing, and curvilinear columns outside the data are
  NaN before the fill. Setting the Density Attribute also stops a variable
  called `density` from multiplying its own density. `write_vdb` takes a
  dict of named grids, ready for a vector grid. Checked with Cycles and
  EEVEE renders of a coastline: the density ends where the data does.
  Tests `test_missing_data_is_masked`, `test_density_material` and the
  unit tests for `frame_grids` and `bleed_missing`.
