#
# This file contains pure python functions
#
# Probably for this reason I should avoid importing bpy here...

## TODO: If netcdf file has been selected already create a copy of the TreeNode
import bpy
# Other imports
import numpy as np
from os.path import basename

from . msg_errors import huge_image, drop_dim

from . image import normalize_data, from_data_to_pixel_value

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

def get_dims(ncdata,var):
    dimensions = list(ncdata[var].coords.dims)
    dim_names = [(dimensions[ii], dimensions[ii], dimensions[ii], "EMPTY_DATA", ii+1) for ii in range(len(dimensions))]
    return dim_names

def get_var(ncdata):
    dimensions = list(ncdata.coords.dims.keys())
    variables = list(ncdata.variables.keys() - dimensions)
    if "long_name" in ncdata[variables[0]].attrs:
        var_names = [(variables[ii], variables[ii], ncdata[variables[0]].attrs['long_name'], "DISK_DRIVE", ii+1) for ii in range(len(variables))]
    else:
        var_names = [(variables[ii], variables[ii], variables[ii], "DISK_DRIVE", ii+1) for ii in range(len(variables))]
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
    if node.inputs:
        if node.inputs[0].is_linked and node.inputs[0].links:
            unique_identifier = node.blendernc_dataset_identifier
            parent_node = node.inputs[0].links[0].from_node
            blendernc_dict = parent_node.blendernc_dict
            if not blendernc_dict:
                return []
            else:
                data_dictionary = node.inputs[0].links[0].from_node.blendernc_dict[unique_identifier]
                ncdata = data_dictionary["Dataset"]
                var_name = data_dictionary["selected_var"]['selected_var_name']
                items = get_dims(ncdata,var_name)
            return items
        else:
            return []
    else:
        return []

def get_possible_files(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    if not unique_identifier in node.blendernc_dict.keys():
        return []
    data_dictionary = node.blendernc_dict[unique_identifier]
    items = [(f, basename(f), basename(f), ii) for ii, f in enumerate(data_dictionary.keys())]
    return items

def update_value(self, context):
    self.update()

def update_value_and_node_tree(self, context):
    self.update()
    update_node_tree(self,context)

def update_node_tree(self,context):
    self.rna_type.id_data.interface_update(context)
    
def update_nodes(scene, context):
    selected_variable = scene.blendernc_netcdf_vars
    bpy.data.node_groups.get('BlenderNC').nodes.get('netCDF input').blendernc_netcdf_vars = selected_variable
    update_proxy_file(scene, context)

def update_dict(selected_variable,node):
    unique_identifier = node.blendernc_dataset_identifier
    node.blendernc_dict[unique_identifier]['selected_var']= {
        "max_value" : None,
        "min_value" : None,
        "selected_var_name" : selected_variable,
        "resolution":50,
        "path": node.blendernc_file,
        }

def update_range(node,context):
    unique_identifier = node.blendernc_dataset_identifier
    dataset = node.blendernc_dict[unique_identifier]["Dataset"]
    selected_variable = node.blendernc_dict[unique_identifier]['selected_var']['selected_var_name']
    try:
        node.blendernc_dict[unique_identifier]['selected_var']["max_value"] = node.blendernc_dataset_max
        node.blendernc_dict[unique_identifier]['selected_var']["min_value"] = node.blendernc_dataset_min 
        
        if node.outputs[0].is_linked:
            NodeTree = node.rna_type.id_data.name
            frame = bpy.context.scene.frame_current
            refresh_cache(NodeTree, unique_identifier,frame)
        update_value_and_node_tree(node,context)
    except:
        if node.blendernc_dict[unique_identifier]['selected_var']["max_value"]:
            pass
        else:
            values = dataarray_random_sampling(dataset[selected_variable],100)
            node.blendernc_dict[unique_identifier]['selected_var']["max_value"] = max(values)
            node.blendernc_dict[unique_identifier]['selected_var']["min_value"] = min(values)

def dataarray_random_sampling(dataarray,n):
    values=np.zeros(n)*np.nan
    dataarray_dims = [dim for dim in dataarray.dims]
    counter=0
    while not np.isfinite(values).all():
        dims_dict = {dataarray_dims[ii]:np.random.randint(0,
                                len(dataarray[dataarray_dims[ii]])) 
                                for ii in range(len(dataarray_dims))}
        values[counter] = dataarray.isel(dims_dict).values
        if np.isfinite(values[counter]):
            counter+=1
    return values

def purge_cache(NodeTree, identifier):
    # TODO: Test number of total loaded frames for 
    # multiple nodetrees and node outputs. 
    # 300 frames at 1440*720 use ~ 6GB of ram. 
    # Make this value dynamic to support computer with more or less ram.
    # Perhaps compress and uncompress data? 
    if len(bpy.context.scene.nc_cache[NodeTree][identifier]) > 2:
        frames_loaded = list(bpy.context.scene.nc_cache[NodeTree][identifier].keys())
        bpy.context.scene.nc_cache[NodeTree][identifier].pop(frames_loaded[0])

def refresh_cache(NodeTree, identifier, frame):
    if bpy.context.scene.nc_cache:
        if frame in list(bpy.context.scene.nc_cache[NodeTree][identifier].keys()):
            bpy.context.scene.nc_cache[NodeTree][identifier].pop(frame)

def del_cache(NodeTree, identifier):
    if bpy.context.scene.nc_cache:
        bpy.context.scene.nc_cache[NodeTree].pop(identifier)
        # keys = list(bpy.context.scene.nc_cache[NodeTree][identifier].keys())
        # for key in keys:
        #     bpy.context.scene.nc_cache[NodeTree][identifier].pop(key)

def update_res(scene,context):
    """
    Simple UI function to update BlenderNC node tree.
    """
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
    dataset_dict= node.blendernc_dict[node.blendernc_dataset_identifier]
    selected_var = dataset_dict['selected_var']['selected_var_name'] if 'selected_var' in dataset_dict.keys() else ''
    # Update if user selected a new variable.
    if selected_var and selected_var != node.blendernc_netcdf_vars:
        #Update dict
        update_dict(node.blendernc_netcdf_vars,node)
        node_tree = node.rna_type.id_data.name
        unique_identifier = node.blendernc_dataset_identifier
        del_cache(node_tree, unique_identifier)
        update_value_and_node_tree(node, context)
    else: 
        update_dict(node.blendernc_netcdf_vars,node)
        update_value(node, context)

def get_node(node_group,node):
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
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get the netcdf of the selected file
    ncdata = data_dictionary[unique_identifier]["Dataset"]
    # Get var name
    var_name = data_dictionary[unique_identifier]["selected_var"]['selected_var_name']
    # Get the data of the selected variable
    # Remove Nans
    # TODO: Add node to preserve NANs
    if node.keep_nan:
        data = ncdata[var_name]
    else:
        data = ncdata[var_name].where(np.isfinite(ncdata[var_name]),0)
    return data

def normalize_data_w_grid(node, node_tree, data,  grid_node):
    node = bpy.data.node_groups[node_tree].nodes[node]
    grid_node = bpy.data.node_groups[node_tree].nodes[grid_node]

    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier

    grid_dictionary = grid_node.blendernc_dict
    grid_identifier = grid_node.blendernc_dataset_identifier

    grid = grid_dictionary[grid_identifier]['Dataset'].copy()
    x_grid_name =  grid_dictionary[grid_identifier]['Coords']['X']
    y_grid_name =  grid_dictionary[grid_identifier]['Coords']['Y']
    active_resolution = data_dictionary[unique_identifier]["selected_var"]['resolution']
    
    # Perhaps useful instead of not converting to dataset? 
    # if x_grid_name in list(grid.coords) or y_grid_name in list(grid.coords):
    #     grid_x = grid.coords[x_grid_name].drop((x_grid_name,y_grid_name))
    #     grid_y = grid.coords[y_grid_name].drop((x_grid_name,y_grid_name))
    #     grid = xarray.merge((grid_y,grid_x))

    x_grid_data = netcdf_values(grid,x_grid_name,active_resolution,False)
    y_grid_data = netcdf_values(grid,y_grid_name,active_resolution,False)
    
    # Plot image using matplotlib.
    # TODO Current implementation is not ideal, it is slow 
    # (3s for 3600x2700 grid), but better than 
    # interpolation.
    # Tripolar grids will have issues 
    # in the North Pole. 
    vmin = data_dictionary[unique_identifier]["selected_var"]['min_value']
    vmax = data_dictionary[unique_identifier]["selected_var"]['max_value']
    norm_data = plot_using_grid(x_grid_data,y_grid_data,data,vmin,vmax)
    return norm_data

def plot_using_grid(x,y,data,vmin,vmax,dpi = 300):
    #from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    import matplotlib
    matplotlib.use('agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(data.shape[1]/dpi, data.shape[0]/dpi), dpi=dpi)
    ax = fig.add_axes((0,0,1,1))
    if vmin and vmax:
        image = ax.pcolormesh(x.values,y.values,data,vmin=vmin,vmax=vmax)
    else:
        image = ax.pcolormesh(x.values,y.values,data)
    ax.set_ylim(-90,90)
    fig.patch.set_visible(False)
    plt.axis('off')
    fig.canvas.draw()
    image = np.fromstring(fig.canvas.tostring_rgb(), dtype='uint8')
    new_image = (image.reshape((data.shape[0],data.shape[1],3)).sum(axis=2)/(3*255))
    plt.close()
    new_image[new_image==1] = new_image.min() - (0.01*new_image.min())
    # fig = plt.figure(figsize=(data.shape[0]/dpi, data.shape[1]/dpi), dpi=dpi)
    # ax = fig.add_axes((0,0,1,1))
    # ax.imshow(new_image)
    # plt.savefig('test.png')
    return normalize_data(new_image[::-1])
    
def get_time(context, node, node_tree,frame):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get the netcdf of the selected file
    ncdata = data_dictionary[unique_identifier]["Dataset"]
    # Get the data of the selected variable
    if 'time' in ncdata.coords.keys():
        time = ncdata['time']
        if time.size == 1:
            return time.values
        elif frame > time.size:
            return time[-1].values
        else:
            return time[frame].values
    else:
        return ''

def get_max_min_data(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get the metadata of the selected variable
    var_metadata = data_dictionary[unique_identifier]["selected_var"]
    if var_metadata['max_value']!=None and var_metadata['min_value']!=None:
        return var_metadata['max_value'],var_metadata['min_value']
    else:
        update_range(node,context)
        return var_metadata['max_value'],var_metadata['min_value']


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
    # TODO: Move dataset shape only do it once, perhaps when selecting variable.
    if len(var_data.shape) == 2:
        frame_data = var_data[:, :].values[:, :]
    elif len(var_data.shape) == 3:
        frame_data = var_data[frame, :, :].values[:, :]
    # TODO: Test if computing vmax and vmin once improves
    # the performance. May be really usefull with 3D and 4D dataset.
    if grid_node:
        normalized_data = normalize_data_w_grid(node, node_tree,frame_data,grid_node)
    else:
        normalized_data = normalize_data(frame_data,vmax,vmin)

    # Store in cache
    var_dict[frame] = from_data_to_pixel_value(normalized_data)


def update_image(context, node, node_tree, frame, image, grid_node=None):
    if not image:
        return False
    # Leave next line here, if move to the end it will crash blender. 
    # TODO: Text why this line crashes, up to this point, it seems quite random.
    timer = Timer()

    # timer.tick('Update time')
    update_datetime_text(context, node, node_tree, frame)
    # timer.tick('Update time')
    node_ = bpy.data.node_groups[node_tree].nodes[node]
    unique_identifier = node_.blendernc_dataset_identifier
    scene = context.scene

    if not grid_node and len(node_.inputs)==2:
        grid_node = node_.inputs[1].links[0].from_node.name
    
    timer.tick('Variable load')
    # Get the data of the selected variable and grid
    
    var_data = get_var_data(context, node, node_tree)
    
    timer.tick('Variable load')
    # Get object shape
    if len(var_data.shape) == 2:
        y, x = var_data.shape
    elif len(var_data.shape) ==3:
        t, y, x = var_data.shape
    else:
        bpy.context.window_manager.popup_menu(drop_dim, title="Error", icon='ERROR')
    
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
        if frame >= var_data.shape[0]:
            frame = var_data.shape[0]-1
        pixels_cache=scene.nc_cache[node_tree][unique_identifier][frame]
        # If the size of the cache data does not match the size of the image multiplied by the 4 channels (RGBA)
        # we need to reload the data.
        if pixels_cache.size != 4 * img_x*img_y:
            raise ValueError("Size of image doesn't match")
    except (KeyError, ValueError):
        # TODO:Use time coordinate, not index.
        if frame >= var_data.shape[0]: 
            frame = var_data.shape[0]-1
        load_frame(context, node, node_tree, frame, grid_node)
    timer.tick('Load Frame')
        
    # In case data has been pre-loaded
    pixels_value = scene.nc_cache[node_tree][unique_identifier][frame]
    timer.tick('Assign to pixel')
    # TODO: Test version, make it copatible with 2.8 forwards
    image.pixels.foreach_set(pixels_value)
    timer.tick('Assign to pixel')
    timer.tick('Update Image')
    image.update()
    timer.tick('Update Image')
    timer.report(total=True)
    purge_cache(node_tree, unique_identifier)
    return True

def update_datetime_text(context,node, node_tree, frame, time_text='',decode=False):
    """
    Update text object with time.

    If text is provided, frame is ignored. 
    """
    if not time_text:
        time = str(get_time(context, node, node_tree, frame))[:10]
    else: 
        time = time_text
    #TODO allow user to define format.
    
    if 'Camera' in bpy.data.objects.keys() and time:
        Camera = bpy.data.objects.get('Camera')
        size = 0.03
        coords = (-0.35,0.17,-1)
        children_name  = [children.name for children in  Camera.children]
        if "BlenderNC_time" not in children_name:
            bpy.ops.object.text_add(radius=size)
            text=bpy.context.object
            text.name="BlenderNC_time"
            text.parent = Camera
            text.location = coords
            mat = ui_material()
            try: 
            # Add material
                text.data.materials.append(mat)        
            except:
                pass
        else:
            childrens = Camera.children
            text = [child for child in childrens if child.name=="BlenderNC_time"][-1]
        text.data.body = time
        if text.select_get():
            text.select_set(False)

def ui_material():
    mat = bpy.data.materials.get("BlenderNC_info")
    if mat is None:
    # create material
        mat = bpy.data.materials.new(name="BlenderNC_info")   
        mat.use_nodes = True
        emission = mat.node_tree.nodes['Principled BSDF'].inputs.get('Emission')
        emission.default_value = (1,1,1,1)
    return mat

def update_colormap_interface(context, node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    # Get var range
    max_val = data_dictionary[unique_identifier]["selected_var"]["max_value"]
    min_val = data_dictionary[unique_identifier]["selected_var"]["min_value"]

    #Find all nodes using the selected image in the node.
    all_nodes = get_all_nodes_using_image(node.image.name)
    #Find only materials using image.
    material_users = [ items for nodes, items in all_nodes.items() if items.rna_type.id_data.name == 'Shader Nodetree']
    #support for multiple materials. This will generate multiple colorbars.
    colormap = [get_colormaps_of_materials(node) for node in material_users]

    width = 0.007
    height = 0.12
    if 'Camera' in bpy.data.objects.keys():
        Camera = bpy.data.objects.get('Camera')
        children_name  = [children.name for children in  Camera.children]
        if 'cbar_{0}'.format(node.name) not in children_name:
            bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False)
            cbar_plane=bpy.context.object
            cbar_plane.name = 'cbar_{0}'.format(node.name) 
            cbar_plane.dimensions =  (width,height,0)
            cbar_plane.location = (0.15,0,-0.5)
            cbar_plane.parent = Camera
            splines = add_splines(colormap[-1].n_stops,cbar_plane,width,height)
        else:
            c_childrens = Camera.children
            cbar_plane = [child for child in c_childrens if child.name=='cbar_{0}'.format(node.name) ][-1]
            splines = [child for child in cbar_plane.children if 'text_cbar_{0}'.format(node.name) in child.name]
        
        # Update splines
        step = (max_val-min_val)/(len(splines)-1)
        labels = np.arange(min_val,max_val+step,step)
        for s_index in range(len(splines)):
            splines[s_index].data.body = str(np.round(labels[s_index],2))
        
        c_material = colorbar_material(context, node, node_tree, colormap[-1])
        if c_material:
            cbar_plane.data.materials.append(c_material)        
    # Get data dictionary stored at scene object

def add_splines(n,cbar_plane,width=0.1,height=1):
    size = 1
    splines = []
    step = 2/n
    locs = np.round(np.arange(-1,1+step,step),2)
    y_rescale = 0.12
    for ii in range(n+1):
        bpy.ops.object.text_add(radius=size)
        spline = bpy.context.object
        spline.data.align_y = 'CENTER'
        spline.parent = cbar_plane
        spline.location = (1.4, locs[ii], 0)
        spline.lock_location = (True, True, True)
        spline.scale = (1.7,y_rescale,1.2)
        spline.name = 'text_{0}'.format(cbar_plane.name) 
        mat = ui_material()
        try: 
            spline.data.materials.append(mat)        
        except:
            pass
        splines.append(spline)
        
    return splines

def colorbar_material(context, node, node_tree,colormap):
    materials = bpy.data.materials
    blendernc_materials = [material for material in bpy.data.materials if ''+node.name in material.name]

    if len(blendernc_materials)!=0:    
        blendernc_material = blendernc_materials[-1]
        cmap = blendernc_material.node_tree.nodes.get('Colormap')
        if cmap.colormaps == colormap.colormaps:
            return
    else:
        bpy.ops.material.new()
        blendernc_material = bpy.data.materials[-1]
        blendernc_material.name = ''+node.name

    if len(blendernc_material.node_tree.nodes.keys())==2:
        texcoord = blendernc_material.node_tree.nodes.new('ShaderNodeTexCoord')
        texcoord.location = (-760,250)
        mapping = blendernc_material.node_tree.nodes.new('ShaderNodeMapping')
        mapping.location = (-580,250)
        cmap = blendernc_material.node_tree.nodes.new('cmapsNode')
        cmap.location = (-290,250)
        emi = blendernc_material.node_tree.nodes.new('ShaderNodeEmission')
        emi.location = (-290,-50)
        P_BSDF = blendernc_material.node_tree.nodes.get('Principled BSDF')
        blendernc_material.node_tree.nodes.remove(P_BSDF)

    else:
        texcoord =  blendernc_material.node_tree.nodes.get('Texture Coordinate')
        mapping = blendernc_material.node_tree.nodes.get('Mapping')
        cmap = blendernc_material.node_tree.nodes.get('Colormap')
        emi = blendernc_material.node_tree.nodes.get('Emission')

    output = blendernc_material.node_tree.nodes.get('Material Output')

    #Lins
    blendernc_material.node_tree.links.new(mapping.inputs[0],texcoord.outputs[0])
    blendernc_material.node_tree.links.new(cmap.inputs[0],mapping.outputs[0])
    blendernc_material.node_tree.links.new(emi.inputs[0],cmap.outputs[0])
    blendernc_material.node_tree.links.new(output.inputs[0],emi.outputs[0])

    #Assign values:
    mapping.inputs['Location'].default_value=(0,-0.6,0)
    mapping.inputs['Rotation'].default_value=(0,np.pi/4,0)
    mapping.inputs['Scale'].default_value=(1,2.8,1)

    cmap.n_stops  = colormap.n_stops
    cmap.fcmap = colormap.fcmap
    cmap.colormaps = colormap.colormaps
    cmap.fv_color = colormap.fv_color

    return blendernc_material

def get_colormaps_of_materials(node):
    '''
    Function to find materials using the BlenderNC output node image.
    '''
    unfind = True
    counter = 0
    links = node.outputs.get('Color').links
    while unfind:
        for link in links:
            if link.to_node.bl_idname == 'cmapsNode':
                colormap_node = link.to_node
                unfind=False
                break
            elif counter == 10:
                unfind= False
            else:
                counter+=1

        links = [llink for llink in link.to_node.outputs.get('Color').links for link in links] 

    if counter == 10:
        raise ValueError('Colormap not found after 10 tree node interations')
    return colormap_node

def get_all_nodes_using_image(image_name):
    users = {}
    for node_group in bpy.data.node_groups:
        for node in node_group.nodes:
            if node.bl_idname == 'netCDFOutput':
                users[node_group.name] = node

    for material in bpy.data.materials:
        if not material.grease_pencil:
            for node in material.node_tree.nodes:
                if node.bl_idname == 'ShaderNodeTexImage':
                    users[material.name] = node

    return users
        
def netcdf_values(dataset,selected_variable,active_resolution,return_dataset=True):
    """
    """
    variable = dataset[selected_variable]
    max_shape = max(variable.shape)

    if variable.dims: 
        dict_var_shape = {ii:slice(0,variable[ii].size,resolution_steps(max_shape,active_resolution))
                for ii in variable.dims if ('time' not in ii and 't' != ii)}
    elif variable.coords:
        dict_var_shape = {ii:slice(0,variable[ii].size,resolution_steps(max_shape,active_resolution))
                for ii in variable.coords if ('time' not in ii and 't' != ii)}
    if return_dataset:
        variable_res = variable.isel(dict_var_shape).to_dataset()
    else:
        variable_res = variable.isel(dict_var_shape)
    return variable_res
    

def resolution_steps(size,res):
    # TODO extend the range of values.
    scaling = 10**int(np.log10(size))

    steps = np.logspace(1,size/scaling,100) - 10
    step = steps[int(100-res)]

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
    dropped_dim = [ii for ii in (old_dims + new_dims) if (old_dims + new_dims).count(ii) ==1]
    if dropped_dim:
        return dropped_dim[0]
    else:
        return node.blendernc_dims

def rotate_longitude(node,context):
    # TODO Clear cache, otherwise the transform wont be applied.
    dataset = node.blendernc_dict[node.blendernc_dataset_identifier]['Dataset']
    lon_coords = [coord for coord in dataset.coords if ('lon' in coord or 'xt' in coord or 'xu' in coord )]
    if len(lon_coords) == 1:
        node.blendernc_dict[node.blendernc_dataset_identifier]['Dataset'] = dataset.roll({lon_coords[0]: int(node.blendernc_rotation)},roll_coords=True)
    else:
        raise ValueError("Multiple lon axis are not supported. The default axis names are anything containing 'lon','xt' and 'yt'.")
    NodeTree = node.rna_type.id_data.name
    frame = bpy.context.scene.frame_current
    identifier = node.blendernc_dataset_identifier
    refresh_cache(NodeTree, identifier, frame)
    

    

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
                except RuntimeError:
                    raise ValueError("File isn't a netCDF:",self.file_path)
        else:
            extension = self.file_path[0].split('.')[-1]
            if extension == ".nc":
                self.load_netcd()
            else:
                try:
                    self.load_netcdf()
                except RuntimeError:
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


