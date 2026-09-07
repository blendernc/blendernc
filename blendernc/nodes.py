from PIL.Image import item
import bpy 
from collections import defaultdict

from dask.delayed import op
from .utils import get_possible_variables, load_dataset, create_datastruct
from .decorators import is_single_input_linked,initialize_BNC_datastructs,has_datastructs
from .properties import BNC_data

class bNCNodeDefault:
    """Base class for all BlenderNC nodes. This class provides common functionality and properties that are shared across all node types."""

    BNC_datastructs : bpy.props.CollectionProperty(type=BNC_data)
    
    

# Custom node type 
class DatacubeImport(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDatacubeImport"  # Unique identifier for the node
    bl_label = "Datacube Import"  # Name that will appear on the node in the editor
    bl_icon = 'EXPERIMENTAL'

    datacube_file: bpy.props.StringProperty(
        name="",
        description="Filepath used for importing the file",
        default="",
        maxlen=1024,
        update=create_datastruct
    )
    """An instance of the original StringProperty."""

    filename: bpy.props.StringProperty(update=lambda self, context: self.update())

    @initialize_BNC_datastructs
    def init(self, context): 
        socket = self.outputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = 'SQUARE'

    def draw_buttons(self, context, layout):
        layout.label(text="Datacube path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = layout.row(align=True)
        split = row.split(factor=0.85, align=True)
        
        split.prop(self, "datacube_file")
        op = split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    def update(self):
        if self.datacube_file:
            self.BNC_datastructs[0].datafile = self.datacube_file
            self.BNC_datastructs[0].filename = self.datacube_file.split("/")[-1]
            self.BNC_datastructs[0].dict[self.BNC_datastructs[0].filename] = load_dataset(self.BNC_datastructs[0].datafile)


class DatacubeCoords(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDatacubeCoords"  # Unique identifier for the node
    bl_label = "Datacube Coords"  # Name that will appear on the node in the editor
    bl_icon = 'EXPERIMENTAL'

    @initialize_BNC_datastructs
    def init(self, context): 
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = 'SQUARE'

    def draw_buttons(self, context, layout):
        pass

    @is_single_input_linked
    @has_datastructs
    def update(self):
        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]
        for coords in dataset.coords:
            if coords not in [socket.name for socket in self.outputs]:
                self.outputs.new("NodeSocketString", coords)


class DatacubeVariable(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDatacubeVariable"  # Unique identifier for the node
    bl_label = "Datacube Variable"  # Name that will appear on the node in the editor
    bl_icon = 'EXPERIMENTAL'

    datacube_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=lambda self, context: self.update(),
    )

    filename: bpy.props.StringProperty()

    @initialize_BNC_datastructs
    def init(self, context): 
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = 'SQUARE'

    def draw_buttons(self, context, layout):
        layout.label(text="Select Variable:")
        layout.prop(self, "datacube_vars", text="")

    def draw_label(self):
        if not self.filename:
            return "datacube Input"
        else:
            return self.filename

    @is_single_input_linked
    @has_datastructs
    def update(self):
        if self.datacube_vars != "No var" and self.datacube_vars not in [socket.name for socket in self.outputs]:
            self.outputs.new("NodeSocketString", self.datacube_vars)


        
class DatacubeGrid(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDatacubeGrid"  # Unique identifier for the node
    bl_label = "Datacube Grid"  # Name that will appear on the node in the editor
    bl_icon = 'EXPERIMENTAL'

    grid_obj_name: bpy.props.StringProperty(
        default="Grid",
    )

    @initialize_BNC_datastructs
    def init(self, context): 
        self.inputs.new("NodeSocketString", "X")
        self.inputs.new("NodeSocketString", "Y")
        self.inputs.new("NodeSocketString", "Z")
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        layout.prop(self, "grid_obj_name", text="")
        op = layout.operator("blendernc.create_grid_from_coords", text="Bake Grid")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    @is_single_input_linked
    @has_datastructs
    def update(self):
        if self.grid_obj_name in bpy.data.objects:
            if "Object" not in [socket.name for socket in self.outputs]:
                object_socket = self.outputs.new("NodeSocketObject", "Object")
                object_socket.default_value = bpy.data.objects[self.grid_obj_name]
            else:
                object_socket = self.outputs.get("Object")
                object_socket.default_value = bpy.data.objects[self.grid_obj_name]


class DatacubeUpdateTexture(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDatacubeUpdateTexture"  # Unique identifier for the node
    bl_label = "Datacube Update Texture"  # Name that will appear on the node in the editor
    bl_icon = 'EXPERIMENTAL'

    @initialize_BNC_datastructs
    def init(self, context): 
        self.inputs.new("NodeSocketObject", "Object")
        self.inputs.new("bNCdatacubeSocket", "xarray datacube")

    def draw_buttons(self, context, layout):
        pass

    @is_single_input_linked
    def update(self):
        pass

class DebugNode(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDebugNode"
    bl_label = "Debug Node"

    @initialize_BNC_datastructs
    def init(self, context):
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")

    def draw_buttons(self, context, layout):
        datastruct = self.BNC_datastructs[0]
        layout.prop(datastruct, "filename")
        layout.prop(datastruct, "datafile")
        if hasattr(datastruct, "dict"):
            layout.label(text=f"Dict keys: {list(datastruct.dict.keys())}")

    @is_single_input_linked
    def update(self):
        pass