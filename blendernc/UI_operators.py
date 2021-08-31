#!/usr/bin/env python3
# Imports
from os.path import dirname, join

import bpy
from bpy_extras.io_utils import ImportHelper

from blendernc.get_utils import get_blendernc_nodetrees
from blendernc.messages import PrintMessage, no_cached_image, no_cached_nodes
from blendernc.translations import translate

# TODO use this across all the add-on.
bpy.types.Scene.default_nodegroup = bpy.props.StringProperty(
    name="BlenderNC",
    description="Default nodegroup name",
    default="BlenderNC",
    maxlen=1024,
)


class BlenderNC_OT_Simple_UI(bpy.types.Operator):
    bl_idname = "blendernc.datacubeload_sui"
    bl_label = "Load datacube file"
    bl_description = "Loads datacube file"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        default_node_group_name = scene.default_nodegroup

        node_group = bpy.data.node_groups.get(default_node_group_name)
        datacube = node_group.nodes.get("datacube Input")

        if not node_group.nodes.get(translate("Resolution")):
            ####################
            resol = node_group.nodes.new("datacubeResolution")
            resol.location[0] = 30
            output = node_group.nodes.new("datacubeOutput")
            output.location[0] = 190
        else:
            resol = node_group.nodes.get(translate("Resolution"))
            output = node_group.nodes.get(translate("Output"))
        # LINK
        node_group.links.new(resol.inputs[0], datacube.outputs[0])

        resol.blendernc_resolution = scene.blendernc_resolution

        # LINK
        node_group.links.new(output.inputs[0], resol.outputs[0])
        bpy.ops.image.new(
            name=default_node_group_name + "_default",
            width=1024,
            height=1024,
            color=(0.0, 0.0, 0.0, 1.0),
            alpha=True,
            generated_type="BLANK",
            float=True,
        )
        output.image = bpy.data.images.get(default_node_group_name + "_default")
        output.update_on_frame_change = scene.blendernc_animate
        output.update()
        return {"FINISHED"}


class ImportDatacubeCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        subtype="DIR_PATH",
    )
    """An instance of the original StringProperty."""


class Import_OT_mfdataset(bpy.types.Operator, ImportHelper):
    """ """

    bl_idname = "blendernc.import_mfdataset"

    bl_label = "Load Datacube"
    bl_description = "Import Datacube with xarray"

    filter_glob: bpy.props.StringProperty(
        default="*.nc;*.grib;*.zarr",
        options={"HIDDEN"},
    )
    """An instance of the original StringProperty."""

    files: bpy.props.CollectionProperty(type=ImportDatacubeCollection)
    """An instance of the original CollectionProperty."""

    node_group: bpy.props.StringProperty(
        name="Node group name", description="Change default node group name"
    )
    """An instance of the original StringProperty."""

    node: bpy.props.StringProperty(name="node", description="Node calling operator")
    """An instance of the original StringProperty."""

    def execute(self, context):
        fdir = dirname(self.properties.filepath)

        if len(self.files) == 1:
            path = join(fdir, self.files[0].name)
        else:
            common_name = findCommonName([f.name for f in self.files])
            path = join(fdir, common_name)

        # Allows user to define a new default nodegroup, other than "BlenderNC"
        if self.node_group != "" and self.node == "":
            context.scene.default_nodegroup = self.node_group
        # Supports nodes when the nodetree and node have been created manually
        elif self.node_group != "" and self.node != "":
            bpy.data.node_groups.get(self.node_group).nodes.get(
                self.node
            ).blendernc_file = path
        # Default mode, where "BlenderNC" node is created.
        else:
            context.scene.blendernc_file = path

        return {"FINISHED"}


def findCommonName(filenames):
    import difflib

    cfname = []
    fcounter = 0
    while len(filenames) - 1 > fcounter:
        S = difflib.SequenceMatcher(None, filenames[fcounter], filenames[fcounter + 1])
        cname = ""
        for block in S.get_matching_blocks():
            cname = name_match(block, cname, filenames[fcounter])
        cfname.append(cname)
        fcounter += 1
    commonName = min(cfname, key=len)
    if "*" not in commonName:
        raise ValueError("Filenames do not match")
    if commonName[-1] == ".":
        raise ValueError("Filenames formats do not match")
    return commonName


def name_match(block, cfname, filename):
    if not cfname and (block.a != 0 or block.b != 0):
        raise ValueError("Start of filename strings do not match.")
    elif block.a == block.b and block.size != 0:
        if len(cfname) != 0 and len(cfname) != block.a:
            cfname += "*"
        cfname += filename[block.a : block.a + block.size]
    elif cfname or block.a != block.b:
        pass
    return cfname


class BlenderNC_OT_purge_all(bpy.types.Operator):
    bl_idname = "blendernc.purge_all"
    bl_label = "Purge all frames"
    bl_description = "Purge all frames except current"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        NodeTrees = get_blendernc_nodetrees()
        cache = bpy.context.scene.datacube_cache
        if cache.keys():
            for NodeTree in NodeTrees:
                NodeTree_name = NodeTree.name
                if not cache[NodeTree_name].keys():
                    PrintMessage(no_cached_image, "Info", "INFO")
                else:
                    self.report(
                        {"INFO"}, "Removed cache from node {0}".format(NodeTree_name)
                    )
                    identifiers = list(cache[NodeTree_name].keys())
                    for identifier in identifiers[:-1]:
                        cache[NodeTree_name].pop(identifier)
        else:
            PrintMessage(no_cached_nodes, "Info", "INFO")
        return {"FINISHED"}
