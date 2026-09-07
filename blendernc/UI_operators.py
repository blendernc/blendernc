import bpy
from bpy_extras.io_utils import ImportHelper

from .decorators import check_if_node_tree_exists

from .translations import translate
from .utils import get_datacube_path, create_datastruct

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

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE', 'HIDDEN'})

    @check_if_node_tree_exists
    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree)
        filepath_string_node = node_tree.nodes.get(self.node_name)

        datacube_path = get_datacube_path(self.directory, self.files)

        filepath_string_node.datacube_file = datacube_path
        if not bpy.app.background: # Check if Blender is running in background mode
            if context.area.type == 'VIEW_3D':
                context.scene.datacube_file = datacube_path

        create_datastruct(self, context)

        return {'FINISHED'}

class Import_OT_CreateGrid(bpy.types.Operator):
    """Create mesh from datacube coordinates."""

    bl_idname = "blendernc.create_grid_from_coords"

    bl_label = "Create Grid"
    bl_description = "Create mesh from datacube coordinates"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    def execute(self, context):
        if self.node_name == "" or self.node_tree == "":
            self.report({'WARNING'}, translate("blendernc", "BlenderNC: Node name or node tree is not set."))
            return {'CANCELLED'}
        
        node_tree = bpy.data.node_groups.get(self.node_tree)
        grid_node = node_tree.nodes.get(self.node_name)
        grid_obj_name = grid_node.grid_obj_name

        grid_coords = {}

        for input in grid_node.inputs:
            if input.is_linked:
                datastruct = grid_node.BNC_datastructs[0] 
                linked_socket = input.links[0].from_socket
                grid_coords[input.name] = {"name": linked_socket.name, "size": datastruct.dict[datastruct.filename][linked_socket.name].shape }

        x_size = grid_coords.get("X", {}).get("size", 1)
        y_size = grid_coords.get("Y", {}).get("size", 1)
        z_size = grid_coords.get("Z", {}).get("size", 1)

        x_size = x_size if isinstance(x_size, tuple) else (x_size,)
        y_size = y_size if isinstance(y_size, tuple) else (y_size,)
        z_size = z_size if isinstance(z_size, tuple) else (z_size,)

        if grid_obj_name in bpy.data.meshes:
            mesh = bpy.data.meshes.get(grid_obj_name)
            grid_obj = bpy.data.objects.get(grid_obj_name)
        else:
            mesh = bpy.data.meshes.new(grid_obj_name)
            grid_obj = bpy.data.objects.new(grid_obj_name, mesh)
            context.collection.objects.link(grid_obj)

        modifier = grid_obj.modifiers.new(name="BlenderNC Grid", type='NODES')

        if grid_obj_name in bpy.data.node_groups:
            grid_nodetree = bpy.data.node_groups.get(grid_obj_name)
        else:
            grid_nodetree = bpy.data.node_groups.new(grid_obj_name, 'GeometryNodeTree')
            
        modifier.node_group = grid_nodetree

        if len(grid_nodetree.nodes) == 0:

            geo_output = grid_nodetree.interface.new_socket(
                name="Geometry",
                in_out='OUTPUT',
                socket_type='NodeSocketGeometry'
            )

            MeshGrid_node = grid_nodetree.nodes.new('GeometryNodeMeshGrid')
            output_node = grid_nodetree.nodes.new('NodeGroupOutput')
        else:
            MeshGrid_node = grid_nodetree.nodes.get('Grid')
            output_node = grid_nodetree.nodes.get('Group Output')
        
        grid_nodetree.links.new(MeshGrid_node.outputs['Mesh'], output_node.inputs['Geometry'])

        if len(x_size) == 1 and len(y_size) == 1:
            MeshGrid_node.inputs[2].default_value = x_size[0]
            MeshGrid_node.inputs[3].default_value = y_size[0]
        elif len(x_size) == 1 and len(z_size) == 1:
            MeshGrid_node.inputs[2].default_value = x_size[0]
            MeshGrid_node.inputs[3].default_value = z_size[0]
        elif len(y_size) == 1 and len(z_size) == 1:
            MeshGrid_node.inputs[2].default_value = y_size[0]
            MeshGrid_node.inputs[3].default_value = z_size[0]
        elif len(x_size) == 2 and len(y_size) == 2:
            MeshGrid_node.inputs[2].default_value = x_size[0]
            MeshGrid_node.inputs[3].default_value = y_size[1]
        elif len(x_size) == 2 and len(z_size) == 2:
            MeshGrid_node.inputs[2].default_value = x_size[0]
            MeshGrid_node.inputs[3].default_value = z_size[1]
        elif len(y_size) == 2 and len(z_size) == 2:
            MeshGrid_node.inputs[2].default_value = y_size[0]
            MeshGrid_node.inputs[3].default_value = z_size[1]
        else:
            self.report({'WARNING'}, translate("blendernc", "BlenderNC: No valid coordinates found"))
            return {'CANCELLED'}

        object_blendernc = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = grid_obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        attr = add_attribute(mesh, "Coordinates", type="FLOAT_VECTOR", domain="POINT")

        import numpy as np

        coords = []
        if x_size!=1 and y_size!=1:
            x = grid_node.datastruct[grid_node.filename][grid_coords.get("X").get("name", 1)].values
            y = grid_node.datastruct[grid_node.filename][grid_coords.get("Y").get("name", 1)].values
            X,Y = np.meshgrid(x, y, indexing='ij')
            coords = ["X", "Y"]
        elif x_size!=1 and z_size!=1:
            x = grid_node.datastruct[grid_node.filename][grid_coords.get("X").get("name", 1)].values
            z = grid_node.datastruct[grid_node.filename][grid_coords.get("Z").get("name", 1)].values
            X,Z = np.meshgrid(x, z, indexing='ij')
            coords = ["X", "Z"]
        elif y_size!=1 and z_size!=1:
            y = grid_node.datastruct[grid_node.filename][grid_coords.get("Y").get("name", 1)].values
            z = grid_node.datastruct[grid_node.filename][grid_coords.get("Z").get("name", 1)].values
            Y,Z = np.meshgrid(y, z, indexing='ij')
            coords = ["Y", "Z"]
        if len(x_size) == 2:
            X = grid_node.datastruct[grid_node.filename][grid_coords.get("X").get("name", 1)].values
            coords.append("X")
        if len(y_size) == 2:
            Y = grid_node.datastruct[grid_node.filename][grid_coords.get("Y").get("name", 1)].values
            coords.append("Y")
        if len(z_size) == 2:
            Z = grid_node.datastruct[grid_node.filename][grid_coords.get("Z").get("name", 1)].values
            coords.append("Z")

        if len(x_size) > 2  or len(y_size) > 2 or len(z_size) >2:
            self.report({'ERROR'}, translate("More than 2 dimensions were found, only 2D grids are supported by the Grid node. For 3D grids, please use the volume node."))
            return {'CANCELLED'}

        for coord in ["X", "Y", "Z"]:
            if coord not in coords:
                if coord == "X":
                    X = np.zeros_like(Y)
                elif coord == "Y":
                    Y = np.zeros_like(Z)
                elif coord == "Z":
                    Z = np.zeros_like(X)
        
        coords = np.stack([X, Y, Z], axis=0).transpose(1,2,0).flatten()

        attr.data.foreach_set("vector", coords)
        grid_node.update()
        bpy.context.view_layer.objects.active = object_blendernc
        return {'FINISHED'}

def add_attribute(mesh, attr_name, type="FLOAT", domain="POINT"):
    """Add a custom attribute to a mesh object."""
    attr = None
    if mesh and mesh.id_type == 'MESH':
        if attr_name not in mesh.attributes:
            attr = mesh.attributes.new(name=attr_name, type=type, domain=domain)
        else:
            attr = mesh.attributes.get(attr_name)
    return attr