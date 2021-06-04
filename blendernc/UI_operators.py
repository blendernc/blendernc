#!/usr/bin/env python3
# Imports
from os.path import dirname, join

import bpy
from bpy_extras.io_utils import ImportHelper


class BlenderNC_OT_Simple_UI(bpy.types.Operator):
    bl_idname = "blendernc.ncload_sui"
    bl_label = "Load netcdf file"
    bl_description = "Loads netcdf file"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        netcdf = bpy.data.node_groups.get("BlenderNC").nodes.get("netCDF input")
        node_group = bpy.data.node_groups.get("BlenderNC")
        if not node_group.nodes.get("Resolution"):
            ####################
            resol = node_group.nodes.new("netCDFResolution")
            resol.location[0] = 30
            output = node_group.nodes.new("netCDFOutput")
            output.location[0] = 190
        else:
            resol = node_group.nodes.get("Resolution")
            output = node_group.nodes.get("Output")
        # LINK
        node_group.links.new(resol.inputs[0], netcdf.outputs[0])

        resol.blendernc_resolution = scene.blendernc_resolution

        # LINK
        node_group.links.new(output.inputs[0], resol.outputs[0])
        bpy.ops.image.new(
            name="BlenderNC_default",
            width=1024,
            height=1024,
            color=(0.0, 0.0, 0.0, 1.0),
            alpha=True,
            generated_type="BLANK",
            float=True,
        )
        output.image = bpy.data.images.get("BlenderNC_default")
        output.update_on_frame_change = scene.blendernc_animate
        output.update()
        return {"FINISHED"}


class ImportnetCDFCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        subtype="FILE_PATH",
    )


class Import_OT_mfnetCDF(bpy.types.Operator, ImportHelper):
    """ """

    bl_idname = "blendernc.import_mfnetcdf"

    bl_label = "Load netCDF"
    bl_description = "Import netCDF with xarray"

    filter_glob: bpy.props.StringProperty(
        default="*.nc",
        options={"HIDDEN"},
    )

    files: bpy.props.CollectionProperty(type=ImportnetCDFCollection)

    node_group: bpy.props.StringProperty(
        name="node_group", description="Node calling operator"
    )

    node: bpy.props.StringProperty(name="node", description="Node calling operator")

    def execute(self, context):
        fdir = dirname(self.properties.filepath)

        if len(self.files) == 1:
            path = join(fdir, self.files[0].name)
        else:
            common_name = findCommonName([f.name for f in self.files])
            path = join(fdir, common_name)

        if self.node_group != "" and self.node != "":
            bpy.data.node_groups.get(self.node_group).nodes.get(
                self.node
            ).blendernc_file = path
        else:
            context.scene.blendernc_file = path

        return {"FINISHED"}


def findCommonName(filenames):
    import difflib

    cfname = ""
    fcounter = 0
    while not cfname or len(filenames) == fcounter:
        S = difflib.SequenceMatcher(None, filenames[fcounter], filenames[fcounter + 1])

        for block in S.get_matching_blocks():
            if block.a == block.b and block.size != 0:
                if len(cfname) != 0 and len(cfname) != block.a:
                    cfname = cfname + "*"
                cfname = cfname + filenames[fcounter][block.a : block.a + block.size]
            elif block.size == 0:
                pass
            else:
                raise ValueError("Filenames don't match")
        fcounter += 1
    return cfname


class BlenderNC_OT_purge_all(bpy.types.Operator):
    bl_idname = "blendernc.purge_all"
    bl_label = "Purge all frames"
    bl_description = "Purge all frames"
    bl_options = {"REGISTER", "UNDO"}

    node: bpy.props.StringProperty()
    node_group: bpy.props.StringProperty()

    def execute(self, context):
        pass

        return {"FINISHED"}
