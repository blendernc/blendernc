# Imports
import bpy

from blendernc.blendernc.python_functions import  update_range

from blendernc.blendernc.msg_errors import unselected_nc_var, unselected_nc_file

from collections import defaultdict

class BlenderNC_NT_range(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFRange'
    # Label for nice name display
    bl_label = "netCDF Range"
    # Icon identifier
    bl_icon = 'OUTLINER'
    blb_type = "NETCDF"

    blendernc_dataset_min: bpy.props.FloatProperty(
                name='vmin',
                default = 0,
                update = update_range
    )
    blendernc_dataset_max: bpy.props.FloatProperty(
                name='vmax',
                default = 1,
                update = update_range
    )

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new('bNCnetcdfSocket',"Dataset")
        self.outputs.new('bNCnetcdfSocket',"Dataset")

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        if self.blendernc_dataset_identifier!='':
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Select:")
        layout.prop(self, "blendernc_dataset_min")
        layout.prop(self, "blendernc_dataset_max")
        layout.label(text="or")
        operator = layout.operator("blendernc.compute_range", icon="DRIVER_DISTANCE")
        operator.node = self.name
        operator.node_group = self.rna_type.id_data.name
        
    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Range"

    def update(self):
        if self.inputs[0].is_linked and self.inputs[0].links:
            self.blendernc_dataset_identifier = self.inputs[0].links[0].from_socket.unique_identifier
            nc_dict = self.inputs[0].links[0].from_socket.dataset
            if self.blendernc_dataset_identifier == '' or len(nc_dict.keys()):
                self.blendernc_dataset_identifier = self.inputs[0].links[0].from_node.blendernc_dataset_identifier
                nc_dict = self.inputs[0].links[0].from_node.blendernc_dict.copy()
            
            # Check that nc_dict contains at least an unique identifier
            if self.blendernc_dataset_identifier in nc_dict.keys():
                self.blendernc_dict[self.blendernc_dataset_identifier] = nc_dict[self.blendernc_dataset_identifier].copy()
                # Check if user has selected a variable
                if 'selected_var' not in self.blendernc_dict[self.blendernc_dataset_identifier].keys():
                    bpy.context.window_manager.popup_menu(unselected_nc_var, title="Error", icon='ERROR')
                    self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
                    return

                self.blendernc_dict[self.blendernc_dataset_identifier]['selected_var']["max_value"] = self.blendernc_dataset_max
                self.blendernc_dict[self.blendernc_dataset_identifier]['selected_var']["min_value"] = self.blendernc_dataset_min 

            else: 
                bpy.context.window_manager.popup_menu(unselected_nc_file, title="Error", icon='ERROR')
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
        else:
            if self.blendernc_dataset_identifier in self.blendernc_dict.keys() :
                self.blendernc_dict.pop(self.blendernc_dataset_identifier)
            
        if self.outputs.items():
            if self.outputs[0].is_linked and self.inputs[0].is_linked:
                self.outputs[0].dataset[self.blendernc_dataset_identifier] = self.blendernc_dict[self.blendernc_dataset_identifier].copy()
                self.outputs[0].unique_identifier = self.blendernc_dataset_identifier