#!/usr/bin/env python3
import os

import bpy
import dask.distributed as ddist
from bpy.app.handlers import persistent

from blendernc.messages import PrintMessage, client_exists, load_after_restart
from blendernc.python_functions import build_enum_prop_list

# Import auto updater
from . import addon_updater_ops


def get_addon_preference():
    """
    get_addon_preference Get addon preferences

    Returns
    -------
    bpy_struct
        bpy structure containing BlenderNC preferences.
    """
    if "blendernc" not in bpy.context.preferences.addons.keys():
        bpy.ops.preferences.addon_enable(module="blendernc")
    addon = bpy.context.preferences.addons.get("blendernc")
    # Check if addon is defined
    if addon is not None:
        prefs = addon.preferences
    else:
        prefs = None
    return prefs


@persistent
def import_workspace(_):
    """
    import_workspace Load BlenderNC workspace, based on the user preferences.

    Parameters
    ----------
    _ : NoneType
        Dummy argument
    """

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
    """
    update_workspace Update workspace when user changes preference.

    Parameters
    ----------
    context : bpy.context
        Context in which update is called.
    """
    import_workspace(None)


def update_message(self, context):
    """
    update_message Update message when changing blendernc_workspace_shading.
        Any changes in shading will be applied after reload.

    Parameters
    ----------
    context : bpy.context
        Context in which update is called.
    """
    # Test for blender running in background mode.
    # If blender is running in background mode,
    # a popup_menu will crash with the following error:
    # ERROR (bke.icons):
    # source/blender/blenkernel/intern/icons.cc:889 BKE_icon_get:
    # no icon for icon ID: 110,101,101
    # TODO: Report issue to Blender.

    PrintMessage(load_after_restart, "Info", "INFO")


def update_client(self, context):
    c = dask_client()
    # Close client.
    if self.blendernc_use_dask == "False" and c:
        c.close()
        c = "No client"
    # Refresh client
    elif self.blendernc_use_dask == "True" and c:
        PrintMessage(client_exists, "Info", "INFO")
        c.close()
        c = ddist.Client(processes=False)
    # Create new client
    elif self.blendernc_use_dask == "True":
        c = ddist.Client(processes=False)
    else:
        c = "No client"
    print(c)


def dask_client(create_client=False):
    # Try to get if client exists
    try:
        c = ddist.get_client()
    except ValueError:
        if create_client:
            c = ddist.Client(processes=False)
        else:
            c = ""
    return c


class BlenderNC_Preferences(bpy.types.AddonPreferences):
    """
    BlenderNC_Preferences Constructor of BlenderNC preferences.

    Parameters
    ----------
    bpy.types.AddonPreferences : bpy_struct
        Blender API bpy types to generate new AddonPreferences.
    """

    bl_idname = "blendernc"

    def item_shadings():
        shadings = ["SOLID", "RENDERED", "MATERIAL"]
        return build_enum_prop_list(shadings)

    def item_workspace_option():
        workspace = ["NONE", "ONLY CREATE WORKSPACE", "INITIATE WITH WORKSPACE"]
        return build_enum_prop_list(workspace)

    def item_dask():
        dask = ["False", "True"]
        return build_enum_prop_list(dask)

    blendernc_workspace: bpy.props.EnumProperty(
        items=item_workspace_option(),
        default="ONLY CREATE WORKSPACE",
        name="",
        update=update_workspace,
    )
    """An instance of the original EnumProperty."""

    blendernc_workspace_shading: bpy.props.EnumProperty(
        items=item_shadings(),
        default="SOLID",
        name="Default load shading:",
        update=update_message,
    )
    """An instance of the original EnumProperty."""

    blendernc_use_dask: bpy.props.EnumProperty(
        items=item_dask(),
        name="Use dask Client:",
        update=update_client,
    )
    """An instance of the original BoolProperty."""

    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )
    """An instance of the original BoolProperty."""

    updater_interval_months: bpy.props.IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )
    """An instance of the original IntProperty."""

    updater_interval_days: bpy.props.IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31,
    )
    """An instance of the original IntProperty."""

    updater_interval_hours: bpy.props.IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )
    """An instance of the original IntProperty."""

    updater_interval_minutes: bpy.props.IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )
    """An instance of the original IntProperty."""

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Create BlenderNC workspace:")
        row.prop(self, "blendernc_workspace")
        row = layout.row()
        row.label(text="Default load shading:")
        row.prop(self, "blendernc_workspace_shading", expand=True)
        row = layout.row()
        row.label(text="Use dask Client:")
        row.prop(self, "blendernc_use_dask", expand=True)
        row = layout.row()
        row.label(text="Useful links:")
        documentation = "https://blendernc.readthedocs.io/en/latest/"
        row.operator("wm.url_open", text="Documentation").url = documentation
        report = "https://github.com/blendernc/blendernc/issues/new"
        row.operator("wm.url_open", text="Report bugs").url = report
        # TODO: Add link to documentation and report bugs to github.
        row = layout.row()
        addon_updater_ops.update_settings_ui(self, context, row)


@persistent
def load_handler_for_startup(_):
    """
    load_handler_for_startup Change shading to the preselected BlenderNC preference.

    Parameters
    ----------
    _ : NoneType
        Dummy argument
    """
    import bpy

    prefs = get_addon_preference()

    if prefs.blendernc_use_dask == "True":
        dask_client(create_client=True)

    # Use material preview shading.
    areas = [
        space
        for screen in bpy.data.screens
        for area in screen.areas
        for space in area.spaces
        if space.type == "VIEW_3D"
    ]

    for space in areas:
        space.shading.type = prefs.blendernc_workspace_shading
        space.shading.use_scene_lights = True
