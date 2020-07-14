# Imports
import bpy

from blendernc.blendernc.python_functions import  update_image, update_value, update_colormap_interface

from blendernc.blendernc.msg_errors import unselected_nc_var, unselected_nc_file

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

    step: bpy.props.IntProperty()

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
        scene = context.scene

        #layout.template_ID(self, "image", new="image.new", open="image.open")
        # Generated image supported by bpy to display, but perhaps show a preview of field?
        layout.template_ID_preview(self, "image", new="image.new", open="image.open",rows=2, cols=3)
        if self.image:
            if self.image.is_float and (not self.image.preview.is_image_custom and
                self.blendernc_dataset_identifier in self.blendernc_dict.keys()):
                image_preview = dataset_2_image_preview(self)
                self.image.preview.image_pixels_float[0:] = image_preview

        if self.image and self.blendernc_dataset_identifier in self.blendernc_dict.keys():
            layout.prop(self, "update_on_frame_change")
            operator = layout.operator("blendernc.nc2img", icon="FILE_REFRESH")
            operator.node = self.name
            operator.node_group = self.rna_type.id_data.name
            operator.step = self.step
            operator.image = self.image.name

            
                
            # Update image preview witn 8 byte image.
            #if self.image.preview.image_pixels_float
            #    self.image.preview.image_pixels_float
            
            #rand = [np.random.rand() for i in range(256*256)]
            #D.node_groups['NodeTree'].nodes['Output'].image.preview.image_pixels_float =  rand

            # Hide unused sockets
            if not self.update_on_frame_change:
                layout.prop(self, "step")
            else:
                layout.label(text="%i" % scene.frame_current)
  
    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Image Output"

    def update(self):
        node_tree = self.rna_type.id_data.name
        if self.inputs[0].is_linked and self.inputs[0].links:
            # Delete cache if a different dataset is loaded.
            if self.blendernc_dataset_identifier !='' and self.blendernc_dataset_identifier != self.inputs[0].links[0].from_node.blendernc_dataset_identifier:
                bpy.context.scene.nc_cache[node_tree].pop(self.name)

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
                if self.image:
                    update_image(bpy.context, self.name, node_tree, bpy.context.scene.frame_current, self.image.name)
                    
            else: 
                bpy.context.window_manager.popup_menu(unselected_nc_file, title="Error", icon='ERROR')
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
        else:
            if self.blendernc_dataset_identifier in self.blendernc_dict.keys() :
                self.blendernc_dict.pop(self.blendernc_dataset_identifier)