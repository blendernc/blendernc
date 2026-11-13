import bpy
from bpy_extras.io_utils import ImportHelper

from .decorators import check_if_node_tree_exists, is_linked
from .messages import report_error, report_errors
from .node_utils import create_links, create_nodes
from .utils import (
    add_attribute,
    assign_modifier_to_object,
    extract_dimensions_of_grid,
    get_2D_coords,
    get_datacube_path,
    get_dataset,
    get_grid_coords,
    look_up_object_and_mesh,
    stack_2D_coords,
)


class Import_OT_mfdataset(bpy.types.Operator, ImportHelper):
    """Import a NetCDF/GRIB/Zarr dataset into BlenderNC."""

    bl_idname = "blendernc.import_mfdataset"

    bl_label = "Load Datacube"
    bl_description = "Import Datacube with xarray"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

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
            files share no pattern or the dataset cannot be opened.
        """
        node_tree = bpy.data.node_groups.get(self.node_tree)
        import_node = node_tree.nodes.get(self.node_name)

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
        grid_obj_name = grid_node.grid_obj_name

        grid_coords = get_grid_coords(grid_node)

        obj, mesh = look_up_object_and_mesh(grid_obj_name)

        modifier, grid_nodetree = assign_modifier_to_object(obj, grid_obj_name)

        nodes = {
            "GeometryNodeMeshGrid": {"links": {"Mesh": {"NodeGroupOutput": "Geometry"}}}
        }
        mesh_grid_nodes = create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, mesh_grid_nodes)
        mesh_grid_node = mesh_grid_nodes["GeometryNodeMeshGrid"]["node"]

        axis1, axis2 = extract_dimensions_of_grid(grid_coords)

        mesh_grid_node.inputs[2].default_value = axis1
        mesh_grid_node.inputs[3].default_value = axis2

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        grid_coords = get_2D_coords(grid_coords)

        flattened_coords = stack_2D_coords(grid_coords)

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
                "links": {"Geometry": {"NodeGroupOutput": "Geometry"}}
            },
        }
        nodes_created = create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, nodes_created)

        nodes_created["GeometryNodeInputNamedAttribute"][
            "node"
        ].data_type = "FLOAT_VECTOR"
        nodes_created["GeometryNodeInputNamedAttribute"]["node"].inputs[
            0
        ].default_value = "Coordinates"
        nodes_created["GeometryNodeRemoveAttribute"]["node"].inputs[
            2
        ].default_value = "Coordinates"
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        return {"FINISHED"}


class BlenderNCBakeFromAttribute(bpy.types.Operator):
    bl_idname = "blendernc.bake_from_attribute"
    bl_label = "Bake From Attribute"

    def execute(self, context):
        # Implement the baking logic here
        return {"FINISHED"}
