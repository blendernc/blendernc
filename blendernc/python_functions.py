#!/usr/bin/env python3

# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...

import glob
import os
from os.path import basename

# TODO: If netcdf file has been selected already create a copy of the TreeNode
import bpy

# Other imports
import numpy as np
import xarray

from .core.logging import Timer
from .get_utils import get_unique_data_dict
from .image import from_data_to_pixel_value, normalize_data
from .messages import drop_dim, huge_image, increase_resolution


def get_dims(ncdata, var):
    dimensions = list(ncdata[var].coords.dims)
    dim_names = [
        (dimensions[ii], dimensions[ii], dimensions[ii], "EMPTY_DATA", ii + 1)
        for ii in range(len(dimensions))
    ]
    return dim_names


def get_geo_coord_names(dataset):
    lon_coords = [coord for coord in dataset.coords if ("lon" in coord or "x" in coord)]
    lat_coords = [coord for coord in dataset.coords if ("lat" in coord or "y" in coord)]
    return {"lon_name": lon_coords, "lat_name": lat_coords}


def get_var(ncdata):
    dimensions = sorted(list(ncdata.coords.dims.keys()))
    variables = sorted(list(ncdata.variables.keys() - dimensions))
    if "long_name" in ncdata[variables[0]].attrs:
        var_names = [
            (
                variables[ii],
                variables[ii],
                ncdata[variables[0]].attrs["long_name"],
                "DISK_DRIVE",
                ii + 1,
            )
            for ii in range(len(variables))
        ]
    else:
        var_names = [
            (variables[ii], variables[ii], variables[ii], "DISK_DRIVE", ii + 1)
            for ii in range(len(variables))
        ]

    return select_item() + [None] + var_names


def empty_item():
    return [("No var", "No variable", "Empty", "CANCEL", 0)]


def select_item():
    return [("No var", "Select variable", "Empty", "NODE_SEL", 0)]


def select_datacube():
    return [("No datacube", "Select datacube", "Empty", "NODE_SEL", 0)]


def get_possible_variables(node, context):
    ncfile = node.blendernc_file
    unique_identifier = node.blendernc_dataset_identifier
    if not ncfile or unique_identifier not in node.blendernc_dict.keys():
        return empty_item()
    unique_data_dict = get_unique_data_dict(node)
    ncdata = unique_data_dict["Dataset"]
    items = get_var(ncdata)
    return items


def get_new_identifier(node):
    if len(node.name.split(".")) == 1:
        return "{:03}".format(0)
    else:
        return "{:03}".format(int(node.name.split(".")[-1]))


# TODO Add decorator to simplify.
def get_possible_dims(node, context):
    if node.inputs:
        if node.inputs[0].is_linked and node.inputs[0].links:
            link = node.inputs[0].links[0]
            unique_identifier = node.blendernc_dataset_identifier
            parent_node = link.from_node
            blendernc_dict = parent_node.blendernc_dict
            if not blendernc_dict:
                return []
            else:
                data_dictionary = parent_node.blendernc_dict[unique_identifier]
                ncdata = data_dictionary["Dataset"]
                var_name = data_dictionary["selected_var"]["selected_var_name"]
                items = get_dims(ncdata, var_name)
            return items
        else:
            return []
    else:
        return []


def get_possible_files(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    if unique_identifier not in node.blendernc_dict.keys():
        return []
    data_dictionary = node.blendernc_dict[unique_identifier]
    enum_data_dict_keys = enumerate(data_dictionary.keys())
    items = [(f, basename(f), basename(f), i) for i, f in enum_data_dict_keys]
    return items


def update_value(self, context):
    self.update()


def update_value_and_node_tree(self, context):
    self.update()
    update_node_tree(self, context)


def update_node_tree(self, context):
    self.rna_type.id_data.interface_update(context)


def update_nodes(scene, context):
    selected_variable = scene.blendernc_netcdf_vars
    bpy.data.node_groups.get("BlenderNC").nodes.get(
        "netCDF input"
    ).blendernc_netcdf_vars = selected_variable
    update_proxy_file(scene, context)


def update_dict(selected_variable, node):
    unique_data_dict = get_unique_data_dict(node)
    unique_data_dict["selected_var"] = {
        "max_value": None,
        "min_value": None,
        "selected_var_name": selected_variable,
        "resolution": 50,
        "path": node.blendernc_file,
    }


def get_selected_var(node):
    unique_data_dict = get_unique_data_dict(node)
    dataset = unique_data_dict["Dataset"]
    selected_variable = unique_data_dict["selected_var"]["selected_var_name"]
    selected_var_dataset = dataset[selected_variable]
    return selected_var_dataset


def update_range(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = get_unique_data_dict(node)
    try:
        max_val = node.blendernc_dataset_max
        min_val = node.blendernc_dataset_min
    except AttributeError:
        dataset = unique_data_dict["Dataset"]
        sel_var = unique_data_dict["selected_var"]
        selected_variable = sel_var["selected_var_name"]
        selected_var_dataset = dataset[selected_variable]
        rand_sample = dataarray_random_sampling(selected_var_dataset, 100)
        max_val = np.max(rand_sample)
        min_val = np.min(rand_sample)
        if max_val == min_val:
            window_manager = bpy.context.window_manager
            window_manager.popup_menu(increase_resolution, title="Error", icon="ERROR")
            # Cancel update range and force the user to change the resolution.
            return

    unique_data_dict["selected_var"]["max_value"] = max_val
    unique_data_dict["selected_var"]["min_value"] = min_val

    if len(node.outputs) != 0:
        NodeTree = node.rna_type.id_data.name
        frame = bpy.context.scene.frame_current
        refresh_cache(NodeTree, unique_identifier, frame)

    update_value_and_node_tree(node, context)


def dataarray_random_sampling(dataarray, n):
    values = np.zeros(n) * np.nan
    dataarray_dims = [dim for dim in dataarray.dims]
    counter = 0
    randint = np.random.randint
    while not np.isfinite(values).all():
        len_data_dims = len(dataarray_dims)
        dims_dict = {
            dataarray_dims[ii]: randint(0, len(dataarray[dataarray_dims[ii]]))
            for ii in range(len_data_dims)
        }
        values[counter] = dataarray.isel(dims_dict).values
        if np.isfinite(values[counter]):
            counter += 1
    return values


def purge_cache(NodeTree, identifier):
    # TODO: Test number of total loaded frames for
    # multiple nodetrees and node outputs.
    # 300 frames at 1440*720 use ~ 6GB of ram.
    # Make this value dynamic to support computer with more or less ram.
    # Perhaps compress and uncompress data?
    cached_nodetree = bpy.context.scene.nc_cache[NodeTree][identifier]
    if len(cached_nodetree) > 10:
        frames_loaded = list(cached_nodetree.keys())
        cached_nodetree.pop(frames_loaded[0])


def refresh_cache(NodeTree, identifier, frame):
    if bpy.context.scene.nc_cache:
        cached_nodetree = bpy.context.scene.nc_cache[NodeTree][identifier]
        if frame in list(cached_nodetree.keys()):
            cached_nodetree.pop(frame)


def is_cached(NodeTree, identifier):
    if NodeTree in bpy.context.scene.nc_cache.keys():
        if identifier in bpy.context.scene.nc_cache[NodeTree].keys():
            return True
    else:
        return False


def del_cache(NodeTree, identifier):
    if bpy.context.scene.nc_cache:
        bpy.context.scene.nc_cache[NodeTree].pop(identifier)
        # keys = list(bpy.context.scene.nc_cache[NodeTree][identifier].keys())
        # for key in keys:
        #     bpy.context.scene.nc_cache[NodeTree][identifier].pop(key)


def update_res(scene, context):
    """
    Simple UI function to update BlenderNC node tree.
    """
    bpy.data.node_groups.get("BlenderNC").nodes.get(
        "Resolution"
    ).blendernc_resolution = scene.blendernc_resolution


def get_max_timestep(self, context):
    scene = context.scene
    ncfile = self.file_name
    data_dictionary = scene.nc_dictionary
    if not ncfile or not data_dictionary:
        return 0
    ncdata = data_dictionary["Dataset"]
    var_name = self.var_name
    var_data = ncdata[var_name]

    t, y, x = var_data.shape
    return t - 1


def dict_update(node, context):
    dataset_dict = node.blendernc_dict[node.blendernc_dataset_identifier]
    selected_var = (
        dataset_dict["selected_var"]["selected_var_name"]
        if "selected_var" in dataset_dict.keys()
        else ""
    )
    node_tree = node.rna_type.id_data.name
    unique_identifier = node.blendernc_dataset_identifier

    update_dict(node.blendernc_netcdf_vars, node)

    if (
        is_cached(node_tree, unique_identifier)
        and selected_var != node.blendernc_netcdf_vars
    ):
        del_cache(node_tree, unique_identifier)

    update_value_and_node_tree(node, context)


def get_node(node_group, node):
    node_group = bpy.data.node_groups.get(node_group)
    return node_group.nodes.get(node)


def get_var_dict(context, node, node_tree):
    scene = context.scene
    node = bpy.data.node_groups[node_tree].nodes[node]
    unique_identifier = node.blendernc_dataset_identifier
    try:
        scene.nc_cache[node_tree]
    except KeyError:
        scene.nc_cache[node_tree] = {}

    # Check if dictionary entry for the variable exists
    try:
        scene.nc_cache[node_tree][unique_identifier]
    except KeyError:
        scene.nc_cache[node_tree][unique_identifier] = {}
    return scene.nc_cache[node_tree][unique_identifier]


def get_var_data(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the netcdf of the selected file
    ncdata = unique_data_dict["Dataset"]
    # Get var name
    var_name = unique_data_dict["selected_var"]["selected_var_name"]
    # Get the data of the selected variable
    # Remove Nans
    # TODO: Add node to preserve NANs
    # if node.keep_nan:
    data = ncdata[var_name]
    # else:
    # data = ncdata[var_name].where(np.isfinite(ncdata[var_name]), 0)
    return data


def normalize_data_w_grid(node, node_tree, data, grid_node):
    node = bpy.data.node_groups[node_tree].nodes[node]
    unique_data_dict = get_unique_data_dict(node)

    grid_node = bpy.data.node_groups[node_tree].nodes[grid_node]
    unique_grid_dict = get_unique_data_dict(grid_node)

    grid = unique_grid_dict["Dataset"].copy()
    x_grid_name = unique_grid_dict["Coords"]["X"]
    y_grid_name = unique_grid_dict["Coords"]["Y"]
    active_resolution = unique_data_dict["selected_var"]["resolution"]

    # Perhaps useful instead of not converting to dataset?
    # if x_grid_name in list(grid.coords) or y_grid_name in list(grid.coords):
    #     grid_x = grid.coords[x_grid_name].drop((x_grid_name,y_grid_name))
    #     grid_y = grid.coords[y_grid_name].drop((x_grid_name,y_grid_name))
    #     grid = xarray.merge((grid_y,grid_x))

    x_grid_data = netcdf_values(grid, x_grid_name, active_resolution, False)
    y_grid_data = netcdf_values(grid, y_grid_name, active_resolution, False)

    # Plot image using matplotlib.
    # TODO Current implementation is not ideal, it is slow
    # (3s for 3600x2700 grid), but better than
    # interpolation.
    # Tripolar grids will have issues
    # in the North Pole.
    vmin = unique_data_dict["selected_var"]["min_value"]
    vmax = unique_data_dict["selected_var"]["max_value"]
    norm_data = plot_using_grid(x_grid_data, y_grid_data, data, vmin, vmax)
    return norm_data


def plot_using_grid(x, y, data, vmin, vmax, dpi=300):
    # from matplotlib.backends.backend_agg import
    # FigureCanvasAgg as FigureCanvas
    import matplotlib

    matplotlib.use("agg")
    import matplotlib.pyplot as plt

    pixel_size_figure = data.shape[1] / dpi, data.shape[0] / dpi
    fig = plt.figure(figsize=(pixel_size_figure), dpi=dpi)
    ax = fig.add_axes((0, 0, 1, 1))

    image = ax.pcolormesh(x.values, y.values, data, vmin=vmin, vmax=vmax)

    ax.set_ylim(-90, 90)
    fig.patch.set_visible(False)
    plt.axis("off")
    fig.canvas.draw()
    image = np.fromstring(fig.canvas.tostring_rgb(), dtype="uint8")
    image_shape = (data.shape[0], data.shape[1], 3)
    new_image = image.reshape(image_shape).sum(axis=2) / (3 * 255)
    plt.close()
    new_image[new_image == 1] = new_image.min() - (0.01 * new_image.min())
    # fig = plt.figure(figsize=(data.shape[0]/dpi, data.shape[1]/dpi), dpi=dpi)
    # ax = fig.add_axes((0,0,1,1))
    # ax.imshow(new_image)
    # plt.savefig('test.png')
    return normalize_data(new_image[::-1])


def get_time(context, node, node_tree, frame):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the netcdf of the selected file
    ncdata = unique_data_dict["Dataset"]
    # Get the data of the selected variable
    if "time" in ncdata.coords.keys():
        time = ncdata["time"]
        if time.size == 1:
            return time.values
        elif frame > time.size:
            return time[-1].values
        else:
            return time[frame].values
    else:
        return ""


def get_max_min_data(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the metadata of the selected variable
    var_metadata = unique_data_dict["selected_var"]
    max_val = var_metadata["max_value"]
    min_val = var_metadata["min_value"]
    if max_val is not None and min_val is not None:
        return var_metadata["max_value"], var_metadata["min_value"]
    else:
        update_range(node, context)
        return var_metadata["max_value"], var_metadata["min_value"]


def load_frame(context, node, node_tree, frame, grid_node=None):
    # Find netcdf file data
    # Get the data of the selected variable and grid

    var_data = get_var_data(context, node, node_tree)

    # Find cache dictionary
    var_dict = get_var_dict(context, node, node_tree)

    # Global max and min
    vmax, vmin = get_max_min_data(context, node, node_tree)

    # TODO: Improve by using coordinates,
    # could generate issues if the first axis isn't time
    # Load data and normalize
    # TODO: Move dataset shape only do it once,
    # perhaps when selecting variable.
    if len(var_data.shape) == 2:
        frame_data = var_data[:, :].values[:, :]
    elif len(var_data.shape) == 3:
        frame_data = var_data[frame, :, :].values[:, :]
    # TODO: Test if computing vmax and vmin once improves
    # the performance. May be really usefull with 3D and 4D dataset.
    if grid_node:
        normalized_data = normalize_data_w_grid(
            node,
            node_tree,
            frame_data,
            grid_node,
        )
    else:
        normalized_data = normalize_data(frame_data, vmax, vmin)

    # Store in cache
    var_dict[frame] = from_data_to_pixel_value(normalized_data)


def update_image(context, node, node_tree, frame, image, grid_node=None):
    window_manager = bpy.context.window_manager
    if not image:
        return False
    # Leave next line here, if move to the end it will crash blender.
    # TODO: Text why this line crashes, up to this point,
    # it seems quite random.
    timer = Timer()

    # timer.tick('Update time')
    update_datetime_text(context, node, node_tree, frame)
    # timer.tick('Update time')
    node_ = bpy.data.node_groups[node_tree].nodes[node]
    unique_identifier = node_.blendernc_dataset_identifier
    scene = context.scene

    if not grid_node and len(node_.inputs) == 2:
        grid_node = node_.inputs[1].links[0].from_node.name

    timer.tick("Variable load")
    # Get the data of the selected variable and grid

    var_data = get_var_data(context, node, node_tree)

    timer.tick("Variable load")
    # Get object shape
    if len(var_data.shape) == 2:
        y, x = var_data.shape
    elif len(var_data.shape) == 3:
        t, y, x = var_data.shape
    else:
        window_manager.popup_menu(drop_dim, title="Error", icon="ERROR")

    if y > 5120 or x > 5120:
        window_manager.popup_menu(huge_image, title="Error", icon="ERROR")
        return

    # Check if the image is an image object or a image name:
    if not isinstance(image, bpy.types.Image):
        images = bpy.data.images
        image = images[image]
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
        frame = var_data.shape[0] - 1
    try:
        # TODO:Use time coordinate, not index.
        pixels_cache = scene.nc_cache[node_tree][unique_identifier][frame]
        # If the size of the cache data does not match the size
        # of the image multiplied by the 4 channels (RGBA)
        # we need to reload the data.
        if pixels_cache.size != 4 * img_x * img_y:
            raise ValueError("Size of image doesn't match")
    except (KeyError, ValueError):
        load_frame(context, node, node_tree, frame, grid_node)
    timer.tick("Load Frame")

    # In case data has been pre-loaded
    pixels_value = scene.nc_cache[node_tree][unique_identifier][frame]
    timer.tick("Assign to pixel")
    # TODO: Test version, make it copatible with 2.8 forwards
    image.pixels.foreach_set(pixels_value)
    timer.tick("Assign to pixel")
    timer.tick("Update Image")
    image.update()
    timer.tick("Update Image")
    timer.report(total=True, frame=frame)
    purge_cache(node_tree, unique_identifier)
    return True


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
        time = str(get_time(context, node, node_tree, frame))[:10]
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
            mat = ui_material()
            text.data.materials.append(mat)
        else:
            childrens = Camera.children
            text = [c for c in childrens if c.name == "BlenderNC_time"][-1]
        text.data.body = time
        if text.select_get():
            text.select_set(False)


def ui_material():
    mat = bpy.data.materials.get("BlenderNC_info")
    if mat is None:
        # create material
        mat = bpy.data.materials.new(name="BlenderNC_info")
        mat.use_nodes = True
        BSDF = mat.node_tree.nodes["Principled BSDF"]
        emission = BSDF.inputs.get("Emission")
        emission.default_value = (1, 1, 1, 1)
    return mat


def update_colormap_interface(context, node, node_tree):
    # Get var range
    max_val, min_val = get_max_min_data(context, node, node_tree)

    node = bpy.data.node_groups[node_tree].nodes[node]

    # Find all nodes using the selected image in the node.
    all_nodes = get_all_nodes_using_image(node.image.name)
    # Find only materials using image.
    material_users = [
        items
        for nodes, items in all_nodes.items()
        if items.rna_type.id_data.name == "Shader Nodetree"
    ]
    # support for multiple materials. This will generate multiple colorbars.
    colormap = [get_colormaps_of_materials(node) for node in material_users]

    width = 0.007
    height = 0.12
    if "Camera" in bpy.data.objects.keys():
        Camera = bpy.data.objects.get("Camera")
        children_name = [children.name for children in Camera.children]
        if "cbar_{}".format(node.name) not in children_name:
            bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False)
            cbar_plane = bpy.context.object
            cbar_plane.name = "cbar_{}".format(node.name)
            cbar_plane.dimensions = (width, height, 0)
            cbar_plane.location = (0.15, 0, -0.5)
            cbar_plane.parent = Camera
            splines = add_splines(
                colormap[-1].n_stops,
                cbar_plane,
                width,
                height,
            )
        else:
            c_childrens = Camera.children
            cbar_plane = [
                child
                for child in c_childrens
                if child.name == "cbar_{}".format(node.name)
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

        c_material = colorbar_material(context, node, node_tree, colormap[-1])
        if c_material:
            cbar_plane.data.materials.append(c_material)
    # Get data dictionary stored at scene object


def add_splines(n, cbar_plane, width=0.1, height=1):
    size = 1
    splines = []
    step = 2 / n
    locs = np.round(np.arange(-1, 1 + step, step), 2)
    y_rescale = 0.12
    for ii in range(n + 1):
        bpy.ops.object.text_add(radius=size)
        spline = bpy.context.object
        spline.data.align_y = "CENTER"
        spline.parent = cbar_plane
        spline.location = (1.4, locs[ii], 0)
        spline.lock_location = (True, True, True)
        spline.scale = (1.7, y_rescale, 1.2)
        spline.name = "text_{}".format(cbar_plane.name)
        mat = ui_material()
        spline.data.materials.append(mat)
        splines.append(spline)
    return splines


def colorbar_material(context, node, node_tree, colormap):
    materials = bpy.data.materials
    blendernc_materials = [
        material for material in materials if "" + node.name in material.name
    ]

    if len(blendernc_materials) != 0:
        blendernc_material = blendernc_materials[-1]
        cmap = blendernc_material.node_tree.nodes.get("Colormap")
        if cmap.colormaps == colormap.colormaps:
            return
    else:
        bpy.ops.material.new()
        blendernc_material = bpy.data.materials[-1]
        blendernc_material.name = "" + node.name

    material_node_tree = blendernc_material.node_tree

    if len(material_node_tree.nodes.keys()) == 2:
        texcoord = material_node_tree.nodes.new("ShaderNodeTexCoord")
        texcoord.location = (-760, 250)
        mapping = material_node_tree.nodes.new("ShaderNodeMapping")
        mapping.location = (-580, 250)
        cmap = material_node_tree.nodes.new("cmapsNode")
        cmap.location = (-290, 250)
        emi = material_node_tree.nodes.new("ShaderNodeEmission")
        emi.location = (-290, -50)
        P_BSDF = material_node_tree.nodes.get("Principled BSDF")
        material_node_tree.nodes.remove(P_BSDF)

    else:
        texcoord = material_node_tree.nodes.get("Texture Coordinate")
        mapping = material_node_tree.nodes.get("Mapping")
        cmap = material_node_tree.nodes.get("Colormap")
        emi = material_node_tree.nodes.get("Emission")

    output = material_node_tree.nodes.get("Material Output")

    # Links
    material_link = material_node_tree.links
    material_link.new(mapping.inputs[0], texcoord.outputs[0])
    material_link.new(cmap.inputs[0], mapping.outputs[0])
    material_link.new(emi.inputs[0], cmap.outputs[0])
    material_link.new(output.inputs[0], emi.outputs[0])

    # Assign values:
    mapping.inputs["Location"].default_value = (0, -0.6, 0)
    mapping.inputs["Rotation"].default_value = (0, np.pi / 4, 0)
    mapping.inputs["Scale"].default_value = (1, 2.8, 1)

    cmap.n_stops = colormap.n_stops
    cmap.fcmap = colormap.fcmap
    cmap.colormaps = colormap.colormaps
    cmap.fv_color = colormap.fv_color

    return blendernc_material


def get_colormaps_of_materials(node):
    """
    Function to find materials using the BlenderNC output node image.
    """
    unfind = True
    counter = 0

    links = node.outputs.get("Color").links
    # TODO: Change this to a recursive search.
    # Currently, only colormaps directly connected to
    # the output will generate a colormap.
    while unfind:
        for link in links:
            if link.to_node.bl_idname == "cmapsNode":
                colormap_node = link.to_node
                unfind = False
                break
            elif counter == 10:
                unfind = False
            else:
                counter += 1

    if counter == 10:
        raise ValueError("Colormap not found after 10 tree node interations")
    return colormap_node


def get_all_nodes_using_image(image_name):
    users = {}
    for node_group in bpy.data.node_groups:
        for node in node_group.nodes:
            if node.bl_idname == "netCDFOutput":
                users[node_group.name] = node

    for material in bpy.data.materials:
        if not material.grease_pencil:
            for node in material.node_tree.nodes:
                if node.bl_idname == "ShaderNodeTexImage":
                    users[material.name] = node

    return users


def netcdf_values(
    dataset,
    selected_variable,
    active_resolution,
    return_dataset=True,
):
    """ """
    variable = dataset[selected_variable]
    max_shape = max(variable.shape)

    if variable.dims:
        axis_selection = variable.dims
    elif variable.coords:
        axis_selection = variable.coords

    resolution_stepping = resolution_steps(max_shape, active_resolution)
    dict_var_shape = {
        ii: slice(0, variable[ii].size, resolution_stepping)
        for ii in axis_selection
        if ("time" not in ii and "t" != ii)
    }

    if return_dataset:
        return variable.isel(dict_var_shape).to_dataset()
    else:
        return variable.isel(dict_var_shape)


def resolution_steps(size, res):
    # TODO extend the range of values.
    scaling = 10 ** int(np.log10(size))

    steps = np.logspace(1, size / scaling, 100) - 10
    step = steps[int(100 - res)]

    if step < 1:
        step = 1
    return int(step)


def update_proxy_file(self, context):
    """
    Update function:
        -   Checks if netCDF file exists
        -   Extracts variable names using netCDF4 conventions.
    """
    bpy.ops.blendernc.ncload_sui(file_path=bpy.context.scene.blendernc_file)


def update_file_vars(node, context):
    """
    Update function:
        -   Checks if netCDF file exists
        -   Extracts variable names using netCDF4 conventions.
    """
    bpy.ops.blendernc.var(file_path=bpy.context.scene.blendernc_file)


def update_animation(self, context):
    try:
        bpy.data.node_groups["BlenderNC"].nodes[
            "Output"
        ].update_on_frame_change = self.blendernc_animate
    except KeyError:
        pass


def rotate_longitude(node, context):
    unique_data_dict = get_unique_data_dict(node)
    # TODO Clear cache, otherwise the transform wont be applied.
    dataset = unique_data_dict["Dataset"]
    lon_coords = get_geo_coord_names(dataset)["lon_name"]
    if len(lon_coords) == 1:
        coord = lon_coords[0]
        new_dataset = dataset.assign_coords(
            {coord: (((dataset[coord] - node.blendernc_rotation) % 360))}
        ).sortby(coord)
        unique_data_dict["Dataset"] = new_dataset
        # dataset.roll(
        # {lon_coords[0]: int(node.blendernc_rotation)}, roll_coords=True
        # )
    else:
        raise ValueError(
            """Multiple lon axis are not supported.
             The default axis names are anything containing
             'lon' or 'x'."""
        )
    NodeTree = node.rna_type.id_data.name
    frame = bpy.context.scene.frame_current
    identifier = node.blendernc_dataset_identifier
    refresh_cache(NodeTree, identifier, frame)


def get_xarray_datasets(node, context):
    xarray_datacube = sorted(xarray.tutorial.file_formats.keys())
    enum_datacube_dict_keys = enumerate(xarray_datacube)
    datacube_names = [
        (
            key,
            key,
            key,
            "DISK_DRIVE",
            i + 1,
        )
        for i, key in enum_datacube_dict_keys
    ]
    return select_datacube() + datacube_names


def dict_update_tutorial_datacube(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    data_dictionary = node.blendernc_dict
    selected_datacube = node.blendernc_xarray_datacube
    if selected_datacube == "No datacube":
        return
    node.blendernc_file = "Tutorial"
    data_dictionary[unique_identifier] = {
        "Dataset": xarray.tutorial.open_dataset(selected_datacube)
    }


# xarray core TODO: Divide file for future computations
# (isosurfaces, vector fields, etc.)


class BlenderncEngine:
    """
    BlenderNC engine, this class makes sure the input file exists
    and it has the right format.

    Returns
    -------
    Datacube
        If datacubes have the expected format (netCDF, cgrid, and zar)
        then the dataset is returned.

    Raises
    ------
    ValueError:
        when `datacubes` are not the expected format
    """

    def __init__(self):
        pass

    def check_files_netcdf(self, file_path):
        """
        Check if file exists and it's format.

        Parameters
        ----------
        filepath: str
            string to data

        Returns
        -------
        dataset: dict
            Initial dictionary containing lazy datacube load.

        Raises
        ------
        NameError:
            when datafile doesn't exist.
        """
        # file_folder = os.path.dirname(file_path)
        if "*" in file_path:
            self.file_path = glob.glob(file_path)
            self.check_netcdf()
        elif os.path.isfile(file_path):
            self.file_path = [file_path]
            self.check_netcdf()
        else:
            raise NameError("File doesn't exist:", file_path)

        return {"Dataset": self.dataset}

    def load_netcdf(self):
        """
        Load netcdf using xarray.
        """
        filepath = self.file_path
        self.dataset = xarray.open_mfdataset(filepath, combine="by_coords")

    def check_netcdf(self):
        """
        Check if file is a netcdf and contain at least one variable.
        """
        if len(self.file_path) == 1:
            extension = self.file_path[0].split(".")[-1]
            if extension == ".nc":
                self.load_netcd()
            else:
                try:
                    self.load_netcdf()
                except RuntimeError:
                    raise ValueError("File isn't a netCDF:", self.file_path)
        else:
            extension = self.file_path[0].split(".")[-1]
            if extension == ".nc":
                self.load_netcd()
            else:
                try:
                    self.load_netcdf()
                except RuntimeError:
                    raise ValueError("Files aren't netCDFs:", self.file_path)


class dataset_modifiers:
    def __init__(self):
        self.type = None
        self.computation = None

    def update_type(self, ctype, computation):
        self.type = ctype
        self.computation = computation

    def get_core_func(self):
        return json_functions[self.type]


json_functions = {"roll": xarray.core.rolling.DataArrayRolling}
