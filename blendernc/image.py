#!/usr/bin/env python3
import numpy as np


def dataset_2_image_preview(node):
    if node.image and node.blendernc_dataset_identifier in node.blendernc_dict.keys():
        data_image = np.zeros((128, 128))
        data = image_data(node)
        min_shape = min(data.shape)
        max_shape = max(data.shape)

        lmaxbound = (128 - (max_shape)) // 2
        umaxbound = (128 + (max_shape)) // 2

        lminbound = (128 - (min_shape)) // 2
        uminbound = (128 + (min_shape)) // 2
        if data.shape[0] == max_shape:
            data_image[lmaxbound:umaxbound, lminbound:uminbound] = data[:128, :]
        else:
            data_image[lminbound:uminbound, lmaxbound:umaxbound] = data[:, :128]

        image = array_to_image(data_image, image_float=False)
    # Commented: This only adds an icon in only a few cases, paricularly when
    # reloading data in developing mode, therefore, it is commented to reduce
    # dependency requirements.
    # else:
    #     i = Image.open(os.path.abspath('./icons/no_image_icon.png')).convert('RGBA')
    #     image = (np.array(i,dtype=np.float16)[::-1,::-1,:]/255).ravel()
    return image


def image_data(node):
    # Get data dictionary stored at scene object
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get dataset
    datacubedata = data_dictionary[unique_identifier]["Dataset"]
    # Get var name
    var_name = data_dictionary[unique_identifier]["selected_var"]["selected_var_name"]
    # Get the data of the selected variable
    if len(datacubedata[var_name].shape) == 2:
        data = datacubedata[var_name][:, :].values[:, :]
    elif len(datacubedata[var_name].shape) == 3:
        data = datacubedata[var_name][0, :, :].values[:, :]
    steps = max(data.shape) // 128
    if steps < 1:
        steps = 1
    while max(data.shape) // steps > 128 - 1:  # subtract 1 so max size is 128
        steps += 1
    return data[::steps, ::steps]


def array_to_image(array, image_float=False):
    """ """
    normalized_data = normalize_data(array)
    rgba = from_data_to_pixel_value(normalized_data, image_float)
    return rgba


# Definitions
def normalize_data(data, max_range=None, min_range=None):
    """ """
    # Find ranges and normalize in the interval [0,1]
    if min_range is None:
        min_range = np.nanmin(data)
    if max_range is None:
        max_range = np.nanmax(data)
    var_range = max_range - min_range

    data[data <= min_range] = min_range
    data[data >= max_range] = max_range
    return (data - min_range) / var_range


def from_data_to_pixel_value(data, image_float=True):
    alpha_channel = np.ones(shape=data.shape)
    # BW in RGB format for image
    rgb = np.repeat(data[:, :, np.newaxis], 3, axis=2)
    rgba = np.concatenate((rgb, alpha_channel[:, :, np.newaxis]), axis=2)
    rgba = rgba.ravel()
    # Using foreach_set function for performance ( requires a 32-bit argument)
    if image_float:
        return np.float32(rgba)
    else:
        return np.float16(rgba)
