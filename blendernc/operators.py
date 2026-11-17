import bpy
from bpy_extras.io_utils import ImportHelper

from .decorators import check_if_node_tree_exists, is_linked
from .messages import report_error, report_errors
from .node_utils import UI_NODE_TREE, create_links, create_nodes
from .shader_utils import texture_material, volume_material
from .utils import (
    GRID_DIMS_PROPERTY,
    TEXTURE_NODE_IDNAMES,
    UI_TEXTURE_NODE,
    add_attribute,
    assign_material,
    assign_modifier_to_object,
    extract_dimensions_of_grid,
    get_2D_coords,
    get_datacube_path,
    get_dataset,
    get_grid_coords,
    grid_dims,
    grid_material,
    look_up_object_and_mesh,
    stack_2D_coords,
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
    @check_if_node_tree_exists
    def execute(self, context):
        """Store the chosen file path on the import node and load the dataset.

        Multiple selected files are collapsed into a single glob pattern.
        Assigning the path to the node loads the dataset through the
        property's update callback. When invoked from the 3D view, the path
        is mirrored to the UI properties.

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
        node_tree = bpy.data.node_groups.get(self.node_tree)
        import_node = node_tree.nodes.get(self.node_name) if node_tree else None
        if import_node is None:
            return report_error(
                self, f"Node {self.node_name!r} not found in {self.node_tree!r}."
            )

        datacube_path = get_datacube_path(self.directory, self.files)
        import_node.datacube_file = datacube_path
        if get_dataset(import_node.BNC_datastructs[0]) is None:
            return report_error(self, f"Could not open {datacube_path}.")

        area = context.area
        if not bpy.app.background and area is not None and area.type == "VIEW_3D":
            context.scene.BlenderNC_UI_Properties.datacube_file = datacube_path

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
        """Bake a mesh grid from the coordinates linked to a grid node.

        A Mesh Grid geometry node sized from the coordinate dimensions is applied
        to the target object, the 2-D coordinate arrays are written to a
        ``Coordinates`` vector attribute, and a second geometry node modifier
        moves the vertices to those positions before removing the attribute.
        Finally the grid node is updated so its ``Object`` output exists and
        downstream texture nodes are rewritten for the new mesh.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report if no input
            is linked or the coordinates cannot form a grid.
        """

        node_tree = bpy.data.node_groups.get(self.node_tree)
        grid_node = node_tree.nodes.get(self.node_name)

        # Work out the vertex layout before touching Blender data, so a
        # dataset that cannot form a grid is reported without side effects.
        grid_coords = get_grid_coords(grid_node)
        dims = grid_dims(grid_coords)
        grid_coords = get_2D_coords(grid_coords)
        vertices_x, vertices_y = extract_dimensions_of_grid(grid_coords)
        flattened_coords = stack_2D_coords(grid_coords)

        obj, mesh = look_up_object_and_mesh(grid_node.grid_obj_name)

        modifier, grid_nodetree = assign_modifier_to_object(obj, obj.name)
        nodes = {
            "GeometryNodeMeshGrid": {"links": {"Mesh": {"NodeGroupOutput": "Geometry"}}}
        }
        create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, nodes)
        mesh_grid_node = nodes["GeometryNodeMeshGrid"]["node"]
        mesh_grid_node.inputs["Vertices X"].default_value = vertices_x
        mesh_grid_node.inputs["Vertices Y"].default_value = vertices_y
        _apply_modifier(context, obj, modifier)

        attr = add_attribute(
            mesh, "Coordinates", attr_type="FLOAT_VECTOR", domain="POINT"
        )
        attr.data.foreach_set("vector", flattened_coords)

        modifier, grid_nodetree = assign_modifier_to_object(obj, "apply_grid_coords")
        nodes = {
            "NodeGroupInput": {
                "links": {"Geometry": {"GeometryNodeSetPosition": "Geometry"}}
            },
            "GeometryNodeInputNamedAttribute": {
                "links": {"Attribute": {"GeometryNodeSetPosition": "Position"}}
            },
            "GeometryNodeSetPosition": {
                "links": {"Geometry": {"GeometryNodeRemoveAttribute": "Geometry"}}
            },
            "GeometryNodeRemoveAttribute": {
                "links": {"Geometry": {"GeometryNodeSetMaterial": "Geometry"}}
            },
            "GeometryNodeSetMaterial": {
                "links": {"Geometry": {"NodeGroupOutput": "Geometry"}}
            },
        }
        create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, nodes)
        named_attribute = nodes["GeometryNodeInputNamedAttribute"]["node"]
        named_attribute.data_type = "FLOAT_VECTOR"
        named_attribute.inputs["Name"].default_value = "Coordinates"
        remove_attribute = nodes["GeometryNodeRemoveAttribute"]["node"]
        remove_attribute.inputs["Name"].default_value = "Coordinates"
        set_material = nodes["GeometryNodeSetMaterial"]["node"]
        set_material.inputs["Material"].default_value = grid_material(grid_node)
        _apply_modifier(context, obj, modifier)

        # Texture nodes read the dims to orient fields the same way.
        if dims:
            mesh[GRID_DIMS_PROPERTY] = ",".join(dims)
        else:
            mesh.pop(GRID_DIMS_PROPERTY, None)

        # Remember what was baked so the node can tell when it is stale, then
        # let it expose the object and refresh the nodes reading from it.
        grid_node.baked_object = obj.name
        grid_node.baked_slicing = grid_node.BNC_datastructs[0].slicing
        grid_node.baked_coords = grid_node.coords_signature()
        grid_node.update()

        return {"FINISHED"}


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


def _apply_modifier(context, obj, modifier):
    """Apply ``modifier`` on ``obj`` without changing the active object."""
    with context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


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
