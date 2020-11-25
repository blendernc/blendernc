# Imports
import bpy

from .. .. blendernc.python_functions import  update_range

from .. .. blendernc.decorators import NodesDecorators

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

    @NodesDecorators.node_connections
    def update(self):
        # Update vmax and vmin of the dataset.
        self.blendernc_dict[self.blendernc_dataset_identifier]['selected_var']["max_value"] = self.blendernc_dataset_max
        self.blendernc_dict[self.blendernc_dataset_identifier]['selected_var']["min_value"] = self.blendernc_dataset_min 