import bpy
import numpy as np

import blendernc.get_utils as bnc_gutils
import blendernc.nodes.cmaps.utils_colorramp as bnc_cramputils
import blendernc.python_functions as bnc_pyfunc
from blendernc.core.logging import Timer
from blendernc.messages import PrintMessage, drop_dim, huge_image, increase_resolution
from blendernc.translations import translate


class UpdateImage:
    """
    UpdateImage class, responsable of loading and generating an
    image from a datacube.
    """

    def __init__(self, context, node, node_tree, frame, image, grid_node=None):
        self.scene = context.scene
        self.nodename = node
        self.node = bpy.data.node_groups[node_tree].nodes[node]
        self.u_identifier = self.node.blendernc_dataset_identifier
        self.node_tree = node_tree
        self.frame = frame
        self.image = image
        self.grid_node = grid_node
        if len(self.node.inputs) == 2 and not grid_node:
            if self.node.inputs[1].is_linked and self.node.inputs[1].links:
                self.grid_node = self.node.inputs[1].links[0].from_node.name

        if self.image:
            self.timer = Timer()
            self.check_image()
            self.update_image()

    def update_image(self):
        self.timer.tick("Variable load")
        # Get the data of the selected variable and grid
        var_data = bnc_gutils.get_var_data(self.node)
        self.timer.tick("Variable load")

        t, y, x = self.data_shape(var_data.shape)

        if y > 5120 or x > 5120:
            PrintMessage(huge_image, title="Error", icon="ERROR")
            return

        self.timer.tick("Image dimensions")
        # Ensure that the image and the data have the same size.
        img_x, img_y = self.image_dims(x, y)
        self.timer.tick("Image dimensions")
        # Get data of the selected step
        self.timer.tick("Load Frame")
        # IF timestep is larger, use the last time value
        if self.frame >= t:
            self.frame = self.preference_animation(t)

        if self.frame is False:
            return self.frame

        self.timer.tick("Update time")
        update_datetime_text(self.node, self.node_tree, self.frame)
        self.timer.tick("Update time")
        self.store_image_in_cache(self.frame, img_x, img_y)
        self.timer.tick("Load Frame")

        # In case data has been pre-loaded
        datacube_cache = self.scene.datacube_cache[self.node_tree]
        pixels_value = datacube_cache[self.u_identifier][self.frame]
        self.timer.tick("Assign to pixel")
        self.image.pixels.foreach_set(pixels_value)
        self.timer.tick("Assign to pixel")
        self.timer.tick("Update Image")
        self.image.update()
        self.timer.tick("Update Image")
        self.timer.report(total=True, frame=self.frame)
        bnc_pyfunc.purge_cache(self.node_tree, self.u_identifier)
        return True

    def store_image_in_cache(self, frame, img_x, img_y):
        try:
            # TODO:Use time coordinate, not index.
            datacube_cache = self.scene.datacube_cache[self.node_tree]
            pixels_cache = datacube_cache[self.u_identifier][frame]
            # If the size of the cache data does not match the size
            # of the image multiplied by the 4 channels (RGBA)
            # we need to reload the data.
            if pixels_cache.size != 4 * img_x * img_y:
                raise ValueError("Size of image doesn't match")
        except (KeyError, ValueError):
            bnc_pyfunc.load_frame(self.node, frame, self.grid_node)

    def check_image(self):
        # Check if the image is an image object or a image name:
        if not isinstance(self.image, bpy.types.Image):
            images = bpy.data.images
            self.image = images[self.image]
            self.image.colorspace_settings.name = "Non-Color"

    def data_shape(self, shape):
        # Get object shape
        if len(shape) == 2:
            y, x = shape
            t = 0
        elif len(shape) == 3:
            t, y, x = shape
        else:
            PrintMessage(drop_dim, title="Error", icon="ERROR")
        return t, y, x

    def image_dims(self, x, y):
        img_x, img_y = list(self.image.size)

        if [img_x, img_y] != [x, y]:
            self.image.scale(x, y)
            img_x, img_y = list(self.image.size)
        return img_x, img_y

    def preference_animation(self, t):
        if self.scene.blendernc_animation_type == "EXTEND":
            frame = t - 1
        elif self.scene.blendernc_animation_type == "LOOP":
            current_frame = self.scene.frame_current
            n_repeat = current_frame // t
            frame = current_frame - n_repeat * t
        else:
            frame = False
        return frame


def update_range(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)
    try:
        max_val = node.blendernc_dataset_max
        min_val = node.blendernc_dataset_min
    except AttributeError:
        max_val, min_val = update_random_range(unique_data_dict)
        if max_val == min_val:
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
    max_val = np.nanmax(rand_sample)
    min_val = np.nanmin(rand_sample)
    return max_val, min_val


def update_datetime_text(
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
        time = str(bnc_gutils.get_time(node, frame))[:10]
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


def update_colormap_interface(nodename, node_tree):
    # Get var range
    node = bpy.data.node_groups[node_tree].nodes[nodename]
    image = node.image
    max_val, min_val = bnc_gutils.get_max_min_data(node)
    units = bnc_gutils.get_units_data(nodename, node_tree)

    # Find materials using image:
    materials = bnc_gutils.get_all_materials_using_image(image)

    # Find all nodes using the selected image in the node.
    image_user_nodes = bnc_gutils.get_all_nodes_using_image(materials, image)

    # support for multiple materials. This will generate multiple colorbars.
    colormap = [
        bnc_gutils.get_colormaps_of_materials(user_node, image)
        for user_node in image_user_nodes
    ]

    width = 0.007
    height = 0.12

    if "Camera" not in bpy.data.objects.keys():
        return

    Camera = bpy.data.objects.get("Camera")
    children_name = [children.name for children in Camera.children]
    if "cbar_{}".format(image.name) not in children_name:
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False)
        cbar_plane = bpy.context.object
        cbar_plane.name = "cbar_{}".format(image.name)
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
            child for child in c_childrens if child.name == "cbar_{}".format(image.name)
        ][-1]
        splines = [
            child
            for child in cbar_plane.children
            if "text_cbar_{}".format(image.name.split(".")[0]) in child.name
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
