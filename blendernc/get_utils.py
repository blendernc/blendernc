#!/usr/bin/env python3
import bpy

import blendernc.core.update_ui as bnc_updateUI

# Partial import to avoid cyclic import
import blendernc.python_functions as bnc_pyfunc
from blendernc.translations import translate


def get_blendernc_nodetrees():
    blendernc_nodetrees = [
        node_group
        for node_group in bpy.data.node_groups
        if "BlenderNC" == node_group.bl_label
    ]
    return blendernc_nodetrees


def get_all_output_nodes():
    nodes = []
    node_trees = get_blendernc_nodetrees()

    # Find all nodes
    for nt in node_trees:
        [nodes.append(node) for node in nt.nodes if node.name == translate("Output")]
    return nodes


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


def get_var(datacubedata):
    dimensions = sorted(list(datacubedata.coords.dims.keys()))
    variables = sorted(list(datacubedata.variables.keys() - dimensions))
    if "long_name" in datacubedata[variables[0]].attrs:
        long_name_list = [datacubedata[var].attrs["long_name"] for var in variables]
        var_names = bnc_pyfunc.build_enum_prop_list(
            variables, "DISK_DRIVE", long_name_list
        )
    else:
        var_names = bnc_pyfunc.build_enum_prop_list(variables, "DISK_DRIVE")

    return bnc_pyfunc.select_item() + [None] + var_names


def get_var_dict(node):
    scene = bpy.context.scene
    node_tree = node.rna_type.id_data.name
    unique_identifier = node.blendernc_dataset_identifier
    try:
        scene.datacube_cache[node_tree]
    except KeyError:
        scene.datacube_cache[node_tree] = {}

    # Check if dictionary entry for the variable exists
    try:
        scene.datacube_cache[node_tree][unique_identifier]
    except KeyError:
        scene.datacube_cache[node_tree][unique_identifier] = {}
    return scene.datacube_cache[node_tree][unique_identifier]


def get_var_data(node):
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the datacube of the selected file
    datacubedata = unique_data_dict["Dataset"]
    # Get var name
    var_name = unique_data_dict["selected_var"]["selected_var_name"]
    # Get the data of the selected variable
    # Remove Nans
    # TODO: Add node to preserve NANs
    # if node.keep_nan:
    data = datacubedata[var_name]
    # else:
    # data = datacubedata[var_name].where(np.isfinite(datacubedata[var_name]), 0)
    return data


def get_units_data(node, node_tree):
    node = bpy.data.node_groups[node_tree].nodes[node]
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the metadata of the selected variable
    var_metadata = unique_data_dict["selected_var"]
    unit = var_metadata["units"]
    return unit


def get_dims(datacubedata, var):
    dimensions = list(datacubedata[var].coords.dims)
    dim_names = bnc_pyfunc.build_enum_prop_list(dimensions, "EMPTY_DATA", start=0)
    return dim_names


def get_coord(coords, geo_coord_name):
    if "lon" in geo_coord_name[0].lower():
        geo_coord_name.append("x")
    elif "lat" in geo_coord_name[0].lower():
        geo_coord_name.append("y")
    return [
        coord
        for coord in coords
        if (geo_coord_name[0] in coord or geo_coord_name[1] in coord)
    ]


def get_geo_coord_names(dataset):
    lon_coords = get_coord(dataset.coords, ["lon"])
    lat_coords = get_coord(dataset.coords, ["lat"])
    return {"lon_name": lon_coords, "lat_name": lat_coords}


def get_possible_variables(node, context):
    datacubefile = node.blendernc_file
    unique_identifier = node.blendernc_dataset_identifier
    if not datacubefile or unique_identifier not in node.blendernc_dict.keys():
        return bnc_pyfunc.empty_item()
    unique_data_dict = get_unique_data_dict(node)
    datacubedata = unique_data_dict["Dataset"]
    items = get_var(datacubedata)
    return items


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
    datacubedata = data_dictionary["Dataset"]
    var_name = data_dictionary["selected_var"]["selected_var_name"]
    items = get_dims(datacubedata, var_name)
    return items


def get_time(node, frame):
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the datacube of the selected file
    datacubedata = unique_data_dict["Dataset"]
    # Get the data of the selected variable
    if "time" in datacubedata.coords.keys():
        time = datacubedata["time"]
        if time.size == 1:
            return time.values
        elif frame > time.size:
            return time[-1].values
        else:
            return time[frame].values
    else:
        return ""


def get_max_min_data(node):
    context = bpy.context
    # Get data dictionary stored at scene object
    unique_data_dict = get_unique_data_dict(node)
    # Get the metadata of the selected variable
    var_metadata = unique_data_dict["selected_var"]
    max_val = var_metadata["max_value"]
    min_val = var_metadata["min_value"]
    if max_val is not None and min_val is not None:
        return var_metadata["max_value"], var_metadata["min_value"]
    else:
        bnc_updateUI.update_range(node, context)
        return var_metadata["max_value"], var_metadata["min_value"]


def get_xarray_datasets(node, context):
    import xarray

    xarray_datacube = sorted(xarray.tutorial.file_formats.keys())
    datacube_names = bnc_pyfunc.build_enum_prop_list(xarray_datacube, "DISK_DRIVE")
    return bnc_pyfunc.select_datacube() + datacube_names


def search(ID):
    def users(col):
        ret = tuple(repr(o) for o in col if o.user_of_id(ID))
        return ret if ret else None

    return filter(None, (users(getattr(bpy.data, p)) for p in dir(bpy.data)))


def get_colormaps_of_materials(node, image):
    """
    Function to find materials using the BlenderNC output node image.
    """
    nodetree = node.id_data

    colormap_nodes = [node for node in nodetree.nodes if "Colormap" in node.name]

    if not colormap_nodes:
        raise ValueError("Colormap not found after 10 tree node interations")
    elif len(colormap_nodes) == 1:
        colormap_node = colormap_nodes[0]
    else:
        cmap_links = get_material_links(colormap_nodes)

        colormap_name = get_colormap_connected_to_image(cmap_links, image)

        colormap_node = nodetree.nodes.get(next(iter(colormap_name)))

    if not colormap_node:
        raise ValueError("Colormap not found after 10 tree node interations")
    return colormap_node


def get_material_links(nodes):
    links = {node.name: node.inputs[0].links for node in nodes}
    return links


def get_colormap_connected_to_image(cmap_links, image):
    colormap_name = None
    connected_nodes = {
        key: links[0].from_node for key, links in cmap_links.items() if links
    }
    count = 0
    while not colormap_name or count > 10:
        node_with_image = {
            key: connection
            for key, connection in connected_nodes.items()
            if hasattr(connection, "image")
        }
        colormap_name = {
            key: node.name
            for key, node in node_with_image.items()
            if node.image == image
        }

        upstream_links = {
            key: get_material_links([links[0].from_node])
            for key, links in cmap_links.items()
            if links
        }

        connected_nodes = {
            key: items[next(iter(items))] for key, items in upstream_links.items()
        }
        count += 1

    return colormap_name


def get_all_materials_using_image(image):
    return [material for material in bpy.data.materials if material.user_of_id(image)]


def get_all_nodes_using_image(materials, image):
    users = {}
    for material in materials:
        user_nodes = [
            node
            for node in material.node_tree.nodes
            if translate("Image Texture") in node.name
        ]
        users = [user for user in user_nodes if user.image == image]
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


def get_default_material():
    blendernc_materials = [
        material
        for material in bpy.data.materials
        if ("BlenderNC_default" in material.name and "Colormap" not in material.name)
    ]
    if len(blendernc_materials) != 0:
        blendernc_material = blendernc_materials[-1]
    else:
        bpy.ops.material.new()
        blendernc_material = bpy.data.materials[-1]
        blendernc_material.name = "BlenderNC_default"

    return blendernc_material


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
#     datacubefile = self.file_name
#     data_dictionary = scene.blendernc_dict
#     if not datacubefile or not data_dictionary:
#         return 0
#     datacubedata = data_dictionary["Dataset"]
#     var_name = self.var_name
#     var_data = datacubedata[var_name]

#     t = var_data.shape[0]
#     return t - 1
