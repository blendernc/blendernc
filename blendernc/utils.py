import logging
from functools import wraps

import bpy
import numpy as np

from .core.dataset import coordinate_names, dataset_key, load_dataset, variable_names
from .core.fields import (
    RANGE_PROPERTIES,
    animated_field_error,
    field_range,
    texture_field_error,
)
from .core.slicing import (
    SLICING_ANY_VARIABLE,
    SLICING_FIELD_SEP,
    SLICING_RECORD_SEP,
    build_indexers,
    encode_slicing_record,
    merge_selector,
    recorded_selector,
)
from .messages import report_error
from .node_utils import get_all_nodes_by_idname

logger = logging.getLogger(__name__)

# Identifier of the enum entry that means "nothing selected".
NO_SELECTION = "No var"

# Up to this many variables, a Datacube Variable node has one output per
# variable; with more, a drop-down and a single output.
MAX_VARIABLE_OUTPUTS = 10

# Nodes that write a variable onto a mesh as a point attribute; both offer
# "Apply Material" and store the field range on the mesh.
TEXTURE_NODE_IDNAMES = ("BlenderNCNodeTexture", "BlenderNCNodeAnimateTexture")


# --------------------------------------------------------------------------
# Loading datasets
# --------------------------------------------------------------------------


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


def coordinate_items(dataset):
    """Enum items for the coordinates of ``dataset``, one per coordinate."""
    return build_enum_prop_list(coordinate_names(dataset), "DISK_DRIVE")


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
    return _with_header(coordinate_items(datacubedata), "Select coordinate")


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
# Slicing records
# --------------------------------------------------------------------------


def _record_stride(datastruct, dims, step, dataset=None):
    """Append one wildcard stride record per dimension to ``slicing``.

    A step of 1 keeps every sample, so nothing is recorded. With
    ``dataset``, a range already recorded on a dimension is kept.
    """
    if step <= 1:
        return
    for dim in dims:
        record_selector(datastruct, dataset, dim, slice(0, None, step))


def record_selector(datastruct, dataset, key, selector, var_name=SLICING_ANY_VARIABLE):
    """Append a wildcard ``slicing`` record for ``key`` to a data item.

    The selector is merged with the one already recorded on the same
    dimensions (see :func:`merge_selector`), so a Slice range and a
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
        SLICING_ANY_VARIABLE, key, merge_selector(previous, selector)
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


# --------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------


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
    # ``values`` can be a view of the dataset, so NaNs are zeroed in a copy;
    # that is a third of the time ``np.nan_to_num`` takes. A contiguous
    # float32 array matches the attribute storage, so ``foreach_set`` copies
    # the buffer instead of converting item by item (0.5 ms against 130 ms
    # for four million values).
    zeroed = np.array(values, dtype=np.float32)
    np.copyto(zeroed, 0.0, where=np.isnan(zeroed))
    attr.data.foreach_set("value", zeroed)
    return attr


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
    """Return the field to write onto ``obj``, or why there is none.

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
        ``(data, "")`` when ``variable`` spans the grid's dimensions with
        one value per vertex of ``obj``, otherwise ``(None, message)`` with
        the message from :func:`texture_field_error` or a shorter one for a
        non-mesh object or an unknown variable.
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
    """Return the field to animate over ``obj``, or why there is none.

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
        ``(data, dim, "")`` when ``variable`` has one dimension more than
        the grid and the others span the vertices of ``obj``, ``dim`` being
        the dimension spread over frames; otherwise ``(None, None, message)``.
    """
    if obj.type != "MESH":
        return None, None, f"{obj.name} is not a mesh.\nLink a baked Datacube Grid."
    dataset = get_dataset(datastruct)
    if dataset is None or variable not in dataset:
        return None, None, f"{variable} is not in the datacube."
    data = get_data_from_datastruct(datastruct, variable, fill=False)
    dim, error = animated_field_error(data, obj.data)
    return (None, None, error) if error else (data, dim, "")


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


def build_triangle_mesh(mesh, positions, triangles):
    """Replace the geometry of ``mesh`` by ``positions`` joined in ``triangles``.

    Vertex ``i`` sits at ``positions[i]``, so a field with one value per
    point lands on the vertices in the same order. Attributes written
    before go with the old geometry; materials stay.

    Positions and corners are written through their attributes, which
    ``foreach_set`` fills with one copy. ``vertices.co`` and
    ``loops.vertex_index`` are set item by item: for a million points
    and two million triangles they took 0.5 s of a 0.66 s bake, against
    1 ms this way.

    Parameters
    ----------
    mesh : bpy.types.Mesh
        Mesh to rebuild.
    positions : numpy.ndarray
        ``(n, 3)`` ``float32`` vertex positions.
    triangles : numpy.ndarray
        ``(m, 3)`` ``int32`` vertex indices.
    """
    positions = np.ascontiguousarray(positions, dtype=np.float32)
    triangles = np.ascontiguousarray(triangles, dtype=np.int32)
    mesh.clear_geometry()
    mesh.vertices.add(len(positions))
    mesh.attributes["position"].data.foreach_set("vector", positions.ravel())
    mesh.loops.add(triangles.size)
    _write_corner_verts(mesh, triangles.ravel())
    mesh.polygons.add(len(triangles))
    starts = np.arange(0, triangles.size, 3, dtype=np.int32)
    mesh.polygons.foreach_set("loop_start", starts)
    mesh.update(calc_edges=True)


def _write_corner_verts(mesh, corner_verts):
    """Set the vertex of every face corner of ``mesh``.

    Goes through the internal ``.corner_vert`` attribute, which Blender 5.2
    exposes, and falls back to ``loops.vertex_index`` should a later
    version rename it.
    """
    attr = mesh.attributes.get(".corner_vert")
    if attr is None:
        mesh.loops.foreach_set("vertex_index", corner_verts)
    else:
        attr.data.foreach_set("value", corner_verts)
