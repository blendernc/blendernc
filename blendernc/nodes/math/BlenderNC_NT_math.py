# Imports
import bpy
import numpy as np

from blendernc.blendernc.python_functions import update_value_and_node_tree, refresh_cache

from blendernc.blendernc.decorators import NodesDecorators

from collections import defaultdict

operation_items = [
    ("Multiply", "Multiply", "", 1),
    ("Divide", "Divide", "", 2),
    ("Logarithm", "Log", "", 3),
#    ("Add", "Add", "", 2),
]

class BlenderNC_NT_math(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFmath'
    # Label for nice name display
    bl_label = "Math"
    # Icon identifier
    bl_icon = 'FCURVE_SNAPSHOT'
    blb_type = "NETCDF"

    blendernc_operation: bpy.props.EnumProperty(
        items=operation_items,
        name="Select operation",
        update=update_value_and_node_tree,
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
        self.inputs.new('NodeSocketFloat',"Float")
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
        layout.prop(self, "blendernc_operation")
            
    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Math"

    @NodesDecorators.node_connections
    def update(self):
        # TODO Real time update to be fixed.
        unique_identifier = self.blendernc_dataset_identifier
        parent_node = self.inputs[0].links[0].from_node
        dataset = parent_node.blendernc_dict[unique_identifier]['Dataset'].copy()
        print(dataset.isel(lat=0).isel(time=0).values)
        if self.blendernc_operation == 'Multiply':
            dataset = dataset*self.inputs.get('Float').default_value
        elif self.blendernc_operation == 'Divide':
            dataset = dataset/self.inputs.get('Float').default_value
        elif self.blendernc_operation == 'Logarithm':
            dataset = np.log10(dataset)
        print(dataset.isel(lat=0).isel(time=0).values)
        self.blendernc_dict[self.blendernc_dataset_identifier]['Dataset'] = dataset

        NodeTree = self.rna_type.id_data.name
        frame = bpy.context.scene.frame_current
        identifier = self.blendernc_dataset_identifier
        refresh_cache(NodeTree, identifier, frame)
 
