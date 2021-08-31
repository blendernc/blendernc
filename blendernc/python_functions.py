#!/usr/bin/env python3

# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...

# import gc
import glob
import os

# TODO: If datacube file has been selected already create a copy of the TreeNode
import bpy

# Other imports
import numpy as np
import xarray

import blendernc.core.update_ui as bnc_updateUI

# Partial import to avoid cyclic import
import blendernc.get_utils as bnc_gutils
from blendernc.decorators import MemoryDecorator
from blendernc.image import from_data_to_pixel_value, normalize_data


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


def dataarray_random_sampling(dataarray, n):
    dataarray_dims = [dim for dim in dataarray.dims]
    randint = np.random.randint
    len_data_dims = len(dataarray_dims)
    dims_dict = {
        dataarray_dims[ii]: [
            randint(0, len(dataarray[dataarray_dims[ii]])) for nn in range(n)
        ]
        for ii in range(len_data_dims)
    }
    values = dataarray.isel(dims_dict).values
    return values


@MemoryDecorator.nodetrees_cached
def purge_cache(NodeTree, identifier, n=0, scene=None):
    if scene.blendernc_memory_handle == "FRAMES":
        while n > scene.blendernc_frames:
            cached_nodetree = scene.datacube_cache[NodeTree][identifier]
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
            cached_nodetree = scene.datacube_cache[NodeTree][identifier]
            frames_loaded = list(cached_nodetree.keys())
            cached_nodetree.pop(frames_loaded[0])
            print("Removed frame: {0}".format(frames_loaded[0]))
            from blendernc.core.sys_utils import get_size

            cache_dict_size = get_size.size(scene.datacube_cache) / (1024 ** 2)  # Mb
            message = "\nDynamic cache:"
            message += "\nTotal dict cache - {0:.2f} Mb"
            message += "\nAvailable percentage - {1:.2f} %"
            warnings.warn(message.format(cache_dict_size, mem_avail_percent))
            n -= 1
    # # Collect Garbage
    # gc.collect()


def refresh_cache(NodeTree, identifier, frame):
    if bpy.context.scene.datacube_cache:
        cached_nodetree = bpy.context.scene.datacube_cache[NodeTree][identifier]
        cached_nodetree.pop(frame, None)


def is_cached(NodeTree, identifier):
    if NodeTree in bpy.context.scene.datacube_cache.keys():
        if identifier in bpy.context.scene.datacube_cache[NodeTree].keys():
            return True
    else:
        return False


def del_cache(NodeTree, identifier):
    if bpy.context.scene.datacube_cache:
        bpy.context.scene.datacube_cache[NodeTree].pop(identifier)
        # keys = list(bpy.context.scene.datacube_cache[NodeTree][identifier].keys())
        # for key in keys:
        #     bpy.context.scene.datacube_cache[NodeTree][identifier].pop(key)


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

        bnc_updateUI.update_dict(node.blendernc_datacube_vars, node)

        if (
            is_cached(node_tree, unique_identifier)
            and selected_var != node.blendernc_datacube_vars
        ):
            del_cache(node_tree, unique_identifier)

        bnc_updateUI.update_value_and_node_tree(node, context)


def normalize_data_w_grid(node, data, grid_node):
    node_tree = node.rna_type.id_data.name
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

    x_grid_data = datacube_values(grid, x_grid_name, active_resolution, False)
    y_grid_data = datacube_values(grid, y_grid_name, active_resolution, False)

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


def load_frame(node, frame, grid_node=None):
    # Find datacube file data
    # Get the data of the selected variable and grid

    var_data = bnc_gutils.get_var_data(node)

    # Find cache dictionary
    var_dict = bnc_gutils.get_var_dict(node)

    # Global max and min
    vmax, vmin = bnc_gutils.get_max_min_data(node)

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
            frame_data,
            grid_node,
        )
    else:
        normalized_data = normalize_data(frame_data, vmax, vmin)

    # Store in cache
    var_dict[frame] = from_data_to_pixel_value(normalized_data)


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


def datacube_values(
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
            self.dataset = xarray.open_mfdataset(
                self.file_path, combine="by_coords", chunks={"time": 1, "t": 1}
            )
            return
        elif ext[1] == ".grib":
            self.dataset = xarray.open_mfdataset(
                self.file_path,
                engine="cfgrib",
                combine="by_coords",
                chunks={"time": 1, "t": 1},
            )
            return
        elif ext[1] == ".zarr":
            self.dataset = xarray.open_mfdataset(
                self.file_path,
                engine="zarr",
                combine="by_coords",
                chunks={"time": 1, "t": 1},
            )
            return
        else:
            raise ValueError(
                """File extension is not supported,
                make sure you select a supported file ('.nc' or '.grib')""",
                self.file_path,
            )
