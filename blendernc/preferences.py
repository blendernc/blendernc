#!/usr/bin/env python3
import os

import bpy
from bpy.app.handlers import persistent

from .messages import load_after_restart


def get_addon_preference():
    addon = bpy.context.preferences.addons.get("blendernc")
    # Check if addon is defined
    if addon is not None:
        prefs = addon.preferences
    else:
        prefs = None
    return prefs


@persistent
def import_workspace(_):
    import bpy

    prefs = get_addon_preference()
    # Make sure the BlenderNC has the right preferences.
    if prefs.blendernc_workspace == "NONE":
        return
    # Close preferences if they are open in a new window, then assign
    # the new workspace.
    if len(bpy.context.window_manager.windows.items()) != 1:
        bpy.ops.wm.window_close()
    import blendernc

    path = os.path.join(os.path.dirname(blendernc.__file__), "workspace/startup.blend")
    previously_selected_workspace = bpy.context.window_manager.windows[0].workspace.name
    bpy.ops.workspace.append_activate(idname="BlenderNC", filepath=path)
    if prefs.blendernc_workspace == "ONLY CREATE WORKSPACE":
        data_workspace = bpy.data.workspaces
        window = bpy.context.window_manager.windows[0]
        window.workspace = data_workspace[previously_selected_workspace]


def update_workspace(self, context):
    import_workspace(None)


def update_message(self, context):
    # Test for blender running in background mode.
    # If blender is running in background mode,
    # a popup_menu will crash with the following error:
    # ERROR (bke.icons):
    # source/blender/blenkernel/intern/icons.cc:889 BKE_icon_get:
    # no icon for icon ID: 110,101,101
    # TODO: Report issue to Blender.
    if not bpy.app.background:
        bpy.context.window_manager.popup_menu(
            load_after_restart, title="Info", icon="INFO"
        )
    else:
        import warnings

        warnings.warn(
            """
            Running in background mode,
            this option will be loaded after restarting Blender.
            """
        )


class BlenderNC_Preferences(bpy.types.AddonPreferences):
    bl_idname = "blendernc"

    def item_shadings(self, context):
        shadings = ["SOLID", "RENDERED", "MATERIAL"]
        return [(shadings[ii], shadings[ii], "", ii) for ii in range(len(shadings))]

    def item_workspace_option(self, context):
        shadings = ["NONE", "ONLY CREATE WORKSPACE", "INITIATE WITH WORKSPACE"]
        return [
            (shadings[ii], shadings[ii].capitalize(), "", "", ii)
            for ii in range(len(shadings))
        ]

    blendernc_workspace: bpy.props.EnumProperty(
        items=item_workspace_option,
        default=1,
        name="",
        update=update_workspace,
    )

    blendernc_workspace_shading: bpy.props.EnumProperty(
        items=item_shadings,
        default=0,
        name="Default load shading:",
        update=update_message,
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Create BlenderNC workspace:")
        row.prop(self, "blendernc_workspace")
        row = layout.row()
        row.label(text="Default load shading:")
        row.prop(self, "blendernc_workspace_shading", expand=True)
        # TODO: Add dask option here!


@persistent
def load_handler_for_startup(_):
    import bpy

    prefs = get_addon_preference()

    # Use smooth faces.
    for mesh in bpy.data.meshes:
        for poly in mesh.polygons:
            poly.use_smooth = False

    # Use material preview shading.
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = prefs.blendernc_workspace_shading
                    space.shading.use_scene_lights = True
