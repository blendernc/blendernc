#
# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...
import bpy
# Other imports
import numpy as np
from os.path import basename

import time
class Timer:
    def __init__(self):
        self.timestamps = []
    def tick(self):
        self.timestamps.append(time.clock())
    def report(self):
        rep = ""
        for i in range(len(self.timestamps)-1):
            rep += "%.1e " % ( self.timestamps[i+1]-self.timestamps[i])
        print(rep)

# Definitions
def normalize_data(data, min_range=None, max_range=None):
    # Find ranges and normalize in the interval [0,1]
    if min_range is None:
        min_range = np.nanmin(data)
    if max_range is None:
        max_range = np.nanmax(data)
    var_range = max_range - min_range
    return data #(data - min_range) / var_range

def get_var(ncdata):
    dimensions = list(ncdata.coords.dims.keys())
    variables = list(ncdata.variables.keys() - dimensions)
    if ncdata[variables[0]].long_name:
        var_names = [(variables[ii], variables[ii], ncdata[variables[ii]].long_name, "DISK_DRIVE", ii) for ii in range(len(variables))]
    else:
        var_names = [(variables[ii], variables[ii], variables[ii], "DISK_DRIVE", ii) for ii in range(len(variables))]
    return var_names

def get_possible_variables(self, context):
    scene = context.scene

    data_dictionary = scene.nc_dictionary
    node = self
    ncfile = node.file_name
    if not ncfile or not data_dictionary:
        return []
    ncdata = data_dictionary[ncfile]
    items = get_var(ncdata)
    return items

def get_possible_files(self, context):
    scene = context.scene
    data_dictionary = scene.nc_dictionary
    if not data_dictionary:
        return []
    items = [(f, basename(f), basename(f), ii) for ii, f in enumerate(data_dictionary.keys())]
    return items

def update_nodes(self, context):
    selected_variable = self.blendernc_netcdf_vars
    node_keys = [key for key in bpy.data.node_groups[-1].nodes.keys() if 'netCDFinput' in key]
    # Change last input node
    bpy.data.node_groups[-1].nodes[node_keys[-1]].var_name = selected_variable


def get_max_timestep(self, context):
    scene = context.scene
    ncfile = self.file_name
    data_dictionary = scene.nc_dictionary
    if not ncfile or not data_dictionary:
        return 0
    ncdata = data_dictionary[ncfile]
    var_name = self.var_name
    var_data = ncdata[var_name]
    t, y, x = var_data.shape
    return t - 1


def step_update(node, context):
    step = node.step
    print(node.file_name, node.var_name, step)
    if step != node.frame_loaded:
        if update_image(context, node.file_name, node.var_name, step, node.flip, node.image):
            node.frame_loaded = step

def from_frame_to_pixel_value(frame):
        alpha_channel = np.ones(shape=frame.shape)
        # BW in RGB format for image
        rgb = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
        rgba = np.concatenate((rgb, alpha_channel[:, :, np.newaxis]), axis=2)
        rgba = rgba.ravel()
        # Using foreach_set function for performance ( requires a 32-bit argument)
        return np.float32(rgba)


def get_var_dict(context, file_path, var_name):
    scene = context.scene
    try:
        scene.nc_cache[file_path]
    except KeyError:
        scene.nc_cache[file_path] = {}

    # Check if dictionary entry for the variable exists
    try:
        scene.nc_cache[file_path][var_name]
    except KeyError:
        scene.nc_cache[file_path][var_name] = {}
    return scene.nc_cache[file_path][var_name]

def get_var_data(context, file_path, var_name):
    scene = context.scene
    # Get data dictionary stored at scene object
    data_dictionary = scene.nc_dictionary
    # Get the netcdf of the selected file
    ncdata = data_dictionary[file_path]
    # Get the data of the selected variable
    return ncdata[var_name]

def load_frame(context, file_path, var_name, frame):
    # Find netcdf file data
    var_data = get_var_data(context, file_path, var_name)
    # Find cache dictionary
    var_dict = get_var_dict(context, file_path, var_name)

    # Load data and normalize

    frame_data = var_data[frame, :, :].values[:, :]
    normalized_data = normalize_data(frame_data)

    # Store in cache
    var_dict[frame] = from_frame_to_pixel_value(normalized_data)


def update_image(context, file_name, var_name, step, flip, image):
    if not image:
        return False

    scene = context.scene
    timer = Timer()

    timer.tick()
    # Get data dictionary stored at scene object
    data_dictionary = scene.nc_dictionary

    # Get the netcdf of the selected file
    ncdata = data_dictionary[file_name]
    # Get the data of the selected variable
    var_data = ncdata[var_name]

    timer.tick()
    # Get object shape
    t, y, x = var_data.shape

    # Check if the image is an image object or a image name:
    if not isinstance(image, bpy.types.Image):
        images = bpy.data.images
        image = images[image]
    timer.tick()
    # Ensure that the image and the data have the same size.
    img_x, img_y = image.size
    img_x, img_y = int(img_x), int(img_y)
    if [img_x, img_y] != [x, y]:
        image.scale(x, y)
    # Get data of the selected step
    timer.tick()
    try:
        scene.nc_cache[file_name][var_name][step]
    except KeyError:
        load_frame(context, file_name, var_name, step)
        
    # In case data has been pre-loaded
    pixels_value = scene.nc_cache[file_name][var_name][step]
    timer.tick()


    image.pixels.foreach_set(pixels_value)
    timer.tick()
    image.update()
    timer.tick()
    timer.report()
    return True
