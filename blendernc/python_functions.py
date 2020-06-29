#
# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...

## TODO: If netcdf file has been selected already create a copy of the TreeNode

import bpy
# Other imports
import numpy as np
from os.path import basename

from .msg_errors import huge_image

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
def normalize_data(data, max_range=None, min_range=None):
    # Find ranges and normalize in the interval [0,1]
    if min_range is None:
        min_range = np.nanmin(data)
    if max_range is None:
        max_range = np.nanmax(data)
    var_range = max_range - min_range
    print(max_range,min_range)
    return (data - min_range) / var_range

def get_var(ncdata):
    dimensions = list(ncdata.coords.dims.keys())
    variables = list(ncdata.variables.keys() - dimensions)
    if "long_name" in ncdata[variables[0]].attrs:
        var_names = [(variables[ii], variables[ii], ncdata[variables[ii]].long_name, "DISK_DRIVE", ii+1) for ii in range(len(variables))]
    else:
        var_names = [(variables[ii], variables[ii], variables[ii], "DISK_DRIVE", ii+1) for ii in range(len(variables))]
    var_names.insert(0,('NONE',"Select Variable","Select Variable","DISK_DRIVE",0))
    return var_names

def get_possible_variables(self, context):
    scene = context.scene
    data_dictionary = scene.nc_dictionary
    node = self
    ncfile = node.blendernc_file
    if not ncfile or not data_dictionary:
        return []
    ncdata = data_dictionary[ncfile]["Dataset"]
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
    node_keys = [key for key in bpy.data.node_groups["BlenderNC"].nodes.keys() if 'netCDFinput' in key]
    # Change last input node
    bpy.data.node_groups[-1].nodes[node_keys[-1]].var_name = selected_variable
    # Compute max and min values only once.
    scene = context.scene
    file_path=self.blendernc_file
    if selected_variable == "NONE":
        return

    update_dict(file_path,selected_variable,scene)
    
def update_dict(file_path,selected_variable,scene):
    scene.nc_dictionary[file_path][selected_variable]= {
        "max_value":scene.nc_dictionary[file_path]["Dataset"][selected_variable].max(),
        "min_value":scene.nc_dictionary[file_path]["Dataset"][selected_variable].min()-abs(1e-5*scene.nc_dictionary[file_path]["Dataset"][selected_variable].min()),
        "resolution":scene.blendernc_resolution
        }

def res_update(node, context):
    # Update dictionary
    if len(context.scene.nc_dictionary)==0 or node.blendernc_file=='':
        pass
    else:
        if node.blendernc_netcdf_vars in bpy.context.scene.nc_dictionary[node.blendernc_file].keys():
            context.scene.nc_dictionary[node.blendernc_file][node.blendernc_netcdf_vars]['resolution'] = node.blendernc_resolution
    
    # Update node tree and image, else write into the Blender NC nodes (used in simple UI)
    if node.name!='Scene':
        node.update()
        if node.outputs[0].is_linked:
            if node.outputs[0].links[0].to_node.bl_idname == 'netCDFOutput':
                image = node.outputs[0].links[0].to_node.image
                update_image(context, node.blendernc_file, node.blendernc_netcdf_vars, 
                        context.scene.frame_current, image)
    else:
        bpy.data.node_groups['BlenderNC'].nodes['Resolution'].blendernc_resolution = node.blendernc_resolution
        #bpy.data.node_groups[]

def get_max_timestep(self, context):
    scene = context.scene
    ncfile = self.file_name
    data_dictionary = scene.nc_dictionary
    if not ncfile or not data_dictionary:
        return 0
    ncdata = data_dictionary[ncfile]["Dataset"]
    var_name = self.var_name
    var_data = ncdata[var_name]
    
    t, y, x = var_data.shape
    return t - 1

def dict_update(node, context):
    if node.blendernc_netcdf_vars not in context.scene.nc_dictionary[node.blendernc_file].keys():
        update_dict(node.blendernc_file, node.blendernc_netcdf_vars,context.scene)

def step_update(node, context):
    dict_update(node,context)
    step = node.step
    print(node.blendernc_file, node.blendernc_netcdf_vars, step)
    if node.blendernc_netcdf_vars=="NONE":
        return
        
    if step != node.frame_loaded:
        if update_image(context, node.blendernc_file, node.blendernc_netcdf_vars, 
                        step, node.image):
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
    # Dataset resolution
    resolution =  data_dictionary[file_path][var_name]['resolution']
    # Get the netcdf of the selected file
    ncdata = data_dictionary[file_path]["Dataset"]
    # Get the data of the selected variable
    return netcdf_values(ncdata,var_name,resolution)

def get_max_min_data(context, file_path, var_name):
    scene = context.scene
    # Get data dictionary stored at scene object
    data_dictionary = scene.nc_dictionary
    # Get the netcdf of the selected file
    var_metadata = data_dictionary[file_path][var_name]
    return var_metadata['max_value'].values,var_metadata['min_value'].values

def load_frame(context, file_path, var_name, frame):
    # Find netcdf file data
    var_data = get_var_data(context, file_path, var_name)

    # Find cache dictionary
    var_dict = get_var_dict(context, file_path, var_name)
    
    # Global max and min
    vmax, vmin = get_max_min_data(context, file_path, var_name)

    # TODO: Improve by using coordinates, 
    # could generate issues if the first axis isn't time
    # Load data and normalize
    # TODO: Move dataset shape only do it once, perhaps when selecting variable.
    if len(var_data.shape) == 2:
        frame_data = var_data[:, :].values[:, :]
    elif len(var_data.shape) == 3:
        frame_data = var_data[frame, :, :].values[:, :]
    # TODO: Test if computing vmax and vmin once improves
    # the performance. May be really usefull with 3D and 4D dataset.
    normalized_data = normalize_data(frame_data,vmax,vmin)

    # Store in cache
    var_dict[frame] = from_frame_to_pixel_value(normalized_data)


def update_image(context, file_name, var_name, step, image):
    if not image:
        return False

    scene = context.scene
    timer = Timer()

    timer.tick()
    # Get data dictionary stored at scene object
    data_dictionary = scene.nc_dictionary

    # Get the data of the selected variable
    var_data = get_var_data(context, file_name, var_name)

    timer.tick()
    # Get object shape
    if len(var_data.shape) == 2:
        y, x = var_data.shape
    elif len(var_data.shape) ==3:
        t, y, x = var_data.shape
    
    if y > 5120 or x > 5120:
        bpy.context.window_manager.popup_menu(huge_image, title="Error", icon='ERROR')
        return

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
        # TODO:Use time coordinate, not index.
        # IF timestep is larger, use the last time value
        if step >= var_data.shape[0]:
            step = var_data.shape[0]-1
        pixels_cache=scene.nc_cache[file_name][var_name][step]
        # If the size of the cache data does not match the size of the image multiplied by the 4 channels (RGBA)
        # we need to reload the data.
        if pixels_cache.size != 4 * img_x*img_y:
            raise ValueError("Size of image doesn't match")
    except (KeyError, ValueError):
        # TODO:Use time coordinate, not index.
        if step >= var_data.shape[0]: 
            step = var_data.shape[0]-1
        load_frame(context, file_name, var_name, step)
        
    # In case data has been pre-loaded
    pixels_value = scene.nc_cache[file_name][var_name][step]
    timer.tick()

    # TODO: Test version, make it copatible with 2.8 forwards
    image.pixels.foreach_set(pixels_value)
    timer.tick()
    image.update()
    timer.tick()
    timer.report()
    return True

def netcdf_values(dataset,selected_variable,active_resolution):
    """
    """

    variable = dataset[selected_variable]

    dict_var_shape = {ii:slice(0,variable[ii].size,resolution_steps(variable[ii].size,active_resolution))
            for ii in variable.coords if 'time' not in ii}
    
    print(selected_variable,dict_var_shape)
    variable_res = variable.isel(dict_var_shape)
    return variable_res
    

def resolution_steps(size,res):
    # TODO: Fix squaring as it depends on each coordinate, not the overall dataset.
    res_interst = res/5 + 80
    log_scale = np.log10(size)/np.log10((size*res_interst/100)) - 1
    step = size * log_scale
    if step ==0:
        step = 1
    return int(step)

def update_proxy_file(self, context):
    """
    Update function:
        -   Checks if netCDF file exists 
        -   Extracts variable names using netCDF4 conventions.
    """
    bpy.ops.blendernc.ncload_sui(file_path=bpy.context.scene.blendernc_file)


def update_file_vars(self, context):
    """
    Update function:
        -   Checks if netCDF file exists 
        -   Extracts variable names using netCDF4 conventions.
    """
    bpy.ops.blendernc.var(file_path=bpy.context.scene.blendernc_file)

def update_animation(self,context):
    try:
        bpy.data.node_groups['BlenderNC'].nodes['Output'].update_on_frame_change=self.blendernc_animate
    except KeyError:
        pass
    
