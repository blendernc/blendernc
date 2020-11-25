# Imports
import bpy
import numpy as np

from .. .. blendernc.python_functions import update_value_and_node_tree, update_node_tree, refresh_cache

from .. .. blendernc.decorators import NodesDecorators

from collections import defaultdict

operation_items = [
    ("Multiply", "Multiply", "", 1),
    ("Divide", "Divide", "", 2),
    ("Add", "Add", "", 3),
    ("Subtract", "Subtract", "", 4),
    ("Logarithm", "Log", "", 5),
    ("SymLog", "SymLog", "", 6),
    ("Power", "Power", "", 7),
]

operation_types = {
    'float':('Multiply','Divide','SymLog','Power'), 
    'unique': ('Logarithm'),
    'dataset': ('Add','Subtract'),
    }

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
        layout.prop(self, "blendernc_operation",text='')
        operation = self.blendernc_operation
        if operation in operation_types['float'] and 'Float' not in self.inputs.keys() :
            if len(self.inputs.keys())==2:
                self.inputs.remove(self.inputs[-1])
            self.inputs.new('bNCfloatSocket',"Float")
        elif operation in operation_types['unique'] and 'Float' in self.inputs.keys() :
            if len(self.inputs.keys())==2:
                # self.inputs.remove(self.inputs[-1])
                self.inputs.remove(self.inputs.get('Float'))
        elif operation in operation_types['unique'] and 'Float' not in self.inputs.keys() :
            if len(self.inputs.keys())==2:
                self.inputs.remove(self.inputs[-1])
        elif operation in operation_types['dataset'] and 'Float' in self.inputs.keys():
            self.inputs.remove(self.inputs.get('Float'))
            self.inputs.new('bNCnetcdfSocket',"Dataset")
        elif operation in operation_types['dataset'] and len(self.inputs.keys())==1:
            self.inputs.new('bNCnetcdfSocket',"Dataset")
        else:
            pass

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
        unique_identifier = self.blendernc_dataset_identifier
        parent_node = self.inputs[0].links[0].from_node
        dataset = parent_node.blendernc_dict[unique_identifier]['Dataset'].copy()
        # print(dataset.isel(latitude=0).isel(time=0).values)
        if self.blendernc_operation == 'Multiply':
            dataset = dataset*self.inputs.get('Float').Float
        elif self.blendernc_operation == 'Divide':
            dataset = dataset/self.inputs.get('Float').Float
        elif self.blendernc_operation == 'Add':
            if  self.inputs[-1].links:
                dataset = dataset+self.inputs[-1].links[0].from_node.blendernc_dict
        elif self.blendernc_operation == 'Subtract':
            if  self.inputs[-1].links:
                dataset = dataset-self.inputs[-1].links[0].from_node.blendernc_dict
        elif self.blendernc_operation == 'Logarithm':
            dataset = np.log10(dataset)
        elif self.blendernc_operation == 'SymLog':
            constant = self.inputs.get('Float').Float
            dataset = np.log10( 1 + np.abs(dataset)/constant ) * np.sign(dataset)
        elif self.blendernc_operation == 'Power':
            constant = self.inputs.get('Float').Float
            dataset = dataset**constant
        # print(dataset.isel(latitude=0).isel(time=0).values)
        self.blendernc_dict[self.blendernc_dataset_identifier]['Dataset'] = dataset

        NodeTree = self.rna_type.id_data.name
        frame = bpy.context.scene.frame_current
        identifier = self.blendernc_dataset_identifier
        refresh_cache(NodeTree, identifier, frame)
        update_node_tree(self,bpy.context)


