#!/usr/bin/env python3
import bpy

from .utils import create_datastruct

bpy.types.Scene.datacube_file = bpy.props.StringProperty(
    name="",
    description="Folder with assets blend files",
    default="",
    maxlen=1024,
    update=create_datastruct,
)


class BlenderNC_UI_PT_3D_VIEW_PARENT(bpy.types.Panel):
    bl_idname = "BLENDERNC_UI_PT_3D_VIEW_PARENT"
    bl_label = "BlenderNC"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.label(text="Import *.nc, *.zarr, and *.grib files.", icon="INFO")


class BlenderNC_UI_PT_3D_VIEW(bpy.types.Panel):
    bl_idname = "BLENDERNC_UI_PT_3D_VIEW"
    bl_label = "Datacube file selection"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_UI_PT_3D_VIEW_PARENT"

    def draw(self, context):
        box_asts = self.layout.box()

        # Open blender file selection
        box_asts.label(text="Datacube path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = box_asts.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(context.scene, "datacube_file")
        split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")

        # Select variables menu
        # box_asts.label(text="Select variable:", icon="WORLD_DATA")
        # box_asts.prop(scn, "blendernc_datacube_vars", text="")
        # box_asts.prop(scn, "blendernc_animate")
        # row = box_asts.row(align=True)
        # split = row.split(factor=0.9)
        # split.prop(scn, "blendernc_resolution")
        # split.label(text=str("%"))

        # if scn.blendernc_datacube_vars != "NONE" and [
        #     True
        #     for node_groups in bpy.data.node_groups.keys()
        #     if "BlenderNC" in node_groups
        # ]:
        #     self.layout.prop(scn, "blendernc_meshes")
        #     self.layout.operator("blendernc.apply_material", text="Apply Material")
