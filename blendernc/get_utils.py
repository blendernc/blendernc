#!/usr/bin/env python3
import bpy

# Partial import to avoid cyclic import
import blendernc.python_functions as bnc_pyfunc


def get_blendernc_nodetrees():
    blendernc_nodetrees = [
        items
        for keys, items in bpy.data.node_groups.items()
        if "BlenderNC" == items.bl_label
    ]
    return blendernc_nodetrees


def get_unique_data_dict(node):
    # Replaces all node.blendernc_dict[unique_identifier]
    # TODO: Make sure to replace all the unique data dicts
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = data_dictionary[unique_identifier]
    return unique_data_dict


def get_node(node_group, node):
    node_group = bpy.data.node_groups.get(node_group)
    return node_group.nodes.get(node)


def get_input_links(node):
    inputs = node.inputs[0]
    return inputs.links[0]


def get_var(ncdata):
    dimensions = sorted(list(ncdata.coords.dims.keys()))
    variables = sorted(list(ncdata.variables.keys() - dimensions))
    if "long_name" in ncdata[variables[0]].attrs:
        long_name_list = [ncdata[var].attrs["long_name"] for var in variables]
        var_names = bnc_pyfunc.build_enum_prop_list(
            variables, "DISK_DRIVE", long_name_list
        )
    else:
        var_names = bnc_pyfunc.build_enum_prop_list(variables, "DISK_DRIVE")

    return bnc_pyfunc.select_item() + [None] + var_names


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


def get_units_data(node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the metadata of the selected variable
    var_metadata = unique_data_dict["selected_var"]
    unit = var_metadata["units"]
    return unit


def get_dims(ncdata, var):
    dimensions = list(ncdata[var].coords.dims)
    dim_names = bnc_pyfunc.build_enum_prop_list(dimensions, "EMPTY_DATA", start=0)
    return dim_names


def get_geo_coord_names(dataset):
    lon_coords = [coord for coord in dataset.coords if ("lon" in coord or "x" in coord)]
    lat_coords = [coord for coord in dataset.coords if ("lat" in coord or "y" in coord)]
    return {"lon_name": lon_coords, "lat_name": lat_coords}


def get_possible_variables(node, context):
    ncfile = node.blendernc_file
    unique_identifier = node.blendernc_dataset_identifier
    if not ncfile or unique_identifier not in node.blendernc_dict.keys():
        return bnc_pyfunc.empty_item()
    unique_data_dict = get_unique_data_dict(node)
    ncdata = unique_data_dict["Dataset"]
    items = get_var(ncdata)
    return items


def infinite_sequence():
    num = 0
    while True:
        yield num
        num += 1


def get_new_identifier(node):
    nodetrees = get_blendernc_nodetrees()
    counter = 0
    identif_list = [0]
    for nodetree in nodetrees:
        same_nodes_idname = [n for n in nodetree.nodes if n.bl_idname == node.bl_idname]
        for same_node in same_nodes_idname:
            assigned_identifiers = same_node.blendernc_dataset_identifier.split("_")[0]
            if assigned_identifiers:
                identif_list.append(int(assigned_identifiers))
            res = [
                ele
                for ele in range(1, max(identif_list) + 1)
                if ele not in identif_list
            ]
            if res:
                counter = res[0]
            else:
                counter += 1
    print(counter, node.bl_idname)
    return "{:03}".format(counter)


# TODO Add decorator to simplify.
def get_possible_dims(node, context):
    unique_identifier = node.blendernc_dataset_identifier
    if unique_identifier not in node.blendernc_dict.keys():
        return bnc_pyfunc.empty_item()
    link = get_input_links(node)
    unique_identifier = node.blendernc_dataset_identifier
    parent_node = link.from_node
    data_dictionary = parent_node.blendernc_dict[unique_identifier]
    ncdata = data_dictionary["Dataset"]
    var_name = data_dictionary["selected_var"]["selected_var_name"]
    items = get_dims(ncdata, var_name)
    return items


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
        bnc_pyfunc.update_range(node, context)
        return var_metadata["max_value"], var_metadata["min_value"]


def get_xarray_datasets(node, context):
    import xarray

    xarray_datacube = sorted(xarray.tutorial.file_formats.keys())
    datacube_names = bnc_pyfunc.build_enum_prop_list(xarray_datacube, "DISK_DRIVE")
    return bnc_pyfunc.select_datacube() + datacube_names


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


def get_items_dims(self, context):
    if self.inputs[0].is_linked and self.inputs[0].links and self.blendernc_dict:
        # BlenderNC dictionary
        blendernc_dict = (
            self.inputs[0]
            .links[0]
            .from_node.blendernc_dict[self.blendernc_dataset_identifier]
            .copy()
        )
        # BlenderNC dataset
        dataset = blendernc_dict["Dataset"]
        # BlenderNC var
        var = blendernc_dict["selected_var"]["selected_var_name"]
        # Extract dataset axis
        dims = dataset[var].dims
        return dims


def get_items_axes(self, context):
    dims = get_items_dims(self, context)
    dims_list = bnc_pyfunc.build_enum_prop_list(dims, "EMPTY_DATA", start=0)
    return dims_list


# Delete if not use in a few months (25-Jun-2021):
#
# def get_selected_var(node):
#     unique_data_dict = get_unique_data_dict(node)
#     dataset = unique_data_dict["Dataset"]
#     selected_variable = unique_data_dict["selected_var"]["selected_var_name"]
#     selected_var_dataset = dataset[selected_variable]
#     return selected_var_dataset


# def get_max_timestep(self, context):
#     scene = context.scene
#     ncfile = self.file_name
#     data_dictionary = scene.nc_dictionary
#     if not ncfile or not data_dictionary:
#         return 0
#     ncdata = data_dictionary["Dataset"]
#     var_name = self.var_name
#     var_data = ncdata[var_name]

#     t = var_data.shape[0]
#     return t - 1
