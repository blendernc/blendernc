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

import re
import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import xarray as xr

from blendernc.handlers import bNC_update_attributes
from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import (
    MAX_VERTEX_SAMPLES,
    RANGE_PROPERTIES,
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
        self.assertFalse(texture.inputs["Variable"].is_linked)
        self.assertFalse(texture.inputs["Object"].is_linked)
        self.assertEqual(sum("link removed" in line for line in logs.output), 2)

        # Matching types still link and the texture is written.
        self.tree.links.new(grid.outputs["Object"], texture.inputs["Object"])
        self.tree.links.new(variable.outputs[var_name], texture.inputs["Variable"])
        self.assertEqual(texture.message, "")
        self.assertIn(VARIABLE, obj.data.attributes)

    def test_resolution_change_rebakes_grid_and_texture(self):
        """Changing the step on the node rebakes the grid and the texture."""
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
        self.assertEqual(len(obj.data.vertices), NX * NY)
        self.assertEqual(texture.message, "")

        resolution.step = 2
        expected = len(range(0, NX, 2)) * len(range(0, NY, 2))
        self.assertEqual(len(obj.data.vertices), expected)
        self.assertEqual(texture.message, "")
        self.assertEqual(len(obj.data.attributes[VARIABLE].data), expected)

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
