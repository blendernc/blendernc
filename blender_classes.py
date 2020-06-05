from .python_functions import *
import bpy
import xarray
from os.path import isfile, abspath

from nodeitems_utils import NodeCategory, NodeItem

# Blender Classes
node_tree_name = "GeoNodes"
create_new_node_tree = node_tree_name != "ShaderNodeTree"
if create_new_node_tree:
    # Derived from the NodeTree base type, similar to Menu, Operator, Panel, etc.
    class GeoNodesNodeTree(bpy.types.NodeTree):
        # Description string
        '''A custom node tree type that will show up in the editor type list'''
        # Optional identifier string. If not explicitly defined, the python class name is used.
        bl_idname = node_tree_name
        # Label for nice name display
        bl_label = "GeoNodes"
        # Icon identifier
        bl_icon = 'WORLD'


class GeoNodes_OT_ncload(bpy.types.Operator):
    bl_idname = "geonodes.ncload"
    bl_label = "Load netcdf file"
    bl_description = "Loads netcdf file"
    bl_options = {"REGISTER", "UNDO"}
    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )

    def execute(self, context):
        if not self.file_path:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_path)

        if not isfile(file_path):
            self.report({'ERROR'}, "It seems that this is not a file!")
            return {'CANCELLED'}
        scene = context.scene
        scene.nc_dictionary[file_path] = xarray.open_dataset(file_path, decode_times=False)
        self.report({'INFO'}, "File: %s loaded!" % file_path)
        return {'FINISHED'}


class GeoNodes_OT_preloader(bpy.types.Operator):
    bl_idname = "geonodes.preloader"
    bl_label = "Preload a range of variable steps into memory"
    bl_description = "Preload a range of variable steps into memory"
    bl_options = {"REGISTER", "UNDO"}
    file_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    var_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    frame_start: bpy.props.IntProperty(
        default=1,
        name="Start",
    )

    frame_end: bpy.props.IntProperty(
        default=250,
        name="End",
    )

    def execute(self, context):
        if not self.file_name:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_name)

        if not isfile(file_path):
            self.report({'ERROR'}, "It seems that this is not a file!")
            return {'CANCELLED'}
        scene = context.scene
        scene.nc_dictionary[file_path] = xarray.open_dataset(file_path, decode_times=False)

        var_name = self.var_name
        if not var_name:
            self.report({'INFO'}, "Select a variable!")
            return {'FINISHED'}

        # Check if dictionary entry for the file exists
        try:
            scene.nc_cache[file_path]
        except KeyError:
            scene.nc_cache[file_path] = {}

        # Check if dictionary entry for the variable exists
        try:
            scene.nc_cache[file_path][var_name]
        except KeyError:
            scene.nc_cache[file_path][var_name] = {}

        # Get data dictionary stored at scene object
        data_dictionary = scene.nc_dictionary

        # Get the netcdf of the selected file
        ncdata = data_dictionary[file_path]
        # Get the data of the selected variable
        var_data = ncdata[var_name]

        var_dict = scene.nc_cache[file_path][var_name]
        # For each frame check if the frame is already in memory
        frame_start, frame_end = self.frame_start, self.frame_end
        for frame in range(frame_start, frame_end):
            try:
                var_dict[frame]
            except KeyError:
                print("Frame %i loaded!" % frame)
                frame_data = var_data[frame, :, :].values[:, :]
                normalized_data = normalize_data(frame_data)
                var_dict[frame] = from_frame_to_pixel_value(normalized_data)
        self.report({'INFO'}, "Frames %i to %i have been loaded!" % (frame_start, frame_end))
        return {'FINISHED'}


class GeoNodes_OT_netcdf2img(bpy.types.Operator):
    bl_idname = "geonodes.nc2img"
    bl_label = "From netcdf to image"
    bl_description = "Updates an image with netcdf data"
    file_name: bpy.props.StringProperty()
    var_name: bpy.props.StringProperty()
    step: bpy.props.IntProperty()
    flip: bpy.props.BoolProperty()
    image: bpy.props.StringProperty()

    def execute(self, context):
        image = self.image
        update_image(context, self.file_name, self.var_name, self.step, self.flip, self.image)
        return {'FINISHED'}


class GeoNodes_UI_PT_3dview(bpy.types.Panel):
    bl_idname = "NCLOAD_PT_Panel"
    bl_label = "GeoNodes"
    bl_category = "GeoNodes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator('geonodes.ncload', text="Load NetCDF")


class GeoNodes_NT_netcdf(bpy.types.Node):
    # === Basics ===
    # Description string
    '''A netcdf node'''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFNode'
    # Label for nice name display
    bl_label = "netCDFinput"
    # Icon identifier
    bl_icon = 'SOUND'
    blb_type = "NETCDF"

    file_name: bpy.props.EnumProperty(
        items=get_possible_files,
        name="",
    )

    var_name: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="",
        update=step_update,
    )

    flip: bpy.props.BoolProperty(
        name="flip",
        update=step_update,
    )
    update_on_frame_change: bpy.props.BoolProperty(
        name="Update on frame change",

        default=False,
    )

    image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name=""
    )
    frame_loaded: bpy.props.IntProperty(
        default=-1,
    )

    step: bpy.props.IntProperty(
        update=step_update,
    )

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        # self.outputs.new('NodeSocketColor',"color")
        self.frame_loaded = -1
        pass

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        if scene.nc_dictionary:
            layout.prop(self, "file_name")
        else:
            layout.label(text="No netcdf loaded")
        if self.file_name:
            layout.prop(self, "var_name")
        if self.var_name:
            layout.prop(self, "flip")

            layout.template_ID(self, "image", new="image.new", open="image.open")

        if self.image:
            layout.prop(self, "update_on_frame_change")
            op = layout.operator("geonodes.nc2img", icon="FILE_REFRESH")
            op.file_name = self.file_name
            op.var_name = self.var_name
            op.step = self.step
            op.flip = self.flip
            op.image = self.image.name

        # Hide unused sockets
        if not self.update_on_frame_change:
            layout.prop(self, "step")
        else:
            layout.label(text="%i" % scene.frame_current)

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "netCDF input"

    def update_value(self, context):
        self.update()

    def update(self):
        pass


class GeoNodes_NT_preloader(bpy.types.Node):
    # === Basics ===
    # Description string
    '''A netcdf node'''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFPreloadNode'
    # Label for nice name display
    bl_label = "Preload netCDF"
    # Icon identifier
    bl_icon = 'SOUND'
    blb_type = "NETCDF"

    file_name: bpy.props.EnumProperty(
        items=get_possible_files,
        name="",
    )

    var_name: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="",
        update=step_update,
    )

    frame_start: bpy.props.IntProperty(
        default=1,
        name="Start",
    )

    frame_end: bpy.props.IntProperty(
        default=250,
        name="End",
    )

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        pass

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        if scene.nc_dictionary:
            layout.prop(self, "file_name")
        else:
            layout.label(text="No netcdf loaded")
        if self.file_name:
            layout.prop(self, "var_name")
        if self.var_name:
            layout.prop(self, "frame_start")
            layout.prop(self, "frame_end")
            if self.frame_end > self.frame_start:
                op = layout.operator("geonodes.preloader", icon="FILE_REFRESH")
                op.file_name = self.file_name
                op.var_name = self.var_name
                op.frame_start = self.frame_start
                op.frame_end = self.frame_end
            else:
                layout.label(text="Cannot preload!")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "netCDF preload"

    def update_value(self, context):
        self.update()

    def update(self):
        pass


class GeoNodesNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == node_tree_name


# all categories in a list
node_categories = [
    # identifier, label, items list
    GeoNodesNodeCategory('netCDF', "netCDF", items=[
        # our basic node
        NodeItem("netCDFNode"),
        NodeItem("netCDFPreloadNode"),

    ])
]
