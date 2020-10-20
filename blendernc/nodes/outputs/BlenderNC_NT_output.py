# Imports
import bpy

from blendernc.blendernc.python_functions import  update_image, update_value, update_colormap_interface

from blendernc.blendernc.decorators import NodesDecorators

from blendernc.blendernc.image import dataset_2_image_preview

from collections import defaultdict

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
        name = "Update on frame change",
        default = False,
    )

    image: bpy.props.PointerProperty(
        type = bpy.types.Image,
        name = "",
        update=update_value,
    )

    frame_loaded: bpy.props.IntProperty(
        default = -1,
    )

    frame: bpy.props.IntProperty(
        default = 1,
    )

    grid_node_name: bpy.props.StringProperty()

    
    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    blendernc_dict = defaultdict(None)

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
        if self.blendernc_dataset_identifier!='':
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        # Generated image supported by bpy to display, but perhaps show a preview of field?
        layout.template_ID_preview(self, "image", new="image.new", open="image.open",rows=2, cols=3)
        if self.image:
            if self.image.is_float and (not self.image.preview.is_image_custom and
                self.blendernc_dataset_identifier in self.blendernc_dict.keys()):
                image_preview = dataset_2_image_preview(self)
                self.image.preview.image_pixels_float[0:] = image_preview

        if self.image and self.blendernc_dataset_identifier in self.blendernc_dict.keys():
            layout.prop(self, "update_on_frame_change")
            # operator = layout.operator("blendernc.nc2img", icon="FILE_REFRESH")
            # operator.node = self.name
            # operator.node_group = self.rna_type.id_data.name
            # operator.frame = self.frame
            # operator.image = self.image.name
            
            operator = layout.operator("blendernc.colorbar", icon='GROUP_VCOL')
            operator.node = self.name
            operator.node_group = self.rna_type.id_data.name
            operator.image = self.image.name
        
        if 'Input Grid' in self.rna_type.id_data.nodes.keys() and len(self.inputs) == 1:
            self.inputs.new('bNCnetcdfSocket',"Grid")
        elif 'Input Grid' not in self.rna_type.id_data.nodes.keys() and len(self.inputs) == 2:
            self.inputs.remove(self.inputs.get("Grid"))
        
    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Image Output"

    @NodesDecorators.node_connections
    def update(self):
        node_tree = self.rna_type.id_data.name
        # TODO Move this section to the decorator.
        if len(self.inputs)==2:
            if self.inputs[1].is_linked and self.inputs[1].links:
                self.grid_node_name = self.inputs[1].links[0].from_node.name

        if self.image:
            update_image(bpy.context, self.name, node_tree, bpy.context.scene.frame_current, self.image.name, self.grid_node_name)
            if self.image.users >=3 :
                update_colormap_interface(bpy.context, self.name, node_tree)
