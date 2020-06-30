# Imports
import bpy

from blendernc.blendernc.python_functions import step_update

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
        update = step_update,
    )

    frame_loaded: bpy.props.IntProperty(
        default = -1,
    )

    step: bpy.props.IntProperty(
        update = step_update,
    )

    blendernc_netcdf_vars: bpy.props.StringProperty()
    blendernc_file: bpy.props.StringProperty()
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
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        scene = context.scene

        layout.template_ID(self, "image", new="image.new", open="image.open")

        if self.image:
            layout.prop(self, "update_on_frame_change")
            op = layout.operator("blendernc.nc2img", icon="FILE_REFRESH")
            op.file_name = self.blendernc_file
            op.var_name = self.blendernc_netcdf_vars
            op.step = self.step
            op.image = self.image.name

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

    def update_value(self, context):
        self.update()

    def update(self):
        if bool(self.inputs[0].is_linked and self.inputs[0].links):
            if self.inputs[0].links[0].from_socket.var != 'NONE':
                self.blendernc_netcdf_vars = self.inputs[0].links[0].from_socket.var 
                self.blendernc_file = self.inputs[0].links[0].from_socket.dataset
