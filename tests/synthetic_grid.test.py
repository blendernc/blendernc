"""Bake grids from synthetic xarray datasets of increasing dimensionality.

Three datasets are generated on the fly with a random-noise variable:

* ``(X, Y)``: the variable itself becomes the Z coordinate of the grid.
* ``(X, Y, time)``: the grid is flat and a Datacube Animate Texture node
  writes the variable onto the mesh for the current frame.
* ``(X, Y, Z, time)``: a Datacube Select node picks one vertical level before
  the variable is animated as above.

The Datacube Texture node is run against the same three datasets: it writes
the 2-D field and refuses the 3-D and 4-D ones with a message naming the
node to use instead.

Axis names are never hard coded: the horizontal axes come from the dataset
through :func:`blendernc.utils.get_surface_dims`, the time axis from its
``datetime64`` dtype and the vertical axis is whatever remains.
"""

import os
import re
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

import bpy
import numpy as np
import xarray as xr
from bpy_extras import anim_utils

from blendernc.blendernc import register_handlers
from blendernc.decorators import flush_pending_unlinks
from blendernc.handlers import bNC_update_attributes
from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import (
    GRID_DIMS_PROPERTY,
    MAX_VERTEX_SAMPLES,
    RANGE_PROPERTIES,
    dataset_engine,
    get_dataset,
    get_surface_dims,
)

NX, NY, NZ, NT = 12, 8, 4, 5
VARIABLE = "noise"


# --------------------------------------------------------------------------
# Synthetic data
# --------------------------------------------------------------------------


def make_dataset(path, with_time=False, with_level=False, seed=0):
    """Write a netCDF file with a noise variable and return the dataset."""
    rng = np.random.default_rng(seed)
    coords = {
        "X": ("X", np.linspace(0.0, 360.0, NX, endpoint=False)),
        "Y": ("Y", np.linspace(-80.0, 80.0, NY)),
    }
    dims, shape = ["Y", "X"], [NY, NX]
    if with_level:
        coords["Z"] = ("Z", np.linspace(0.0, 300.0, NZ))
        dims.insert(0, "Z")
        shape.insert(0, NZ)
    if with_time:
        start = np.datetime64("2000-01-01")
        coords["time"] = ("time", start + np.arange(NT).astype("timedelta64[D]"))
        dims.insert(0, "time")
        shape.insert(0, NT)
    dataset = xr.Dataset({VARIABLE: (dims, rng.standard_normal(shape))}, coords=coords)
    dataset.to_netcdf(path)
    return dataset


def horizontal_axes(dataset):
    """Return ``(x_name, y_name)`` detected from the dataset's dimension names."""
    surface = get_surface_dims(dataset)
    x_like = [d for d in surface if re.search(r"(^|[^a-z])(x|lon)", d.lower())]
    y_like = [d for d in surface if re.search(r"(^|[^a-z])(y|lat)", d.lower())]
    assert len(x_like) == 1 and len(y_like) == 1, surface
    return x_like[0], y_like[0]


def time_axis(dataset):
    """Return the name of the datetime dimension, or ``None``."""
    for dim in dataset.dims:
        if np.issubdtype(dataset[dim].dtype, np.datetime64):
            return dim
    return None


def vertical_axis(dataset):
    """Return the dimension that is neither horizontal nor time, or ``None``."""
    taken = set(get_surface_dims(dataset)) | {time_axis(dataset)}
    rest = [dim for dim in dataset[VARIABLE].dims if dim not in taken]
    return rest[0] if rest else None


# --------------------------------------------------------------------------
# Mesh helpers
# --------------------------------------------------------------------------


def vertex_positions(obj):
    """Vertex coordinates of a mesh object as an ``(n, 3)`` array."""
    count = len(obj.data.vertices)
    positions = np.empty(count * 3)
    obj.data.vertices.foreach_get("co", positions)
    return positions.reshape(count, 3)


def field_at_vertices(obj, field, x_name, y_name):
    """Values of ``field`` at each vertex's (x, y), in mesh order."""
    positions = vertex_positions(obj)
    points = {
        x_name: xr.DataArray(positions[:, 0], dims="vertex"),
        y_name: xr.DataArray(positions[:, 1], dims="vertex"),
    }
    return field.sel(points, method="nearest").values


def write_field(path, dims, seed=0):
    """Write a noise variable with the given dimension order; return it."""
    rng = np.random.default_rng(seed)
    sizes = {"X": NX, "Y": NY}
    dataset = xr.Dataset(
        {VARIABLE: (dims, rng.standard_normal([sizes[d] for d in dims]))},
        coords={
            "X": np.linspace(0.0, 330.0, NX),
            "Y": np.linspace(-70.0, 70.0, NY),
        },
    )
    dataset.to_netcdf(path)
    return dataset


def point_attribute(obj, name):
    """Values of a float point attribute as a 1-D array."""
    attribute = obj.data.attributes[name]
    values = np.empty(len(attribute.data))
    attribute.data.foreach_get("value", values)
    return values


def edge_steps(obj):
    """Absolute ``(dx, dy)`` of every edge of a mesh object."""
    positions = vertex_positions(obj)
    count = len(obj.data.edges)
    pairs = np.empty(count * 2, dtype=np.int64)
    obj.data.edges.foreach_get("vertices", pairs)
    pairs = pairs.reshape(count, 2)
    return np.abs(positions[pairs[:, 0], :2] - positions[pairs[:, 1], :2])


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class TestSyntheticGrids(unittest.TestCase):
    """Bake grids from generated datasets and check mesh and attributes."""

    @classmethod
    def setUpClass(cls):
        """Generate the three netCDF files in a temporary directory."""
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_")
        cls.files = {}
        cls.datasets = {}
        for key, with_time, with_level in (
            ("xy", False, False),
            ("xyt", True, False),
            ("xyzt", True, True),
        ):
            path = f"{cls.tmpdir}/{key}.nc"
            cls.datasets[key] = make_dataset(path, with_time, with_level)
            cls.files[key] = path

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary netCDF files."""
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        """Give every test its own node tree and grid object name."""
        self.tree_name = f"BNC_TEST_{self._testMethodName}"
        self.grid_name = f"Grid_{self._testMethodName}"
        self.tree = create_blenderncnodetree(self.tree_name)

    def tearDown(self):
        """Drop the node tree, the baked object and its mesh."""
        if self.grid_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[self.grid_name])
        if self.grid_name in bpy.data.meshes:
            bpy.data.meshes.remove(bpy.data.meshes[self.grid_name])
        bpy.data.node_groups.remove(self.tree)

    # -- pipeline -----------------------------------------------------------

    def build_pipeline(self, key, select_level=False, animate=False, texture=False):
        """Create the nodes, link them and bake the grid for dataset ``key``.

        With ``texture=True`` a Datacube Texture node is linked last and kept
        as ``self.texture_node``.
        """
        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        coords = tree.nodes.new("BlenderNCNodeCoords")
        variable = tree.nodes.new("BlenderNCNodeVariable")
        grid = tree.nodes.new("BlenderNCNodeGrid")

        import_node.datacube_file = self.files[key]
        datacube = "xarray datacube"
        tree.links.new(import_node.outputs[datacube], coords.inputs[datacube])
        tree.links.new(import_node.outputs[datacube], variable.inputs[datacube])

        dataset = get_dataset(import_node.BNC_datastructs[0])
        self.assertIsNotNone(dataset, "dataset was not loaded by the import node")
        var_name = list(dataset.data_vars)[0]
        variable.datacube_vars = var_name
        z_source = variable.outputs[var_name]

        if select_level:
            select = self.select_node = tree.nodes.new("BlenderNCNodeSelect")
            tree.links.new(z_source, select.inputs["Variable"])
            select.datacube_coords = vertical_axis(dataset)
            z_source = select.outputs["Variable"]

        x_name, y_name = horizontal_axes(dataset)
        tree.links.new(coords.outputs[x_name], grid.inputs["X"])
        tree.links.new(coords.outputs[y_name], grid.inputs["Y"])
        tree.links.new(z_source, grid.inputs["Z"])

        grid.grid_obj_name = self.grid_name
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=tree.name
        )
        grid.update()
        obj = bpy.data.objects[self.grid_name]

        if animate:
            node = tree.nodes.new("BlenderNCNodeAnimateTexture")
            tree.links.new(grid.outputs["Object"], node.inputs["Object"])
            tree.links.new(z_source, node.inputs["Variable"])
        if texture:
            self.texture_node = tree.nodes.new("BlenderNCNodeTexture")
            tree.links.new(grid.outputs["Object"], self.texture_node.inputs["Object"])
            tree.links.new(z_source, self.texture_node.inputs["Variable"])
        return obj, dataset, var_name

    def build_refused_texture(self, key, select_level=False):
        """Build a texture pipeline that must be refused; return the warning."""
        logger_name = bpy.types.Node.bl_rna_get_subclass_py(
            "BlenderNCNodeTexture"
        ).__module__
        with self.assertLogs(logger_name, level="WARNING") as logs:
            obj, _, _ = self.build_pipeline(key, select_level, texture=True)
        self.assertNotIn(VARIABLE, obj.data.attributes)
        message = self.texture_node.message
        self.assertTrue(message, "node shows no message")
        self.assertTrue(
            any(message.replace("\n", " ") in line for line in logs.output),
            f"message not logged: {message!r} not in {logs.output}",
        )
        return message

    # -- shared assertions --------------------------------------------------

    def assert_grid_topology(self, obj, dataset):
        """Vertex count and edge spacing must match the horizontal axes."""
        x_name, y_name = horizontal_axes(dataset)
        nx, ny = dataset.sizes[x_name], dataset.sizes[y_name]
        self.assertEqual(len(obj.data.vertices), nx * ny)

        positions = vertex_positions(obj)
        np.testing.assert_allclose(np.unique(positions[:, 0]), dataset[x_name].values)
        np.testing.assert_allclose(np.unique(positions[:, 1]), dataset[y_name].values)

        # Every edge joins horizontally or vertically adjacent grid points.
        dx = float(np.diff(dataset[x_name].values)[0])
        dy = float(np.diff(dataset[y_name].values)[0])
        steps = edge_steps(obj)
        along_x = np.isclose(steps[:, 0], dx, atol=1e-4) & np.isclose(steps[:, 1], 0)
        along_y = np.isclose(steps[:, 1], dy, atol=1e-4) & np.isclose(steps[:, 0], 0)
        self.assertTrue(np.all(along_x | along_y), "edges join non-adjacent points")

    def assert_frame_attribute(self, obj, expected, frame):
        """After a frame change the point attribute holds ``expected``."""
        scene = bpy.context.scene
        scene.frame_set(frame)
        bNC_update_attributes(scene)  # same handler; surfaces exceptions
        self.assertIn(VARIABLE, obj.data.attributes)
        values = point_attribute(obj, VARIABLE)
        np.testing.assert_allclose(
            np.sort(values), np.sort(expected.ravel()), rtol=1e-6, atol=1e-6
        )

    # -- cases --------------------------------------------------------------

    def test_xy_variable_as_z(self):
        """(X, Y): the baked mesh takes its Z coordinate from the variable."""
        obj, dataset, var_name = self.build_pipeline("xy")
        self.assert_grid_topology(obj, dataset)
        z_values = vertex_positions(obj)[:, 2]
        np.testing.assert_allclose(
            np.sort(z_values), np.sort(dataset[var_name].values.ravel()), rtol=1e-6
        )

    def test_xyt_animated_texture(self):
        """(X, Y, time): flat grid plus an attribute that follows the frame."""
        obj, dataset, var_name = self.build_pipeline("xyt", animate=True)
        self.assert_grid_topology(obj, dataset)
        np.testing.assert_allclose(vertex_positions(obj)[:, 2], 0.0)

        t_name = time_axis(dataset)
        for frame in (0, NT - 1):
            expected = dataset[var_name].isel({t_name: frame}).values
            self.assert_frame_attribute(obj, expected, frame)

    def test_xy_static_texture(self):
        """(X, Y): the texture node writes the field with no frame change."""
        obj, dataset, var_name = self.build_pipeline("xy", texture=True)
        self.assertEqual(self.texture_node.message, "")
        self.assertIn(VARIABLE, obj.data.attributes)
        values = point_attribute(obj, VARIABLE)
        np.testing.assert_allclose(
            np.sort(values), np.sort(dataset[var_name].values.ravel()), rtol=1e-6
        )
        field = dataset[var_name].values
        low, high = RANGE_PROPERTIES
        self.assertAlmostEqual(obj.data[low], float(field.min()), places=6)
        self.assertAlmostEqual(obj.data[high], float(field.max()), places=6)

    def test_texture_range_ignores_nan(self):
        """NaN samples are written as 0 but left out of the stored range."""
        path = f"{self.tmpdir}/holes.nc"
        rng = np.random.default_rng(3)
        field = rng.uniform(5.0, 9.0, (NY, NX))
        field[0, 0] = field[NY - 1, NX - 1] = np.nan
        xr.Dataset(
            {VARIABLE: (("Y", "X"), field)},
            coords={"X": np.arange(float(NX)), "Y": np.arange(float(NY))},
        ).to_netcdf(path)
        self.files["holes"] = path
        self.datasets["holes"] = xr.open_dataset(path)

        obj, _, _ = self.build_pipeline("holes", texture=True)
        self.assertEqual(self.texture_node.message, "")
        values = point_attribute(obj, VARIABLE)
        self.assertEqual(np.count_nonzero(values == 0.0), 2)
        low, high = RANGE_PROPERTIES
        self.assertAlmostEqual(obj.data[low], float(np.nanmin(field)), places=5)
        self.assertAlmostEqual(obj.data[high], float(np.nanmax(field)), places=5)
        self.assertGreaterEqual(obj.data[low], 5.0)

    def test_xy_texture_removed_when_variable_unlinked(self):
        """Unlinking the Variable input deletes the attribute it wrote."""
        obj, _, _ = self.build_pipeline("xy", texture=True)
        self.assertIn(VARIABLE, obj.data.attributes)
        socket = self.texture_node.inputs["Variable"]
        self.tree.links.remove(socket.links[0])
        self.assertNotIn(VARIABLE, obj.data.attributes)
        self.assertEqual(self.texture_node.written, "")
        self.assertEqual(self.texture_node.message, "")

    def test_xyt_texture_refused_suggests_animate(self):
        """(X, Y, time): a 3-D field is refused and Animate Texture suggested."""
        message = self.build_refused_texture("xyt")
        self.assertIn("3D", message)
        self.assertIn("Animate Texture", message)

    def test_xyzt_texture_refused_suggests_select(self):
        """(X, Y, Z, time): a 4-D field is refused and Datacube Select suggested."""
        message = self.build_refused_texture("xyzt")
        self.assertIn("4D", message)
        self.assertIn("Datacube Select", message)

    def test_xyzt_selected_level_texture_suggests_animate(self):
        """A selected level leaves a 3-D field, so Animate Texture is suggested."""
        message = self.build_refused_texture("xyzt", select_level=True)
        self.assertIn("3D", message)
        self.assertIn("Animate Texture", message)

    def test_xyzt_select_level_and_animate(self):
        """(X, Y, Z, time): one level is selected, then animated in time."""
        obj, dataset, var_name = self.build_pipeline(
            "xyzt", select_level=True, animate=True
        )
        self.assert_grid_topology(obj, dataset)
        np.testing.assert_allclose(vertex_positions(obj)[:, 2], 0.0)

        t_name, z_name = time_axis(dataset), vertical_axis(dataset)
        for level in (0, NZ - 1, NZ + 5):  # the last one is clamped to NZ - 1
            self.select_node.index = level
            clamped = min(level, NZ - 1)
            for frame in (0, NT - 1):
                expected = (
                    dataset[var_name].isel({t_name: frame, z_name: clamped}).values
                )
                self.assert_frame_attribute(obj, expected, frame)

    def test_mismatched_link_is_removed(self):
        """Linking sockets of different types unlinks them with a warning."""
        obj, _, var_name = self.build_pipeline("xy")
        grid = next(n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeGrid")
        variable = next(
            n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeVariable"
        )
        texture = self.tree.nodes.new("BlenderNCNodeTexture")
        logger_name = bpy.types.Node.bl_rna_get_subclass_py(
            "BlenderNCNodeTexture"
        ).__module__.rsplit(".", 1)[0]

        with self.assertLogs(logger_name, level="WARNING") as logs:
            self.tree.links.new(grid.outputs["Object"], texture.inputs["Variable"])
            self.tree.links.new(variable.outputs[var_name], texture.inputs["Object"])
        # Removal happens from a timer once Blender is done updating the tree;
        # timers do not run in background mode, so run it here.
        flush_pending_unlinks()
        self.assertFalse(texture.inputs["Variable"].is_linked)
        self.assertFalse(texture.inputs["Object"].is_linked)
        self.assertEqual(sum("link removed" in line for line in logs.output), 2)

        # Matching types still link and the texture is written.
        self.tree.links.new(grid.outputs["Object"], texture.inputs["Object"])
        self.tree.links.new(variable.outputs[var_name], texture.inputs["Variable"])
        self.assertEqual(texture.message, "")
        self.assertIn(VARIABLE, obj.data.attributes)

    # -- dimension order (potential bug: transpose assumed (y, x)) ----------

    def test_field_values_follow_vertices_for_both_dim_orders(self):
        """(Y, X) and (X, Y) variables give the same value at each vertex."""
        for dims in (("Y", "X"), ("X", "Y")):
            with self.subTest(dims=dims):
                key = "order_" + "".join(dims)
                path = f"{self.tmpdir}/{key}.nc"
                self.datasets[key] = write_field(path, dims)
                self.files[key] = path
                obj, dataset, var_name = self.build_pipeline(key, texture=True)
                self.assertEqual(self.texture_node.message, "")
                self.assertEqual(obj.data[GRID_DIMS_PROPERTY], "Y,X")
                expected = field_at_vertices(obj, dataset[var_name], "X", "Y")
                # Z comes from the variable, and so does the texture.
                np.testing.assert_allclose(
                    vertex_positions(obj)[:, 2], expected, rtol=1e-5, atol=1e-6
                )
                np.testing.assert_allclose(
                    point_attribute(obj, VARIABLE), expected, rtol=1e-5, atol=1e-6
                )
                self.tearDown()
                self.setUp()

    # -- two 2-D coordinates (potential bug: (ny, ny) vertex counts) --------

    def test_curvilinear_2d_coords_bake_a_connected_grid(self):
        """2-D lon/lat of shape (ny, nx) give nx * ny vertices, edges adjacent."""
        ny, nx = 5, 9
        j, i = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
        lon, lat = i * 10.0 + j * 1.0, j * 10.0 + i * 0.5
        path = f"{self.tmpdir}/curvilinear.nc"
        xr.Dataset(
            {VARIABLE: (("y", "x"), np.zeros((ny, nx)))},
            coords={"lon": (("y", "x"), lon), "lat": (("y", "x"), lat)},
        ).to_netcdf(path)

        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        coords = tree.nodes.new("BlenderNCNodeCoords")
        grid = tree.nodes.new("BlenderNCNodeGrid")
        import_node.datacube_file = path
        tree.links.new(import_node.outputs[0], coords.inputs[0])
        tree.links.new(coords.outputs["lon"], grid.inputs["X"])
        tree.links.new(coords.outputs["lat"], grid.inputs["Y"])
        grid.grid_obj_name = self.grid_name
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=tree.name
        )
        obj = bpy.data.objects[self.grid_name]

        self.assertEqual(len(obj.data.vertices), nx * ny)
        self.assertEqual(len(obj.data.edges), (nx - 1) * ny + nx * (ny - 1))
        index = {
            (round(float(a), 3), round(float(b), 3)): (jj, ii)
            for (jj, ii), a, b in zip(np.ndindex(ny, nx), lon.ravel(), lat.ravel())
        }
        cells = [index[(round(p[0], 3), round(p[1], 3))] for p in vertex_positions(obj)]
        pairs = np.empty(len(obj.data.edges) * 2, dtype=np.int64)
        obj.data.edges.foreach_get("vertices", pairs)
        for a, b in pairs.reshape(-1, 2):
            (ja, ia), (jb, ib) = cells[a], cells[b]
            self.assertEqual(abs(ja - jb) + abs(ia - ib), 1)

    # -- dataset cache (potential bugs: basename keys, free, engines) -------

    def test_same_basename_in_two_folders(self):
        """Files with one name in two folders are two datasets, not one."""
        nodes = []
        for value in (1.0, 2.0):
            folder = f"{self.tmpdir}/folder{int(value)}"
            os.makedirs(folder, exist_ok=True)
            xr.Dataset({VARIABLE: (("Y", "X"), np.full((NY, NX), value))}).to_netcdf(
                f"{folder}/same.nc"
            )
            node = self.tree.nodes.new("BlenderNCNodeImport")
            node.datacube_file = f"{folder}/same.nc"
            nodes.append(node)
        datasets = [get_dataset(n.BNC_datastructs[0]) for n in nodes]
        means = [float(d[VARIABLE].mean()) for d in datasets]
        self.assertEqual(means, [1.0, 2.0])

    def test_deleting_one_import_node_keeps_shared_dataset(self):
        """The cache entry lives until the last import node using it is gone."""
        first = self.tree.nodes.new("BlenderNCNodeImport")
        second = self.tree.nodes.new("BlenderNCNodeImport")
        first.datacube_file = second.datacube_file = self.files["xy"]
        key = second.BNC_datastructs[0].filename
        cache = second.BNC_datastructs[0].dict
        self.assertIs(get_dataset(first.BNC_datastructs[0]), cache[key])

        self.tree.nodes.remove(first)
        self.assertIsNotNone(get_dataset(second.BNC_datastructs[0]))
        self.tree.nodes.remove(second)
        self.assertNotIn(key, cache)

    def test_zarr_store_opens_with_zarr_engine(self):
        """A .zarr store is opened with the zarr engine."""
        path = f"{self.tmpdir}/cube.zarr"
        self.datasets["xy"].to_zarr(path, mode="w")
        self.assertEqual(dataset_engine(path), "zarr")
        self.assertEqual(dataset_engine("a/b.GRIB2"), "cfgrib")
        self.assertIsNone(dataset_engine("a/b.nc"))
        node = self.tree.nodes.new("BlenderNCNodeImport")
        node.datacube_file = path
        dataset = get_dataset(node.BNC_datastructs[0])
        self.assertIsNotNone(dataset)
        self.assertIn(VARIABLE, dataset)

    # -- registration and baking side effects --------------------------------

    def test_frame_handler_registered_once(self):
        """Registering handlers again leaves exactly one copy in each list."""
        register_handlers()
        register_handlers()
        for handler_list in (
            bpy.app.handlers.frame_change_pre,
            bpy.app.handlers.render_pre,
        ):
            copies = [
                f
                for f in handler_list
                if getattr(f, "__module__", None) == bNC_update_attributes.__module__
                and getattr(f, "__name__", None) == bNC_update_attributes.__name__
            ]
            self.assertEqual(len(copies), 1)

    def test_bake_keeps_active_object(self):
        """Baking applies its modifiers without changing the active object."""
        other = bpy.data.objects.new(f"Other_{self._testMethodName}", None)
        bpy.context.collection.objects.link(other)
        bpy.context.view_layer.objects.active = other
        try:
            self.build_pipeline("xy")
            self.assertEqual(bpy.context.view_layer.objects.active, other)
        finally:
            bpy.data.objects.remove(other)

    def test_rebake_after_grid_object_deleted(self):
        """Deleting the grid object but not its mesh still lets it rebake."""
        obj, dataset, _ = self.build_pipeline("xy")
        grid = next(n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeGrid")
        bpy.data.objects.remove(obj)
        self.assertIn(self.grid_name, bpy.data.meshes)
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=self.tree.name
        )
        self.assert_grid_topology(bpy.data.objects[self.grid_name], dataset)

    def test_grid_name_taken_by_non_mesh_is_reported(self):
        """A non-mesh object with the grid's name cancels with a report."""
        empty = bpy.data.objects.new(self.grid_name, None)
        try:
            with self.assertRaisesRegex(RuntimeError, "choose another grid name"):
                self.build_pipeline("xy")
        finally:
            bpy.data.objects.remove(empty)

    def test_enum_items_are_kept_alive(self):
        """Enum callbacks keep their lists referenced; the panel copy is separate."""
        from blendernc import utils

        obj, dataset, var_name = self.build_pipeline("xy")
        variable = next(
            n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeVariable"
        )
        items = utils.get_possible_variables(variable, bpy.context)
        self.assertIn(var_name, [item[0] for item in items if item])
        self.assertTrue(any(kept is items for kept in utils._ENUM_ITEMS.values()))

        coords = next(
            n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeCoords"
        )
        before = list(utils.get_possible_coordinates(coords, bpy.context))
        utils.get_possible_coordinates_UI(None, bpy.context)  # edits its own copy
        self.assertEqual(utils.get_possible_coordinates(coords, bpy.context), before)

    def build_resolution_texture_tree(self):
        """Full-resolution tree with a resolution node and a linked texture."""
        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        resolution = tree.nodes.new("BlenderNCNodeResolution")
        coords = tree.nodes.new("BlenderNCNodeCoords")
        variable = tree.nodes.new("BlenderNCNodeVariable")
        grid = tree.nodes.new("BlenderNCNodeGrid")
        texture = tree.nodes.new("BlenderNCNodeTexture")

        resolution.suggested_step = False
        resolution.step = 1  # full resolution for the first bake
        import_node.datacube_file = self.files["xy"]
        datacube = "xarray datacube"
        tree.links.new(import_node.outputs[datacube], resolution.inputs[datacube])
        tree.links.new(resolution.outputs[datacube], coords.inputs[datacube])
        tree.links.new(resolution.outputs[datacube], variable.inputs[datacube])
        variable.datacube_vars = VARIABLE
        x_name, y_name = horizontal_axes(self.datasets["xy"])
        tree.links.new(coords.outputs[x_name], grid.inputs["X"])
        tree.links.new(coords.outputs[y_name], grid.inputs["Y"])
        grid.grid_obj_name = self.grid_name
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=tree.name
        )
        obj = bpy.data.objects[self.grid_name]
        tree.links.new(grid.outputs["Object"], texture.inputs["Object"])
        tree.links.new(variable.outputs[VARIABLE], texture.inputs["Variable"])
        return obj, resolution, texture

    def test_resolution_change_rebakes_grid_and_texture(self):
        """Changing the step on the node rebakes the grid and the texture."""
        obj, resolution, texture = self.build_resolution_texture_tree()
        self.assertEqual(len(obj.data.vertices), NX * NY)
        self.assertEqual(texture.message, "")

        resolution.step = 2
        expected = len(range(0, NX, 2)) * len(range(0, NY, 2))
        self.assertEqual(len(obj.data.vertices), expected)
        self.assertEqual(texture.message, "")
        self.assertEqual(len(obj.data.attributes[VARIABLE].data), expected)

    def test_keyframed_node_step_rebakes(self):
        """Keyframing the resolution node's step rebakes on frame change."""
        obj, resolution, texture = self.build_resolution_texture_tree()
        scene, tree = bpy.context.scene, self.tree
        scene.frame_set(1)
        try:
            resolution.keyframe_insert("step", frame=1)
            anim = tree.animation_data
            bag = anim_utils.action_get_channelbag_for_slot(
                anim.action, anim.action_slot
            )
            path = f'nodes["{resolution.name}"].step'
            bag.fcurves.find(path).keyframe_points.insert(10, 2)
            for frame, step in ((10, 2), (1, 1)):
                scene.frame_set(frame)
                expected = len(range(0, NX, step)) * len(range(0, NY, step))
                self.assertEqual(resolution.step, step)
                self.assertEqual(len(obj.data.vertices), expected)
                self.assertEqual(len(obj.data.attributes[VARIABLE].data), expected)
                self.assertEqual(texture.message, "")
        finally:
            tree.animation_data_clear()
            scene.frame_set(1)

    def test_lock_range_setting(self):
        """Unlocked, the range follows the data; locked, it stays fixed."""
        settings = bpy.context.scene.BlenderNC_Settings
        panel = getattr(bpy.types, "BLENDERNC_NODE_PT_SETTINGS")
        self.assertEqual(panel.bl_space_type, "NODE_EDITOR")
        editing = SimpleNamespace(space_data=SimpleNamespace(tree_type=""))
        cases = (("BlenderNCNodeTree", True), ("ShaderNodeTree", False))
        for tree_type, shown in cases:
            editing.space_data.tree_type = tree_type
            self.assertEqual(panel.poll(editing), shown)
        field = self.datasets["xy"][VARIABLE].values
        strided = field[::2, ::2]
        low, high = RANGE_PROPERTIES
        obj, resolution, _ = self.build_resolution_texture_tree()
        try:
            settings.lock_range = True
            resolution.step = 2
            self.assertAlmostEqual(obj.data[low], float(field.min()), places=5)

            settings.lock_range = False  # releasing the lock recomputes
            self.assertAlmostEqual(obj.data[low], float(strided.min()), places=5)
            self.assertAlmostEqual(obj.data[high], float(strided.max()), places=5)

            resolution.step = 1
            self.assertAlmostEqual(obj.data[low], float(field.min()), places=5)
        finally:
            settings.lock_range = False

    def test_grid_material_follows_linked_texture(self):
        """Set Material gets the material named after the linked texture's variable."""
        obj, dataset, var_name = self.build_pipeline("xy", texture=True)
        grid = next(n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeGrid")
        set_material = bpy.data.node_groups["apply_grid_coords"].nodes["Set Material"]
        rebake = {"node_name": grid.name, "node_tree": self.tree.name}

        bpy.ops.blendernc.create_grid_from_coords(**rebake)
        self.assertIsNone(set_material.inputs["Material"].default_value)

        material = bpy.data.materials.new(var_name)
        try:
            bpy.ops.blendernc.create_grid_from_coords(**rebake)
            self.assertIs(set_material.inputs["Material"].default_value, material)
            self.assertIn(material, list(obj.data.materials))
            used = {p.material_index for p in obj.data.polygons}
            self.assertEqual({obj.data.materials[i] for i in used}, {material})
        finally:
            bpy.data.materials.remove(material)

    def test_apply_material_from_texture_node(self):
        """The node's Apply Material colours its object and reuses the slot."""
        obj, _, var_name = self.build_pipeline("xy", texture=True)
        apply = {"node_name": self.texture_node.name, "node_tree": self.tree.name}
        material = None
        try:
            for _ in range(2):  # a second click must not add a slot
                bpy.ops.blendernc.bake_from_attribute(**apply)
                self.assertEqual(len(obj.data.materials), 1)
            material = obj.data.materials[0]
            self.assertEqual(material.name, var_name)
            nodes = material.node_tree.nodes
            self.assertEqual(nodes["Attribute"].attribute_name, var_name)
            for key, prop in (
                ("Attribute.001", "Max value"),
                ("Attribute.002", "Min value"),
            ):
                self.assertEqual(nodes[key].attribute_type, "OBJECT")
                self.assertEqual(nodes[key].attribute_name, prop)
            base_color = nodes["Principled BSDF"].inputs["Base Color"]
            self.assertEqual(
                base_color.links[0].from_node.bl_idname, "ShaderNodeValToRGB"
            )
        finally:
            if material is not None:
                bpy.data.materials.remove(material)

    def test_apply_material_without_object_is_reported(self):
        """A texture node that never had a grid reports instead of raising."""
        self.build_pipeline("xy", texture=True)
        variable = self.texture_node.inputs["Variable"].links[0].from_socket
        lonely = self.tree.nodes.new("BlenderNCNodeTexture")
        self.tree.links.new(variable, lonely.inputs["Variable"])
        with self.assertRaisesRegex(RuntimeError, "link a baked Datacube Grid"):
            bpy.ops.blendernc.bake_from_attribute(
                node_name=lonely.name, node_tree=self.tree.name
            )
        self.assertNotIn(VARIABLE, bpy.data.materials)

    def test_apply_material_on_refused_texture_is_reported(self):
        """Nothing was written onto the mesh, so the node's message is reported."""
        self.build_refused_texture("xyt")
        with self.assertRaisesRegex(RuntimeError, "Animate Texture"):
            bpy.ops.blendernc.bake_from_attribute(
                node_name=self.texture_node.name, node_tree=self.tree.name
            )

    def test_resolution_suggested_step(self):
        """The node picks ceil(smallest surface size / budget) once, not twice."""
        ny, nx = MAX_VERTEX_SAMPLES + 1, 2 * MAX_VERTEX_SAMPLES
        path = f"{self.tmpdir}/wide.nc"
        wide = xr.Dataset(
            {VARIABLE: (("Y", "X"), np.zeros((ny, nx), dtype=np.int8))},
            coords={"X": np.arange(float(nx)), "Y": np.arange(float(ny))},
        )
        wide.to_netcdf(path)
        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        resolution = tree.nodes.new("BlenderNCNodeResolution")
        coords = tree.nodes.new("BlenderNCNodeCoords")
        import_node.datacube_file = path
        datacube = "xarray datacube"
        tree.links.new(import_node.outputs[datacube], resolution.inputs[datacube])
        tree.links.new(resolution.outputs[datacube], coords.inputs[datacube])

        self.assertTrue(resolution.suggested_step)
        self.assertEqual(resolution.step, 2)  # ceil((budget + 1) / budget)
        records = [r for r in resolution.BNC_datastructs[0].slicing.split(",") if r]
        self.assertEqual(sorted(records), ["*|X|0::2", "*|Y|0::2"])
        downstream = coords.BNC_datastructs[0].slicing
        self.assertEqual(downstream, "".join(f"{r}," for r in records))

        resolution.suggested_step = False
        resolution.step = 5
        records = [r for r in resolution.BNC_datastructs[0].slicing.split(",") if r]
        self.assertEqual(sorted(records), ["*|X|0::5", "*|Y|0::5"])


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSyntheticGrids)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
