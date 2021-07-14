#!/usr/bin/env python3

# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...

import glob
import os

# TODO: If netcdf file has been selected already create a copy of the TreeNode
import bpy

# Other imports
import numpy as np
import xarray

# Partial import to avoid cyclic import
import blendernc.get_utils as bnc_gutils
import blendernc.nodes.cmaps.utils_colorramp as bnc_cramputils
from blendernc.core.logging import Timer
from blendernc.image import from_data_to_pixel_value, normalize_data
from blendernc.messages import drop_dim, huge_image, increase_resolution
from blendernc.translations import translate


def build_enum_prop_list(list, icon="NONE", long_name_list=None, start=1):
    if long_name_list:
        list = [
            (str(list[ii]), str(list[ii]), long_name_list[ii], icon, ii + start)
            for ii in range(len(list))
        ]
    else:
        list = [
            (str(list[ii]), str(list[ii]), str(list[ii]), icon, ii + start)
            for ii in range(len(list))
        ]
    return list


def empty_item():
    return [("No var", "No variable", "Empty", "CANCEL", 0)]


def select_item():
    return [("No var", "Select variable", "Empty", "NODE_SEL", 0)]


def select_datacube():
    return [("No datacube", "Select datacube", "Empty", "NODE_SEL", 0)]


def update_value(self, context):
    self.update()


def update_value_and_node_tree(self, context):
    self.update()
    update_node_tree(self, context)


def update_node_tree(self, context):
    self.rna_type.id_data.interface_update(context)


def update_nodes(scene, context):
    selected_variable = scene.blendernc_netcdf_vars
    default_node_group_name = scene.default_nodegroup
    bpy.data.node_groups.get(default_node_group_name).nodes.get(
        "netCDF input"
    ).blendernc_netcdf_vars = selected_variable
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


def update_range(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)
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

    scene = bpy.context.scene
    nodetrees = bnc_gutils.get_blendernc_nodetrees()
    n = 0
    for node in nodetrees:
        # Make sure the nc_cache is loaded.
        if node.name in scene.nc_cache.keys():
            cache = scene.nc_cache[node.name]
            for key, item in cache.items():
                n += len(item)

    if scene.blendernc_memory_handle == "FRAMES":
        while n > scene.blendernc_frames:
            cached_nodetree = scene.nc_cache[NodeTree][identifier]
            frames_loaded = list(cached_nodetree.keys())
            cached_nodetree.pop(frames_loaded[0])
            n -= 1
            print("Removed frame: {0}".format(frames_loaded[0]))
    else:
        import warnings

        import psutil

        mem = psutil.virtual_memory()
        mem_avail_percent = (mem.available / mem.total) * 100
        while mem_avail_percent < scene.blendernc_avail_mem_purge and n > 1:
            cached_nodetree = scene.nc_cache[NodeTree][identifier]
            frames_loaded = list(cached_nodetree.keys())
            cached_nodetree.pop(frames_loaded[0])
            print("Removed frame: {0}".format(frames_loaded[0]))
            from blendernc.core.sys_utils import get_size

            cache_dict_size = get_size(scene.nc_cache)
            message = "Dynamic cache: \n Total dict cache - {0} \n"
            message += "Available percentage - {1}"
            warnings.warn(message.format(cache_dict_size, mem_avail_percent))
            n -= 1

        # print(cache_dict_size/2**10, mem.available/2**10,mem.total/2**10)
        # print(scene.nc_cache['BlenderNC']['001'].keys() )


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
        translate("Resolution")
    ).blendernc_resolution = scene.blendernc_resolution


def dict_update(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    data_dictionary = node.blendernc_dict
    if unique_identifier in data_dictionary:
        dataset_dict = data_dictionary[unique_identifier]
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


def normalize_data_w_grid(node, node_tree, data, grid_node):
    node = bpy.data.node_groups[node_tree].nodes[node]
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)

    grid_node = bpy.data.node_groups[node_tree].nodes[grid_node]
    unique_grid_dict = bnc_gutils.get_unique_data_dict(grid_node)

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


def load_frame(context, node, node_tree, frame, grid_node=None):
    # Find netcdf file data
    # Get the data of the selected variable and grid

    var_data = bnc_gutils.get_var_data(context, node, node_tree)

    # Find cache dictionary
    var_dict = bnc_gutils.get_var_dict(context, node, node_tree)

    # Global max and min
    vmax, vmin = bnc_gutils.get_max_min_data(context, node, node_tree)

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
    # the performance. May be really useful with 3D and 4D dataset.
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
        window_manager.popup_menu(drop_dim, title="Error", icon="ERROR")

    if y > 5120 or x > 5120:
        window_manager.popup_menu(huge_image, title="Error", icon="ERROR")
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
            mat = ui_material()
            text.data.materials.append(mat)
        else:
            children = Camera.children
            text = [c for c in children if c.name == "BlenderNC_time"][-1]
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
    max_val, min_val = bnc_gutils.get_max_min_data(context, node, node_tree)
    units = bnc_gutils.get_units_data(node, node_tree)

    node = bpy.data.node_groups[node_tree].nodes[node]

    # Find all nodes using the selected image in the node.
    all_nodes = bnc_gutils.get_all_nodes_using_image(node.image.name)
    # Find only materials using image.
    material_users = [
        items
        for nodes, items in all_nodes.items()
        if items.rna_type.id_data.name == "Shader Nodetree"
    ]
    # support for multiple materials. This will generate multiple colorbars.
    colormap = [bnc_gutils.get_colormaps_of_materials(node) for node in material_users]

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
            splines = bnc_cramputils.add_splines(
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

        unit_obj.data.body = units

        c_material = bnc_cramputils.colorbar_material(node, colormap[-1])
        if c_material:
            cbar_plane.data.materials.append(c_material)
    # Get data dictionary stored at scene object


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
    bpy.ops.blendernc.ncload_sui()


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
            translate("Output")
        ].update_on_frame_change = self.blendernc_animate
    except KeyError:
        pass


def rotate_longitude(node, context):
    unique_data_dict = bnc_gutils.get_unique_data_dict(node)
    # TODO Clear cache, otherwise the transform won't be applied.
    dataset = unique_data_dict["Dataset"]
    lon_coords = bnc_gutils.get_geo_coord_names(dataset)["lon_name"]
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
        If datacubes have the expected format (netCDF, cfgrib, and zarr)
        then the dataset is returned.

    Raises
    ------
    ValueError:
        when `datacubes` are not the expected format
    """

    def __init__(self):
        pass

    def check_files_datacube(self, file_path):
        """
        Check that file(s) exist and they are xarray datacube compatible.

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
            self.check_datacube()
        elif os.path.isfile(file_path):
            self.file_path = [file_path]
            self.check_datacube()
        elif os.path.isdir(file_path) and os.path.splitext(file_path)[-1] == ".zarr":
            self.file_path = [file_path]
            self.check_datacube()
        else:
            raise NameError("File doesn't exist:", file_path)

        return {"Dataset": self.dataset}

    def check_datacube(self):
        """
        Check if file(s) are xarray compatible and contain at least one variable.
        """
        extension = os.path.splitext(self.file_path[0])
        print(f"Attempting to load {extension} format files")
        try:
            self.load_datacube()
        except RuntimeError:
            raise ValueError("File isn't supported by Xarray install:", self.file_path)

    def load_datacube(self):
        """
        Detect format and load datacube using appropriate Xarray Driver
        - NetCDF is the existing implementation
        - CFGrib support is being implemented as part of ECMWC
        - Zarr support will give true scalable cloud-native usage and on the roadmap
        Engine detection by extension :
        http://xarray.pydata.org/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset
        """
        # Determine engine to use based on extension of first file
        basename = os.path.basename(self.file_path[0])
        ext = os.path.splitext(basename)
        if ext[1] == ".nc":
            self.dataset = xarray.open_mfdataset(self.file_path, combine="by_coords")
            return
        elif ext[1] == ".grib":
            self.dataset = xarray.open_mfdataset(
                self.file_path, engine="cfgrib", combine="by_coords"
            )
            return
        elif ext[1] == ".zarr":
            self.dataset = xarray.open_mfdataset(
                self.file_path, engine="zarr", combine="by_coords"
            )
            return
        else:
            raise ValueError(
                """File extension is not supported,
                make sure you select a supported file ('.nc' or '.grib')""",
                self.file_path,
            )
