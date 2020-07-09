# Imports
import bpy

from blendernc.blendernc.python_functions import (get_possible_files, get_possible_variables,
                                dict_update)

from blendernc.blendernc.msg_errors import unselected_nc_file

from collections import defaultdict

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

    # Note that this dictionary is in shared memory.
    blendernc_dict = defaultdict(None)

    blendernc_file: bpy.props.StringProperty()
    
    blendernc_netcdf_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="",
        update=dict_update,
    )

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
        self.blendernc_dict.pop(self.name)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        if self.name in self.blendernc_dict.keys():
            layout.label(text = "Loaded netcdf:")
            layout.label(text = self.blendernc_file.split("/")[-1])
            layout.prop(self, "blendernc_netcdf_vars")
        else:
            layout.label(text="No netcdf loaded!")
            
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
        #print(self.name, (self.inputs[0].is_linked and self.inputs[0].links))
        if (self.inputs[0].is_linked and self.inputs[0].links):
            self.blendernc_file=self.inputs[0].links[0].from_socket.text
            if (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath'
                and self.blendernc_file and self.name not in self.blendernc_dict.keys()):
                bpy.ops.blendernc.ncload(file_path = self.blendernc_file, node_group = self.rna_type.id_data.name, node = self.name)
            elif (self.inputs[0].links[0].from_node.bl_idname == 'netCDFPath'  and 
                  self.blendernc_file in self.blendernc_dict[self.name].keys()):
                pass
            else:
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
                bpy.context.window_manager.popup_menu(unselected_nc_file, title="Error", icon='ERROR')
        else:
            if self.blendernc_file and self.name in self.blendernc_dict.keys() :
                self.blendernc_dict.pop(self.name)
        
        if self.outputs.items():
            if self.outputs[0].is_linked and self.blendernc_file:
                self.outputs[0].dataset=self.blendernc_file
                self.outputs[0].input_load_node=self.name
        else: 
            pass