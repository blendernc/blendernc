# Imports
import bpy

from blendernc.blendernc.decorators import NodesDecorators

from collections import defaultdict

class BlenderNC_NT_input_grid(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFinputgrid'
    # Label for nice name display
    bl_label = "Input Grid"
    # Icon identifier
    bl_icon = 'SNAP_GRID'
    blb_type = "NETCDF"

    blendernc_file: bpy.props.StringProperty()
    
    blendernc_grid_x: bpy.props.EnumProperty(
        items=[],
        name="Select X grid",
        #update=dict_update,
    )

    blendernc_grid_y: bpy.props.EnumProperty(
        items=[],
        name="Select Y grid",
        #update=dict_update,
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
        self.inputs.new('bNCstringSocket',"Path")
        self.outputs.new('bNCnetcdfSocket',"Grid")

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
        layout.label(text="Select grid:")
        layout.label(text="X grid:")
        layout.prop(self, "blendernc_grid_x",text="")
        layout.label(text="Y grid:")
        layout.prop(self, "blendernc_grid_y",text="")
        
    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Grid Import"

    @NodesDecorators.node_connections
    def update(self):
        #####################
        # OPERATION HERE!!! #
        #####################
        pass
        