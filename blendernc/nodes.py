import logging

import bpy

from .decorators import (
    has_datastructs,
    initialize_BNC_datastructs,
    is_single_input_linked,
)
from .properties import BNC_data
from .utils import (
    SLICING_ANY_VARIABLE,
    _record_stride,
    create_datastruct,
    delete_point_attribute,
    encode_slicing_record,
    field_to_point_values,
    get_dataset,
    get_possible_coordinates,
    get_possible_variables,
    get_surface_dims,
    store_dataset,
    suggested_stride,
    texture_field,
    write_field_range,
    write_point_attribute,
)

logger = logging.getLogger(__name__)


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
        if not self.datacube_file:
            return
        changed = self.datacube_file != datastruct.datafile
        evicted = datastruct.filename and get_dataset(datastruct) is None
        if changed or evicted:
            store_dataset(datastruct, self.datacube_file)

    def free(self):
        """Drop the dataset from the cache when the node is deleted."""
        datastruct = self.BNC_datastructs[0]
        datastruct.dict.pop(datastruct.filename, None)
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
        dataset = datastruct.dict[datastruct.filename]
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
            return self.BNC_datastructs[0].filename

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Create an output socket named after the selected variable."""
        if self.datacube_vars != "No var" and self.datacube_vars not in [
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

    def is_stale(self):
        """True when the object this node baked no longer matches the slicing."""
        baked = bpy.data.objects.get(self.baked_object) if self.baked_object else None
        slicing = self.BNC_datastructs[0].slicing
        return baked is not None and slicing != self.baked_slicing

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


class DatacubeSlice(bpy.types.Node, bNCNodeDefault):
    """Node intended to slice a variable along a coordinate (not yet implemented)."""

    bl_idname = "BlenderNCNodeSlice"  # Unique identifier for the node
    bl_label = "Datacube Slice"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    datacube_coords: bpy.props.EnumProperty(
        items=get_possible_coordinates,
        name="Select Variable",
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
        """Draw the coordinate drop-down once a variable is connected."""
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")

    @is_single_input_linked
    def update(self):
        """Placeholder; slicing is not implemented yet."""
        pass


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
        dataset = datastruct.dict[datastruct.filename]
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
        """Show the last message on the node, one label per line."""
        if not self.message:
            return
        lines = self.message.split("\n")
        layout.label(text=lines[0], icon="ERROR")
        for line in lines[1:]:
            layout.label(text=line)

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
        values = field_to_point_values(data)  # the one dask compute
        write_field_range(obj.data, values)
        write_point_attribute(obj.data, variable, values)
        self.written = variable
        logger.info(f"{self.name}: wrote {variable} onto {obj.name}")


class DebugNode(bpy.types.Node, bNCNodeDefault):
    """Node that displays the fields of the connected data item."""

    bl_idname = "BlenderNCNodeDebugNode"
    bl_label = "Debug Node"

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the ``"xarray datacube"`` input socket."""
        self.inputs.new("bNCdatacubeSocket", "xarray datacube")

    def draw_buttons(self, context, layout):
        """Draw every data item field and the cached dataset keys."""
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
        dataset = datastruct.dict[datastruct.filename]
        if self.step > 1 and self.datacube_coords in dataset.coords:
            datastruct.slicing += encode_slicing_record(
                SLICING_ANY_VARIABLE,
                self.datacube_coords,
                slice(0, None, self.step),
            )

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
        update=lambda self, context: self.update(),
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
        if "xarray datacube" not in [socket.name for socket in self.outputs]:
            self.outputs.new("bNCdatacubeSocket", "xarray datacube")

        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]
        surface_dims = get_surface_dims(dataset)
        if self.suggested_step:
            stride = suggested_stride([dataset.sizes[dim] for dim in surface_dims])
            if self.step != stride:
                self.step = stride  # the property callback is a no-op here
                logger.info(f"{self.name}: suggested step {stride}")

        if self.step > 1:
            _record_stride(datastruct, surface_dims, self.step)

        self.refresh_downstream()
