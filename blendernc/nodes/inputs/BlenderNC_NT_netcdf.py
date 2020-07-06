# Imports
import bpy

from blendernc.blendernc.python_functions import (get_possible_files, get_possible_variables,
                                dict_update)

from blendernc.blendernc.msg_errors import unselected_nc_file

class BlenderNC_NT_netcdf(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Node to initiate netCDF dataset using xarray'''
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
        if (self.inputs[0].is_linked):
            file_path=self.inputs[0].links[0].from_socket.text
            if (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath' 
                and file_path not in bpy.context.scene.nc_dictionary.keys() 
                and file_path):
                bpy.ops.blendernc.ncload(file_path = file_path)
                # Update 
                while not bpy.context.scene.nc_dictionary:
                    self.update()
            elif (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath'  and file_path in bpy.context.scene.nc_dictionary.keys()):
                pass
            else:
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
                bpy.context.window_manager.popup_menu(unselected_nc_file, title="Error", icon='ERROR')
        else: 
            pass
        
        if self.outputs.items() and self.blendernc_netcdf_vars:
            if self.outputs[0].is_linked:
                self.outputs[0].dataset=self.blendernc_file
                self.outputs[0].var = self.blendernc_netcdf_vars
        else: 
            pass