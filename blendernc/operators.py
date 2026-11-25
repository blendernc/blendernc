from contextlib import contextmanager

import bpy
from bpy_extras.io_utils import ImportHelper

from .core.dataset import get_datacube_path
from .core.fields import GRID_DIMS_PROPERTY
from .core.grid import (
    extract_dimensions_of_grid,
    get_2D_coords,
    grid_dims,
    stack_2D_coords,
)
from .core.points import scattered_mesh
from .decorators import is_linked
from .messages import report_error, report_errors
from .node_utils import (
    UI_IMPORT_NODE,
    UI_NODE_TREE,
    UI_TEXTURE_NODE,
    create_links,
    create_nodes,
)
from .shader_utils import texture_material, volume_material
from .ui import use_import_node
from .utils import (
    TEXTURE_NODE_IDNAMES,
    add_attribute,
    assign_material,
    build_triangle_mesh,
    get_dataset,
    get_grid_coords,
    grid_material,
    look_up_object_and_mesh,
)
from .volume_utils import bake_volume


class Import_OT_mfdataset(bpy.types.Operator, ImportHelper):
    """Import a NetCDF/GRIB/Zarr dataset into BlenderNC."""

    bl_idname = "blendernc.import_mfdataset"

    bl_label = "Load Datacube"
    bl_description = "Import Datacube with xarray"

    # Not remembered between calls: the 3D view panel passes neither, and
    # must not inherit the tree last picked from a node editor button.
    node_name: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    node_tree: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})

    filter_glob: bpy.props.StringProperty(
        default="*.nc;*.grib;*.zarr",
        options={"HIDDEN"},
    )
    """An instance of the original StringProperty."""

    directory: bpy.props.StringProperty(
        subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"}
    )
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"}
    )

    @report_errors
    def execute(self, context):
        """Store the chosen file path on the import node and load the dataset.

        Multiple selected files are collapsed into a single glob pattern.
        The node is the one passed, or the import node of the 3D view
        panel's tree when none is (see :func:`blendernc.ui.use_import_node`).
        Assigning the path to the node loads the dataset through the
        property's update callback. The panel's import node is only ever
        given the panel's path, so for it the panel's path is set instead,
        which passes it on.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report when the
            node is missing, the files share no pattern or the dataset cannot
            be opened.
        """
        use_import_node(self, context)
        node_tree = bpy.data.node_groups.get(self.node_tree)
        import_node = node_tree.nodes.get(self.node_name) if node_tree else None
        if import_node is None:
            return report_error(
                self, f"Node {self.node_name!r} not found in {self.node_tree!r}."
            )

        datacube_path = get_datacube_path(self.directory, self.files)
        if node_tree.name == UI_NODE_TREE and import_node.name == UI_IMPORT_NODE:
            context.scene.BlenderNC_UI_Properties.datacube_file = datacube_path
        else:
            import_node.datacube_file = datacube_path
        datastruct = import_node.BNC_datastructs[0]
        # A path the panel cannot match never reaches its import node, which
        # then still holds the previous dataset.
        if datastruct.datafile != datacube_path or get_dataset(datastruct) is None:
            return report_error(self, f"Could not open {datacube_path}.")
        return {"FINISHED"}


class Import_OT_CreateGrid(bpy.types.Operator):
    """Create mesh from datacube coordinates."""

    bl_idname = "blendernc.create_grid_from_coords"

    bl_label = "Create Grid"
    bl_description = "Create mesh from datacube coordinates"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    @report_errors
    @is_linked
    def execute(self, context):
        """Bake a mesh from the coordinates linked to a grid node.

        Coordinates over two dimensions give a grid (see
        :func:`_bake_mesh_grid`); X and Y over one shared dimension, such as
        the ``lon(ncells)`` and ``lat(ncells)`` of an unstructured model,
        give one vertex per point joined in triangles (see
        :func:`_bake_points`). Finally the grid node is updated so its
        ``Object`` output exists and downstream texture nodes are rewritten
        for the new mesh.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report if no input
            is linked or the coordinates cannot form a mesh.
        """

        node_tree = bpy.data.node_groups.get(self.node_tree)
        grid_node = node_tree.nodes.get(self.node_name)

        grid_coords = get_grid_coords(grid_node)
        dims = grid_dims(grid_coords)
        if dims and len(dims) == 1:
            obj, mesh = _bake_points(grid_node, grid_coords, dims[0])
        else:
            obj, mesh = _bake_mesh_grid(context, grid_node, grid_coords)
        _record_bake(grid_node, obj, mesh, dims)
        return {"FINISHED"}


def _bake_points(grid_node, grid_coords, dim):
    """Bake one vertex per point along ``dim``, joined in triangles.

    The triangles are worked out before touching Blender data, so points
    that cannot be triangulated are reported without side effects.

    Returns
    -------
    tuple
        ``(object, mesh)`` of the grid.
    """
    positions, triangles = scattered_mesh(grid_coords, dim, grid_node.max_edge)
    obj, mesh = look_up_object_and_mesh(grid_node.grid_obj_name)
    build_triangle_mesh(mesh, positions, triangles)
    assign_material(mesh, grid_material(grid_node))
    return obj, mesh


def _bake_mesh_grid(context, grid_node, grid_coords):
    """Bake a Mesh Grid moved onto the 2-D coordinate arrays.

    A Mesh Grid geometry node sized from the coordinate dimensions is applied
    to the target object, the 2-D coordinate arrays are written to a
    ``Coordinates`` vector attribute, and a second geometry node modifier
    moves the vertices to those positions before removing the attribute.
    Both node groups only live for the bake (see
    :func:`_applied_geometry_nodes`).

    Returns
    -------
    tuple
        ``(object, mesh)`` of the grid.
    """
    # Work out the vertex layout before touching Blender data, so a
    # dataset that cannot form a grid is reported without side effects.
    grid_coords = get_2D_coords(grid_coords)
    vertices_x, vertices_y = extract_dimensions_of_grid(grid_coords)
    flattened_coords = stack_2D_coords(grid_coords)

    obj, mesh = look_up_object_and_mesh(grid_node.grid_obj_name)

    with _applied_geometry_nodes(context, obj, "BlenderNC Mesh Grid") as tree:
        nodes = create_nodes(tree, MESH_GRID_NODES)
        create_links(tree, nodes)
        mesh_grid_node = nodes["GeometryNodeMeshGrid"]["node"]
        mesh_grid_node.inputs["Vertices X"].default_value = vertices_x
        mesh_grid_node.inputs["Vertices Y"].default_value = vertices_y

    attr = add_attribute(mesh, "Coordinates", attr_type="FLOAT_VECTOR", domain="POINT")
    attr.data.foreach_set("vector", flattened_coords)

    with _applied_geometry_nodes(context, obj, "BlenderNC Grid Coords") as tree:
        nodes = create_nodes(tree, GRID_COORDS_NODES)
        create_links(tree, nodes)
        named_attribute = nodes["GeometryNodeInputNamedAttribute"]["node"]
        named_attribute.data_type = "FLOAT_VECTOR"
        named_attribute.inputs["Name"].default_value = "Coordinates"
        remove_attribute = nodes["GeometryNodeRemoveAttribute"]["node"]
        remove_attribute.inputs["Name"].default_value = "Coordinates"
        set_material = nodes["GeometryNodeSetMaterial"]["node"]
        set_material.inputs["Material"].default_value = grid_material(grid_node)
    return obj, mesh


# Geometry nodes of the two modifiers :func:`_bake_mesh_grid` applies, in
# the format of :func:`blendernc.node_utils.create_nodes`.
MESH_GRID_NODES = {
    "GeometryNodeMeshGrid": {"links": {"Mesh": {"NodeGroupOutput": "Geometry"}}}
}


GRID_COORDS_NODES = {
    "NodeGroupInput": {"links": {"Geometry": {"GeometryNodeSetPosition": "Geometry"}}},
    "GeometryNodeInputNamedAttribute": {
        "links": {"Attribute": {"GeometryNodeSetPosition": "Position"}}
    },
    "GeometryNodeSetPosition": {
        "links": {"Geometry": {"GeometryNodeRemoveAttribute": "Geometry"}}
    },
    "GeometryNodeRemoveAttribute": {
        "links": {"Geometry": {"GeometryNodeSetMaterial": "Geometry"}}
    },
    "GeometryNodeSetMaterial": {"links": {"Geometry": {"NodeGroupOutput": "Geometry"}}},
}


@contextmanager
def _applied_geometry_nodes(context, obj, name):
    """Yield a new geometry node group run by a modifier of ``obj``, then apply it.

    The group and the modifier are made for this bake alone and removed
    afterwards, also when building or applying them fails. The file then
    keeps no node group per grid, and node groups of the user's are never
    reused or deleted, whatever their names.

    Parameters
    ----------
    context : bpy.types.Context
        Current Blender context.
    obj : bpy.types.Object
        Object receiving the modifier.
    name : str
        Name of the node group; Blender adds a suffix when it is taken.
    """
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    modifier = obj.modifiers.new(name=tree.name, type="NODES")
    modifier.node_group = tree
    modifier_name = modifier.name  # applying frees the modifier
    try:
        yield tree
        _apply_modifier(context, obj, modifier_name)
    finally:
        leftover = obj.modifiers.get(modifier_name)
        if leftover is not None:
            obj.modifiers.remove(leftover)
        bpy.data.node_groups.remove(tree)


def _record_bake(grid_node, obj, mesh, dims):
    """Remember what was baked, then let the node expose the object.

    The dims are stored on the mesh for the texture nodes, which read them
    to orient fields the same way; the node keeps the object, slicing and
    coordinates so it can tell when the mesh is stale.
    """
    if dims:
        mesh[GRID_DIMS_PROPERTY] = ",".join(dims)
    else:
        mesh.pop(GRID_DIMS_PROPERTY, None)
    grid_node.baked_object = obj.name
    grid_node.baked_slicing = grid_node.BNC_datastructs[0].slicing
    grid_node.baked_coords = grid_node.coords_signature()
    grid_node.update()


class Import_OT_CreateVolume(bpy.types.Operator):
    """Create a Volume object from a 3D or 4D variable."""

    bl_idname = "blendernc.create_volume"

    bl_label = "Create Volume"
    bl_description = "Write the variable to OpenVDB files and load them as a volume"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")
    # Set by the node when the tree changes; the button always bakes fully.
    keep_placement: bpy.props.BoolProperty(
        default=False,
        options={"SKIP_SAVE"},
        description="Only refresh the values when the coordinates are unchanged",
    )

    @report_errors
    @is_linked
    def execute(self, context):
        """Bake the volume of a Datacube Volume node.

        The VDB files are written by :func:`blendernc.volume_utils.bake_volume`
        and the variable's density-only material is assigned. A problem is
        shown on the node as well as reported, since the node can rebake
        itself when the tree changes and nobody sees the status bar then; so
        are the notes about resampling and the warning about an unsaved
        file. A refresh of the values changes neither, so reports nothing.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report when the
            variable cannot form a volume.
        """
        node_tree = bpy.data.node_groups.get(self.node_tree)
        volume_node = node_tree.nodes.get(self.node_name)
        volume_node.warning = volume_node.note = ""
        try:
            obj, notes, refreshed = bake_volume(
                volume_node, context.scene, self.keep_placement
            )
        except (ValueError, OSError) as exc:
            volume_node.message = str(exc)
            raise
        volume_node.message = ""
        volume_node.warning = "\n".join(notes["WARNING"])
        volume_node.note = "\n".join(notes["INFO"])
        if not refreshed:
            self._report_notes(notes)

        variable = volume_node.inputs["Variable"].default_value
        assign_material(obj.data, volume_material(variable))

        volume_node.baked_object = obj.name
        volume_node.baked_signature = volume_node.signature()
        volume_node.update()
        return {"FINISHED"}

    def _report_notes(self, notes):
        """Report each note of a bake on one line, at its level."""
        for level, lines in notes.items():
            for line in lines:
                report_error(self, line.replace("\n", " "), level)


def _apply_modifier(context, obj, modifier_name):
    """Apply the named modifier on ``obj`` without changing the active object."""
    with context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=modifier_name)


class BlenderNCBakeFromAttribute(bpy.types.Operator):
    """Colour the object of a Datacube Texture or Animate Texture node.

    The material (see :func:`blendernc.shader_utils.texture_material`) is
    named after the variable and goes into the object's first material slot,
    so running the operator again reuses both. It maps the attribute through
    the range the node stored on the mesh; for an animation, that of the
    first frame it loaded.

    Called with no properties, from the 3D view panel, it acts on the
    "Datacube Texture" node of the panel's tree. The button on either node
    passes that node and its tree.
    """

    bl_idname = "blendernc.bake_from_attribute"
    bl_label = "Apply Material"
    bl_description = "Colour the object from the variable written by the texture node"

    # Not remembered between calls: the panel passes neither, and must not
    # inherit the node last picked in a node editor.
    node_name: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    node_tree: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})

    @report_errors
    def execute(self, context):
        """Create or reuse the variable's material and assign it.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report when the
            node is missing or has no texture written onto a mesh.
        """
        tree_name = self.node_tree or UI_NODE_TREE
        node_name = self.node_name or UI_TEXTURE_NODE
        node_tree = bpy.data.node_groups.get(tree_name)
        texture_node = node_tree.nodes.get(node_name) if node_tree else None
        if texture_node is None or texture_node.bl_idname not in TEXTURE_NODE_IDNAMES:
            return report_error(
                self, f"Texture node {node_name!r} not found in {tree_name!r}."
            )

        obj = texture_node.inputs["Object"].default_value
        variable = texture_node.inputs["Variable"].default_value
        if obj is None or obj.type != "MESH":
            return report_error(
                self, f"{texture_node.name}: link a baked Datacube Grid to Object."
            )
        if not variable or texture_node.written != variable:
            reason = texture_node.message.replace("\n", " ") or "link a variable."
            return report_error(self, f"{texture_node.name}: {reason}")

        assign_material(obj.data, texture_material(variable))
        return {"FINISHED"}
