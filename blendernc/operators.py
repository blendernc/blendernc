#!/usr/bin/env python3
# Imports
from os.path import abspath

import bpy

from .messages import active_selection_preference, unselected_object
from .python_functions import (
    BlenderncEngine,
    get_node,
    get_var,
    load_frame,
    update_colormap_interface,
    update_image,
    update_nodes,
)

bNCEngine = BlenderncEngine()


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

    node_group: bpy.props.StringProperty(
        name="node", description="Node calling operator"
    )

    node: bpy.props.StringProperty(name="node", description="Node calling operator")

    def execute(self, context):
        if not self.file_path:
            self.report({"INFO"}, "Select a file!")
            return {"FINISHED"}
        file_path = abspath(self.file_path)

        node = get_node(self.node_group, self.node)
        # TODO: allow xarray.open_mfdataset if wildcard "*" use in name.
        # Useful for large datasets. Implement node with chunks if file is huge.

        unique_identifier = node.blendernc_dataset_identifier
        node.blendernc_dict[unique_identifier] = bNCEngine.check_files_netcdf(file_path)
        self.report({"INFO"}, "Lazy load of %s!" % file_path)
        # If quick import, define global variable.
        if self.node_group == "BlenderNC":
            var_names = get_var(node.blendernc_dict[unique_identifier]["Dataset"])
            bpy.types.Scene.blendernc_netcdf_vars = bpy.props.EnumProperty(
                items=var_names, name="Select Variable", update=update_nodes
            )
        # Create new node in BlenderNC node
        blendernc_nodes = [
            keys
            for keys in bpy.data.node_groups.keys()
            if ("BlenderNC" in keys or "NodeTree" in keys)
        ]
        if not blendernc_nodes:
            bpy.data.node_groups.new("BlenderNC", "BlenderNC")
            bpy.data.node_groups["BlenderNC"].use_fake_user = True

        if not bpy.data.node_groups[-1].nodes:
            bpy.data.node_groups[-1].nodes.new("netCDFNode")

        return {"FINISHED"}


class BlenderNC_OT_var(bpy.types.Operator):
    bl_idname = "blendernc.var"
    bl_label = "Load netcdf vars"
    bl_description = "Loads netcdf vars"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty()

    def execute(self, context):
        if not self.file_path:
            self.report({"INFO"}, "Select a file!")
            return {"FINISHED"}

        blendernc_nodes = [
            bpy.data.node_groups[keys]
            for keys in bpy.data.node_groups.keys()
            if (
                bpy.data.node_groups[keys].bl_label == "BlenderNC"
                and keys == "BlenderNC"
            )
        ]
        if not blendernc_nodes:
            bpy.data.node_groups.new("BlenderNC", "BlenderNC")
            bpy.data.node_groups["BlenderNC"].use_fake_user = True

        node_group = bpy.data.node_groups.get("BlenderNC")
        if not node_group.nodes:
            path = node_group.nodes.new("netCDFPath")
            path.location[0] = -300
            netcdf = node_group.nodes.new("netCDFNode")
            netcdf.location[0] = -130
        else:
            path = node_group.nodes.get("netCDF Path")
            netcdf = node_group.nodes.get("netCDF input")
        path.blendernc_file = self.file_path
        # LINK nodes
        if not node_group.links:
            node_group.links.new(netcdf.inputs[0], path.outputs[0])

        netcdf.update()
        return {"FINISHED"}


class BlenderNC_OT_compute_range(bpy.types.Operator):
    bl_idname = "blendernc.compute_range"
    bl_label = "Compute vmin & vmax"
    bl_description = "Compute vmax and vmin of netcdf selected variable"
    bl_options = {"REGISTER", "UNDO"}

    node: bpy.props.StringProperty()
    node_group: bpy.props.StringProperty()

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
            self.report({"INFO"}, "Select a file!")
            return {"FINISHED"}
        file_path = abspath(self.file_name)

        scene = context.scene
        scene.nc_dictionary[file_path] = bNCEngine.check_files_netcdf(file_path)

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


class BlenderNC_OT_netcdf2img(bpy.types.Operator):
    bl_idname = "blendernc.nc2img"
    bl_label = "From netcdf to image"
    bl_description = "Updates an image with netcdf data"
    node: bpy.props.StringProperty()
    node_group: bpy.props.StringProperty()
    frame: bpy.props.IntProperty()
    flip: bpy.props.BoolProperty()
    image: bpy.props.StringProperty()

    def execute(self, context):
        update_image(context, self.node, self.node_group, self.frame, self.image)
        return {"FINISHED"}


class BlenderNC_OT_colorbar(bpy.types.Operator):
    bl_idname = "blendernc.colorbar"
    bl_label = "Create/Update colobar"
    bl_description = "Create or updates colorbar"
    node: bpy.props.StringProperty()
    node_group: bpy.props.StringProperty()
    image: bpy.props.StringProperty()

    def execute(self, context):
        if bpy.data.images[self.image].users >= 2:
            update_colormap_interface(context, self.node, self.node_group)
        else:
            self.report({"ERROR"}, "Assigned material to object!")
        return {"FINISHED"}


class BlenderNC_OT_apply_material(bpy.types.Operator):
    bl_label = "Load netCDF"
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
                bpy.context.window_manager.popup_menu(
                    active_selection_preference, title="Warning", icon="INFO"
                )
                sel_obj = act_obj
        else:
            bpy.context.window_manager.popup_menu(
                unselected_object, title="Error", icon="ERROR"
            )
            return {"FINISHED"}

        blendernc_materials = [
            material
            for material in bpy.data.materials
            if "BlenderNC_default" in material.name
        ]
        if len(blendernc_materials) != 0:
            blendernc_material = blendernc_materials[-1]
        else:
            bpy.ops.material.new()
            blendernc_material = bpy.data.materials[-1]
            blendernc_material.name = "BlenderNC_default"

        if len(blendernc_material.node_tree.nodes.keys()) == 2:
            texcoord = blendernc_material.node_tree.nodes.new("ShaderNodeTexCoord")
            texcoord.location = (-760, 250)
            imagetex = blendernc_material.node_tree.nodes.new("ShaderNodeTexImage")
            imagetex.location = (-580, 250)
            imagetex.interpolation = "Smart"
            cmap = blendernc_material.node_tree.nodes.new("cmapsNode")
            cmap.location = (-290, 250)
            bump = blendernc_material.node_tree.nodes.new("ShaderNodeBump")
            bump.location = (-290, -50)

        else:
            texcoord = blendernc_material.node_tree.nodes.get("Texture Coordinate")
            imagetex = blendernc_material.node_tree.nodes.get("Image Texture")
            cmap = blendernc_material.node_tree.nodes.get("Colormap")
            bump = blendernc_material.node_tree.nodes.get("Bump")

        P_BSDF = blendernc_material.node_tree.nodes.get("Principled BSDF")

        if sel_obj.name == "Icosphere":
            texcoord_link = texcoord.outputs.get("Generated")
            imagetex.projection = "SPHERE"
        else:
            texcoord_link = texcoord.outputs.get("UV")
            imagetex.projection = "FLAT"

        blendernc_material.node_tree.links.new(imagetex.inputs[0], texcoord_link)
        blendernc_material.node_tree.links.new(cmap.inputs[0], imagetex.outputs[0])
        blendernc_material.node_tree.links.new(bump.inputs[2], imagetex.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[0], cmap.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[-3], bump.outputs[0])

        imagetex.image = bpy.data.images.get("BlenderNC_default")

        if sel_obj or act_obj.type == "MESH":
            sel_obj.active_material = bpy.data.materials.get("BlenderNC_default")

        return {"FINISHED"}
