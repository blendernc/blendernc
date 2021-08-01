#!/usr/bin/env python3
import bpy

from blendernc.core.update_ui import update_animation, update_file_vars, update_res
from blendernc.preferences import dask_client, get_addon_preference
from blendernc.python_functions import build_enum_prop_list, empty_item


def select_only_meshes(self, object):
    return object.type == "MESH"


# TODO: Change all this settings into a PropertyGroup,
# see: https://docs.blender.org/api/current/bpy.props.html
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

bpy.types.Scene.blendernc_datacube_vars = bpy.props.EnumProperty(
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
    default=False, name="Animate datacube", update=update_animation
)


class BlenderNC_UI_PT_parent(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_3Dview_PARENT"
    bl_label = "BlenderNC"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.label(text="Import *.nc and *.grib files.", icon="INFO")


class BlenderNC_UI_PT_file_selection(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_3Dview_SELECTION"
    bl_label = "Datacube file selection"
    bl_category = "BlenderNC"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_PT_3Dview_PARENT"

    def draw(self, context):
        box_asts = self.layout.box()
        scn = context.scene

        # Open blender file selection
        box_asts.label(text="Datacube path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = box_asts.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(scn, "blendernc_file")
        split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")
        # Select variables menu
        box_asts.label(text="Select variable:", icon="WORLD_DATA")
        box_asts.prop(scn, "blendernc_datacube_vars", text="")
        box_asts.prop(scn, "blendernc_animate")
        row = box_asts.row(align=True)
        split = row.split(factor=0.9)
        split.prop(scn, "blendernc_resolution")
        split.label(text=str("%"))

        if scn.blendernc_datacube_vars != "NONE" and [
            True
            for node_groups in bpy.data.node_groups.keys()
            if "BlenderNC" in node_groups
        ]:
            self.layout.prop(scn, "blendernc_meshes")
            self.layout.operator("blendernc.apply_material", text="Apply Material")


class BlenderNC_workspace_panel(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_workspace_parent"
    bl_label = "BlenderNC"
    bl_category = "BlenderNC"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(self, context):
        return context.area.ui_type == "BlenderNC"

    def draw(self, context):
        self.layout.label(text="Animation and memory handeling", icon="INFO")


def item_animation():
    animation_type = ["NONE", "EXTEND", "LOOP"]
    return build_enum_prop_list(animation_type)


def item_memory_handle():
    animation_type = ["FRAMES", "DYNAMIC"]
    return build_enum_prop_list(animation_type)


bpy.types.Scene.blendernc_animation_type = bpy.props.EnumProperty(
    items=item_animation(),
    default="EXTEND",
    name="",
)

bpy.types.Scene.blendernc_memory_handle = bpy.props.EnumProperty(
    items=item_memory_handle(),
    default="FRAMES",
    name="",
)

bpy.types.Scene.blendernc_frames = bpy.props.IntProperty(
    name="# of stored frames", min=0, max=1000, default=10
)

bpy.types.Scene.blendernc_avail_mem_purge = bpy.props.FloatProperty(
    name="Min percentage of avail memory", min=0, max=100, default=10
)


class BlenderNC_workspace_animation(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_workspace_animation"
    bl_label = "Animation settings"
    bl_category = "BlenderNC"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_PT_workspace_parent"

    def draw(self, context):
        scn = context.scene
        box_asts = self.layout.box()
        row = box_asts.row()
        row.label(text="Default image load:")
        col = box_asts.column()
        col.prop(scn, "blendernc_animation_type", text=" ", expand=True)


class BlenderNC_workspace_memory(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_workspace_memory"
    bl_label = "Memory settings"
    bl_category = "BlenderNC"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_PT_workspace_parent"

    """An instance of the original EnumProperty."""

    def draw(self, context):
        scn = context.scene
        box_asts = self.layout.box()
        row = box_asts.row()
        row.label(text="Experimental!", icon="EXPERIMENTAL")
        row = box_asts.row()
        row.label(text="Memory handler!", icon="DISK_DRIVE")
        col = box_asts.column()
        col.prop(scn, "blendernc_memory_handle", text=" ", expand=True)
        if scn.blendernc_memory_handle == "FRAMES":
            row = box_asts.row()
            row.label(text="Number of stored frames:")
            row = box_asts.row()
            row.prop(scn, "blendernc_frames")
        else:
            row = box_asts.row()
            row.label(text="Minimum available memory:")
            row = box_asts.row()
            row.prop(scn, "blendernc_avail_mem_purge", text="")

        box_asts = self.layout.box()
        row = box_asts.row()
        row.label(text="Remove all cache!", icon="CANCEL")
        row = box_asts.row()
        row.operator("blendernc.purge_all", text="Purge")
        scn = context.scene


class BlenderNC_dask_client(bpy.types.Panel):
    bl_idname = "BLENDERNC_PT_dask"
    bl_label = "Dask Client"
    bl_category = "BlenderNC"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "BLENDERNC_PT_workspace_parent"

    def draw(self, context):
        box_asts = self.layout.box()
        row = box_asts.row()
        pref = get_addon_preference()
        if pref.blendernc_use_dask == "True":
            c = dask_client(create_client=True)

            row.label(text="Dask client:", icon="LINKED")
            row = box_asts.row()
            row.label(text=c.dashboard_link)
            row = box_asts.row()
            row.operator(
                "wm.url_open", text="Open dask dashboard"
            ).url = c.dashboard_link
        else:
            row.label(text="No dask client.", icon="UNLINKED")
