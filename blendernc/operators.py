#!/usr/bin/env python3
# Imports
from os.path import abspath

import bpy

from blendernc.core.update_ui import (
    UpdateImage,
    update_colormap_interface,
    update_nodes,
)
from blendernc.get_utils import (
    get_blendernc_nodetrees,
    get_default_material,
    get_node,
    get_var,
)
from blendernc.messages import (
    PrintMessage,
    active_selection_preference,
    asign_material,
    select_file,
    unselected_object,
)
from blendernc.python_functions import BlenderncEngine, load_frame
from blendernc.translations import translate

bNCEngine = BlenderncEngine()


class BlenderNC_OT_datacubeload(bpy.types.Operator):
    """
    BlenderNC_OT_datacubeload Load datacube files within Blender.

    Parameters
    ----------
    bpy : bpy.types.Operator
        Blender API bpy socket to generate a new Operator.

    Returns
    -------
    dict
        {FINISHED} if operator exits successfully.
    """

    bl_idname = "blendernc.datacubeload"
    bl_label = "Load datacube file"
    bl_description = "Loads datacube file"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the datacube file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    """An instance of the original StringProperty."""

    node_group: bpy.props.StringProperty(
        name="node", description="Node calling operator"
    )
    """An instance of the original StringProperty."""

    node: bpy.props.StringProperty(name="node", description="Node calling operator")
    """An instance of the original StringProperty."""

    def execute(self, context):
        if not self.file_path:
            PrintMessage(select_file, "Error", "ERROR")
            return {"FINISHED"}
        file_path = abspath(self.file_path)

        node = get_node(self.node_group, self.node)

        # TODO: Implement node with chunks if file is huge.

        unique_identifier = node.blendernc_dataset_identifier
        node.blendernc_dict[unique_identifier] = bNCEngine.check_files_datacube(
            file_path
        )
        self.report({"INFO"}, "Lazy load of %s!" % file_path)
        scn = context.scene
        default_node_group_name = scn.default_nodegroup
        # If quick import, define global variable.
        if self.node_group == default_node_group_name:
            var_names = get_var(node.blendernc_dict[unique_identifier]["Dataset"])
            bpy.types.Scene.blendernc_datacube_vars = bpy.props.EnumProperty(
                items=var_names, name="Select Variable", update=update_nodes
            )

        return {"FINISHED"}


class BlenderNC_OT_var(bpy.types.Operator):
    bl_idname = "blendernc.var"
    bl_label = "Load datacube vars"
    bl_description = "Loads datacube vars"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    def execute(self, context):
        if not self.file_path:
            PrintMessage(select_file, "Error", "ERROR")
            return {"CANCELLED"}

        blendernc_nodes = get_blendernc_nodetrees()
        scn = context.scene
        default_node_group_name = scn.default_nodegroup

        if not blendernc_nodes:
            bpy.data.node_groups.new(default_node_group_name, "BlenderNC")
            bpy.data.node_groups[default_node_group_name].use_fake_user = True

        node_group = bpy.data.node_groups.get(default_node_group_name)
        if not node_group.nodes:
            path = node_group.nodes.new("datacubePath")
            path.location[0] = -300
            datacube = node_group.nodes.new("datacubeNode")
            datacube.location[0] = -130
        else:
            path = node_group.nodes.get("datacube Path")
            datacube = node_group.nodes.get("datacube Input")
        path.blendernc_file = self.file_path
        # LINK nodes
        if not node_group.links:
            node_group.links.new(datacube.inputs[0], path.outputs[0])

        datacube.update()
        return {"FINISHED"}


class BlenderNC_OT_compute_range(bpy.types.Operator):
    bl_idname = "blendernc.compute_range"
    bl_label = "Compute vmin & vmax"
    bl_description = "Compute vmax and vmin of datacube selected variable"
    bl_options = {"REGISTER", "UNDO"}

    node: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    node_group: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    def execute(self, context):
        node = bpy.data.node_groups.get(self.node_group).nodes.get(self.node)
        unique_identifier = node.blendernc_dataset_identifier
        # TODO: Fix bug when the node isn't connected.
        dataset = node.blendernc_dict[unique_identifier]["Dataset"]
        selected_variable = node.blendernc_dict[unique_identifier]["selected_var"][
            "selected_var_name"
        ]

        node.blendernc_dataset_min = (
            (
                dataset[selected_variable].min()
                - abs(1e-5 * dataset[selected_variable].min())
            )
            .compute()
            .values
        )
        node.blendernc_dataset_max = dataset[selected_variable].max().compute().values
        return {"FINISHED"}


class BlenderNC_OT_preloader(bpy.types.Operator):
    bl_idname = "blendernc.preloader"
    bl_label = "Preload a range of variable steps into memory"
    bl_description = "Preload a range of variable steps into memory"
    bl_options = {"REGISTER", "UNDO"}
    file_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the datacube file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    """An instance of the original StringProperty."""
    var_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the datacube file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    """An instance of the original StringProperty."""
    frame_start: bpy.props.IntProperty(
        default=1,
        name="Start",
    )
    """An instance of the original IntProperty."""

    frame_end: bpy.props.IntProperty(
        default=250,
        name="End",
    )
    """An instance of the original IntProperty."""

    def execute(self, context):
        if not self.file_name:
            self.report({"INFO"}, "Select a file!")
            return {"FINISHED"}
        file_path = abspath(self.file_name)

        scene = context.scene
        scene.blendernc_dict

        var_name = self.var_name
        if not var_name:
            self.report({"INFO"}, "Select a variable!")
            return {"FINISHED"}

        # For each frame check if the frame is already in memory
        frame_start, frame_end = self.frame_start, self.frame_end
        for frame in range(frame_start, frame_end):
            print("Frame %i loaded!" % frame)
            load_frame(context, file_path, var_name, frame)

        self.report(
            {"INFO"}, "Frames %i to %i have been loaded!" % (frame_start, frame_end)
        )
        return {"FINISHED"}


class BlenderNC_OT_datacube2img(bpy.types.Operator):
    bl_idname = "blendernc.datacube2img"
    bl_label = "From datacube to image"
    bl_description = "Updates an image with datacube data"
    node: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    node_group: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    frame: bpy.props.IntProperty()
    """An instance of the original IntProperty."""
    flip: bpy.props.BoolProperty()
    """An instance of the original BoolProperty."""
    image: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    def execute(self, context):
        UpdateImage(context, self.node, self.node_group, self.frame, self.image)
        return {"FINISHED"}


class BlenderNC_OT_colorbar(bpy.types.Operator):
    bl_idname = "blendernc.colorbar"
    bl_label = "Create/Update colobar"
    bl_description = "Create or updates colorbar"
    node: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    node_group: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    image: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    def execute(self, context):
        if bpy.data.images[self.image].users >= 2:
            update_colormap_interface(self.node, self.node_group)
        else:
            PrintMessage(asign_material, "Error", "ERROR")
        return {"FINISHED"}


class BlenderNC_OT_apply_material(bpy.types.Operator):
    bl_label = "Load datacube"
    bl_idname = "blendernc.apply_material"
    bl_description = "Apply texture to material for simple cases"
    bl_context = "objectmode"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        act_obj = (
            context.active_object
            if context.active_object.select_get() is True
            else None
        )
        sel_obj = context.scene.blendernc_meshes
        # Check if an object is selected or picked.
        # TODO change to hasattr(context.scene, "my_prop")?
        if not sel_obj and act_obj:
            sel_obj = act_obj
        elif sel_obj and not act_obj:
            pass
        elif sel_obj and act_obj:
            if sel_obj.name != act_obj.name:
                PrintMessage(active_selection_preference, "Warning", "INFO")
                sel_obj = act_obj
        else:
            PrintMessage(unselected_object, "Error", "ERROR")
            return {"FINISHED"}

        blendernc_material = get_default_material()
        self.create_materials(blendernc_material)

        imagetex = self.get_translated_node(blendernc_material, "Image Texture")
        cmap = self.get_translated_node(blendernc_material, "Colormap")
        bump = self.get_translated_node(blendernc_material, "Bump")

        P_BSDF = self.get_translated_node(blendernc_material, "Principled BSDF")

        texcoord_link = self.get_projection(sel_obj.name, blendernc_material, imagetex)

        blendernc_material.node_tree.links.new(imagetex.inputs[0], texcoord_link)
        blendernc_material.node_tree.links.new(cmap.inputs[0], imagetex.outputs[0])
        blendernc_material.node_tree.links.new(bump.inputs[2], imagetex.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[0], cmap.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[-3], bump.outputs[0])

        imagetex.image = bpy.data.images.get("BlenderNC_default")

        self.apply_material(sel_obj)

        return {"FINISHED"}

    @staticmethod
    def create_materials(blendernc_material):
        if len(blendernc_material.node_tree.nodes.keys()) == 2:
            texcoord = blendernc_material.node_tree.nodes.new("ShaderNodeTexCoord")
            texcoord.location = (-760, 250)
            imagetex = blendernc_material.node_tree.nodes.new("ShaderNodeTexImage")
            imagetex.location = (-580, 250)
            imagetex.interpolation = "Smart"
            cmap = blendernc_material.node_tree.nodes.new("cmapsNode")
            cmap.location = (-290, 250)
            bump = blendernc_material.node_tree.nodes.new("ShaderNodeBump")
            bump.inputs[0].default_value = 0.3
            bump.location = (-290, -50)

    @staticmethod
    def get_translated_node(blendernc_material, eng_node_name):
        P_BSDF = blendernc_material.node_tree.nodes.get(translate(eng_node_name))
        # This line is executed when a different language is selected. By
        # default a new blender file will create a node named "Principled BSDF"
        if not P_BSDF:
            P_BSDF = blendernc_material.node_tree.nodes.get(eng_node_name)
        return P_BSDF

    @staticmethod
    def get_projection(name, blendernc_material, imagetex):
        texcoord = blendernc_material.node_tree.nodes.get(
            translate("Texture Coordinate")
        )
        if name == "Icosphere":
            texcoord_link = texcoord.outputs.get(translate("Generated"))
            imagetex.projection = "SPHERE"
        else:
            texcoord_link = texcoord.outputs.get(translate("UV"))
            imagetex.projection = "FLAT"
        return texcoord_link

    @staticmethod
    def apply_material(sel_obj):
        if sel_obj.type == "MESH":
            sel_obj.active_material = bpy.data.materials.get("BlenderNC_default")


class ImportDatacubeCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        subtype="FILE_PATH",
    )
