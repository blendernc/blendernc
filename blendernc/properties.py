from collections import defaultdict

import bpy

from .utils import (
    create_datastruct,
    get_possible_coordinates_UI,
    get_possible_variables_UI,
    update_coords_links_UI,
    update_variable_UI,
)


class BNC_data(bpy.types.PropertyGroup):
    filename: bpy.props.StringProperty()
    datafile: bpy.props.StringProperty()
    operations: bpy.props.StringProperty()
    slicing: bpy.props.StringProperty()
    dict = defaultdict()


class BlenderNC_UI_Properties(bpy.types.PropertyGroup):
    bl_idname = "BlenderNC_UI_Properties"

    datacube_file: bpy.props.StringProperty(
        name="",
        description="Folder with assets blend files",
        default="",
        maxlen=1024,
        update=create_datastruct,
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
