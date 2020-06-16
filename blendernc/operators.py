# Imports
import bpy
import xarray
from os.path import abspath, isfile

from . python_functions import load_frame, update_image, get_var, update_nodes

class BlenderNC_OT_ncload(bpy.types.Operator):
    bl_idname = "blendernc.ncload"
    bl_label = "Load netcdf file"
    bl_description = "Loads netcdf file"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )

    def execute(self, context):
        if not self.file_path:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_path)

        if not isfile(file_path):
            self.report({'ERROR'}, "It seems that this is not a file!")
            return {'CANCELLED'}
        scene = context.scene
        scene.nc_dictionary[file_path] = xarray.open_dataset(file_path, decode_times=False)
        self.report({'INFO'}, "File: %s loaded!" % file_path)
        var_names = get_var(scene.nc_dictionary[file_path])
        bpy.types.Scene.blendernc_netcdf_vars = bpy.props.EnumProperty(items=var_names,
                                                                name="",update=update_nodes)
        # Create new node in BlenderNC node
        if not bpy.data.node_groups:
            bpy.data.node_groups.new("BlenderNC","BlenderNC")
        
        if not bpy.data.node_groups[-1].nodes:
            bpy.data.node_groups[-1].nodes.new("netCDFNode")
        return {'FINISHED'}


class BlenderNC_OT_preloader(bpy.types.Operator):
    bl_idname = "blendernc.preloader"
    bl_label = "Preload a range of variable steps into memory"
    bl_description = "Preload a range of variable steps into memory"
    bl_options = {"REGISTER", "UNDO"}
    file_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    var_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    frame_start: bpy.props.IntProperty(
        default=1,
        name="Start",
    )

    frame_end: bpy.props.IntProperty(
        default=250,
        name="End",
    )

    def execute(self, context):
        if not self.file_name:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_name)

        if not isfile(file_path):
            self.report({'ERROR'}, "It seems that this is not a file!")
            return {'CANCELLED'}
        scene = context.scene
        scene.nc_dictionary[file_path] = xarray.open_dataset(file_path, decode_times=False)

        var_name = self.var_name
        if not var_name:
            self.report({'INFO'}, "Select a variable!")
            return {'FINISHED'}

        # For each frame check if the frame is already in memory
        frame_start, frame_end = self.frame_start, self.frame_end
        for frame in range(frame_start, frame_end):
            print("Frame %i loaded!" % frame)
            load_frame(context, file_path,var_name,frame)

        self.report({'INFO'}, "Frames %i to %i have been loaded!" % (frame_start, frame_end))
        return {'FINISHED'}


class BlenderNC_OT_netcdf2img(bpy.types.Operator):
    bl_idname = "blendernc.nc2img"
    bl_label = "From netcdf to image"
    bl_description = "Updates an image with netcdf data"
    file_name: bpy.props.StringProperty()
    var_name: bpy.props.StringProperty()
    step: bpy.props.IntProperty()
    flip: bpy.props.BoolProperty()
    image: bpy.props.StringProperty()

    def execute(self, context):
        image = self.image
        update_image(context, self.file_name, self.var_name, self.step, self.flip, self.image)
        return {'FINISHED'}

