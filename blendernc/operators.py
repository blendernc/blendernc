import bpy
from bpy_extras.io_utils import ImportHelper

from .decorators import check_if_node_tree_exists, is_linked
from .node_utils import create_nodes
from .utils import (
    add_attribute,
    assign_modifier_to_object,
    create_datastruct,
    extract_dimensions_of_grid,
    get_2D_coords,
    get_coords_from_datastruct,
    get_datacube_path,
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

    @check_if_node_tree_exists
    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree)
        filepath_string_node = node_tree.nodes.get(self.node_name)

        datacube_path = get_datacube_path(self.directory, self.files)

        filepath_string_node.datacube_file = datacube_path
        if not bpy.app.background:  # Check if Blender is running in background mode
            if context.area.type == "VIEW_3D":
                context.scene.datacube_file = datacube_path

        create_datastruct(self, context)

        return {"FINISHED"}


class Import_OT_CreateGrid(bpy.types.Operator):
    """Create mesh from datacube coordinates."""

    bl_idname = "blendernc.create_grid_from_coords"

    bl_label = "Create Grid"
    bl_description = "Create mesh from datacube coordinates"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    @is_linked
    def execute(self, context):

        node_tree = bpy.data.node_groups.get(self.node_tree)
        grid_node = node_tree.nodes.get(self.node_name)
        grid_obj_name = grid_node.grid_obj_name

        grid_coords = get_grid_coords(grid_node)

        obj, mesh = look_up_object_and_mesh(grid_obj_name)

        modifier, grid_nodetree = assign_modifier_to_object(obj, grid_obj_name)

        nodes = {
            "GeometryNodeMeshGrid": {"links": {"Mesh": {"NodeGroupOutput": "Geometry"}}}
        }
        MeshGrid_nodes = create_nodes(grid_nodetree, nodes)
        MeshGrid_node = MeshGrid_nodes["GeometryNodeMeshGrid"]["node"]

        axis1, axis2 = extract_dimensions_of_grid(grid_coords)

        MeshGrid_node.inputs[2].default_value = axis1
        MeshGrid_node.inputs[3].default_value = axis2

        object_blendernc = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        datastruct = grid_node.BNC_datastructs[0]

        grid_coords = get_coords_from_datastruct(datastruct, grid_coords)

        grid_coords = get_2D_coords(grid_coords)

        flattened_coords = stack_2D_coords(grid_coords)

        attr = add_attribute(mesh, "Coordinates", type="FLOAT_VECTOR", domain="POINT")

        attr.data.foreach_set("vector", flattened_coords)
        # grid_node.update()

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

        bpy.context.view_layer.objects.active = object_blendernc

        return {"FINISHED"}
