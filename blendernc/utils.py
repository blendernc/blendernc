import difflib
import logging
import os.path
import re
from itertools import combinations
from math import prod

import bpy
import numpy as np
import xarray as xr

from .decorators import check_if_node_tree_exists, file_exists
from .node_utils import create_blenderncnodetree, create_link, delete_link

logger = logging.getLogger(__name__)

# Identifier of the enum entry that means "nothing selected".
NO_SELECTION = "No var"

# Node tree and node labels driven by the 3D view panel.
UI_NODE_TREE = "BLENDERNC"
UI_VARIABLE_NODE = "Datacube Variable"
UI_COORDS_NODE = "Datacube Coords"
UI_GRID_NODE = "Datacube Grid"

# Encoding of the ``BNC_data.slicing`` string: ``"<var>|<coord>|<spec>,"``.
SLICING_RECORD_SEP = ","
SLICING_FIELD_SEP = "|"
SLICING_ANY_VARIABLE = "*"

# Names that mark a horizontal dimension. ``lon``/``lat`` anywhere in the
# name; ``x``/``y`` only as a token, optionally with one trailing letter so
# that ``xc``, ``xu``, ``xi_rho`` and ``y_rho`` match but ``index`` does not.
SURFACE_DIM_PATTERNS = (
    re.compile(r"lon"),
    re.compile(r"lat"),
    re.compile(r"(^|[^a-z])x[a-z]?([^a-z]|$)"),
    re.compile(r"(^|[^a-z])y[a-z]?([^a-z]|$)"),
)


# --------------------------------------------------------------------------
# Loading datasets
# --------------------------------------------------------------------------


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
        common_name = find_common_name(filenames)
        datacube_path = os.path.join(directory, common_name)
    return datacube_path


@file_exists
def load_dataset(filepath):
    """
    Load a dataset using xarray and return the dataset object.

    Parameters:
        filepath (str): The path to the dataset file.
    """
    logger.info(f"Loading dataset from {filepath}")
    dataset = xr.open_mfdataset(filepath)
    return dataset


def store_dataset(datastruct, path):
    """Load ``path`` and register it on a ``BNC_data`` item.

    Parameters
    ----------
    datastruct : BNC_data
        Data item that will reference the dataset.
    path : str
        File path or glob pattern accepted by :func:`load_dataset`.
    """
    datastruct.datafile = path
    datastruct.filename = os.path.basename(path)
    datastruct.dict[datastruct.filename] = load_dataset(path)


def get_dataset(datastruct):
    """Return the dataset cached for a ``BNC_data`` item, or ``None``.

    Parameters
    ----------
    datastruct : BNC_data
        Data item to read.

    Returns
    -------
    xarray.Dataset or None
        ``None`` when no file is registered or the cache has no entry.
    """
    if not datastruct.dict or not datastruct.filename:
        return None
    return datastruct.dict.get(datastruct.filename)


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
    node = node_tree.nodes.get(self.node_name)
    store_dataset(node.BNC_datastructs[0], node.datacube_file)


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


def find_common_name(filenames):
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


# --------------------------------------------------------------------------
# Enum items
# --------------------------------------------------------------------------


def _placeholder_item(text, icon):
    """Return a single-entry enum list whose identifier is ``NO_SELECTION``."""
    return [(NO_SELECTION, text, "Empty", icon, 0)]


def select_item(text="Select variable"):
    """Return the placeholder enum item shown before a selection is made."""
    return _placeholder_item(text, "NODE_SEL")


def empty_item(text="No variable"):
    """Return the enum item shown when nothing can be selected."""
    return _placeholder_item(text, "CANCEL")


def _with_header(items, text):
    """Prepend a header entry and a separator to a list of enum items."""
    return select_item(text) + [None] + items


def build_enum_prop_list(names, icon="NONE", long_name_list=None, start=1):
    """Build ``EnumProperty`` item tuples from a list of names.

    Parameters
    ----------
    names : list of str
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
    descriptions = long_name_list or names
    return [
        (str(name), str(name), str(description), icon, number)
        for number, (name, description) in enumerate(zip(names, descriptions), start)
    ]


def _coordinate_names(dataset):
    """Sorted coordinate names of a dataset."""
    return sorted(dataset.coords.keys())


def get_dims(datacubedata):
    """Build enum items for the coordinates of a dataset.

    Parameters
    ----------
    datacubedata : xarray.Dataset
        Dataset to list coordinates from.

    Returns
    -------
    list of tuple
        A header item, a separator (``None``) and one item per coordinate.
    """
    names = _coordinate_names(datacubedata)
    return _with_header(build_enum_prop_list(names, "DISK_DRIVE"), "Select coordinate")


def get_var(datacubedata):
    """Build enum items for the data variables of a dataset.

    Coordinates are excluded. A variable's ``long_name`` attribute is used as
    the item description when present, otherwise its name.

    Parameters
    ----------
    datacubedata : xarray.Dataset
        Dataset to list variables from.

    Returns
    -------
    list of tuple
        A header item, a separator (``None``) and one item per variable.
    """
    coordinates = _coordinate_names(datacubedata)
    variables = sorted(datacubedata.variables.keys() - coordinates)
    descriptions = [datacubedata[var].attrs.get("long_name", var) for var in variables]
    items = build_enum_prop_list(variables, "DISK_DRIVE", descriptions)
    return _with_header(items, "Select variable")


def _enum_items(node, builder, empty_text):
    """Build enum items from a node's dataset, or a placeholder without one."""
    dataset = get_dataset(node.BNC_datastructs[0])
    if dataset is None:
        return empty_item(empty_text)
    return builder(dataset)


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
    return _enum_items(node, get_var, "No variable")


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
    return _enum_items(node, get_dims, "No Coordinate")


# --------------------------------------------------------------------------
# 3D view panel callbacks
# --------------------------------------------------------------------------


def _get_ui_node(label):
    """Return the node called ``label`` in the panel's node tree, or ``None``."""
    node_tree = create_blenderncnodetree(UI_NODE_TREE)
    return node_tree.nodes.get(label)


def _enum_items_UI(label, items_callback, context):
    """Delegate an enum items callback to a node of the panel's node tree."""
    node = _get_ui_node(label)
    if not node:
        return empty_item()
    return items_callback(node, context)


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
    return _enum_items_UI(UI_VARIABLE_NODE, get_possible_variables, context)


def get_possible_coordinates_UI(self, context):
    """Enum items callback for the X, Y and Z selectors in the 3D view panel.

    The header entry is replaced by a ``NO_SELECTION`` item so the user can
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
    items = _enum_items_UI(UI_COORDS_NODE, get_possible_coordinates, context)
    if len(items) > 1 and items[1] is None:
        items.pop(1)
    items[0] = _placeholder_item("", "CANCEL")[0]
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
    var_node = _get_ui_node(UI_VARIABLE_NODE)
    if var_node:
        var_node.datacube_vars = context.scene.BlenderNC_UI_Properties.variable


def update_coords_links_UI(self, context):
    """Link or unlink coordinate outputs to the grid node from the panel enums.

    For each of ``X``, ``Y`` and ``Z``, the selected coordinate output of the
    "Datacube Coords" node is linked to the matching grid input, or the
    existing link is removed when ``NO_SELECTION`` is selected.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the axis enums.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = create_blenderncnodetree(UI_NODE_TREE)
    coord_node = node_tree.nodes.get(UI_COORDS_NODE)
    grid_node = node_tree.nodes.get(UI_GRID_NODE)
    if not coord_node or not grid_node:
        return

    for axis in ("X", "Y", "Z"):
        selected = getattr(self, axis)
        action = delete_link if selected == NO_SELECTION else create_link
        action(node_tree, coord_node, grid_node, selected, axis)


# --------------------------------------------------------------------------
# Slicing records
# --------------------------------------------------------------------------


def encode_slicing_record(var_name, coord, selector):
    """Encode one ``slicing`` record as ``"<var>|<coord>|<spec>,"``.

    Parameters
    ----------
    var_name : str
        Variable the record applies to, or ``SLICING_ANY_VARIABLE`` for every
        array that has the dimension (coordinates included).
    coord : str
        Dimension or coordinate name.
    selector : int or slice
        Index to pick, or stride to apply. ``slice(0, None, 2)`` is stored as
        ``"0::2"``; ``None`` bounds are left empty.

    Returns
    -------
    str
        The record, including its trailing separator.
    """
    if isinstance(selector, slice):
        bounds = (selector.start, selector.stop, selector.step)
        spec = ":".join("" if b is None else str(b) for b in bounds)
    else:
        spec = str(int(selector))
    return SLICING_FIELD_SEP.join((var_name, coord, spec)) + SLICING_RECORD_SEP


def _record_stride(datastruct, dims, step):
    """Append one wildcard stride record per dimension to ``slicing``."""
    for dim in dims:
        datastruct.slicing += encode_slicing_record(
            SLICING_ANY_VARIABLE, dim, slice(0, None, step)
        )


def _decode_selector(spec):
    """Turn ``"i"`` into ``int`` and ``"start:stop:step"`` into ``slice``."""
    if ":" not in spec:
        return int(spec)
    parts = [int(p) if p else None for p in spec.split(":")]
    parts += [None] * (3 - len(parts))
    return slice(*parts[:3])


def parse_slicing(slicing, var_name):
    """Collect the selectors in ``slicing`` that apply to ``var_name``.

    Later records override earlier ones for the same coordinate.

    Returns
    -------
    dict
        Mapping of dimension or coordinate name to ``int`` or ``slice``.
    """
    indexers = {}
    for record in filter(None, slicing.split(SLICING_RECORD_SEP)):
        fields = record.split(SLICING_FIELD_SEP)
        if len(fields) != 3:
            logger.warning(f"Ignoring malformed slicing record {record!r}")
            continue
        target, coord, spec = fields
        if target in (var_name, SLICING_ANY_VARIABLE):
            indexers[coord] = _decode_selector(spec)
    return indexers


def _dims_for_key(dataset, key):
    """Dimensions a slicing key refers to: itself, or those of a coordinate."""
    if key in dataset.dims:
        return (key,)
    if key in dataset.coords:
        return dataset[key].dims
    return ()


def build_indexers(dataset, data, slicing, var_name):
    """Map the slicing records for ``var_name`` onto the dims ``data`` has.

    Parameters
    ----------
    dataset : xarray.Dataset
        Dataset used to resolve coordinate names to dimensions.
    data : xarray.DataArray
        Array the indexers will be applied to.
    slicing : str
        Encoded ``slicing`` string of a ``BNC_data`` item.
    var_name : str
        Name of ``data`` inside ``dataset``.

    Returns
    -------
    dict
        Mapping of dimension name to ``int`` or ``slice`` for ``isel``.
    """
    selectors = parse_slicing(slicing, var_name)
    return {
        dim: selector
        for key, selector in selectors.items()
        for dim in _dims_for_key(dataset, key)
        if dim in data.dims
    }


def get_data_from_datastruct(datastruct, var_name):
    """Return ``var_name`` from the cached dataset with its slicing applied.

    Records may name a dimension directly or a coordinate; a coordinate is
    resolved to the dimensions it spans, so a 2-D coordinate strides both.
    Selections on dimensions the array does not have are ignored, which is
    what lets wildcard records apply safely to coordinates.
    """
    dataset = get_dataset(datastruct)
    data = dataset[var_name]
    indexers = build_indexers(dataset, data, datastruct.slicing, var_name)
    return data.isel(indexers).fillna(0)


# --------------------------------------------------------------------------
# Surface dimensions
# --------------------------------------------------------------------------


def is_surface_name(name):
    """Return ``True`` when ``name`` looks like a horizontal dimension."""
    lowered = name.lower()
    return any(pattern.search(lowered) for pattern in SURFACE_DIM_PATTERNS)


def get_surface_dims(dataset):
    """Dimensions that span the horizontal surface of a dataset.

    A dimension qualifies when its name matches ``SURFACE_DIM_PATTERNS`` or
    when any 2-D coordinate is defined over it.

    Parameters
    ----------
    dataset : xarray.Dataset
        Dataset to inspect.

    Returns
    -------
    list of str
        Surface dimension names in dataset order.
    """
    surface = {dim for dim in dataset.dims if is_surface_name(dim)}
    for coord in dataset.coords.values():
        if coord.ndim == 2:
            surface.update(coord.dims)
    order = list(dataset.dims)
    return sorted(surface, key=order.index)


# --------------------------------------------------------------------------
# Grid coordinates
# --------------------------------------------------------------------------


def get_grid_coords(grid_node):
    """Describe the coordinates linked to a grid node's X, Y and Z inputs.

    Sizes and data are both taken from the lazily sliced arrays, so the Mesh
    Grid vertex counts always match the coordinate values written to the
    mesh, whatever ``slicing`` records are active.

    Parameters
    ----------
    grid_node : DatacubeGrid
        Grid node whose linked input sockets are inspected.

    Returns
    -------
    dict
        Mapping of socket name to
        ``{"name": coordinate_name, "size": shape, "data": DataArray}``.
    """
    datastruct = grid_node.BNC_datastructs[0]

    coords = {}
    for socket in grid_node.inputs:
        if not socket.is_linked:
            continue
        data = get_data_from_datastruct(datastruct, socket.default_value)
        coords[socket.name] = {
            "name": socket.default_value,
            "size": data.shape,
            "data": data,
        }

    return coords


def _unwrap(coords, *names):
    """Replace the ``"data"`` DataArray of each named entry by its values."""
    for name in names:
        coords[name]["data"] = coords[name]["data"].values


def _meshgrid_coords(coords, x_name, y_name):
    """Replace two 1-D coordinates with their 2-D mesh grid, in place.

    Parameters
    ----------
    coords : dict
        Coordinate mapping as returned by :func:`get_grid_coords`.
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
        groups[ndim if ndim in (1, 2) else "gt2"].append(name)
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
        template = _meshgrid_coords(coords, x_name, y_name)
    elif x.ndim == y.ndim == 2:
        _unwrap(coords, x_name, y_name)
        template = coords[x_name]["data"]
    else:
        raise ValueError("Coordinates must be either all 1D or all 2D.")

    _add_missing_coord(coords, missing_dim, template)
    return coords


def _handle_2x1d_1x2d(coords, groups):
    """Mesh-grid two 1-D coordinates and unwrap the single 2-D one."""
    _meshgrid_coords(coords, *groups[1])
    _unwrap(coords, *groups[2])
    return coords


def _handle_3x2d(coords, groups):
    """Unwrap three 2-D coordinates to plain arrays."""
    _unwrap(coords, *groups[2])
    return coords


def _handle_animation_coord(coords, groups):
    """Mesh-grid two 1-D coordinates and mark the higher-dimensional one.

    The coordinate with more than two dimensions is flagged with
    ``"animate": True`` and replaced by zeros so it can be animated later.
    """
    logger.warning(
        "A coordinate has more than 2 dimensions. "
        "The additional dimension will be animated over time."
    )

    X = _meshgrid_coords(coords, *groups[1])

    name = groups["gt2"][0]
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
    pattern = (len(groups[1]), len(groups[2]), len(groups["gt2"]))

    match pattern:
        case (2, 1, 0):
            return _handle_2x1d_1x2d(coords, groups)
        case (0, 3, 0):
            return _handle_3x2d(coords, groups)
        case (2, 0, 1):
            return _handle_animation_coord(coords, groups)
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
    dims = {
        name: coord["size"]
        for name, coord in grid_coords.items()
        if len(coord["size"]) <= 2 and coord["size"] != (1,)
    }
    if len(dims) < 2:
        raise ValueError("Not enough dimensions with size <= 2 found.")

    surface_dims = {name: size for name, size in dims.items() if len(size) == 2}
    if len(dims) > 2 and surface_dims != dims:
        # Mixed 1-D and 2-D coordinates: the 1-D ones define the grid.
        sizes = [size for name, size in dims.items() if name not in surface_dims]
        return sizes[0][0], sizes[1][0]

    first, second = list(dims.values())[:2]
    second_index = 1 if len(dims) > 2 else 0
    return first[0], second[second_index]


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


# --------------------------------------------------------------------------
# Blender objects
# --------------------------------------------------------------------------


def add_attribute(mesh, attr_name, attr_type="FLOAT", domain="POINT"):
    """Add a custom attribute to a mesh object.

    Parameters
    ----------
    mesh : bpy.types.Mesh
        Mesh receiving the attribute.
    attr_name : str
        Attribute name.
    attr_type : str, optional
        Blender attribute data type, by default ``"FLOAT"``.
    domain : str, optional
        Attribute domain, by default ``"POINT"``.

    Returns
    -------
    bpy.types.Attribute or None
        The existing or new attribute, or ``None`` if ``mesh`` is not a mesh.
    """
    attr = None
    if mesh and mesh.id_type == "MESH":
        if attr_name not in mesh.attributes:
            attr = mesh.attributes.new(name=attr_name, type=attr_type, domain=domain)
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
