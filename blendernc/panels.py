import bpy
from . python_functions import step_update

gui_active_panel_fin = None

def update_proxy_file(self, context):
    """
    Update function:
        -   Checks if netCDF file exists 
        -   Extracts variable names using netCDF4 conventions.
    """
    bpy.ops.blendernc.ncload(file_path=bpy.context.scene.blendernc_file)

    # try:
        
    #     #blendernc_core.check_files_netcdf(file_path)
    # except (NameError, ValueError):
    #     bpy.ops.blendernc.file_error()

# Scene globals
bpy.types.Scene.blendernc_resolution = bpy.props.FloatProperty(name = 'Resolution', 
                                                min = 1, max = 100, 
                                                default = 50, step =100,
                                                update=step_update,
                                                precision=0, options={'ANIMATABLE'})

bpy.types.Scene.blendernc_netcdf_vars = bpy.props.EnumProperty(items=(''),
                                                                name="")

bpy.types.Scene.blendernc_file = bpy.props.StringProperty(
    name="",
    description="Folder with assets blend files",
    default="",
    maxlen=1024,
    update=update_proxy_file,
    subtype='FILE_PATH')

class BlenderNC_LOAD_OT_On(bpy.types.Operator):
    bl_label = 'Load netCDF'
    bl_idname = 'blendernc.button_file_on'
    bl_description = 'Open file and netCDF panel'
    bl_context = 'objectmode'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        global gui_active_panel_fin
        gui_active_panel_fin = "Files"
        return {'FINISHED'}

class BlenderNC_LOAD_OT_Off(bpy.types.Operator):
    bl_label = 'Load netCDF'
    bl_idname = 'blendernc.button_file_off'
    bl_description = 'Close file and netCDF panel'
    bl_context = 'objectmode'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        global gui_active_panel_fin
        gui_active_panel_fin = None
        return {'FINISHED'}


class BlenderNC_UI_PT_3dview(bpy.types.Panel):
    bl_idname = "NCLOAD_PT_Panel"
    bl_label = "BlenderNC"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):

        icon_expand = "DISCLOSURE_TRI_RIGHT"
        icon_collapse = "DISCLOSURE_TRI_DOWN"

        box_post_opt = self.layout.box()
        scn=context.scene

        box_post_opt.label(text="Load netCDF", icon='MODIFIER_ON')
        if gui_active_panel_fin != "Files":
            box_post_opt.operator('blendernc.button_file_on', icon=icon_expand)
        else:
            box_post_opt.operator('blendernc.button_file_off', icon=icon_collapse)
            # Box containing pop up menu.
            box_asts = box_post_opt.box()

            # Open blender file selection
            box_asts.label(text="netCDF File", icon='OUTLINER_OB_GROUP_INSTANCE')
            box_asts.prop(scn, 'blendernc_file')
            # Select variables menu
            box_asts.label(text="Select variable:", icon='WORLD_DATA')
            box_asts.prop(scn, 'blendernc_netcdf_vars')
            # TO DO: Add info?
            box_asts.label(text="INFO", icon='INFO')
        
        self.layout.label(text="WIP.", icon='INFO')
        self.layout.prop(scn, 'blendernc_resolution')
        


