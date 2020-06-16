# Imports
import bpy
from nodeitems_utils import NodeCategory, NodeItem
from . python_functions import get_possible_files, get_possible_variables, step_update
# Blender Classes
node_tree_name = "BlenderNC"
create_new_node_tree = node_tree_name != "ShaderNodeTree"
if create_new_node_tree:
    # Derived from the NodeTree base type, similar to Menu, Operator, Panel, etc.
    class BlenderNCNodeTree(bpy.types.NodeTree):
        # Description string
        '''A custom node tree type that will show up in the editor type list'''
        # Optional identifier string. If not explicitly defined, the python class name is used.
        bl_idname = node_tree_name
        # Label for nice name display
        bl_label = "BlenderNC"
        # Icon identifier
        bl_icon = 'WORLD'


class BlenderNC_NT_netcdf(bpy.types.Node):
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
        self.outputs.new('NodeSocketFloat',"Dataset")
        self.frame_loaded = -1

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
            op = layout.operator("blendernc.nc2img", icon="FILE_REFRESH")
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


class BlenderNC_NT_preloader(bpy.types.Node):
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
                op = layout.operator("blendernc.preloader", icon="FILE_REFRESH")
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


class BlenderNC_NT_resolution(bpy.types.Node):
    # === Basics ===
    # Description string
    '''NetCDF loading resolution '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFResolution'
    # Label for nice name display
    bl_label = "Resolution"
    # Icon identifier
    bl_icon = 'MESH_GRID'
    blb_type = "NETCDF"

    resolution: bpy.props.FloatProperty(name = 'Resolution', 
                                                min = 1, max = 100, 
                                                default = 50, step =100,
                                                #update=update_proxy_resolution,
                                                precision=0, options={'ANIMATABLE'})

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new('NodeSocketString',"Dataset")
        self.outputs.new('NodeSocketString',"Dataset")

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        layout.prop(self, "resolution")
  

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


class BlenderNC_NT_output(bpy.types.Node):
    # === Basics ===
    # Description string
    '''NetCDF loading resolution '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFOutput'
    # Label for nice name display
    bl_label = "Output"
    # Icon identifier
    bl_icon = 'RENDER_RESULT'
    blb_type = "NETCDF"

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new('NodeSocketString',"Dataset")

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        layout.prop(self, "resolution")
  
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


class BlenderNCNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == node_tree_name


# all categories in a list
node_categories = [
    # identifier, label, items list
    BlenderNCNodeCategory('netCDF', "netCDF", items=[
        # our basic node
        NodeItem("netCDFNode"),
        NodeItem("netCDFPreloadNode"),
    ]),
    BlenderNCNodeCategory('Grid', "Grid", items=[
        # our basic node
        NodeItem("netCDFResolution"),
    ]),
    BlenderNCNodeCategory('Output', "Output", items=[
        # our basic node
        NodeItem("netCDFOutput"),
    ])

    
]
