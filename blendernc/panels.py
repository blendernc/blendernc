#!/usr/bin/env python3
import bpy


class BlenderNC_UI_PT_3D_VIEW_PARENT(bpy.types.Panel):
    """Parent panel of the BlenderNC tab in the 3D viewport sidebar."""

    bl_idname = "BLENDERNC_UI_PT_3D_VIEW_PARENT"
    bl_label = "BlenderNC"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        """Draw the informational header label."""
        self.layout.label(text="Import *.nc, *.zarr, and *.grib files.", icon="INFO")


class BlenderNC_UI_PT_3D_VIEW(bpy.types.Panel):
    """Sub-panel with the datacube path field and file browser button."""

    bl_idname = "BLENDERNC_UI_PT_3D_VIEW"
    bl_label = "Datacube Load"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_UI_PT_3D_VIEW_PARENT"

    def draw(self, context):
        """Draw the datacube path property and the import operator button."""
        # Open blender file selection
        scene = context.scene
        UI_props = scene.BlenderNC_UI_Properties
        self.layout.label(text="Datacube Path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = self.layout.row(align=True)
        split = row.split(factor=0.85, align=True)
        split.prop(UI_props, "datacube_file")
        split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")
