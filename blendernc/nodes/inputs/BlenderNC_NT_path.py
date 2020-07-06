# Imports
import bpy

class BlenderNC_NT_path(bpy.types.Node):
    # === Basics ===
    # Description string
    '''Select axis '''
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = 'netCDFPath'
    # Label for nice name display
    bl_label = "netCDF Path"
    # Icon identifier
    bl_icon = 'FOLDER_REDIRECT'
    blb_type = "NETCDF"
    
    blendernc_file: bpy.props.StringProperty(name="",
                    description="Folder with assets blend files",
                    default="",
                    maxlen=1024)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.outputs.new('bNCstringSocket',"Path")
        self.color = (0.4,0.8,0.4)
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
        
        row = layout.row(align=True)
        split = row.split(factor=0.85,align=True)

        split.prop(self, 'blendernc_file')
        split.operator('blendernc.import_mfnetcdf', text='', icon='FILEBROWSER')
        

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "netCDF Path"

    def update_value(self, context):
        self.update()

    def update(self):
        if self.outputs[0].is_linked and self.blendernc_file:
            self.outputs[0].text=self.blendernc_file