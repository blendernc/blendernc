#
# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...
import bpy
# Other imports
import numpy as np
from os.path import basename


# Definitions
def get_possible_variables(self, context):
    scene = context.scene

    data_dictionary = scene.nc_dictionary
    node = self
    ncfile = node.file_name
    if not ncfile or not data_dictionary:
        return []
    ncdata = data_dictionary[ncfile]
    dimensions = list(ncdata.coords.dims.keys())
    variables = list(ncdata.variables.keys() - dimensions)
    items = [(var, var, ncdata[var].name, "DISK_DRIVE", ii) for ii, var in enumerate(variables)]
    return items


def get_possible_files(self, context):
    scene = context.scene
    data_dictionary = scene.nc_dictionary
    if not data_dictionary:
        return []
    items = [(f, basename(f), basename(f), ii) for ii, f in enumerate(data_dictionary.keys())]
    return items


def get_max_timestep(self, context):
    scene = context.scene
    # ncfile = scene.nc_file_path
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
    step = node.inputs['frame'].default_value
    print(node.file_name, node.var_name, step)
    if step != node.frame_loaded:
        if update_image(context, node.file_name, node.var_name, step, node.flip, node.image):
            node.frame_loaded = step


def update_image(context, file_name, var_name, step, flip, image):
    if not image:
        return False
    scene = context.scene

    # Get data dictionary stored at scene object
    data_dictionary = scene.nc_dictionary

    # Get the netcdf of the selected file
    ncdata = data_dictionary[file_name]
    # Get the data of the selected variable
    var_data = ncdata[var_name]

    # Get object shape
    t, y, x = var_data.shape

    # Check if the image is an image object or a image name:
    if not isinstance(image, bpy.types.Image):
        images = bpy.data.images
        image = images[image]

    # Ensure that the image and the data have the same size.
    img_x, img_y = image.size
    img_x, img_y = int(img_x), int(img_y)
    if [img_x, img_y] != [x, y]:
        image.scale(x, y)
    # Get data of the selected step
    frame_data = var_data[step, :, :]
    if flip:
        frame_data = np.flip(frame_data, axis=0)

    # Find ranges and normalize in the interval [0,1]
    dmin, dmax = frame_data.min(), frame_data.max()
    var_range = dmax - dmin
    frame_data = (frame_data - dmin) / var_range

    alpha_channel = frame_data.where(np.isfinite(frame_data), 0).where(~np.isfinite(frame_data), 1).values
    normalized_data = frame_data

    # BW in RGB format for image
    rgb = np.repeat(normalized_data.values[:, :, np.newaxis], 3, axis=2)
    rgba = np.concatenate((rgb, alpha_channel[:, :, np.newaxis]), axis=2)

    image.pixels = rgba.ravel()
    image.update()
    return True
