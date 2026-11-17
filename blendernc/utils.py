import difflib
import logging
import os.path
import re
from functools import wraps
from itertools import combinations
from math import ceil, prod

import bpy
import numpy as np
import xarray as xr

from .decorators import check_if_node_tree_exists
from .messages import report_error
from .node_utils import (
    UI_NODE_TREE,
    create_blenderncnodetree,
    create_link,
    delete_link,
    get_all_nodes_by_idname,
)
from .panels_draw import draw_resolution_grid_and_texture, show_section

logger = logging.getLogger(__name__)

# Identifier of the enum entry that means "nothing selected".
NO_SELECTION = "No var"

# Up to this many variables, a Datacube Variable node has one output per
# variable; with more, a drop-down and a single output.
MAX_VARIABLE_OUTPUTS = 10

# Node labels in the 3D view panel's tree (``UI_NODE_TREE``).
UI_VARIABLE_NODE = "Datacube Variable"
UI_COORDS_NODE = "Datacube Coords"
UI_GRID_NODE = "Datacube Grid"
UI_TEXTURE_NODE = "Datacube Texture"
UI_STEP_NODE = "Datacube Resolution"

# Nodes that write a variable onto a mesh as a point attribute; both offer
# "Apply Material" and store the field range on the mesh.
TEXTURE_NODE_IDNAMES = ("BlenderNCNodeTexture", "BlenderNCNodeAnimateTexture")

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


# xarray engine by file extension; anything else is left to xarray to detect.
DATASET_ENGINES = {
    ".zarr": "zarr",
    ".grib": "cfgrib",
    ".grib2": "cfgrib",
    ".grb": "cfgrib",
    ".grb2": "cfgrib",
}


def dataset_engine(path):
    """Return the xarray engine for ``path``, or ``None`` to let xarray choose."""
    extension = os.path.splitext(path.rstrip("/\\"))[1].lower()
    return DATASET_ENGINES.get(extension)


def dataset_key(path):
    """Cache key for ``path``: the absolute, normalised path or pattern.

    Two files with the same name in different folders get different keys.
    """
    return os.path.normcase(os.path.abspath(path))


def load_dataset(filepath):
    """Open a file, Zarr store or glob pattern with xarray.

    Parameters
    ----------
    filepath : str
        Path or pattern accepted by :func:`xarray.open_mfdataset`. GRIB and
        Zarr inputs get their engine from :func:`dataset_engine`.

    Returns
    -------
    xarray.Dataset

    Raises
    ------
    OSError
        If nothing matches ``filepath`` or a file cannot be read.
    ValueError
        If no xarray backend understands the file.
    """
    engine = dataset_engine(filepath)
    logger.info(f"Loading dataset from {filepath} (engine: {engine or 'auto'})")
    kwargs = {"engine": engine} if engine else {}
    return xr.open_mfdataset(filepath, **kwargs)


def dataset_in_use(key, ignore=None):
    """True when an import node other than ``ignore`` references ``key``."""
    skip = ignore.as_pointer() if ignore is not None else None
    for node in get_all_nodes_by_idname("BlenderNCNodeImport"):
        if node.as_pointer() == skip or not len(node.BNC_datastructs):
            continue
        if node.BNC_datastructs[0].filename == key:
            return True
    return False


def release_dataset(datastruct, key, ignore=None):
    """Close and drop the cached dataset ``key`` once no import node uses it.

    Parameters
    ----------
    datastruct : BNC_data
        Any data item; only its shared ``dict`` cache is used.
    key : str
        Cache key, as stored in ``BNC_data.filename``.
    ignore : bpy.types.Node, optional
        Import node to leave out of the search, typically the one being
        deleted.
    """
    if not key or dataset_in_use(key, ignore):
        return
    dataset = datastruct.dict.pop(key, None)
    if dataset is not None:
        dataset.close()
        logger.info(f"Closed {key}")


def store_dataset(datastruct, path):
    """Load ``path`` and register it on a ``BNC_data`` item.

    The cache is keyed by :func:`dataset_key`, so an already open dataset is
    shared instead of opened twice, and the dataset the item held before is
    released when nothing else uses it. On failure the item keeps
    ``datafile`` so the path is not retried on every node update, but
    ``filename`` is cleared so downstream nodes see no dataset.

    Parameters
    ----------
    datastruct : BNC_data
        Data item that will reference the dataset.
    path : str
        File path or glob pattern accepted by :func:`load_dataset`.

    Returns
    -------
    bool
        ``True`` when the dataset is available on the item.
    """
    if datastruct.datafile == path and get_dataset(datastruct) is not None:
        return True
    previous, key = datastruct.filename, dataset_key(path)
    datastruct.datafile = path
    dataset = _open_cached(datastruct, path, key)
    datastruct.filename = key if dataset is not None else ""
    if datastruct.filename != previous:
        release_dataset(datastruct, previous)
    return dataset is not None


def _open_cached(datastruct, path, key):
    """Return the cached dataset ``key``, opening ``path`` on a miss.

    Returns ``None`` after reporting when the file cannot be opened; a broken
    ``cfgrib`` install raises ``RuntimeError`` or ``ImportError``.
    """
    if key in datastruct.dict:
        return datastruct.dict[key]
    try:
        dataset = load_dataset(path)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        report_error(None, f"Could not open {path}: {exc}")
        return None
    datastruct.dict[key] = dataset
    return dataset


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
def create_datastruct(self, context):
    """Load the datacube referenced by a node into its ``BNC_data`` item.

    Used as the ``update`` callback of the datacube path properties. The node
    tree and node are resolved by the decorator. A path that cannot be
    opened is logged by :func:`store_dataset`; an update callback has no
    way to report to the user. Once another dataset is loaded, the nodes
    after this one are updated, so their outputs show the new dataset; a
    path that failed leaves them, and their links, as they were.

    Parameters
    ----------
    self : bpy.types.Node, bpy.types.PropertyGroup or bpy.types.Operator
        Owner of the path property.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = bpy.data.node_groups.get(self.node_tree)
    node = node_tree.nodes.get(self.node_name)
    datastruct = node.BNC_datastructs[0]
    previous = datastruct.filename
    store_dataset(datastruct, node.datacube_file)
    if datastruct.filename and datastruct.filename != previous:
        node.refresh_downstream()


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


def variable_names(dataset):
    """Sorted names of the data variables of a dataset, coordinates excluded."""
    return sorted(str(name) for name in dataset.data_vars)


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
    variables = variable_names(datacubedata)
    descriptions = [datacubedata[var].attrs.get("long_name", var) for var in variables]
    items = build_enum_prop_list(variables, "DISK_DRIVE", descriptions)
    return _with_header(items, "Select variable")


# Blender only borrows the strings an EnumProperty ``items`` callback
# returns: Python must keep them referenced, or the drop-down can show
# garbage or crash. The last list per callback and owner is kept here.
_ENUM_ITEMS = {}


def keep_enum_items(callback):
    """Keep the list returned by an enum ``items`` callback referenced."""

    @wraps(callback)
    def wrapper(owner, context):
        """Run the callback and store its result under the owner."""
        items = callback(owner, context)
        owner_id = owner.as_pointer() if hasattr(owner, "as_pointer") else id(owner)
        _ENUM_ITEMS[(callback.__name__, owner_id)] = items
        return items

    return wrapper


def _enum_items(node, builder, empty_text):
    """Build enum items from a node's dataset, or a placeholder without one."""
    dataset = get_dataset(node.BNC_datastructs[0])
    if dataset is None:
        return empty_item(empty_text)
    return builder(dataset)


@keep_enum_items
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


@keep_enum_items
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


@keep_enum_items
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


@keep_enum_items
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
    # Copy: the node's own list is kept alive and must not be edited.
    items = list(_enum_items_UI(UI_COORDS_NODE, get_possible_coordinates, context))
    if len(items) > 1 and items[1] is None:
        items.pop(1)
    items[0] = _placeholder_item("", "CANCEL")[0]
    return items


def update_variable_UI(self, context):
    """Link the variable chosen in the 3D view panel to the texture node.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the ``variable`` enum.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = bpy.data.node_groups.get(UI_NODE_TREE)
    if node_tree is None or node_tree.nodes.get(UI_VARIABLE_NODE) is None:
        return
    sync_texture_section(self, node_tree)


# A grid needs at least two axes (see get_2D_coords).
MIN_GRID_AXES = 2


def _enough_axes(UI_props):
    """True when the panel has enough axes selected to bake a grid."""
    axes = [getattr(UI_props, axis) for axis in ("X", "Y", "Z")]
    selected_axes = [axis for axis in axes if axis and axis != NO_SELECTION]
    return len(selected_axes) >= MIN_GRID_AXES


def sync_texture_section(UI_props, node_tree):
    """Show the resolution/texture section and wire the texture when ready.

    The section, the grid bake and the texture links only make sense once
    both a variable and the coordinates are chosen; otherwise the section is
    hidden and the texture node is unlinked. Called from both the variable
    and the coordinate selectors, since either may be chosen last. The grid
    is only baked when its coordinates or step changed: picking another
    variable relinks the texture and swaps the material, the mesh stays.
    The texture is linked to the variable node's output carrying the chosen
    variable (see :meth:`blendernc.nodes.DatacubeVariable.pick`).
    """
    var_node = node_tree.nodes.get(UI_VARIABLE_NODE)
    grid_node = node_tree.nodes.get(UI_GRID_NODE)
    texture_node = node_tree.nodes.get(UI_TEXTURE_NODE)
    if var_node is None:
        return
    variable_output = var_node.pick(UI_props.variable)
    ready = variable_output is not None and _enough_axes(UI_props)
    show_section(draw_resolution_grid_and_texture, ready)
    if grid_node is None or texture_node is None:
        return
    if not ready:
        delete_link(node_tree, var_node, texture_node, "Variable")
        delete_link(node_tree, grid_node, texture_node, "Object")
        return
    _bake_ui_grid(node_tree, grid_node)
    create_link(node_tree, grid_node, texture_node, "Object", "Object")
    create_link(node_tree, var_node, texture_node, variable_output.name, "Variable")
    _follow_variable_material(grid_node)


def _bake_ui_grid(node_tree, grid_node):
    """Bake the panel's grid when its coordinates or step changed.

    A failed bake has already been reported and logged by the operator,
    which ``bpy.ops`` turns into a ``RuntimeError``; it must not escape the
    property callback that called this.
    """
    if not any(socket.is_linked for socket in grid_node.inputs):
        return
    if not grid_node.needs_bake():
        return
    try:
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid_node.name, node_tree=node_tree.name
        )
    except RuntimeError:
        pass


def _follow_variable_material(grid_node):
    """Give the panel's grid the material of the variable now linked.

    A bake does this through the Set Material node; without a bake the
    first material slot is set here instead: the material named after the
    texture's variable, as made by "Apply Material", or none.
    """
    obj = bpy.data.objects.get(grid_node.baked_object)
    if obj is not None and obj.type == "MESH":
        assign_material(obj.data, grid_material(grid_node))


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
        if selected == NO_SELECTION:
            delete_link(node_tree, coord_node, grid_node, axis)
        else:
            create_link(node_tree, coord_node, grid_node, selected, axis)
    sync_texture_section(self, node_tree)


def update_step_UI(self, context):
    """Push the step typed in the panel to the resolution node.

    Typing a step is a manual choice, so the node's ``suggested_step`` is
    switched off before the value is pushed. The new slicing travels down the
    tree and a grid that was already baked rebakes itself.
    """
    node_tree = bpy.data.node_groups.get(UI_NODE_TREE)
    step_node = node_tree.nodes.get(UI_STEP_NODE) if node_tree else None
    if step_node is None or step_node.step == self.step:
        return
    # Step first: while the suggestion is on, writing it is a no-op, and
    # switching the suggestion off then copies this value back to the panel.
    step_node.step = self.step
    step_node.suggested_step = False


def update_suggested_step(node, context):
    """Callback for a resolution node's ``suggested_step`` toggle.

    Turning the suggestion off keeps the suggested value: the panel's own
    ``step`` is set to the node's current step, instead of showing its default
    (2), which on a large dataset could ask for far more vertices than Blender
    can handle. ``update_step_UI`` sees equal values and does nothing.
    """
    node.update()
    in_panel_tree = node.id_data.name == UI_NODE_TREE and node.name == UI_STEP_NODE
    if node.suggested_step or not in_panel_tree:
        return
    UI_props = bpy.context.scene.BlenderNC_UI_Properties
    if UI_props.step != node.step:
        UI_props.step = node.step


# --------------------------------------------------------------------------
# Slicing records
# --------------------------------------------------------------------------


# Largest number of samples a surface dimension keeps with the suggested stride.
MAX_VERTEX_SAMPLES = 1000


def suggested_stride(sizes):
    """Smallest stride keeping every surface dimension within the sample budget.

    Parameters
    ----------
    sizes : list of int
        Sizes of the surface dimensions.

    Returns
    -------
    int
        ``ceil(min(sizes) / MAX_VERTEX_SAMPLES)``, at least 1.
    """
    if not sizes:
        return 1
    return max(1, ceil(min(sizes) / MAX_VERTEX_SAMPLES))


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


def _record_stride(datastruct, dims, step, dataset=None):
    """Append one wildcard stride record per dimension to ``slicing``.

    A step of 1 keeps every sample, so nothing is recorded. With
    ``dataset``, a range already recorded on a dimension is kept.
    """
    if step <= 1:
        return
    for dim in dims:
        record_selector(datastruct, dataset, dim, slice(0, None, step))


def _merge_selector(previous, selector):
    """Combine ``selector`` with the one recorded before it on the same dims.

    A range (``start:stop``) and a stride (``0::step``) are independent, so
    a new range keeps an earlier stride and a new stride keeps an earlier
    range. Anything else, an index in particular, replaces what was there.
    """
    if not (isinstance(previous, slice) and isinstance(selector, slice)):
        return selector
    if selector.step is None:  # a range
        return slice(selector.start, selector.stop, previous.step)
    if not selector.start and selector.stop is None:  # a stride
        return slice(previous.start, previous.stop, selector.step)
    return selector


def recorded_selector(dataset, slicing, var_name, key):
    """Return the selector ``slicing`` holds for the dimensions of ``key``.

    Records may name the dimension or a coordinate on it, so they are
    compared by the dimensions they resolve to. ``None`` when there is none.
    """
    dims = _dims_for_key(dataset, key) if dataset is not None else (key,)
    if not dims:
        return None
    found = None
    for other, selector in parse_slicing(slicing, var_name).items():
        other_dims = _dims_for_key(dataset, other) if dataset is not None else (other,)
        if other_dims == dims:
            found = selector
    return found


def record_selector(datastruct, dataset, key, selector, var_name=SLICING_ANY_VARIABLE):
    """Append a wildcard ``slicing`` record for ``key`` to a data item.

    The selector is merged with the one already recorded on the same
    dimensions (see :func:`_merge_selector`), so a Slice range and a
    Subsample or Resolution stride combine whatever their order.

    Parameters
    ----------
    datastruct : BNC_data
        Data item whose ``slicing`` grows.
    dataset : xarray.Dataset or None
        Dataset resolving coordinate names to dimensions; without it only
        records with the same name are merged.
    key : str
        Dimension or coordinate name.
    selector : int or slice
        Index, range or stride.
    var_name : str, optional
        Variable whose records are merged with, by default every variable.
    """
    previous = recorded_selector(dataset, datastruct.slicing, var_name, key)
    datastruct.slicing += encode_slicing_record(
        SLICING_ANY_VARIABLE, key, _merge_selector(previous, selector)
    )


def clamp_index_range(size, first, last):
    """Return ``(first, last)`` clamped to ``0 .. size - 1`` and in order."""
    first, last = sorted((min(first, size - 1), min(last, size - 1)))
    return max(first, 0), max(last, 0)


def value_index_range(values, low, high):
    """First and last position of the ``values`` within ``[low, high]``.

    Node properties hold single-precision floats, so the bounds are widened
    by a relative tolerance that absorbs their rounding.

    Parameters
    ----------
    values : numpy.ndarray
        1-D numeric coordinate values, normally monotonic.
    low, high : float
        Bounds, in either order.

    Returns
    -------
    tuple of int or None
        ``(first, last)``, or ``None`` when no value is in range.
    """
    values = np.asarray(values, dtype=np.float64)
    low, high = sorted((low, high))
    tolerance = 1e-6 * max(abs(low), abs(high))
    inside = np.flatnonzero((values >= low - tolerance) & (values <= high + tolerance))
    if inside.size == 0:
        return None
    return int(inside[0]), int(inside[-1])


def format_coord_value(value):
    """Short text for one coordinate value: dates to the second, numbers to 6 digits."""
    if np.issubdtype(np.asarray(value).dtype, np.datetime64):
        return str(np.datetime64(value, "s"))
    if np.issubdtype(np.asarray(value).dtype, np.number):
        return f"{float(value):.6g}"
    return str(value)


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


def get_data_from_datastruct(datastruct, var_name, fill=True):
    """Return ``var_name`` from the cached dataset with its slicing applied.

    Records may name a dimension directly or a coordinate; a coordinate is
    resolved to the dimensions it spans, so a 2-D coordinate strides both.
    Selections on dimensions the array does not have are ignored, which is
    what lets wildcard records apply safely to coordinates.

    With ``fill`` (the default) missing values become 0, which mesh
    coordinates need; pass ``fill=False`` to keep NaN for statistics.
    """
    dataset = get_dataset(datastruct)
    data = dataset[var_name]
    indexers = build_indexers(dataset, data, datastruct.slicing, var_name)
    data = data.isel(indexers)
    return data.fillna(0) if fill else data


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


def grid_dims(coords):
    """Return the ``(rows, columns)`` dimensions of the grid, or ``None``.

    Two 1-D coordinates give ``(y_dim, x_dim)``, the layout of their mesh
    grid; otherwise the dimensions of the first 2-D coordinate are used.

    Parameters
    ----------
    coords : dict
        Mapping as returned by :func:`get_grid_coords`, still holding
        :class:`xarray.DataArray` objects.
    """
    arrays = [coords[k]["data"] for k in ("X", "Y", "Z") if k in coords]
    if len(arrays) < 2 or not all(hasattr(a, "dims") for a in arrays):
        return None
    first, second = arrays[:2]
    if first.ndim == 1 and second.ndim == 1:
        return (second.dims[0], first.dims[0])
    return next((tuple(a.dims) for a in arrays if a.ndim == 2), None)


def _align_to_grid(coords, dims):
    """Transpose every 2-D array spanning ``dims`` into ``dims`` order."""
    for coord in coords.values():
        data = coord["data"]
        if hasattr(data, "dims") and data.ndim == 2 and set(data.dims) == set(dims):
            coord["data"] = data.transpose(*dims)
            coord["size"] = coord["data"].shape


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
    dims = grid_dims(coords)
    if dims:
        # A variable stored as (x, y) must land on the same vertices as one
        # stored as (y, x), so every 2-D array follows the grid's order.
        _align_to_grid(coords, dims)

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


def extract_dimensions_of_grid(coords):
    """Return ``(vertices_x, vertices_y)`` for the Mesh Grid node.

    Takes the coordinates after :func:`get_2D_coords`, where X, Y and Z are
    2-D arrays of shape ``(rows, columns)``. :func:`stack_2D_coords` emits
    the vertices column by column, which is the order Mesh Grid uses along
    its X axis, so ``vertices_x`` is the number of columns.

    Parameters
    ----------
    coords : dict
        Mapping with 2-D ``"data"`` arrays under ``"X"``, ``"Y"`` and ``"Z"``.

    Returns
    -------
    tuple of int
        ``(columns, rows)``.

    Raises
    ------
    ValueError
        If the arrays do not share one 2-D shape.
    """
    shapes = {name: coord["data"].shape for name, coord in coords.items()}
    unique = set(shapes.values())
    if len(unique) != 1 or len(next(iter(unique))) != 2:
        listed = ", ".join(f"{name} {shape}" for name, shape in shapes.items())
        raise ValueError(f"X, Y and Z do not form one 2D grid: {listed}.")
    rows, columns = unique.pop()
    return columns, rows


def find_coord_matches(length, dims):
    """Find the dimension combinations whose total size equals ``length``.

    Parameters
    ----------
    length : int
        Target size, typically the vertex count of a mesh.
    dims : dict
        Mapping of dimension name to its shape (tuple) or size (int).

    Returns
    -------
    list of tuple of str
        Matching name combinations, shortest first. Empty when none matches.
    """
    sizes = {
        name: prod(shape) if isinstance(shape, tuple) else shape
        for name, shape in dims.items()
    }

    return [
        combo
        for r in range(1, len(sizes) + 1)
        for combo in combinations(sizes, r)
        if prod(sizes[name] for name in combo) == length
    ]


# --------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------

# Advice given when a variable has too many dimensions to be written onto a
# mesh as a static texture, keyed by its number of dimensions. Anything
# above four falls back to the four-dimensional hint.
TEXTURE_DIM_HINTS = {
    3: (
        "Use a Datacube Animate Texture node to animate the extra dimension,"
        " or a Datacube Volume node."
    ),
    4: "Use a Datacube Select node to pick a slice first.",
}


# Mesh custom property recording the (rows, columns) dimensions of a grid.
GRID_DIMS_PROPERTY = "BlenderNC grid dims"


def mesh_grid_dims(mesh):
    """Return the ``(rows, columns)`` dims ``mesh`` was baked on, or ``None``."""
    value = mesh.get(GRID_DIMS_PROPERTY) if mesh is not None else None
    return tuple(value.split(",")) if value else None


def field_to_point_values(data, dims=None):
    """Flatten a 2-D field into the vertex order of a baked grid.

    Parameters
    ----------
    data : xarray.DataArray
        Two-dimensional array whose dimensions span the mesh.
    dims : tuple of str, optional
        ``(rows, columns)`` dimensions the grid was baked with (see
        :func:`mesh_grid_dims`). When ``data`` has the same dimensions in
        another order it is transposed first, so ``(x, y)`` and ``(y, x)``
        fields land on the same vertices.

    Returns
    -------
    numpy.ndarray
        1-D ``float32`` array with one value per vertex. Missing values stay
        NaN; :func:`write_point_attribute` zeroes them when writing.
    """
    if dims and set(dims) == set(data.dims):
        data = data.transpose(*dims)
    return np.ascontiguousarray(data.values.transpose(1, 0).ravel(), dtype=np.float32)


def write_point_attribute(mesh, name, values):
    """Store ``values`` in a float point attribute of ``mesh`` called ``name``.

    Parameters
    ----------
    mesh : bpy.types.Mesh
        Mesh receiving the attribute.
    name : str
        Attribute name, usually the variable name.
    values : numpy.ndarray
        One value per vertex, in mesh order.

    Returns
    -------
    bpy.types.Attribute
        The attribute that was written.
    """
    attr = add_attribute(mesh, name, attr_type="FLOAT", domain="POINT")
    # A contiguous float32 array matches the attribute storage, so
    # ``foreach_set`` copies the buffer instead of converting item by item.
    attr.data.foreach_set("value", np.nan_to_num(values, nan=0.0))
    return attr


# Custom properties on the mesh that hold the range of the written field.
RANGE_PROPERTIES = ("Min value", "Max value")


def field_range(values):
    """Return ``(min, max)`` of the finite values, or ``(0.0, 0.0)`` if none.

    One pass over an array that is already in memory; sampling would be
    slower to set up than the reduction itself.
    """
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0, 0.0
    return float(finite.min()), float(finite.max())


def write_field_range(mesh, values, locked=False):
    """Store the range of ``values`` as custom properties of ``mesh``.

    Shaders read ``mesh["Min value"]`` and ``mesh["Max value"]`` to map the
    attribute onto a colour ramp.

    Parameters
    ----------
    mesh : bpy.types.Mesh
        Mesh receiving the properties.
    values : numpy.ndarray
        Field written onto the mesh.
    locked : bool, optional
        Keep a range that is already stored, so the colour scale stays fixed
        while the field changes (see :func:`range_locked`). A mesh without a
        range always gets one.
    """
    if locked and all(key in mesh for key in RANGE_PROPERTIES):
        return
    for key, value in zip(RANGE_PROPERTIES, field_range(values)):
        mesh[key] = value


def range_locked():
    """Return the scene's "Lock range" setting, ``False`` when unavailable."""
    settings = getattr(bpy.context.scene, "BlenderNC_Settings", None)
    return bool(settings and settings.lock_range)


def update_lock_range(self, context):
    """Recompute the stored ranges as soon as the lock is released."""
    if self.lock_range:
        return
    for idname in TEXTURE_NODE_IDNAMES:
        for node in list(get_all_nodes_by_idname(idname)):
            node.update()


def delete_point_attribute(mesh, name):
    """Delete a point attribute from a mesh.

    Parameters
    ----------
    mesh : bpy.types.Mesh
        Mesh from which to delete the attribute.
    name : str
        Name of the attribute to delete.

    Returns
    -------
    bool
        True if the attribute was found and deleted, False otherwise.
    """
    if name in mesh.attributes:
        mesh.attributes.remove(mesh.attributes[name])
        return True
    return False


def texture_field(datastruct, obj, variable):
    """Return the 2-D field to write onto ``obj``, or why there is none.

    Parameters
    ----------
    datastruct : BNC_data
        Data item of the texture node.
    obj : bpy.types.Object
        Object linked to the node.
    variable : str
        Variable linked to the node.

    Returns
    -------
    tuple
        ``(data, "")`` when ``variable`` is a 2-D field with one value per
        vertex of ``obj``, otherwise ``(None, message)`` with the message
        from :func:`texture_field_error` or a shorter one for a non-mesh
        object or an unknown variable.
    """
    if obj.type != "MESH":
        return None, f"{obj.name} is not a mesh.\nLink a baked Datacube Grid."
    dataset = get_dataset(datastruct)
    if dataset is None or variable not in dataset:
        return None, f"{variable} is not in the datacube."
    data = get_data_from_datastruct(datastruct, variable, fill=False)
    error = texture_field_error(data, obj.data)
    return (None, error) if error else (data, "")


def animated_field(datastruct, obj, variable):
    """Return the 3-D field to animate over ``obj``, or why there is none.

    Parameters
    ----------
    datastruct : BNC_data
        Data item of the animate texture node.
    obj : bpy.types.Object
        Object linked to the node.
    variable : str
        Variable linked to the node.

    Returns
    -------
    tuple
        ``(data, dim, "")`` when ``variable`` is a 3-D field whose other two
        dimensions span the vertices of ``obj``, ``dim`` being the dimension
        spread over frames; otherwise ``(None, None, message)``.
    """
    if obj.type != "MESH":
        return None, None, f"{obj.name} is not a mesh.\nLink a baked Datacube Grid."
    dataset = get_dataset(datastruct)
    if dataset is None or variable not in dataset:
        return None, None, f"{variable} is not in the datacube."
    data = get_data_from_datastruct(datastruct, variable, fill=False)
    dim, error = animated_field_error(data, obj.data)
    return (None, None, error) if error else (data, dim, "")


# Advice for a variable an animate texture node cannot animate, keyed by its
# number of dimensions, four and more sharing one entry.
ANIMATED_DIM_HINTS = {
    2: "Use a Datacube Texture node for a 2D field.",
    4: "Use a Datacube Select node to pick a slice first.",
}


def animated_field_error(data, mesh):
    """Find the dimension of ``data`` to animate over ``mesh``, or say why not.

    Returns
    -------
    tuple
        ``(dim, "")``, or ``(None, message)`` with two lines: what is wrong,
        then what to do about it.
    """
    ndim = len(data.dims)
    dims = ", ".join(str(dim) for dim in data.dims)
    if ndim != 3:
        hint = ANIMATED_DIM_HINTS.get(min(ndim, 4), "An animation needs a 3D field.")
        return None, f"{data.name} is {ndim}D ({dims}).\n{hint}"
    dim = animation_dim(data, mesh)
    if dim is None:
        return None, (
            f"No two dimensions of {data.name} ({dims}) match the mesh's "
            f"{len(mesh.vertices)} vertices.\n"
            "Bake the grid from the coordinates of this variable."
        )
    return dim, ""


def animation_dim(data, mesh):
    """The dimension of a 3-D ``data`` to spread over frames on ``mesh``.

    The other two must span the mesh: the dimensions the grid was baked on
    when it recorded them, otherwise the first pair whose sizes multiply to
    the vertex count. ``None`` when no pair does.
    """
    pairs = [
        set(pair)
        for pair in combinations(data.dims, 2)
        if prod(data.sizes[dim] for dim in pair) == len(mesh.vertices)
    ]
    baked = set(mesh_grid_dims(mesh) or ())
    grid = baked if baked in pairs else next(iter(pairs), None)
    if grid is None:
        return None
    return next(dim for dim in data.dims if dim not in grid)


def animation_frame(data, dim, frame):
    """The 2-D field of ``data`` shown at scene frame ``frame``.

    Frame 0 shows the first step along ``dim``; frames past the last step
    hold it, and negative frames hold the first.
    """
    return data.isel({dim: min(max(frame, 0), data.sizes[dim] - 1)})


def texture_field_error(data, mesh):
    """Explain why ``data`` cannot be written onto ``mesh`` as a 2-D texture.

    Only dimensions are counted, so an index picked with a Datacube Select
    node, which xarray keeps as a scalar coordinate, does not add to the
    total.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing already applied.
    mesh : bpy.types.Mesh
        Mesh the field would be written onto.

    Returns
    -------
    str
        Empty when the field is 2-D and has one value per vertex. Otherwise
        two lines: what is wrong, then what to do about it.
    """
    ndim = len(data.dims)
    dims = ", ".join(str(dim) for dim in data.dims)
    problem = f"{data.name} is {ndim}D ({dims})."
    if ndim == 2:
        size, vertices = prod(data.shape), len(mesh.vertices)
        if size != vertices:
            return (
                f"{data.name} has {size} values ({dims}), mesh has {vertices} vertices."
                "\nBake the grid from the coordinates of this variable."
            )
        baked = mesh_grid_dims(mesh)
        if baked and set(baked) != set(data.dims):
            return (
                f"{data.name} spans ({dims}), the grid spans ({', '.join(baked)})."
                "\nBake the grid from the coordinates of this variable."
            )
        return ""
    if ndim < 2:
        return problem + "\nA texture needs a 2D field."
    hint = TEXTURE_DIM_HINTS.get(ndim, TEXTURE_DIM_HINTS[4])
    return problem + "\n" + hint


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


def assign_material(data, material):
    """Show ``material`` in the first slot of ``data``, adding the slot if needed.

    Faces use slot 0 unless told otherwise, so replacing it, rather than
    appending a slot on every call, changes what the object shows.

    Parameters
    ----------
    data : bpy.types.Mesh or bpy.types.Volume
        Object data receiving the material.
    material : bpy.types.Material or None
        ``None`` empties the first slot.
    """
    if not data.materials:
        if material is not None:
            data.materials.append(material)
    elif data.materials[0] != material:
        data.materials[0] = material


def grid_material(grid_node):
    """Material the grid baked by ``grid_node`` should carry, or ``None``.

    Looks for a Datacube Texture or Animate Texture node in the same tree
    whose ``Object`` input is linked from ``grid_node``, and returns the
    material named after that node's variable, as created by "Apply
    Material". ``None`` makes the Set Material node assign no material.
    """
    for link in grid_node.id_data.links:
        texture = link.to_node
        if link.from_node != grid_node or link.to_socket.name != "Object":
            continue
        if texture.bl_idname not in TEXTURE_NODE_IDNAMES:
            continue
        material = bpy.data.materials.get(texture.inputs["Variable"].default_value)
        if material is not None:
            return material
    return None


def look_up_object_and_mesh(object_name):
    """Return ``(object, mesh)`` for the grid object, creating what is missing.

    An existing mesh object is reused with its own mesh. When the object was
    deleted, an orphan mesh of the same name is reused, and an object that
    is in no collection is linked to the active one.

    Parameters
    ----------
    object_name : str
        Name of the grid object.

    Raises
    ------
    ValueError
        If ``object_name`` belongs to an object that is not a mesh.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is not None and obj.type != "MESH":
        raise ValueError(
            f"{object_name} is not a mesh ({obj.type.lower()}); "
            "choose another grid name."
        )
    if obj is None:
        mesh = bpy.data.meshes.get(object_name)
        if mesh is None or mesh.users:
            mesh = bpy.data.meshes.new(object_name)
        obj = bpy.data.objects.new(object_name, mesh)
    if not obj.users_collection:
        bpy.context.collection.objects.link(obj)
    return obj, obj.data


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
