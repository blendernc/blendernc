from collections import defaultdict

import bpy

from .ui import (
    get_possible_coordinates_UI,
    get_possible_variables_UI,
    update_coords_links_UI,
    update_datacube_file_UI,
    update_variable_UI,
)
from .utils import update_lock_range


class BNC_data(bpy.types.PropertyGroup):
    """Per-node record of the loaded datacube.

    ``dict`` is a class-level cache shared by every node and node tree; it maps
    ``filename`` to the opened :class:`xarray.Dataset`.
    """

    filename: bpy.props.StringProperty()
    datafile: bpy.props.StringProperty()
    slicing: bpy.props.StringProperty()
    dict = defaultdict()


class BlenderNC_UI_Properties(bpy.types.PropertyGroup):
    """Scene-level properties backing the BlenderNC 3D view panel."""

    bl_idname = "BlenderNC_UI_Properties"

    datacube_file: bpy.props.StringProperty(
        name="",
        description="Datacube file to import, or a glob pattern matching several",
        default="",
        maxlen=1024,
        update=update_datacube_file_UI,
    )
    X: bpy.props.EnumProperty(
        items=get_possible_coordinates_UI, name="X:", update=update_coords_links_UI
    )
    Y: bpy.props.EnumProperty(
        items=get_possible_coordinates_UI, name="Y:", update=update_coords_links_UI
    )
    Z: bpy.props.EnumProperty(
        items=get_possible_coordinates_UI, name="Z:", update=update_coords_links_UI
    )

    variable: bpy.props.EnumProperty(
        items=get_possible_variables_UI,
        name="Select Variable",
        update=update_variable_UI,
    )


class BlenderNC_Settings(bpy.types.PropertyGroup):
    """Scene-wide BlenderNC settings, shown in the node editor's Settings panel.

    New preferences belong here, so they are saved with the .blend file and
    drawn by :class:`blendernc.panels.BlenderNC_NODE_PT_SETTINGS` in the
    sidebar of the BlenderNC node editor.
    """

    bl_idname = "BlenderNC_Settings"

    lock_range: bpy.props.BoolProperty(
        name="Lock range",
        description=(
            "Keep the stored min and max of each texture, so the colour scale "
            "stays fixed when the resolution or the data changes"
        ),
        default=True,
        update=update_lock_range,
    )
