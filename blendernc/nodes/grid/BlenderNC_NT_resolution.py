# Imports
import bpy

from blendernc.blendernc.python_functions import res_update

from blendernc.blendernc.msg_errors import unselected_nc_var, unselected_nc_file

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

    blendernc_import_node: bpy.props.StringProperty()
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
        if bool(self.inputs[0].is_linked and self.inputs[0].links):
            if (self.inputs[0].links[0].from_socket.input_load_node):
                self.blendernc_import_node = self.inputs[0].links[0].from_socket.input_load_node 
                self.blendernc_file = self.inputs[0].links[0].from_socket.dataset
                bpy.context.scene.nc_dictionary[self.blendernc_file][self.blendernc_netcdf_vars]['resolution'] = self.blendernc_resolution
                #bpy.ops.blendernc.ncload(file_path = self.inputs[0].links[0].from_node.blendernc_file)
            elif (self.inputs[0].links[0].from_socket.var == 'NONE'):
                bpy.context.window_manager.popup_menu(unselected_nc_var, title="Error", icon='ERROR')
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
            else: 
                bpy.context.window_manager.popup_menu(unselected_nc_file, title="Error", icon='ERROR')
        else:
            pass
            
        if self.outputs.items() and self.blendernc_netcdf_vars:
            if self.outputs[0].is_linked and self.inputs[0].is_linked:
                self.outputs[0].dataset = self.blendernc_file
                self.outputs[0].input_load_node = self.blendernc_import_node
        else: 
            # TODO Raise issue to user
            pass