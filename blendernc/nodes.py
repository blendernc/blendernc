# Imports
import bpy
from nodeitems_utils import  NodeItem
from . python_functions import (get_possible_files, get_possible_variables, 
                                step_update, res_update,
                                dict_update)

from . events import CurrentEvents, BlenderEventsTypes
from . node_tree import updateNode, BlenderNCNodeCategory

########################################################
########################################################
########################################################

class BlenderNC_NT_path(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFPath'
    # Label for nice name display
    bl_label = "netCDF Path"
    # Icon identifier
    bl_icon = 'FOLDER_REDIRECT'
    blb_type = "NETCDF"

    # TODO: Fix updateNode, currently it doesn't update the nodetree, and therefore
    # the user has to reconnect the node.
    blendernc_file: bpy.props.StringProperty(
                    name="",
                    description="Folder with assets blend files",
                    default="",
                    maxlen=1024,
                    update=updateNode,
                    subtype='FILE_PATH')    

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.outputs.new('bNCstringSocket',"Path")
        self.color = (0.4,0.8,0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene
        layout.prop(self, "blendernc_file")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "netCDF Path"

    def update_value(self, context):
        self.update()

    def update(self):
        if self.outputs[0].is_linked and self.blendernc_file:
            self.outputs[0].text=self.blendernc_file

########################################################
########################################################
########################################################

class BlenderNC_NT_netcdf(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Node to initiate dataset'''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFNode'
    # Label for nice name display
    bl_label = "netCDF input"
    # Icon identifier
    bl_icon = 'UGLYPACKAGE'
    bl_type = "NETCDF"

    blendernc_file: bpy.props.EnumProperty(
        items=get_possible_files,
        name="",
    )

    blendernc_netcdf_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="",
        update=dict_update,
    )

    # flip: bpy.props.BoolProperty(
    #     name="flip",
    #     update=step_update,
    # )

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new('bNCstringSocket',"Path")
        self.outputs.new('bNCnetcdfSocket',"Dataset")
        self.color = (0.4,0.8,0.4)
        self.use_custom_color = True
        

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
            layout.prop(self, "blendernc_file")
        else:
            layout.label(text="No netcdf loaded")
        if self.blendernc_file:
            layout.prop(self, "blendernc_netcdf_vars")

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
        file_path=self.inputs[0].links[0].from_socket.text
        if (self.inputs[0].is_linked) and file_path:
            if (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath' and file_path not in bpy.context.scene.nc_dictionary.keys()):
                bpy.ops.blendernc.ncload(file_path = file_path)
                # Update 
                while not bpy.context.scene.nc_dictionary:
                    self.update()
            elif (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath'  and file_path in bpy.context.scene.nc_dictionary.keys()):
                pass
            else:
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
        else: 
            # TODO Raise issue to user
            pass
        
        if self.outputs[0].is_linked and self.blendernc_netcdf_vars:
            self.outputs[0].dataset=self.blendernc_file
            self.outputs[0].var = self.blendernc_netcdf_vars
        else: 
            # TODO Raise issue to user
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

    blendernc_resolution: bpy.props.FloatProperty(name = 'Resolution', 
                                                min = 1, max = 100, 
                                                default = 50, step =100,
                                                update=res_update,
                                                precision=0, options={'ANIMATABLE'})

    blendernc_netcdf_vars: bpy.props.StringProperty()
    blendernc_file: bpy.props.StringProperty()

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new('bNCnetcdfSocket',"Dataset")
        self.outputs.new('bNCnetcdfSocket',"Dataset")
        self.color = (0.4,0.4,0.8)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene
        layout.prop(self, "blendernc_resolution")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Resolution"

    def update_value(self, context):
        self.update()

    def update(self):
        if (self.inputs[0].is_linked) and self.inputs[0].links[0].from_socket.var !='NONE':
            self.blendernc_netcdf_vars = self.inputs[0].links[0].from_socket.var 
            self.blendernc_file = self.inputs[0].links[0].from_socket.dataset
            bpy.context.scene.nc_dictionary[self.blendernc_file][self.blendernc_netcdf_vars]['resolution'] = self.blendernc_resolution
            #bpy.ops.blendernc.ncload(file_path = self.inputs[0].links[0].from_node.blendernc_file)
        elif self.inputs[0].is_linked:
            # TODO Raise issue to select variable
            self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
        else: 
            # TODO Raise issue to user
            pass
            
        if self.outputs[0].is_linked and self.blendernc_netcdf_vars:
            self.outputs[0].dataset=self.blendernc_file
            self.outputs[0].var = self.blendernc_netcdf_vars
        else: 
            # TODO Raise issue to user
            pass

class BlenderNC_NT_select_axis(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFaxis'
    # Label for nice name display
    bl_label = "Select Axis"
    # Icon identifier
    bl_icon = 'MESH_GRID'
    blb_type = "NETCDF"

    axis: bpy.props.EnumProperty(items=(''),name="")

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
        layout.prop(self, "axis")
  

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Select Axis"

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

    blendernc_netcdf_vars: bpy.props.StringProperty()
    blendernc_file: bpy.props.StringProperty()
    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.frame_loaded = -1
        self.inputs.new('bNCnetcdfSocket',"Dataset")
        self.color = (0.8,0.4,0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        layout.template_ID(self, "image", new="image.new", open="image.open")

        if self.image:
            layout.prop(self, "update_on_frame_change")
            op = layout.operator("blendernc.nc2img", icon="FILE_REFRESH")
            op.file_name = self.blendernc_file
            op.var_name = self.blendernc_netcdf_vars
            op.step = self.step
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
        return "Image Output"

    def update_value(self, context):
        self.update()

    def update(self):
        if (self.inputs[0].is_linked) and self.inputs[0].links[0].from_socket.var !='NONE':
            self.blendernc_netcdf_vars = self.inputs[0].links[0].from_socket.var 
            self.blendernc_file = self.inputs[0].links[0].from_socket.dataset

class BlenderNC_NT_preloader(bpy.types.Node):
    # === Basics ===
    # Description string
    '''A netcdf node'''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFPreloadNode'
    # Label for nice name display
    bl_label = "Load netCDF"
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
        return "Load netCDF"

    def update_value(self, context):
        self.update()

    def update(self):
        pass

# all categories in a list
node_categories = [
    # identifier, label, items list
    BlenderNCNodeCategory('netCDF', "netCDF", items=[
        # our basic node
        NodeItem("netCDFNode"),
        NodeItem("netCDFPath"),
    ]),
    BlenderNCNodeCategory('Grid', "Grid", items=[
        # our basic node
        NodeItem("netCDFResolution"),
    ]),
    BlenderNCNodeCategory('Selection', "Selection", items=[
        # our basic node
        NodeItem("netCDFaxis"),
    ]),
    BlenderNCNodeCategory('Math', "Math", items=[
        # our basic node
        NodeItem("netCDFOutput")
    ]),
    BlenderNCNodeCategory('Output', "Output", items=[
        # our basic node
        NodeItem("netCDFOutput"),
        NodeItem("netCDFPreloadNode"),
    ])

    
]
