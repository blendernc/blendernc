#!/usr/bin/env python3
import bpy

from .python_functions import empty_item, update_animation, update_file_vars, update_res

gui_active_panel_fin = None
gui_active_materials = None


class BlenderNC_LOAD_OT_On(bpy.types.Operator):
    bl_label = "Load netCDF"
    bl_idname = "blendernc.button_file_on"
    bl_description = "Open file and netCDF panel"
    bl_context = "objectmode"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        global gui_active_panel_fin
        gui_active_panel_fin = "Files"
        return {"FINISHED"}


class BlenderNC_LOAD_OT_Off(bpy.types.Operator):
    bl_label = "Load netCDF"
    bl_idname = "blendernc.button_file_off"
    bl_description = "Close file and netCDF panel"
    bl_context = "objectmode"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        global gui_active_panel_fin
        gui_active_panel_fin = None
        return {"FINISHED"}


def select_only_meshes(self, object):
    return object.type == "MESH"


# Scene globals
bpy.types.Scene.blendernc_resolution = bpy.props.FloatProperty(
    name="Resolution",
    min=1,
    max=100,
    default=50,
    step=100,
    update=update_res,
    precision=0,
    options={"ANIMATABLE"},
)

bpy.types.Scene.blendernc_netcdf_vars = bpy.props.EnumProperty(
    items=empty_item(), name="No variable"
)

bpy.types.Scene.blendernc_file = bpy.props.StringProperty(
    name="",
    description="Folder with assets blend files",
    default="",
    maxlen=1024,
    update=update_file_vars,
)

bpy.types.Scene.blendernc_meshes = bpy.props.PointerProperty(
    name="Select a mesh", type=bpy.types.Object, poll=select_only_meshes
)

bpy.types.Scene.blendernc_animate = bpy.props.BoolProperty(
    default=False, name="Animate netCDF", update=update_animation
)


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
        scn = context.scene

        box_post_opt.label(text="netCDF file selection", icon="MODIFIER_ON")
        if gui_active_panel_fin != "Files":
            box_post_opt.operator("blendernc.button_file_on", icon=icon_expand)
        else:
            box_post_opt.operator("blendernc.button_file_off", icon=icon_collapse)
            # Box containing pop up menu.
            box_asts = box_post_opt.box()

            # Open blender file selection
            box_asts.label(text="netCDF File", icon="OUTLINER_OB_GROUP_INSTANCE")
            # box_asts.prop(scn, 'blendernc_file')
            row = box_asts.row(align=True)
            split = row.split(factor=0.85, align=True)

            split.prop(scn, "blendernc_file")
            split.operator("blendernc.import_mfnetcdf", text="", icon="FILEBROWSER")
            # Select variables menu
            box_asts.label(text="Select variable:", icon="WORLD_DATA")
            box_asts.prop(scn, "blendernc_netcdf_vars", text="")
            box_asts.prop(scn, "blendernc_animate")
            row = box_asts.row(align=True)
            split = row.split(factor=0.9)
            split.prop(scn, "blendernc_resolution")
            split.label(text=str("%"))
            # TO DO: Add info?
            # box_asts.label(text="INFO", icon='INFO')

        if scn.blendernc_netcdf_vars != "NONE" and [
            True
            for node_groups in bpy.data.node_groups.keys()
            if "BlenderNC" in node_groups
        ]:
            self.layout.prop(scn, "blendernc_meshes")
            # self.layout.prop_search(scn, "theChosenObject", scn, "objects")
            self.layout.operator("blendernc.apply_material", text="Apply Material")
