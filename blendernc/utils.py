import glob
import logging
import os.path
from itertools import combinations
from math import prod

import bpy
import numpy as np
import xarray as xr

from .decorators import check_if_node_tree_exists
from .node_utils import create_geometrynodetree


def get_datacube_path(directory, files):
    """
    Get the datacube path based on the provided directory and files.

    Parameters:
        directory (str): The directory where the files are located.
        files (list): A list of file names.
    """
    if len(files) == 1:
        datacube_path = os.path.join(directory, files[0].name)
    else:
        filenames = [f.name for f in files]
        common_name = findCommonName(filenames)
        datacube_path = os.path.join(directory, common_name)
    return datacube_path


@check_if_node_tree_exists
def create_datastruct(self, context):
    node_tree = bpy.data.node_groups.get(self.node_tree)
    filepath_string_node = node_tree.nodes.get(self.node_name)

    BNC_datastructs = filepath_string_node.BNC_datastructs[0]
    BNC_datastructs.datafile = filepath_string_node.datacube_file
    BNC_datastructs.filename = filepath_string_node.datacube_file.split("/")[-1]
    BNC_datastructs.dict[BNC_datastructs.filename] = load_dataset(
        BNC_datastructs.datafile
    )


def load_dataset(filepath):
    """
    Load a dataset using xarray and return the dataset object.

    Parameters:
        filepath (str): The path to the dataset file.
    """
    logging.info(f"Loading dataset from {filepath}")
    if glob.glob(filepath):
        dataset = xr.open_mfdataset(filepath)
    else:
        raise NameError(f"File {filepath} does not exist")
    return dataset


def name_match(block, cfname, filename):
    if not cfname and (block.a != 0 or block.b != 0):
        raise ValueError("Start of filename strings do not match.")
    elif block.a == block.b and block.size != 0:
        if len(cfname) != 0 and len(cfname) != block.a:
            cfname += "*"
        cfname += filename[block.a : block.a + block.size]
    elif cfname or block.a != block.b:
        pass
    return cfname


def findCommonName(filenames):
    import difflib

    cfname = []
    fcounter = 0
    while len(filenames) - 1 > fcounter:
        S = difflib.SequenceMatcher(None, filenames[fcounter], filenames[fcounter + 1])
        cname = ""
        for block in S.get_matching_blocks():
            cname = name_match(block, cname, filenames[fcounter])
        cfname.append(cname)
        fcounter += 1
    commonName = min(cfname, key=len)
    if "*" not in commonName:
        raise ValueError("Filenames do not match")
    if commonName[-1] == ".":
        raise ValueError("Filenames formats do not match")
    return commonName


def get_grid_coords(grid_node):
    datastruct = grid_node.BNC_datastructs[0]

    coords = {}
    for socket in grid_node.inputs:
        if not socket.is_linked:
            continue

        linked = socket.links[0].from_socket
        dataset = datastruct.dict[datastruct.filename]

        coords[socket.name] = {
            "name": socket.default_value,
            "size": return_tuple(dataset[socket.default_value].shape),
        }

    return coords


def return_tuple(value):
    return value if isinstance(value, tuple) else (value,)


def get_possible_variables(node, context):
    datastruct = node.BNC_datastructs[0]
    if not datastruct.dict or not datastruct.filename:
        return empty_item()
    datacubedata = datastruct.dict[datastruct.filename]
    items = get_var(datacubedata)
    return items


def get_possible_coordinates(node, context):
    datastruct = node.BNC_datastructs[0]
    if not datastruct.dict or not datastruct.filename:
        return empty_item(text="No Coordinate")
    datacubedata = datastruct.dict[datastruct.filename]
    items = get_dims(datacubedata)
    return items


def get_2D_coords(coords):
    expected_dims = ["X", "Y", "Z"]
    missing_dims = [dim for dim in expected_dims if dim not in coords]
    coord_dims = [dim for dim in expected_dims if dim in coords]

    if len(coord_dims) == 1:
        raise ValueError("Only one dimension is present. Expected at least two.")
    elif len(coord_dims) == 2:
        # Either both have to be 1D or 2D
        x = coords[coord_dims[0]]["data"].values
        y = coords[coord_dims[1]]["data"].values
        if x.ndim == 1 and y.ndim == 1:
            Y, X = np.meshgrid(y, x, indexing="ij")
            coords[coord_dims[0]]["data"] = X
            coords[coord_dims[1]]["data"] = Y
            coords[missing_dims[0]] = {
                "name": missing_dims[0],
                "size": X.shape,
                "data": np.zeros_like(X),
            }
        elif x.ndim == 2 and y.ndim == 2:
            coords[coord_dims[0]]["data"] = x.values
            coords[coord_dims[1]]["data"] = y.values
            coords[missing_dims[0]] = {
                "name": missing_dims[0],
                "size": X.shape,
                "data": np.zeros_like(X),
            }
        else:
            raise ValueError(
                "Dimensions of the coordinates can be either 1D or 2D. Mixed dimensions are not supported."
            )
    elif len(coord_dims) == 3:
        # Either it has to be one 2D and the rest 1D or all 2D

        coords_ndim_1 = [
            name for name, coord in coords.items() if coord["data"].ndim == 1
        ]
        coords_ndim_2 = [
            name for name, coord in coords.items() if coord["data"].ndim == 2
        ]
        coords_ndim_gt2 = [
            name for name, coord in coords.items() if coord["data"].ndim > 2
        ]

        if sum([len(coords_ndim_1), len(coords_ndim_2), len(coords_ndim_gt2)]) != 3:
            raise ValueError(
                "The dimensions don't match the input coordinates, make sure your slicing is correct and that the coordinates are either 1D or 2D."
            )

        if len(coords_ndim_1) == 2 and len(coords_ndim_2) == 1:
            x = coords[coords_ndim_1[0]]["data"].values
            y = coords[coords_ndim_1[1]]["data"].values
            Y, X = np.meshgrid(y, x, indexing="ij")
            coords[coords_ndim_1[0]]["data"] = X
            coords[coords_ndim_1[1]]["data"] = Y
            coords[coords_ndim_2[0]]["data"] = coords[coords_ndim_2[0]]["data"].values
        elif len(coords_ndim_2) == 3:
            x = coords[coords_ndim_2[0]]["data"].values
            y = coords[coords_ndim_2[1]]["data"].values
            z = coords[coords_ndim_2[2]]["data"].values
            coords[coords_ndim_2[0]]["data"] = x
            coords[coords_ndim_2[1]]["data"] = y
            coords[coords_ndim_2[2]]["data"] = z
        elif len(coords_ndim_1) == 2 and len(coords_ndim_gt2) == 1:
            logging.warning(
                f"A coordinate has more than 2 dimensions. The additional dimension will be animated over time."
            )
            x = coords[coords_ndim_1[0]]["data"].values
            y = coords[coords_ndim_1[1]]["data"].values
            Y, X = np.meshgrid(y, x, indexing="ij")
            coords[coords_ndim_1[0]]["data"] = X
            coords[coords_ndim_1[1]]["data"] = Y
            coords[coords_ndim_gt2[0]]["animate"] = True
            coords[coords_ndim_gt2[0]]["data"] = np.zeros_like(X)
        elif len(coords_ndim_gt2) > 1:
            # Implement animation over time of the grid coordinates. This is a complex task and requires additional logic to handle the animation over time. For now, we will raise an error.
            raise ValueError("3D coordinates are not yet supported.")
        else:
            raise ValueError(
                "Dimensions of the coordinates can be either two 1D and one 2D or all 2D"
            )
    return coords


def stack_2D_coords(coords):
    X = coords.get("X")["data"]
    Y = coords.get("Y")["data"]
    Z = coords.get("Z")["data"]

    flatten_coords = np.stack([X, Y, Z], axis=0).transpose(2, 1, 0).flatten()

    return flatten_coords


def add_attribute(mesh, attr_name, type="FLOAT", domain="POINT"):
    """Add a custom attribute to a mesh object."""
    attr = None
    if mesh and mesh.id_type == "MESH":
        if attr_name not in mesh.attributes:
            attr = mesh.attributes.new(name=attr_name, type=type, domain=domain)
        else:
            attr = mesh.attributes.get(attr_name)
    return attr


def look_up_object_and_mesh(object_name):
    """
    Look up an object in the current Blender context by name.

    Parameters:
        object_name (str): The name of the object to look up.
    """
    if object_name in bpy.data.meshes:
        mesh = bpy.data.meshes.get(object_name)
        obj = bpy.data.objects.get(object_name)
    else:
        mesh = bpy.data.meshes.new(object_name)
        obj = bpy.data.objects.new(object_name, mesh)
        bpy.context.collection.objects.link(obj)
    return obj, mesh


def assign_modifier_to_object(obj, modifier_name):
    if modifier_name in obj.modifiers:
        modifier = obj.modifiers.get(modifier_name)
    else:
        modifier = obj.modifiers.new(name=modifier_name, type="NODES")

    nodetree = create_geometrynodetree(modifier_name)

    modifier.node_group = nodetree

    return modifier, nodetree


def extract_dimensions_of_grid(grid_coords):
    # Extract the dimensions of the grid based on the provided grid coordinates.
    sizes = {name: grid_coords.get(name).get("size") for name in grid_coords.keys()}
    # Filter out dimensions with size greater than 2 and different from (1,)
    dims = {
        name: size for name, size in sizes.items() if len(size) <= 2 and size != (1,)
    }
    if len(dims) == 2:
        size1 = dims.get(list(dims.keys())[0])[0]
        size2 = dims.get(list(dims.keys())[1])[0]
    elif len(dims) > 2:
        surface_dims = {name: size for name, size in dims.items() if len(size) == 2}
        if surface_dims == dims:
            size1 = dims.get(list(dims.keys())[0])[0]
            size2 = dims.get(list(dims.keys())[1])[1]
        else:
            key2ignore = surface_dims.keys()
            key = [key for key in dims.keys() if key not in key2ignore]
            size1 = dims.get(list(key[0]))[0]
            size2 = dims.get(list(key[1]))[0]
    else:
        raise ValueError("Not enough dimensions with size <= 2 found.")
    return size1, size2


def get_data_from_datastruct(datastruct, var_name):
    """
    Get data from the datastruct for a given variable name.

    Parameters:
        datastruct: The datastruct containing the dataset.
        var_name (str): The name of the variable to retrieve data for.
    """
    dataset = datastruct.dict[datastruct.filename]
    if datastruct.slicing != "":
        slicing = datastruct.slicing.split(",")
        slicing = [s.split("_") for s in slicing if var_name in s]
        select_dict = {select[1]: int(select[2]) for select in slicing}
    else:
        select_dict = {}
    return dataset[var_name].isel(select_dict).fillna(0)


def get_coords_from_datastruct(datastruct, grid_coords):
    """
    Get coordinates from the datastruct for a given dimension.

    Parameters:
        datastruct: The datastruct containing the dataset.
        grid_coords: The grid coordinates containing dimension information.
    """
    for coords in grid_coords.keys():
        coord_name = grid_coords[coords].get("name")
        data = get_data_from_datastruct(datastruct, coord_name)
        grid_coords[coords]["data"] = data
    return grid_coords


def get_dims(datacubedata):
    """
    Get the dimensions of the datacube data.

    Parameters:
        datacubedata: The datacube data object.
    """
    dimensions = sorted(list(datacubedata.coords.keys()))
    dimensions_names = build_enum_prop_list(dimensions, "DISK_DRIVE")
    return select_item("Select coordinate") + [None] + dimensions_names


def get_var(datacubedata, str_filter=None):
    """
    get_var _summary_

    Parameters
    ----------
    datacubedata : _type_
        _description_
    str_filter : List, optional
        _description_, by default None

    Returns
    -------
    _type_
        _description_
    """
    dimensions = sorted(list(datacubedata.coords.keys()))
    variables = sorted(list(datacubedata.variables.keys() - dimensions))

    if str_filter is not None:
        variables = filter_2_string_lists(variables, str_filter)

    if "long_name" in datacubedata[variables[0]].attrs:
        long_name_list = [
            (
                datacubedata[var].attrs["long_name"]
                if "long_name" in datacubedata[var].attrs
                else ""
            )
            for var in variables
        ]
        var_names = build_enum_prop_list(variables, "DISK_DRIVE", long_name_list)
    else:
        var_names = build_enum_prop_list(variables, "DISK_DRIVE")
    return select_item() + [None] + var_names


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


def filter_2_string_lists(list, str_filter):
    tmp_list = []
    for strfit in str_filter:
        for item in list:
            if strfit in item.lower() and "" in item.lower().split(strfit):
                tmp_list.append(item)
    return tmp_list


def select_item(text="Select variable"):
    return [("No var", text, "Empty", "NODE_SEL", 0)]


def empty_item(text="No variable"):
    return [("No var", text, "Empty", "CANCEL", 0)]


def find_coord_matches(length, dims):
    sizes = {
        name: prod(shape) if isinstance(shape, tuple) else shape
        for name, shape in dims.items()
    }

    matches = []

    for r in range(1, len(sizes) + 1):
        for combo in combinations(sizes, r):
            if prod(sizes[name] for name in combo) == length:
                matches.append(combo)

    return np.squeeze(matches)
