import bpy

from .decorators import (
    has_datastructs,
    initialize_BNC_datastructs,
    is_single_input_linked,
)
from .properties import BNC_data
from .utils import (
    create_datastruct,
    get_possible_coordinates,
    get_possible_variables,
    load_dataset,
)


class bNCNodeDefault:
    """
    Base class for all BlenderNC nodes. This class provides common
    functionality and properties that are shared across all node types.
    """

    BNC_datastructs: bpy.props.CollectionProperty(type=BNC_data)

    def invoke(self, context):
        space = context.space_data
        if space and space.type == "NODE_EDITOR":
            cursor = space.cursor_location
            self.location = cursor


# Custom node type
class DatacubeImport(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeImport"  # Unique identifier for the node
    bl_label = "Datacube Import"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_file: bpy.props.StringProperty(
        name="",
        description="Filepath used for importing the file",
        default="",
        maxlen=1024,
        update=create_datastruct,
    )
    """An instance of the original StringProperty."""

    filename: bpy.props.StringProperty(update=lambda self, context: self.update())

    @initialize_BNC_datastructs
    def init(self, context):
        socket = self.outputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        layout.label(text="Datacube path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = layout.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(self, "datacube_file")
        op = split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    def update(self):
        datastruct = self.BNC_datastructs[0]
        if self.datacube_file and datastruct.filename not in datastruct.dict.keys():
            datastruct.datafile = self.datacube_file
            datastruct.filename = self.datacube_file.split("/")[-1]
            datastruct.dict[datastruct.filename] = load_dataset(datastruct.datafile)

    def free(self):
        datastruct = self.BNC_datastructs[0]
        datastruct.dict.pop(datastruct.filename, None)
        datastruct.filename = ""
        datastruct.datafile = ""


class DatacubeCoords(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeCoords"  # Unique identifier for the node
    bl_label = "Datacube Coords"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    @initialize_BNC_datastructs
    def init(self, context):
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        pass

    @is_single_input_linked
    @has_datastructs
    def update(self):
        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]
        for coords in dataset.coords:
            if coords not in [socket.name for socket in self.outputs]:
                socket = self.outputs.new("NodeSocketString", coords)
                socket.default_value = coords


class DatacubeVariable(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeVariable"  # Unique identifier for the node
    bl_label = "Datacube Variable"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        layout.label(text="Select Variable:")
        layout.prop(self, "datacube_vars", text="")

    def draw_label(self):
        if not self.BNC_datastructs[0].filename:
            return "datacube Input"
        else:
            return self.BNC_datastructs[0].filename

    @is_single_input_linked
    @has_datastructs
    def update(self):
        if self.datacube_vars != "No var" and self.datacube_vars not in [
            socket.name for socket in self.outputs
        ]:
            socket = self.outputs.new("NodeSocketString", self.datacube_vars)
            socket.default_value = self.datacube_vars


class DatacubeGrid(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeGrid"  # Unique identifier for the node
    bl_label = "Datacube Grid"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

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


class DatacubeSlice(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeSlice"  # Unique identifier for the node
    bl_label = "Datacube Slice"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Select Variable",
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        self.inputs.new("NodeSocketString", "Variable")
        self.outputs.new("NodeSocketString", "Variable")
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")

    @is_single_input_linked
    def update(self):
        pass
        # var = self.inputs[0].default_value


class DatacubeSelect(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeSelect"  # Unique identifier for the node
    bl_label = "Datacube Select"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Select Variable",
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        self.inputs.new("NodeSocketString", "Variable")
        self.outputs.new("NodeSocketString", "Variable")
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")

    @is_single_input_linked
    @has_datastructs
    def update(self):
        if "Variable" not in [socket.name for socket in self.outputs]:
            socket = self.outputs.new("NodeSocketString", "Variable")
            socket.default_value = self.inputs[0].default_value
        value = 0
        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]
        if self.datacube_coords and self.datacube_coords in dataset.coords.keys():
            datastruct.slicing += (
                self.inputs[0].default_value
                + "_"
                + self.datacube_coords
                + "_"
                + str(value)
                + ","
            )


class DatacubeAnimateTexture(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeAnimateTexture"  # Unique identifier for the node
    bl_label = (
        "Datacube Animate Texture"  # Name that will appear on the node in the editor
    )
    bl_icon = "EXPERIMENTAL"

    @initialize_BNC_datastructs
    def init(self, context):
        self.inputs.new("NodeSocketObject", "Object")
        self.inputs.new("NodeSocketString", "Variable")

    def draw_buttons(self, context, layout):
        pass

    @is_single_input_linked
    @has_datastructs
    def update(self):
        pass


class DebugNode(bpy.types.Node, bNCNodeDefault):
    bl_idname = "BlenderNCNodeDebugNode"
    bl_label = "Debug Node"

    @initialize_BNC_datastructs
    def init(self, context):
        self.inputs.new("bNCdatacubeSocket", "xarray datacube")

    def draw_buttons(self, context, layout):
        datastruct = self.BNC_datastructs[0]
        layout.prop(datastruct, "filename")
        layout.prop(datastruct, "datafile")
        layout.prop(datastruct, "operations")
        layout.prop(datastruct, "slicing")
        if hasattr(datastruct, "dict"):
            layout.label(text=f"Dict keys: {list(datastruct.dict.keys())}")

    @is_single_input_linked
    def update(self):
        pass
