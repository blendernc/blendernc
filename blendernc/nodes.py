import logging
import os

import bpy
import numpy as np

from .decorators import (
    has_datastructs,
    initialize_BNC_datastructs,
    is_single_input_linked,
)
from .node_utils import node_updates_enabled
from .properties import BNC_data
from .utils import (
    NO_SELECTION,
    SLICING_ANY_VARIABLE,
    _record_stride,
    clamp_index_range,
    create_datastruct,
    delete_point_attribute,
    encode_slicing_record,
    field_to_point_values,
    format_coord_value,
    get_dataset,
    get_possible_coordinates,
    get_possible_variables,
    get_surface_dims,
    mesh_grid_dims,
    range_locked,
    record_selector,
    release_dataset,
    store_dataset,
    suggested_stride,
    texture_field,
    update_suggested_step,
    value_index_range,
    write_field_range,
    write_point_attribute,
)
from .volume_utils import (
    DEFAULT_VDB_DIR,
    FRAMES_LIVE,
    FRAMES_SEQUENCE,
    get_animate_dims,
    release_vdb_directory,
)

logger = logging.getLogger(__name__)


def draw_message(layout, message, icon="ERROR"):
    """Draw a multi-line node message: an icon on the first line only."""
    if not message:
        return
    lines = message.split("\n")
    layout.label(text=lines[0], icon=icon)
    for line in lines[1:]:
        layout.label(text=line)


class bNCNodeDefault:
    """
    Base class for all BlenderNC nodes. This class provides common
    functionality and properties that are shared across all node types.
    """

    BNC_datastructs: bpy.props.CollectionProperty(type=BNC_data)

    def refresh_downstream(self):
        """Run ``update`` on every node linked to an output of this node.

        Downstream nodes copy the data item (filename and slicing) from their
        inputs when they update, so a change here has to be pushed to them
        instead of waiting for the next link change.
        """
        for socket in self.outputs:
            for link in socket.links:
                link.to_node.update()


# Custom node type
class DatacubeImport(bpy.types.Node, bNCNodeDefault):
    """Node that opens a NetCDF, GRIB or Zarr datacube from a path or pattern.

    The loaded :class:`xarray.Dataset` is exposed to downstream nodes through
    the ``"xarray datacube"`` output socket.
    """

    bl_idname = "BlenderNCNodeImport"  # Unique identifier for the node
    bl_label = "Datacube Import"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_file: bpy.props.StringProperty(
        name="",
        description="Filepath used for importing the file",
        default="",
        maxlen=1024,
        update=create_datastruct,
    )
    """An instance of the original StringProperty."""

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"xarray datacube"`` output socket."""
        socket = self.outputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        """Draw the path field and the file browser button."""
        layout.label(text="Datacube path", icon="OUTLINER_OB_GROUP_INSTANCE")
        row = layout.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(self, "datacube_file")
        op = split.operator("blendernc.import_mfdataset", text="", icon="FILEBROWSER")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    def update(self):
        """Load the dataset when the path changed or the cache lost it.

        A path that failed to open is left alone until it is edited, so the
        failure is logged once rather than on every tree update.
        """
        datastruct = self.BNC_datastructs[0]
        if not self.datacube_file or not node_updates_enabled():
            return
        changed = self.datacube_file != datastruct.datafile
        evicted = datastruct.filename and get_dataset(datastruct) is None
        if changed or evicted:
            store_dataset(datastruct, self.datacube_file)

    def free(self):
        """Release the dataset unless another import node still uses it."""
        datastruct = self.BNC_datastructs[0]
        release_dataset(datastruct, datastruct.filename, ignore=self)
        datastruct.filename = ""
        datastruct.datafile = ""


class DatacubeCoords(bpy.types.Node, bNCNodeDefault):
    """Node that exposes every coordinate of the dataset as a string output."""

    bl_idname = "BlenderNCNodeCoords"  # Unique identifier for the node
    bl_label = "Datacube Coords"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"xarray datacube"`` input socket."""
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        """Nothing to draw; the node only has sockets."""
        pass

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Add one string output socket per dataset coordinate."""
        datastruct = self.BNC_datastructs[0]
        dataset = get_dataset(datastruct)
        if dataset is None:
            return
        for coords in dataset.coords:
            if coords not in [socket.name for socket in self.outputs]:
                socket = self.outputs.new("NodeSocketString", coords)
                socket.default_value = coords
        self.refresh_downstream()


class DatacubeVariable(bpy.types.Node, bNCNodeDefault):
    """Node that selects one variable of the dataset.

    The chosen variable name becomes a string output socket.
    """

    bl_idname = "BlenderNCNodeVariable"  # Unique identifier for the node
    bl_label = "Datacube Variable"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"xarray datacube"`` input socket."""
        socket = self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        socket.display_shape = "SQUARE"

    def draw_buttons(self, context, layout):
        """Draw the variable drop-down."""
        layout.label(text="Select Variable:")
        layout.prop(self, "datacube_vars", text="")

    def draw_label(self):
        """Show the loaded filename as the node label, or a placeholder."""
        if not self.BNC_datastructs[0].filename:
            return "datacube Input"
        else:
            return os.path.basename(self.BNC_datastructs[0].filename)

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Create an output socket named after the selected variable."""
        if self.datacube_vars != NO_SELECTION and self.datacube_vars not in [
            socket.name for socket in self.outputs
        ]:
            socket = self.outputs.new("NodeSocketString", self.datacube_vars)
            socket.default_value = self.datacube_vars
        self.refresh_downstream()


class DatacubeGrid(bpy.types.Node, bNCNodeDefault):
    """Node that bakes a mesh from coordinates linked to its X, Y and Z inputs.

    The resulting object is exposed through an ``"Object"`` output socket.
    Once baked, the grid follows the tree: when the slicing in force differs
    from the one used for the last bake (a resolution or subsample node
    changed), ``update`` bakes again so the mesh keeps one vertex per sample.
    """

    bl_idname = "BlenderNCNodeGrid"  # Unique identifier for the node
    bl_label = "Datacube Grid"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    grid_obj_name: bpy.props.StringProperty(
        default="Grid",
    )
    baked_object: bpy.props.StringProperty(
        description="Object this node baked last; only that object is rebaked",
    )
    baked_slicing: bpy.props.StringProperty(
        description="Slicing records in force when the grid was last baked",
    )
    baked_coords: bpy.props.StringProperty(
        description="Coordinates linked to X, Y and Z when the grid was last baked",
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the hidden-value X, Y and Z string inputs."""
        self.inputs.new("NodeSocketString", "X")
        self.inputs.new("NodeSocketString", "Y")
        self.inputs.new("NodeSocketString", "Z")
        for socket in self.inputs:
            socket.hide_value = True

    def draw_buttons(self, context, layout):
        """Draw the object name field and the "Bake Grid" button."""
        layout.prop(self, "grid_obj_name", text="")
        op = layout.operator("blendernc.create_grid_from_coords", text="Bake Grid")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    def _baked(self):
        """The object this node baked last, or ``None``."""
        return bpy.data.objects.get(self.baked_object) if self.baked_object else None

    def is_stale(self):
        """True when the object this node baked no longer matches the slicing."""
        slicing = self.BNC_datastructs[0].slicing
        return self._baked() is not None and slicing != self.baked_slicing

    def coords_signature(self):
        """The coordinates linked to X, Y and Z, as one string."""
        return "|".join(s.default_value if s.is_linked else "" for s in self.inputs)

    def needs_bake(self):
        """True unless the baked object matches the object name and the inputs.

        Only the coordinates and the slicing shape the mesh; a variable is
        painted onto it by a texture node and needs no bake.
        """
        return (
            self._baked() is None
            or self.baked_object != self.grid_obj_name
            or self.baked_coords != self.coords_signature()
            or self.is_stale()
        )

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Expose the baked object, rebaking first when the slicing changed."""
        if self.is_stale():
            # The operator records the new slicing and calls update() again.
            try:
                bpy.ops.blendernc.create_grid_from_coords(
                    node_name=self.name, node_tree=self.id_data.name
                )
            except RuntimeError:
                pass  # already reported and logged by the operator
            return
        obj = bpy.data.objects.get(self.grid_obj_name)
        if obj is None:
            return
        socket = self.outputs.get("Object") or self.outputs.new(
            "NodeSocketObject", "Object"
        )
        socket.default_value = obj
        self.refresh_downstream()


# Values of the Slice node's ``slice_by`` enum.
SLICE_BY_INDEX = "INDEX"
SLICE_BY_VALUE = "VALUE"


# Nodes whose bounds are being reset; their property callbacks wait, so
# the node slices, and rebakes downstream grids and volumes, only once.
_RESETTING = set()


def _reset_slice_range(node, context):
    """Give a newly picked coordinate its full range, then update once."""
    dataset = get_dataset(node.BNC_datastructs[0])
    coord = node.datacube_coords
    if dataset is not None and coord in dataset.coords and dataset[coord].ndim == 1:
        values = dataset[coord].values
        _RESETTING.add(node.as_pointer())
        try:
            node.first, node.last = 0, values.size - 1
            if np.issubdtype(values.dtype, np.number) and np.isfinite(values).any():
                node.minimum = float(np.nanmin(values))
                node.maximum = float(np.nanmax(values))
        finally:
            _RESETTING.discard(node.as_pointer())
    node.update()


def _update_node(node, context):
    """Property callback that runs the node's ``update``, unless resetting."""
    if node.as_pointer() not in _RESETTING:
        node.update()


class DatacubeSlice(bpy.types.Node, bNCNodeDefault):
    """Node that keeps a range of positions along one coordinate.

    "Slice by" chooses how the range is given: by index ("First" and
    "Last", both kept, clamped to the coordinate size) or by value
    ("Minimum" and "Maximum", in the coordinate's units, for a numeric
    coordinate). The range is recorded in the data item's ``slicing`` string
    as ``"*|<coordinate>|<first>:<last + 1>:,"`` and merged with a stride
    already recorded on the same dimension, so a Subsample or Resolution
    step still applies. Indices count along the full coordinate, as in the
    Datacube Select node.
    """

    bl_idname = "BlenderNCNodeSlice"  # Unique identifier for the node
    bl_label = "Datacube Slice"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Coordinate",
        update=_reset_slice_range,
    )
    slice_by: bpy.props.EnumProperty(
        items=[
            (SLICE_BY_INDEX, "Index", "Keep the positions from First to Last"),
            (SLICE_BY_VALUE, "Value", "Keep the values from Minimum to Maximum"),
        ],
        name="Slice by",
        default=SLICE_BY_INDEX,
        update=_update_node,
    )
    first: bpy.props.IntProperty(
        name="First",
        description="First position kept along the coordinate",
        default=0,
        min=0,
        update=_update_node,
    )
    last: bpy.props.IntProperty(
        name="Last",
        description="Last position kept (clamped to the coordinate size)",
        default=0,
        min=0,
        update=_update_node,
    )
    minimum: bpy.props.FloatProperty(
        name="Minimum",
        description="Smallest coordinate value kept",
        default=0.0,
        precision=4,
        update=_update_node,
    )
    maximum: bpy.props.FloatProperty(
        name="Maximum",
        description="Largest coordinate value kept",
        default=0.0,
        precision=4,
        update=_update_node,
    )
    summary: bpy.props.StringProperty(
        description="Values and positions of the range kept",
    )
    message: bpy.props.StringProperty(
        description="Why nothing is sliced",
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"Variable"`` input and output sockets."""
        self.inputs.new("NodeSocketString", "Variable")
        self.outputs.new("NodeSocketString", "Variable")
        for socket in self.inputs:
            socket.hide_value = True
        self.width = 220

    def draw_buttons(self, context, layout):
        """Draw the coordinate, the mode and its bounds once a variable is linked."""
        if not self.inputs.get("Variable").default_value:
            return
        layout.prop(self, "datacube_coords", text="")
        layout.prop(self, "slice_by", expand=True)
        bounds = ("minimum", "maximum")
        if self.slice_by == SLICE_BY_INDEX:
            bounds = ("first", "last")
        column = layout.column(align=True)
        for bound in bounds:
            column.prop(self, bound)
        if self.summary:
            layout.label(text=self.summary)
        draw_message(layout, self.message)

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Forward the variable and append the range to ``slicing``."""
        if "Variable" not in [socket.name for socket in self.outputs]:
            self.outputs.new("NodeSocketString", "Variable")
        variable = self.inputs[0].default_value
        self.outputs["Variable"].default_value = variable

        datastruct = self.BNC_datastructs[0]
        dataset = get_dataset(datastruct)
        if dataset is None:
            return
        bounds = self._bounds(dataset)
        if bounds is not None:
            first, last = bounds
            selector = slice(first, last + 1)
            record_selector(datastruct, dataset, self.datacube_coords, selector)
        self.refresh_downstream()

    def _bounds(self, dataset):
        """Return ``(first, last)`` positions to keep, or ``None``.

        ``summary`` and ``message`` are set on the way: what is kept, or
        why nothing is.
        """
        self.summary = self.message = ""
        values = self._slice_values(dataset)
        if values is None:
            return None
        if self.slice_by == SLICE_BY_INDEX:
            bounds = clamp_index_range(values.size, self.first, self.last)
        else:
            bounds = value_index_range(values, self.minimum, self.maximum)
        if bounds is None:
            self.message = (
                f"No {self.datacube_coords} value in"
                f" {self.minimum:g} to {self.maximum:g}.\nWiden the range."
            )
            return None
        first, last = bounds
        low, high = (format_coord_value(values[i]) for i in bounds)
        self.summary = f"Keeps {low} to {high} (positions {first} to {last})"
        return bounds

    def _slice_values(self, dataset):
        """Values of the picked coordinate, or ``None`` if it can't be sliced.

        ``message`` says why: a coordinate that is not 1-D, or one that is not
        numeric in Value mode.
        """
        coord = self.datacube_coords
        if coord not in dataset.coords:
            return None
        values = dataset[coord]
        if values.ndim != 1:
            self.message = f"{coord} is {values.ndim}D.\nPick a 1D coordinate."
            return None
        values = values.values
        by_value = self.slice_by != SLICE_BY_INDEX
        if by_value and not np.issubdtype(values.dtype, np.number):
            self.message = f"{coord} is not numeric.\nSlice it by index."
            return None
        return values


class DatacubeSelect(bpy.types.Node, bNCNodeDefault):
    """Node that selects a single index along a coordinate of a variable.

    The selection is recorded in the data item's ``slicing`` string as
    ``"*|<coordinate>|<index>,"`` and applied by
    :func:`blendernc.utils.get_data_from_datastruct`.
    """

    bl_idname = "BlenderNCNodeSelect"  # Unique identifier for the node
    bl_label = "Datacube Select"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Coordinate",
        update=lambda self, context: self.update(),
    )
    index: bpy.props.IntProperty(
        name="Index",
        description="Position along the coordinate to keep (clamped to its size)",
        default=0,
        min=0,
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"Variable"`` input and output sockets."""
        self.inputs.new("NodeSocketString", "Variable")
        self.outputs.new("NodeSocketString", "Variable")
        for socket in self.inputs:
            socket.hide_value = True

    def draw_buttons(self, context, layout):
        """Draw the coordinate drop-down and index once a variable is connected."""
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")
            layout.prop(self, "index")

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Forward the variable and append the index selection to ``slicing``."""
        if "Variable" not in [socket.name for socket in self.outputs]:
            self.outputs.new("NodeSocketString", "Variable")
        self.outputs["Variable"].default_value = self.inputs[0].default_value

        datastruct = self.BNC_datastructs[0]
        dataset = get_dataset(datastruct)
        if dataset is None:
            return
        if self.datacube_coords in dataset.coords:
            last = dataset[self.datacube_coords].shape[0] - 1
            datastruct.slicing += encode_slicing_record(
                SLICING_ANY_VARIABLE,
                self.datacube_coords,
                min(self.index, last),
            )

        self.refresh_downstream()


class DatacubeAnimateTexture(bpy.types.Node, bNCNodeDefault):
    """Node that animates a variable as a point attribute on an object.

    The actual work is done per frame by
    :func:`blendernc.handlers.bNC_update_attributes`.
    """

    bl_idname = "BlenderNCNodeAnimateTexture"  # Unique identifier for the node
    bl_label = (
        "Datacube Animate Texture"  # Name that will appear on the node in the editor
    )
    bl_icon = "EXPERIMENTAL"

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"Object"`` and ``"Variable"`` input sockets."""
        self.inputs.new("NodeSocketObject", "Object")
        self.inputs.new("NodeSocketString", "Variable")

    def draw_buttons(self, context, layout):
        """Nothing to draw; the node only has sockets."""
        pass

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Nothing to update; the frame handler reads the inputs directly."""
        pass


class DatacubeTexture(bpy.types.Node, bNCNodeDefault):
    """Node that writes a 2-D variable onto an object as a point attribute.

    The counterpart of :class:`DatacubeAnimateTexture` for fields without an
    extra dimension: the attribute is written once, whenever the node
    updates, and does not depend on the frame. A variable with the wrong
    number of dimensions is refused and the reason is shown on the node and
    written to the log. A 3-D field is pointed to the Datacube Animate
    Texture node and a 4-D field to the Datacube Select node. Unlinking the
    ``Variable`` input removes the attribute from the object again.
    """

    bl_idname = "BlenderNCNodeTexture"  # Unique identifier for the node
    bl_label = "Datacube Texture"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    message: bpy.props.StringProperty(
        name="Message",
        description="Why the variable was not written onto the object",
        default="",
    )
    written: bpy.props.StringProperty(
        name="Written attribute",
        description="Point attribute this node last wrote onto the object",
        default="",
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"Object"`` and ``"Variable"`` input sockets."""
        self.inputs.new("NodeSocketObject", "Object")
        self.inputs.new("NodeSocketString", "Variable")

    def draw_buttons(self, context, layout):
        """Draw "Apply Material", then the last message, one label per line."""
        row = layout.row()
        row.enabled = bool(self.written)  # nothing to colour before that
        op = row.operator("blendernc.bake_from_attribute", icon="MATERIAL")
        op.node_name = self.name
        op.node_tree = self.id_data.name
        draw_message(layout, self.message)

    def _delete_written(self):
        """Remove the attribute this node last wrote, if any."""
        socket = self.inputs.get("Object")
        obj = socket.default_value if socket else None
        if self.written and obj is not None and obj.data is not None:
            delete_point_attribute(obj.data, self.written)
        self.written = ""

    def update(self):
        """Drop the attribute when the variable is unlinked, then write it."""
        socket = self.inputs.get("Variable")  # None until init() has run
        if socket is not None and not socket.is_linked:
            socket.default_value = ""  # else the stale name would be rewritten
            self._delete_written()
            self.message = ""
        self._write_texture()

    @is_single_input_linked
    @has_datastructs
    def _write_texture(self):
        """Write the variable onto the object, or show why it cannot be."""
        obj = self.inputs["Object"].default_value
        variable = self.inputs["Variable"].default_value
        if obj is None or not variable:
            self.message = ""
            return
        if self.written != variable:
            self._delete_written()  # a new variable replaces the old attribute

        data, self.message = texture_field(self.BNC_datastructs[0], obj, variable)
        if data is None:
            logger.warning(f"{self.name}: {self.message.replace(chr(10), ' ')}")
            return
        values = field_to_point_values(data, mesh_grid_dims(obj.data))
        write_field_range(obj.data, values, locked=range_locked())
        write_point_attribute(obj.data, variable, values)
        self.written = variable
        logger.info(f"{self.name}: wrote {variable} onto {obj.name}")


def _apply_vertical_scale(node, context):
    """Stretch the baked volume vertically; no files need rewriting."""
    obj = bpy.data.objects.get(node.baked_object) if node.baked_object else None
    if obj is not None and obj.type == "VOLUME":
        obj.location.z = node.baked_z_origin * node.vertical_scale
        obj.scale.z = node.baked_z_step * node.vertical_scale


class DatacubeVolume(bpy.types.Node, bNCNodeDefault):
    """Node that turns a 3-D or 4-D variable into a Volume object.

    The variable is written to OpenVDB files read by a Blender Volume:
    ``(x, y, z)`` gives a static volume, ``(x, y, time)`` a static
    space-time cube with time running upwards, and ``(x, y, z, time)`` a
    volume animated along time. "Animate along" overrides that choice.

    In "Bake all frames" mode one file per frame is written and Blender
    plays them as a volume sequence; in "Current frame" mode only the frame
    shown is written, by :func:`blendernc.handlers.bNC_update_volumes`.
    Voxels are placed on the x/y coordinates, so the volume lines up with a
    Datacube Grid baked from the same coordinates; uneven or curvilinear
    coordinates are resampled onto a regular grid first, and the node says
    so. An evenly spaced vertical coordinate sets the voxel height too.
    Like the grid, the volume is baked again when the slicing, variable,
    animated dimension or frame mode changes. Deleting the node deletes its
    VDB folder once no Volume reads from it.
    """

    bl_idname = "BlenderNCNodeVolume"
    bl_label = "Datacube Volume"
    bl_icon = "EXPERIMENTAL"

    volume_obj_name: bpy.props.StringProperty(
        name="Volume name",
        description="Name of the Volume object to create or update",
        default="Volume",
    )
    animate_dim: bpy.props.EnumProperty(
        items=get_animate_dims,
        name="Animate along",
        description="Dimension spread over frames; the others form the volume",
        update=lambda self, context: self.update(),
    )
    frame_mode: bpy.props.EnumProperty(
        items=[
            (
                FRAMES_SEQUENCE,
                "Bake all frames",
                "Write one VDB file per frame; plays and renders without BlenderNC",
            ),
            (
                FRAMES_LIVE,
                "Current frame",
                "Write only the frame shown; less disk, playback needs BlenderNC",
            ),
        ],
        name="Frames",
        default=FRAMES_SEQUENCE,
        update=lambda self, context: self.update(),
    )
    vertical_scale: bpy.props.FloatProperty(
        name="Vertical scale",
        description=(
            "Multiplies the evenly spaced vertical coordinate; without one, "
            "the height of one voxel"
        ),
        default=1.0,
        min=1e-6,
        soft_max=100.0,
        update=_apply_vertical_scale,
    )
    vdb_dir: bpy.props.StringProperty(
        name="VDB folder",
        description="Folder for the VDB files ('//' is next to the .blend file)",
        default=DEFAULT_VDB_DIR,
        subtype="DIR_PATH",
    )
    message: bpy.props.StringProperty(
        name="Message",
        description="Why the volume could not be baked",
        default="",
    )
    warning: bpy.props.StringProperty(
        description="Problem with the last bake that the user should fix",
    )
    note: bpy.props.StringProperty(
        description="What the last bake resampled",
    )
    baked_z_origin: bpy.props.FloatProperty(
        description="Vertical position of the first voxel, before the scale",
        default=0.0,
    )
    baked_z_step: bpy.props.FloatProperty(
        description="Voxel height of the last bake, before the scale",
        default=1.0,
    )
    baked_object: bpy.props.StringProperty(
        description="Object this node baked last; only that object is rebaked",
    )
    baked_signature: bpy.props.StringProperty(
        description="Slicing, variable, animated dim and frame mode of the last bake",
    )
    bake_token: bpy.props.IntProperty(
        description="Counter in the VDB file names; Blender caches grids by path",
        default=0,
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the hidden-value ``"Variable"`` input."""
        socket = self.inputs.new("NodeSocketString", "Variable")
        socket.hide_value = True

    def draw_buttons(self, context, layout):
        """Draw the settings, the "Bake Volume" button and the last messages."""
        layout.prop(self, "volume_obj_name", text="")
        layout.prop(self, "animate_dim")
        layout.prop(self, "frame_mode", text="")
        layout.prop(self, "vertical_scale")
        layout.prop(self, "vdb_dir", text="")
        op = layout.operator("blendernc.create_volume", text="Bake Volume")
        op.node_name = self.name
        op.node_tree = self.id_data.name
        draw_message(layout, self.message)
        draw_message(layout, self.warning)
        draw_message(layout, self.note, icon="INFO")

    def free(self):
        """Delete this node's VDB folder unless a Volume still reads from it."""
        release_vdb_directory(self)

    def signature(self):
        """Everything that decides which files a bake writes."""
        variable = self.inputs["Variable"].default_value
        slicing = self.BNC_datastructs[0].slicing
        return f"{slicing}|{variable}|{self.animate_dim}|{self.frame_mode}"

    def is_stale(self):
        """True when the object this node baked no longer matches the tree."""
        baked = bpy.data.objects.get(self.baked_object) if self.baked_object else None
        return baked is not None and self.signature() != self.baked_signature

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Expose the baked volume, rebaking first when the tree changed."""
        if self.is_stale():
            # The operator records the new signature and calls update() again.
            try:
                bpy.ops.blendernc.create_volume(
                    node_name=self.name, node_tree=self.id_data.name
                )
            except RuntimeError:
                pass  # already reported, logged and shown on the node
            return
        obj = bpy.data.objects.get(self.volume_obj_name)
        if obj is None or obj.type != "VOLUME":
            return
        socket = self.outputs.get("Object") or self.outputs.new(
            "NodeSocketObject", "Object"
        )
        socket.default_value = obj
        self.refresh_downstream()


def _describe_value(socket):
    """Return a short text for the value an output socket carries."""
    if not hasattr(socket, "default_value"):
        return "no value"
    value = socket.default_value
    if isinstance(value, bpy.types.ID):  # Object, Material, ...
        return value.name
    if hasattr(value, "__len__") and not isinstance(value, str):
        return str(tuple(value))  # vectors and colours
    return repr(value)


class DebugNode(bpy.types.Node, bNCNodeDefault):
    """Node that displays whatever is connected to it.

    It takes a link from an output of any type (datacube, variable name,
    object, ...), shows where the link comes from, the socket type and the
    value, and the fields of the upstream node's data item. Nodes saved with
    the older ``"xarray datacube"`` input accept any link as well.
    """

    bl_idname = "BlenderNCNodeDebugNode"
    bl_label = "Debug Node"

    # Read by decorators._accepts_link: links of any type are kept.
    accepts_any_link = True

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the input socket, which accepts any type."""
        self.inputs.new("bNCAnySocket", "Input")

    def draw_buttons(self, context, layout):
        """Draw the linked output, then every data item field."""
        socket = self.inputs[0] if self.inputs else None
        if socket is not None and socket.is_linked:
            link = socket.links[0]
            from_socket = link.from_socket
            kind = from_socket.bl_label or from_socket.bl_idname
            layout.label(text=f"From: {link.from_node.name} > {from_socket.name}")
            layout.label(text=f"Type: {kind}")
            layout.label(text=f"Value: {_describe_value(from_socket)}")
        datastruct = self.BNC_datastructs[0]
        layout.prop(datastruct, "filename")
        layout.prop(datastruct, "datafile")
        layout.prop(datastruct, "slicing")
        if hasattr(datastruct, "dict"):
            layout.label(text=f"Dict keys: {list(datastruct.dict.keys())}")

    @is_single_input_linked
    def update(self):
        """Nothing to update beyond syncing the data item."""
        pass


class DatacubeSubsample(bpy.types.Node, bNCNodeDefault):
    """Node that lowers resolution by striding a coordinate.

    Appends a ``"*|<coordinate>|0::<step>,"`` record to the data item's
    ``slicing`` string. The stride is applied lazily by
    :func:`blendernc.utils.get_data_from_datastruct` to the variable and to
    every coordinate sharing the dimension, so the baked grid and the
    animated attribute keep matching sizes.
    """

    bl_idname = "BlenderNCNodeSubsample"
    bl_label = "Datacube Subsample"
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Coordinate",
        update=lambda self, context: self.update(),
    )
    step: bpy.props.IntProperty(
        name="Step",
        description="Keep one sample every N indices (1 = full resolution)",
        default=2,
        min=1,
        soft_max=20,
        update=lambda self, context: self.update(),
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"Variable"`` input and output sockets."""
        self.inputs.new("NodeSocketString", "Variable")
        self.outputs.new("NodeSocketString", "Variable")
        for socket in self.inputs:
            socket.hide_value = True

    def draw_buttons(self, context, layout):
        """Draw the coordinate drop-down and step once a variable is linked."""
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")
            layout.prop(self, "step")

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Forward the variable and record the stride in ``slicing``."""
        if "Variable" not in [socket.name for socket in self.outputs]:
            self.outputs.new("NodeSocketString", "Variable")
        self.outputs["Variable"].default_value = self.inputs[0].default_value

        datastruct = self.BNC_datastructs[0]
        dataset = get_dataset(datastruct)
        if dataset is None:
            return
        if self.step > 1 and self.datacube_coords in dataset.coords:
            stride = slice(0, None, self.step)
            record_selector(datastruct, dataset, self.datacube_coords, stride)
        self.refresh_downstream()


class DatacubeResolution(bpy.types.Node, bNCNodeDefault):
    """Node that lowers the horizontal resolution of the dataset.

    Every dimension identified by :func:`blendernc.utils.get_surface_dims`
    receives a ``"*|<dim>|0::<step>,"`` record, so the variable, the grid
    coordinates and the animated attribute are all strided by the same
    factor while time and depth are left untouched.
    """

    bl_idname = "BlenderNCNodeResolution"
    bl_label = "Datacube Resolution"
    bl_icon = "EXPERIMENTAL"

    # While the step is suggested, ``update`` assigns it itself; running
    # ``update`` again from the property callback would recurse.
    step: bpy.props.IntProperty(
        name="Step",
        description="Keep one surface sample every N indices (1 = full)",
        default=2,
        min=1,
        soft_max=20,
        update=lambda self, context: None if self.suggested_step else self.update(),
    )

    suggested_step: bpy.props.BoolProperty(
        name="Suggested Step",
        description="Use the suggested step based on the surface dimensions",
        default=True,
        update=update_suggested_step,
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"xarray datacube"`` input and output sockets."""
        self.inputs.new("bNCdatacubeSocket", "xarray datacube")
        self.outputs.new("bNCdatacubeSocket", "xarray datacube")
        for socket in self.inputs:
            socket.hide_value = True

    def draw_buttons(self, context, layout):
        """Draw the step and list the dimensions it will apply to."""
        if not self.inputs.get("xarray datacube"):
            return
        layout.prop(self, "step")
        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict.get(datastruct.filename)
        if dataset is not None:
            layout.prop(self, "suggested_step")
            dims = get_surface_dims(dataset)
            text = ", ".join(dims) if dims else "no surface dimensions found"
            layout.label(text=text, icon="MESH_GRID")

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Forward the variable and record one stride per surface dimension."""
        if "xarray datacube" not in self.outputs:
            self.outputs.new("bNCdatacubeSocket", "xarray datacube")

        datastruct = self.BNC_datastructs[0]
        dataset = get_dataset(datastruct)
        if dataset is None:
            return
        surface_dims = get_surface_dims(dataset)
        if self.suggested_step:
            self._use_suggested_step([dataset.sizes[dim] for dim in surface_dims])
        _record_stride(datastruct, surface_dims, self.step, dataset)
        self.refresh_downstream()

    def _use_suggested_step(self, sizes):
        """Set ``step`` to the stride suggested for these surface sizes."""
        stride = suggested_stride(sizes)
        if self.step != stride:
            self.step = stride  # the property callback is a no-op here
            logger.info(f"{self.name}: suggested step {stride}")
