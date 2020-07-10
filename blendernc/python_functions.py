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
        self.timestamps = {}
        self.nolabel = []
        self.tmp = []
    def tick(self,label=''):
        if label == '':
            self.nolabel.append(time.clock())
            self.timestamps[label] = self.nolabel
        else:
            self.tmp.append(time.clock())
            self.timestamps[label] = self.tmp
            if len(self.timestamps[label]) == 2:
                self.tmp = []

    def report(self,total = False):
        titles = ""
        times = ""
        for key,item in self.timestamps.items():
            if key != '':
                titles += "| {0} |".format(key)  
                time_elapsed_s = "{0:.2e}".format(item[1]-item[0])
                spaceL = ' '*(len(key) - len(time_elapsed_s))
                times += "| {0}{1} |".format(spaceL,time_elapsed_s )
        print('-'*len(titles)) 
        print(titles)
        print(times)
        if total:
            times = np.array([item for key,item in self.timestamps.items()]).ravel()
            print('-'*len(titles))
            total_text = '| Total = ' 
            total_t = '{0:.2e} seconds |'.format(max(times)-min(times))
            print('{0}{1}{2}'.format(total_text,' '*(len(titles)-len(total_text)-len(total_t)),total_t))
            FPS_text = '| FPS = '
            FPS = '{0:.2g} |'.format(1/(max(times)-min(times)))
            print('{0}{1}{2}'.format(FPS_text,' '*(len(titles)-len(FPS_text)-len(FPS)),FPS))
            print('-'*len(titles))

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

def get_dims(ncdata,var):
    dimensions = list(ncdata[var].coords.dims)
    dim_names = [(dimensions[ii], dimensions[ii], dimensions[ii], "DISK_DRIVE", ii+1) for ii in range(len(dimensions))]
    dim_names.insert(0,('NONE',"Select Dim","Select Dim","DISK_DRIVE",0))
    return dim_names

def get_var(ncdata):
    dimensions = list(ncdata.coords.dims.keys())
    variables = list(ncdata.variables.keys() - dimensions)
    if "long_name" in ncdata[variables[0]].attrs:
        var_names = [(variables[ii], variables[ii], ncdata[variables[ii]].long_name, "DISK_DRIVE", ii+1) for ii in range(len(variables))]
    else:
        var_names = [(variables[ii], variables[ii], variables[ii], "DISK_DRIVE", ii+1) for ii in range(len(variables))]
    var_names.insert(0,('NONE',"Select Variable","Select Variable","DISK_DRIVE",0))
    return var_names

def get_possible_variables(node, context):
    ncfile = node.blendernc_file
    unique_identifier = node.blendernc_dataset_identifier 
    if not ncfile or unique_identifier not in node.blendernc_dict.keys():
        return []
    data_dictionary = node.blendernc_dict[unique_identifier]
    ncdata = data_dictionary["Dataset"]
    items = get_var(ncdata)
    return items

def get_new_identifier(node):
    if len(node.name.split('.')) == 1:
        return '{0:03}'.format(0)
    else:
        return '{0:03}'.format(int(node.name.split('.')[-1]))

def get_possible_dims(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    if unique_identifier not in node.blendernc_dict.keys():
        return []
    data_dictionary = node.blendernc_dict[unique_identifier]
    ncdata = data_dictionary["Dataset"]
    var_name = data_dictionary["selected_var"]['selected_var_name']
    items = get_dims(ncdata,var_name)
    return items

def get_possible_files(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    if not unique_identifier in node.blendernc_dict.keys():
        return []
    data_dictionary = node.blendernc_dict[unique_identifier]
    items = [(f, basename(f), basename(f), ii) for ii, f in enumerate(data_dictionary.keys())]
    return items

def update_value(self, context):
    self.update()
    self.rna_type.id_data.interface_update(context)
    
def update_nodes(scene, context):
    selected_variable = scene.blendernc_netcdf_vars
    bpy.data.node_groups.get('BlenderNC').nodes.get('netCDF input').blendernc_netcdf_vars = selected_variable
    update_proxy_file(scene, context)

def update_dict(selected_variable,node):
    if selected_variable == "NONE":
        return
    unique_identifier = node.blendernc_dataset_identifier
    dataset = node.blendernc_dict[unique_identifier]["Dataset"]
    node.blendernc_dict[unique_identifier]["Dataset"] = dataset[selected_variable].to_dataset()
    node.blendernc_dict[unique_identifier]['selected_var']= {
        "max_value" : dataset[selected_variable].max().compute().values,
        "min_value" :(dataset[selected_variable].min()-abs(1e-5*dataset[selected_variable].min())).compute().values,
        "selected_var_name" : selected_variable,
        "resolution":50
        }

def update_res(scene,context):
    bpy.data.node_groups.get('BlenderNC').nodes.get('Resolution').blendernc_resolution = scene.blendernc_resolution


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
    if 'selected_var' not in node.blendernc_dict[node.blendernc_dataset_identifier].keys():
        update_dict(node.blendernc_netcdf_vars,node)

def from_frame_to_pixel_value(frame):
    alpha_channel = np.ones(shape=frame.shape)
    # BW in RGB format for image
    rgb = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
    rgba = np.concatenate((rgb, alpha_channel[:, :, np.newaxis]), axis=2)
    rgba = rgba.ravel()
    # Using foreach_set function for performance ( requires a 32-bit argument)
    return np.float32(rgba)

def get_node(node_group,node):
    node_group = bpy.data.node_groups.get(node_group)
    return node_group.nodes.get(node)

def get_var_dict(context, node, node_tree):
    scene = context.scene
    try:
        scene.nc_cache[node_tree]
    except KeyError:
        scene.nc_cache[node_tree] = {}

    # Check if dictionary entry for the variable exists
    try:
        scene.nc_cache[node_tree][node]
    except KeyError:
        scene.nc_cache[node_tree][node] = {}
    return scene.nc_cache[node_tree][node]

def get_var_data(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get the netcdf of the selected file
    ncdata = data_dictionary[unique_identifier]["Dataset"]
    # Get var name
    var_name = data_dictionary[unique_identifier]["selected_var"]['selected_var_name']
    # Get the data of the selected variable
    return ncdata[var_name]

def get_max_min_data(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get the netcdf of the selected file
    ncdata = data_dictionary[unique_identifier]["Dataset"]
    # Get the metadata of the selected variable
    var_metadata = data_dictionary[unique_identifier]["selected_var"]
    return var_metadata['max_value'],var_metadata['min_value']

def load_frame(context, node, node_tree, frame):
    # Find netcdf file data
    var_data = get_var_data(context, node, node_tree)

    # Find cache dictionary
    var_dict = get_var_dict(context, node, node_tree)
    
    # Global max and min
    vmax, vmin = get_max_min_data(context, node, node_tree)

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


def update_image(context, node, node_tree, step, image):
    if not image:
        return False

    scene = context.scene
    timer = Timer()

    timer.tick('Variable load')

    # Get the data of the selected variable
    var_data = get_var_data(context, node, node_tree)

    timer.tick('Variable load')
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
    timer.tick('Image dimensions')
    # Ensure that the image and the data have the same size.
    img_x, img_y = list(image.size)

    if [img_x, img_y] != [x, y]:
        image.scale(x, y)
        img_x, img_y = list(image.size)
    timer.tick('Image dimensions')
    # Get data of the selected step
    timer.tick('Load Frame')
    try:
        # TODO:Use time coordinate, not index.
        # IF timestep is larger, use the last time value
        if step >= var_data.shape[0]:
            step = var_data.shape[0]-1
        pixels_cache=scene.nc_cache[node_tree][node][step]
        # If the size of the cache data does not match the size of the image multiplied by the 4 channels (RGBA)
        # we need to reload the data.
        if pixels_cache.size != 4 * img_x*img_y:
            raise ValueError("Size of image doesn't match")
    except (KeyError, ValueError):
        # TODO:Use time coordinate, not index.
        if step >= var_data.shape[0]: 
            step = var_data.shape[0]-1
        load_frame(context, node, node_tree, step)
    timer.tick('Load Frame')
        
    # In case data has been pre-loaded
    pixels_value = scene.nc_cache[node_tree][node][step]
    timer.tick('Assign to pixel')
    # TODO: Test version, make it copatible with 2.8 forwards
    image.pixels.foreach_set(pixels_value)
    timer.tick('Assign to pixel')
    timer.tick('Update Image')
    image.update()
    timer.tick('Update Image')
    timer.report(total=True)
    return True

def netcdf_values(dataset,selected_variable,active_resolution):
    """
    """
    variable = dataset[selected_variable]

    dict_var_shape = {ii:slice(0,variable[ii].size,resolution_steps(variable[ii].size,active_resolution))
            for ii in variable.coords if 'time' not in ii}
    
    variable_res = variable.isel(dict_var_shape).to_dataset()
    return variable_res
    

def resolution_steps(size,res):
    # TODO: Fix squaring as it depends on each coordinate, not the overall dataset.
    res_interst = res/5 + 80
    log_scale = np.log10(size)/np.log10((size*res_interst/100)) - 1
    step = size * log_scale
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

def update_animation(self,context):
    try:
        bpy.data.node_groups['BlenderNC'].nodes['Output'].update_on_frame_change=self.blendernc_animate
    except KeyError:
        pass

def get_lost_dim(node):
    new_dims = list(node.blendernc_dict[node.blendernc_dataset_identifier]['Dataset'].coords.dims)
    old_dims = list(node.inputs[0].links[0].from_node.blendernc_dict[node.blendernc_dataset_identifier]['Dataset'].coords.dims)

    return [ii for ii in (old_dims + new_dims) if (old_dims + new_dims).count(ii) ==1][0]

# xarray core TODO: Divide file for future computations (isosurfaces, vector fields, etc.)
import xarray
import os
import glob

class BlenderncEngine():
    """"
    """
    def __init__(self):
        pass

    def check_files_netcdf(self,file_path):
        """
        Check that file exists.
        """
        #file_folder = os.path.dirname(file_path)
        if "*" in file_path:
            self.file_path = glob.glob(file_path)
            self.check_netcdf()
        elif os.path.isfile(file_path):
            self.file_path = [file_path]
            self.check_netcdf()
        else:
            raise NameError("File doesn't exist:",file_path)

        return {'Dataset' : self.dataset}
            
    def check_netcdf(self):
        """
        Check if file is a netcdf and contain at least one variable.
        """
        if len(self.file_path) == 1:
            extension = self.file_path[0].split('.')[-1]
            if extension == ".nc":
                self.load_netcd()
            else:
                try:
                    self.load_netcdf()
                except:
                    raise ValueError("File isn't a netCDF:",self.file_path)
        else:
            extension = self.file_path[0].split('.')[-1]
            if extension == ".nc":
                self.load_netcd()
            else:
                try:
                    self.load_netcdf()
                except:
                    raise ValueError("Files aren't netCDFs:",self.file_path)

    def load_netcdf(self):
        """
        Load netcdf using xarray.
        """
        self.dataset = xarray.open_mfdataset(self.file_path,combine='by_coords')


class dataset_modifiers():
    def __init__(self):
        self.type = None
        self.computation = None

    def update_type(self, ctype, computation):
        self.type = ctype
        self.computation = computation

    def get_core_func(self):
        return json_functions[self.type]


json_functions={'roll': xarray.core.rolling.DataArrayRolling}


from xarray.core.dataset import Dataset


