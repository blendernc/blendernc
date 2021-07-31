import bpy
import numpy as np

import blendernc.get_utils as bnc_gutils
import blendernc.nodes.cmaps.utils_colorramp as bnc_cramputils
import blendernc.python_functions as bnc_pyfunc
from blendernc.core.logging import Timer
from blendernc.decorators import ImageDecorator
from blendernc.messages import PrintMessage, drop_dim, huge_image, increase_resolution
from blendernc.translations import translate


@ImageDecorator.check_data
def update_image(context, node, node_tree, frame, image, grid_node=None):
    # Leave next line here, if move to the end it will crash blender.
    # TODO: Text why this line crashes, up to this point,
    # it seems quite random.
    timer = Timer()

    node_ = bpy.data.node_groups[node_tree].nodes[node]
    unique_identifier = node_.blendernc_dataset_identifier
    scene = context.scene

    if not grid_node and len(node_.inputs) == 2:
        grid_node = node_.inputs[1].links[0].from_node.name

    timer.tick("Variable load")
    # Get the data of the selected variable and grid

    var_data = bnc_gutils.get_var_data(context, node, node_tree)

    timer.tick("Variable load")
    # Get object shape
    if len(var_data.shape) == 2:
        y, x = var_data.shape
    elif len(var_data.shape) == 3:
        t, y, x = var_data.shape
    else:
        PrintMessage(drop_dim, title="Error", icon="ERROR")

    if y > 5120 or x > 5120:
        PrintMessage(huge_image, title="Error", icon="ERROR")
        return

    # Check if the image is an image object or a image name:
    if not isinstance(image, bpy.types.Image):
        images = bpy.data.images
        image = images[image]
        image.colorspace_settings.name = "Non-Color"

    timer.tick("Image dimensions")
    # Ensure that the image and the data have the same size.
    img_x, img_y = list(image.size)

    if [img_x, img_y] != [x, y]:
        image.scale(x, y)
        img_x, img_y = list(image.size)
    timer.tick("Image dimensions")
    # Get data of the selected step
    timer.tick("Load Frame")
    # IF timestep is larger, use the last time value
    if frame >= var_data.shape[0]:
        if scene.blendernc_animation_type == "EXTEND":
            frame = var_data.shape[0] - 1
        elif scene.blendernc_animation_type == "LOOP":
            current_frame = scene.frame_current
            n_repeat = current_frame // var_data.shape[0]
            frame = current_frame - n_repeat * var_data.shape[0]
        else:
            return False

    # timer.tick('Update time')
    update_datetime_text(context, node, node_tree, frame)
    # timer.tick('Update time')

    try:
        # TODO:Use time coordinate, not index.
        pixels_cache = scene.datacube_cache[node_tree][unique_identifier][frame]
        # If the size of the cache data does not match the size
        # of the image multiplied by the 4 channels (RGBA)
        # we need to reload the data.
        if pixels_cache.size != 4 * img_x * img_y:
            raise ValueError("Size of image doesn't match")
    except (KeyError, ValueError):
        bnc_pyfunc.load_frame(context, node, node_tree, frame, grid_node)
    timer.tick("Load Frame")

    # In case data has been pre-loaded
    pixels_value = scene.datacube_cache[node_tree][unique_identifier][frame]
    timer.tick("Assign to pixel")
    # TODO: Test version, make it copatible with 2.8 forwards
    image.pixels.foreach_set(pixels_value)
    timer.tick("Assign to pixel")
    timer.tick("Update Image")
    image.update()
    timer.tick("Update Image")
    timer.report(total=True, frame=frame)
    bnc_pyfunc.purge_cache(node_tree, unique_identifier)
    return True


def update_range(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)
    try:
        max_val = node.blendernc_dataset_max
        min_val = node.blendernc_dataset_min
    except AttributeError:
        max_val, min_val = update_random_range(unique_data_dict)
        if max_val == min_val:
            window_manager = bpy.context.window_manager
            PrintMessage(increase_resolution, title="Error", icon="ERROR")
            # Cancel update range and force the user to change the resolution.
            return

    unique_data_dict["selected_var"]["max_value"] = max_val
    unique_data_dict["selected_var"]["min_value"] = min_val

    if len(node.outputs) != 0:
        NodeTree = node.rna_type.id_data.name
        frame = bpy.context.scene.frame_current
        bnc_pyfunc.refresh_cache(NodeTree, unique_identifier, frame)

    update_value_and_node_tree(node, context)


def update_random_range(unique_data_dict):
    dataset = unique_data_dict["Dataset"]
    sel_var = unique_data_dict["selected_var"]
    selected_variable = sel_var["selected_var_name"]
    selected_var_dataset = dataset[selected_variable]
    rand_sample = bnc_pyfunc.dataarray_random_sampling(selected_var_dataset, 100)
    max_val = np.max(rand_sample)
    min_val = np.min(rand_sample)
    return max_val, min_val


def update_datetime_text(
    context,
    node,
    node_tree,
    frame,
    time_text="",
    decode=False,
):
    """
    Update text object with time.

    If text is provided, frame is ignored.
    """
    if not time_text:
        time = str(bnc_gutils.get_time(context, node, node_tree, frame))[:10]
    else:
        time = time_text
    # TODO allow user to define format.

    if "Camera" in bpy.data.objects.keys() and time:
        Camera = bpy.data.objects.get("Camera")
        size = 0.03
        coords = (-0.35, 0.17, -1)
        children_name = [children.name for children in Camera.children]
        if "BlenderNC_time" not in children_name:
            bpy.ops.object.text_add(radius=size)
            text = bpy.context.object
            text.name = "BlenderNC_time"
            text.parent = Camera
            text.location = coords
            mat = bnc_pyfunc.ui_material()
            text.data.materials.append(mat)
        else:
            children = Camera.children
            text = [c for c in children if c.name == "BlenderNC_time"][-1]
        text.data.body = time
        if text.select_get():
            text.select_set(False)


def update_colormap_interface(context, node, node_tree):
    # Get var range
    max_val, min_val = bnc_gutils.get_max_min_data(context, node, node_tree)
    units = bnc_gutils.get_units_data(node, node_tree)

    node = bpy.data.node_groups[node_tree].nodes[node]

    # Find materials using image:
    materials = bnc_gutils.get_all_materials_using_image(node.image)

    # Find all nodes using the selected image in the node.
    image_user_nodes = bnc_gutils.get_all_nodes_using_image(materials, node.image)

    # support for multiple materials. This will generate multiple colorbars.
    colormap = [
        bnc_gutils.get_colormaps_of_materials(user_node, node.image)
        for user_node in image_user_nodes
    ]

    width = 0.007
    height = 0.12

    if "Camera" not in bpy.data.objects.keys():
        return

    Camera = bpy.data.objects.get("Camera")
    children_name = [children.name for children in Camera.children]
    if "cbar_{}".format(node.name) not in children_name:
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False)
        cbar_plane = bpy.context.object
        cbar_plane.name = "cbar_{}".format(node.name)
        cbar_plane.dimensions = (width, height, 0)
        cbar_plane.location = (0.15, 0, -0.5)
        cbar_plane.parent = Camera
        splines = bnc_cramputils.add_splines(
            colormap[-1].n_stops,
            cbar_plane,
            width,
            height,
        )
    else:
        c_childrens = Camera.children
        cbar_plane = [
            child for child in c_childrens if child.name == "cbar_{}".format(node.name)
        ][-1]
        splines = [
            child
            for child in cbar_plane.children
            if "text_cbar_{}".format(node.name.split(".")[0]) in child.name
        ]

    # Update splines
    step = (max_val - min_val) / (len(splines) - 1)
    labels = np.arange(min_val, max_val + step, step)
    for s_index in range(len(splines)):
        splines[s_index].data.body = str(np.round(labels[s_index], 2))

    unit_obj = create_unit_obj(cbar_plane)

    unit_obj.data.body = units

    c_material = bnc_cramputils.colorbar_material(node, colormap[-1])

    if c_material:
        cbar_plane.data.materials.append(c_material)
    # Get data dictionary stored at scene object


def create_unit_obj(cbar_plane):
    # TODO: Make the text pattern search more generic. i.e, include
    unit_objs = [
        child
        for child in cbar_plane.children
        if "text_units_{}".format(cbar_plane.name) in child.name
    ]

    if not unit_objs:
        unit_obj = bnc_cramputils.add_units(cbar_plane)
    else:
        unit_obj = unit_objs[0]
    return unit_obj


def update_res(scene, context):
    """
    Simple UI function to update BlenderNC node tree.
    """
    bpy.data.node_groups.get("BlenderNC").nodes.get(
        translate("Resolution")
    ).blendernc_resolution = scene.blendernc_resolution


def update_proxy_file(self, context):
    """
    Update function:
        -   Checks if datacube file exists
        -   Extracts variable names using datacube conventions.
    """
    bpy.ops.blendernc.datacubeload_sui()


def update_file_vars(node, context):
    """
    Update function:
        -   Checks if datacube file exists
        -   Extracts variable names using datacube conventions.
    """
    bpy.ops.blendernc.var(file_path=bpy.context.scene.blendernc_file)


def update_animation(self, context):
    try:
        bpy.data.node_groups["BlenderNC"].nodes[
            translate("Output")
        ].update_on_frame_change = self.blendernc_animate
    except KeyError:
        pass


def update_value(self, context):
    self.update()


def update_value_and_node_tree(self, context):
    self.update()
    update_node_tree(self, context)


def update_node_tree(self, context):
    self.rna_type.id_data.interface_update(context)


def update_socket_and_tree(self, context):
    self.node.update()
    update_node_tree(self, context)


def update_nodes(scene, context):
    selected_variable = scene.blendernc_datacube_vars
    default_node_group_name = scene.default_nodegroup
    bpy.data.node_groups.get(default_node_group_name).nodes.get(
        "datacube Input"
    ).blendernc_datacube_vars = selected_variable
    update_proxy_file(scene, context)


def update_dict(selected_variable, node):
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)
    if hasattr(unique_data_dict["Dataset"][selected_variable], "units"):
        units = unique_data_dict["Dataset"][selected_variable].units
    else:
        units = ""

    unique_data_dict["selected_var"] = {
        "max_value": None,
        "min_value": None,
        "selected_var_name": selected_variable,
        "resolution": 50,
        "path": node.blendernc_file,
        "units": units,
    }
