from collections import defaultdict

import bpy


class BNC_data(bpy.types.PropertyGroup):
    filename: bpy.props.StringProperty()
    datafile: bpy.props.StringProperty()
    operations: bpy.props.StringProperty()
    slicing: bpy.props.StringProperty()
    dict = defaultdict()
