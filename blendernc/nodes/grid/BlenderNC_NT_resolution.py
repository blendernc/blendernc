# Imports
import bpy

from ....blendernc.python_functions import netcdf_values, update_value_and_node_tree

from ....blendernc.decorators import NodesDecorators

from collections import defaultdict


class BlenderNC_NT_resolution(bpy.types.Node):
    # === Basics ===
    # Description string
    """NetCDF loading resolution """
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = "netCDFResolution"
    # Label for nice name display
    bl_label = "Resolution"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    blendernc_resolution: bpy.props.FloatProperty(
        name="Resolution",
        min=1,
        max=100,
        default=50,
        step=100,
        update=update_value_and_node_tree,
        precision=0,
        options={"ANIMATABLE"},
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
        self.inputs.new("bNCnetcdfSocket", "Dataset")
        self.outputs.new("bNCnetcdfSocket", "Dataset")
        self.color = (0.4, 0.4, 0.8)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        if self.blendernc_dataset_identifier != "":
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.prop(self, "blendernc_resolution")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Resolution"

    @NodesDecorators.node_connections
    def update(self):
        dataset = self.blendernc_dict[self.blendernc_dataset_identifier]["Dataset"]
        var_name = self.blendernc_dict[self.blendernc_dataset_identifier][
            "selected_var"
        ]["selected_var_name"]
        self.blendernc_dict[self.blendernc_dataset_identifier][
            "Dataset"
        ] = netcdf_values(dataset, var_name, self.blendernc_resolution)
        self.blendernc_dict[self.blendernc_dataset_identifier]["selected_var"][
            "resolution"
        ] = self.blendernc_resolution
        # TODO: Do I know time here if so, select time and load snapshot here
