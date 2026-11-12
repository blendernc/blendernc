import logging
import os.path
from itertools import combinations
from math import prod

import bpy
import numpy as np
import xarray as xr

from .decorators import check_if_node_tree_exists, file_exists
from .node_utils import create_blenderncnodetree, create_link, delete_link


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
@file_exists
def create_datastruct(self, context):
    """Load the datacube referenced by a node into its ``BNC_data`` item.

    Used as the ``update`` callback of the datacube path properties. The node
    tree and node are resolved by the decorators, which also raise
    ``FileNotFoundError`` when the path matches no file.

    Parameters
    ----------
    self : bpy.types.Node, bpy.types.PropertyGroup or bpy.types.Operator
        Owner of the path property.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = bpy.data.node_groups.get(self.node_tree)
    filepath_string_node = node_tree.nodes.get(self.node_name)

    BNC_datastructs = filepath_string_node.BNC_datastructs[0]
    BNC_datastructs.datafile = filepath_string_node.datacube_file
    BNC_datastructs.filename = filepath_string_node.datacube_file.split("/")[-1]
    BNC_datastructs.dict[BNC_datastructs.filename] = load_dataset(
        BNC_datastructs.datafile
    )


@file_exists
def load_dataset(filepath):
    """
    Load a dataset using xarray and return the dataset object.

    Parameters:
        filepath (str): The path to the dataset file.
    """
    logging.info(f"Loading dataset from {filepath}")
    dataset = xr.open_mfdataset(filepath)
    return dataset


def name_match(block, cfname, filename):
    """Extend a glob pattern with one matching block from ``difflib``.

    Parameters
    ----------
    block : difflib.Match
        Matching block ``(a, b, size)`` between two filenames.
    cfname : str
        Pattern built so far.
    filename : str
        Filename the block indices ``a`` refer to.

    Returns
    -------
    str
        ``cfname`` extended with the matched text, preceded by ``"*"`` when a
        gap separates it from the previous block.

    Raises
    ------
    ValueError
        If the first block does not start at the beginning of both names.
    """
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
    """Build a glob pattern matching a list of similar filenames.

    Consecutive filenames are compared and the shortest common pattern is
    kept, e.g. ``["ssh_1995-01.nc", "ssh_1995-02.nc"]`` gives
    ``"ssh_1995-0*.nc"``.

    Parameters
    ----------
    filenames : list of str
        Filenames to combine.

    Returns
    -------
    str
        Glob pattern containing at least one ``"*"``.

    Raises
    ------
    ValueError
        If the names share no wildcard-able pattern or differ in extension.
    """
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
    """Describe the coordinates linked to a grid node's X, Y and Z inputs.

    Parameters
    ----------
    grid_node : DatacubeGrid
        Grid node whose linked input sockets are inspected.

    Returns
    -------
    dict
        Mapping of socket name to ``{"name": coordinate_name, "size": shape}``.
    """
    datastruct = grid_node.BNC_datastructs[0]

    coords = {}
    for socket in grid_node.inputs:
        if not socket.is_linked:
            continue

        # linked = socket.links[0].from_socket
        dataset = datastruct.dict[datastruct.filename]

        coords[socket.name] = {
            "name": socket.default_value,
            "size": return_tuple(dataset[socket.default_value].shape),
        }

    return coords


def return_tuple(value):
    """Wrap a value in a tuple unless it already is one."""
    return value if isinstance(value, tuple) else (value,)


def get_possible_variables_UI(self, context):
    """Enum items callback for the variable selector in the 3D view panel.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the enum.
    context : bpy.types.Context
        Current Blender context.

    Returns
    -------
    list of tuple
        Enum items from the "Datacube Variable" node of the ``BLENDERNC``
        tree, or a single empty item when the node or dataset is missing.
    """
    node_tree = create_blenderncnodetree("BLENDERNC")
    var_node = node_tree.nodes.get("Datacube Variable")
    if not var_node:
        return empty_item()
    items = get_possible_variables(var_node, context)
    return items


def get_possible_variables(node, context):
    """Enum items callback listing the variables of a node's dataset.

    Parameters
    ----------
    node : bpy.types.Node
        Node with a ``BNC_datastructs`` collection.
    context : bpy.types.Context
        Current Blender context (unused).

    Returns
    -------
    list of tuple
        Enum items, or a single empty item when no dataset is loaded.
    """
    datastruct = node.BNC_datastructs[0]
    if not datastruct.dict or not datastruct.filename:
        return empty_item()
    datacubedata = datastruct.dict[datastruct.filename]
    items = get_var(datacubedata)
    return items


def get_possible_coordinates_UI(self, context):
    """Enum items callback for the X, Y and Z selectors in the 3D view panel.

    The header entry is replaced by a ``"No var"`` item so the user can
    unlink an axis, and the separator is dropped.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the enum.
    context : bpy.types.Context
        Current Blender context.

    Returns
    -------
    list of tuple
        Enum items from the "Datacube Coords" node of the ``BLENDERNC`` tree.
    """
    node_tree = create_blenderncnodetree("BLENDERNC")
    coord_node = node_tree.nodes.get("Datacube Coords")
    if not coord_node:
        return empty_item()
    items = get_possible_coordinates(coord_node, context)
    items.pop(1)
    items[0] = ("No var", "", "", "CANCEL", 0)
    return items


def get_possible_coordinates(node, context):
    """Enum items callback listing the coordinates of a node's dataset.

    Parameters
    ----------
    node : bpy.types.Node
        Node with a ``BNC_datastructs`` collection.
    context : bpy.types.Context
        Current Blender context (unused).

    Returns
    -------
    list of tuple
        Enum items, or a single empty item when no dataset is loaded.
    """
    datastruct = node.BNC_datastructs[0]
    if not datastruct.dict or not datastruct.filename:
        return empty_item(text="No Coordinate")
    datacubedata = datastruct.dict[datastruct.filename]
    items = get_dims(datacubedata)
    return items


def update_variable_UI(self, context):
    """Push the variable chosen in the 3D view panel to the variable node.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the ``variable`` enum.
    context : bpy.types.Context
        Current Blender context.
    """
    scene = context.scene
    UI_props = scene.BlenderNC_UI_Properties
    node_tree = create_blenderncnodetree("BLENDERNC")
    var_node = node_tree.nodes.get("Datacube Variable")
    if not var_node:
        return
    var_node.datacube_vars = UI_props.variable


def update_coords_links_UI(self, context):
    """Link or unlink coordinate outputs to the grid node from the panel enums.

    For each of ``X``, ``Y`` and ``Z``, the selected coordinate output of the
    "Datacube Coords" node is linked to the matching grid input, or the
    existing link is removed when ``"No var"`` is selected.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the axis enums.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = create_blenderncnodetree("BLENDERNC")
    coord_node = node_tree.nodes.get("Datacube Coords")
    grid_node = node_tree.nodes.get("Datacube Grid")
    if not coord_node or not grid_node:
        return

    (
        create_link(node_tree, coord_node, grid_node, self.X, "X")
        if self.X != "No var"
        else delete_link(node_tree, coord_node, grid_node, self.X, "X")
    )
    (
        create_link(node_tree, coord_node, grid_node, self.Y, "Y")
        if self.Y != "No var"
        else delete_link(node_tree, coord_node, grid_node, self.Y, "Y")
    )
    (
        create_link(node_tree, coord_node, grid_node, self.Z, "Z")
        if self.Z != "No var"
        else delete_link(node_tree, coord_node, grid_node, self.Z, "Z")
    )


# def get_2D_coords(coords):
# expected_dims = ["X", "Y", "Z"]
# missing_dims = [dim for dim in expected_dims if dim not in coords]
# coord_dims = [dim for dim in expected_dims if dim in coords]

# if len(coord_dims) == 1:
#     raise ValueError("Only one dimension is present. Expected at least two.")
# elif len(coord_dims) == 2:
#     # Either both have to be 1D or 2D
#     x = coords[coord_dims[0]]["data"].values
#     y = coords[coord_dims[1]]["data"].values
#     if x.ndim == 1 and y.ndim == 1:
#         Y, X = np.meshgrid(y, x, indexing="ij")
#         coords[coord_dims[0]]["data"] = X
#         coords[coord_dims[1]]["data"] = Y
#         coords[missing_dims[0]] = {
#             "name": missing_dims[0],
#             "size": X.shape,
#             "data": np.zeros_like(X),
#         }
#     elif x.ndim == 2 and y.ndim == 2:
#         coords[coord_dims[0]]["data"] = x.values
#         coords[coord_dims[1]]["data"] = y.values
#         coords[missing_dims[0]] = {
#             "name": missing_dims[0],
#             "size": X.shape,
#             "data": np.zeros_like(X),
#         }
#     else:
#         raise ValueError(
#             """
#             Dimensions of the coordinates can be either 1D or 2D.
#             Mixed dimensions are not supported.
#             """
#         )
# elif len(coord_dims) == 3:
#     # Either it has to be one 2D and the rest 1D or all 2D

#     coords_ndim_1 = [
#         name for name, coord in coords.items() if coord["data"].ndim == 1
#     ]
#     coords_ndim_2 = [
#         name for name, coord in coords.items() if coord["data"].ndim == 2
#     ]
#     coords_ndim_gt2 = [
#         name for name, coord in coords.items() if coord["data"].ndim > 2
#     ]

#     if sum([len(coords_ndim_1), len(coords_ndim_2), len(coords_ndim_gt2)]) != 3:
#         raise ValueError(
#             """
#             The dimensions don't match the input coordinates.
#             Make sure your slicing is correct and that the coordinates
#             are either 1D or 2D."""
#         )

#     if len(coords_ndim_1) == 2 and len(coords_ndim_2) == 1:
#         x = coords[coords_ndim_1[0]]["data"].values
#         y = coords[coords_ndim_1[1]]["data"].values
#         Y, X = np.meshgrid(y, x, indexing="ij")
#         coords[coords_ndim_1[0]]["data"] = X
#         coords[coords_ndim_1[1]]["data"] = Y
#         coords[coords_ndim_2[0]]["data"] = coords[coords_ndim_2[0]]["data"].values
#     elif len(coords_ndim_2) == 3:
#         x = coords[coords_ndim_2[0]]["data"].values
#         y = coords[coords_ndim_2[1]]["data"].values
#         z = coords[coords_ndim_2[2]]["data"].values
#         coords[coords_ndim_2[0]]["data"] = x
#         coords[coords_ndim_2[1]]["data"] = y
#         coords[coords_ndim_2[2]]["data"] = z
#     elif len(coords_ndim_1) == 2 and len(coords_ndim_gt2) == 1:
#         logging.warning(
#             """
#             A coordinate has more than 2 dimensions.
#             The additional dimension will be animated over time.
#             """
#         )
#         x = coords[coords_ndim_1[0]]["data"].values
#         y = coords[coords_ndim_1[1]]["data"].values
#         Y, X = np.meshgrid(y, x, indexing="ij")
#         coords[coords_ndim_1[0]]["data"] = X
#         coords[coords_ndim_1[1]]["data"] = Y
#         coords[coords_ndim_gt2[0]]["animate"] = True
#         coords[coords_ndim_gt2[0]]["data"] = np.zeros_like(X)
#     elif len(coords_ndim_gt2) > 1:
#         # Implement animation over time of the grid coordinates.
#         # This is a complex task and requires additional logic
#         # to handle the animation over time. For now, we will
#         # raise an error.
#         raise ValueError("3D coordinates are not yet supported.")
#     else:
#         raise ValueError(
#             """
#             Dimensions of the coordinates can be either two
#             1D and one 2D or all 2D.
#             """
#         )
# return coords


def _meshgrid_coords(coords, x_name, y_name):
    """Replace two 1-D coordinates with their 2-D mesh grid, in place.

    Parameters
    ----------
    coords : dict
        Coordinate mapping as returned by :func:`get_coords_from_datastruct`.
    x_name, y_name : str
        Keys of the two 1-D coordinates.

    Returns
    -------
    numpy.ndarray
        The 2-D ``X`` array, useful as a shape template.
    """
    x = coords[x_name]["data"].values
    y = coords[y_name]["data"].values

    Y, X = np.meshgrid(y, x, indexing="ij")

    coords[x_name]["data"] = X
    coords[y_name]["data"] = Y

    return X


def _add_missing_coord(coords, name, template):
    """Add a zero-filled coordinate entry shaped like ``template``.

    Parameters
    ----------
    coords : dict
        Coordinate mapping to extend in place.
    name : str
        Key of the new entry (``"X"``, ``"Y"`` or ``"Z"``).
    template : numpy.ndarray
        Array whose shape the new coordinate copies.
    """
    coords[name] = {
        "name": name,
        "size": template.shape,
        "data": np.zeros_like(template),
    }


def _coords_by_ndim(coords):
    """Group coordinate names by the dimensionality of their data.

    Parameters
    ----------
    coords : dict
        Coordinate mapping with a ``"data"`` array per entry.

    Returns
    -------
    dict
        Keys ``1``, ``2`` and ``"gt2"`` mapping to lists of coordinate names.
    """
    groups = {1: [], 2: [], "gt2": []}

    for name, coord in coords.items():
        ndim = coord["data"].ndim

        if ndim == 1:
            groups[1].append(name)
        elif ndim == 2:
            groups[2].append(name)
        else:
            groups["gt2"].append(name)

    return groups


def get_2D_coords(coords):
    """Expand the grid coordinates to 2-D arrays suitable for a mesh grid.

    Parameters
    ----------
    coords : dict
        Mapping of ``"X"``, ``"Y"`` and/or ``"Z"`` to coordinate entries
        holding a ``"data"`` :class:`xarray.DataArray`.

    Returns
    -------
    dict
        ``coords`` with every entry's ``"data"`` replaced by a 2-D
        :class:`numpy.ndarray`; a missing third axis is filled with zeros.

    Raises
    ------
    ValueError
        If fewer than two axes are present or their dimensions cannot be
        combined.
    """
    expected_dims = ["X", "Y", "Z"]

    coord_dims = [dim for dim in expected_dims if dim in coords]
    missing_dims = [dim for dim in expected_dims if dim not in coords]

    if len(coord_dims) < 2:
        raise ValueError("At least two coordinates (X, Y, Z) are required.")

    if len(coord_dims) == 2:
        return _handle_two_coords(coords, coord_dims, missing_dims[0])

    return _handle_three_coords(coords)


def _handle_two_coords(coords, coord_dims, missing_dim):
    """Expand two coordinates and synthesise the missing third one.

    Parameters
    ----------
    coords : dict
        Coordinate mapping to update in place.
    coord_dims : list of str
        The two present axis keys.
    missing_dim : str
        The absent axis key, filled with zeros.

    Returns
    -------
    dict
        The updated mapping.

    Raises
    ------
    ValueError
        If one coordinate is 1-D and the other 2-D.
    """
    x_name, y_name = coord_dims

    x = coords[x_name]["data"]
    y = coords[y_name]["data"]

    if x.ndim == y.ndim == 1:
        X = _meshgrid_coords(coords, x_name, y_name)
        _add_missing_coord(coords, missing_dim, X)

    elif x.ndim == y.ndim == 2:
        coords[x_name]["data"] = x.values
        coords[y_name]["data"] = y.values
        _add_missing_coord(coords, missing_dim, x.values)

    else:
        raise ValueError("Coordinates must be either all 1D or all 2D.")

    return coords


def _get_coord_pattern(groups):
    """Return the ``(n_1d, n_2d, n_gt2d)`` counts of a dimensionality grouping."""
    return (
        len(groups[1]),
        len(groups[2]),
        len(groups["gt2"]),
    )


def _handle_2x1d_1x2d(coords, ndim_1, ndim_2, _):
    """Mesh-grid two 1-D coordinates and unwrap the single 2-D one."""
    _meshgrid_coords(coords, ndim_1[0], ndim_1[1])
    name = ndim_2[0]
    coords[name]["data"] = coords[name]["data"].values
    return coords


def _handle_3x2d(coords, _, ndim_2, __):
    """Unwrap three 2-D coordinates to plain arrays."""
    for name in ndim_2:
        coords[name]["data"] = coords[name]["data"].values
    return coords


def _handle_animation_coord(coords, ndim_1, _, ndim_gt2):
    """Mesh-grid two 1-D coordinates and mark the higher-dimensional one.

    The coordinate with more than two dimensions is flagged with
    ``"animate": True`` and replaced by zeros so it can be animated later.
    """
    logging.warning(
        "A coordinate has more than 2 dimensions. "
        "The additional dimension will be animated over time."
    )

    X = _meshgrid_coords(coords, ndim_1[0], ndim_1[1])

    name = ndim_gt2[0]
    coords[name]["animate"] = True
    coords[name]["data"] = np.zeros_like(X)

    return coords


def _handle_three_coords(coords):
    """Dispatch three coordinates to the handler matching their dimensions.

    Parameters
    ----------
    coords : dict
        Coordinate mapping with ``"X"``, ``"Y"`` and ``"Z"`` entries.

    Returns
    -------
    dict
        The updated mapping.

    Raises
    ------
    ValueError
        If the combination of dimensions is not supported.
    """
    groups = _coords_by_ndim(coords)
    pattern = _get_coord_pattern(groups)

    match pattern:
        case (2, 1, 0):
            return _handle_2x1d_1x2d(coords, groups[1], groups[2], groups["gt2"])
        case (0, 3, 0):
            return _handle_3x2d(coords, groups[1], groups[2], groups["gt2"])
        case (2, 0, 1):
            return _handle_animation_coord(coords, groups[1], groups[2], groups["gt2"])
        case (_, _, n) if n > 1:
            raise ValueError("3D coordinates are not yet supported.")
        case _:
            raise ValueError(
                "Expected either two 1D and one 2D coordinate "
                "or three 2D coordinates."
            )


def stack_2D_coords(coords):
    """Flatten X, Y and Z arrays into the layout expected by ``foreach_set``.

    Parameters
    ----------
    coords : dict
        Mapping with 2-D ``"data"`` arrays under ``"X"``, ``"Y"`` and ``"Z"``.

    Returns
    -------
    numpy.ndarray
        1-D array of interleaved ``(x, y, z)`` triplets, one per vertex.
    """
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
    """Get or create a Geometry Nodes modifier backed by a tree of the same name.

    Parameters
    ----------
    obj : bpy.types.Object
        Object receiving the modifier.
    modifier_name : str
        Name of the modifier and of its geometry node group.

    Returns
    -------
    tuple
        ``(modifier, nodetree)``.
    """
    if modifier_name in obj.modifiers:
        modifier = obj.modifiers.get(modifier_name)
    else:
        modifier = obj.modifiers.new(name=modifier_name, type="NODES")

    nodetree = create_blenderncnodetree(modifier_name, "GeometryNodeTree")

    modifier.node_group = nodetree

    return modifier, nodetree


def extract_dimensions_of_grid(grid_coords):
    """Pick the two vertex counts for the Mesh Grid node.

    Sizes with more than two dimensions or of length one are ignored. With
    two remaining coordinates their first dimensions are used; with more, the
    2-D surface coordinates are preferred.

    Parameters
    ----------
    grid_coords : dict
        Mapping as returned by :func:`get_grid_coords`.

    Returns
    -------
    tuple of int
        ``(size1, size2)``.

    Raises
    ------
    ValueError
        If fewer than two usable dimensions are found.
    """
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
    """Build enum items for the data variables of a dataset.

    Coordinates are excluded. When the variables carry a ``long_name``
    attribute it is used as the item description.

    Parameters
    ----------
    datacubedata : xarray.Dataset
        Dataset to list variables from.
    str_filter : list of str, optional
        Substrings used to keep only matching variable names, by default
        ``None`` (no filtering).

    Returns
    -------
    list of tuple
        A header item, a separator (``None``) and one item per variable.
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
    """Build ``EnumProperty`` item tuples from a list of names.

    Parameters
    ----------
    list : list of str
        Identifiers, also used as display names.
    icon : str, optional
        Icon identifier for every item, by default ``"NONE"``.
    long_name_list : list of str, optional
        Descriptions, one per item. When omitted the name is reused.
    start : int, optional
        Number assigned to the first item, by default 1.

    Returns
    -------
    list of tuple
        ``(identifier, name, description, icon, number)`` tuples.
    """
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
    """Keep the items that contain any of the filter substrings.

    Parameters
    ----------
    list : list of str
        Candidate strings.
    str_filter : list of str
        Lower-case substrings to look for.

    Returns
    -------
    list of str
        Matching items, in filter order; an item may appear more than once.
    """
    tmp_list = []
    for strfit in str_filter:
        for item in list:
            if strfit in item.lower() and "" in item.lower().split(strfit):
                tmp_list.append(item)
    return tmp_list


def select_item(text="Select variable"):
    """Return the placeholder enum item shown before a selection is made."""
    return [("No var", text, "Empty", "NODE_SEL", 0)]


def empty_item(text="No variable"):
    """Return the enum item shown when nothing can be selected."""
    return [("No var", text, "Empty", "CANCEL", 0)]


def find_coord_matches(length, dims):
    """Find the coordinate combinations whose total size equals ``length``.

    Parameters
    ----------
    length : int
        Target size, typically the vertex count of a mesh.
    dims : dict
        Mapping of coordinate name to its shape (tuple) or size (int).

    Returns
    -------
    numpy.ndarray
        Squeezed array of matching name combinations.
    """
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
