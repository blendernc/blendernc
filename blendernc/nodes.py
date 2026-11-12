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
    encode_slicing_record,
    get_possible_coordinates,
    get_possible_variables,
    get_surface_dims,
    load_dataset,
)


class bNCNodeDefault:
    """
    Base class for all BlenderNC nodes. This class provides common
    functionality and properties that are shared across all node types.
    """

    BNC_datastructs: bpy.props.CollectionProperty(type=BNC_data)

    def invoke(self, context):
        """Place the node at the cursor when added from the node editor."""
        space = context.space_data
        if space and space.type == "NODE_EDITOR":
            cursor = space.cursor_location
            self.location = cursor


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

    filename: bpy.props.StringProperty(update=lambda self, context: self.update())

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
        """Load the dataset into the shared cache if it is not already there."""
        datastruct = self.BNC_datastructs[0]
        if self.datacube_file and datastruct.filename not in datastruct.dict.keys():
            datastruct.datafile = self.datacube_file
            datastruct.filename = self.datacube_file.split("/")[-1]
            datastruct.dict[datastruct.filename] = load_dataset(datastruct.datafile)

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


class DatacubeGrid(bpy.types.Node, bNCNodeDefault):
    """Node that bakes a mesh from coordinates linked to its X, Y and Z inputs.

    The resulting object is exposed through an ``"Object"`` output socket.
    """

    bl_idname = "BlenderNCNodeGrid"  # Unique identifier for the node
    bl_label = "Datacube Grid"  # Name that will appear on the node in the editor
    bl_icon = "EXPERIMENTAL"

    grid_obj_name: bpy.props.StringProperty(
        default="Grid",
    )

    @initialize_BNC_datastructs
    def init(self, context):
        """Create the hidden-value X, Y and Z string inputs."""
        self.inputs.new("NodeSocketString", "X")
        self.inputs.new("NodeSocketString", "Y")
        self.inputs.new("NodeSocketString", "Z")
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        """Draw the object name field and the "Bake Grid" button."""
        layout.prop(self, "grid_obj_name", text="")
        op = layout.operator("blendernc.create_grid_from_coords", text="Bake Grid")
        op.node_name = self.name
        op.node_tree = self.id_data.name

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Expose the baked object on the ``"Object"`` output once it exists."""
        if self.grid_obj_name in bpy.data.objects:
            if "Object" not in [socket.name for socket in self.outputs]:
                object_socket = self.outputs.new("NodeSocketObject", "Object")
                object_socket.default_value = bpy.data.objects[self.grid_obj_name]
            else:
                object_socket = self.outputs.get("Object")
                object_socket.default_value = bpy.data.objects[self.grid_obj_name]


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
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        """Draw the coordinate drop-down once a variable is connected."""
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")

    @is_single_input_linked
    def update(self):
        """Placeholder; slicing is not implemented yet."""
        pass
        # var = self.inputs[0].default_value


class DatacubeSelect(bpy.types.Node, bNCNodeDefault):
    """Node that selects a single index along a coordinate of a variable.

    The selection is recorded in the data item's ``slicing`` string as
    ``"<variable>_<coordinate>_<index>,"`` and applied by
    :func:`blendernc.utils.get_data_from_datastruct`.
    """

    bl_idname = "BlenderNCNodeSelect"  # Unique identifier for the node
    bl_label = "Datacube Select"  # Name that will appear on the node in the editor
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
        [setattr(input, "hide_value", True) for input in self.inputs]

    def draw_buttons(self, context, layout):
        """Draw the coordinate drop-down once a variable is connected."""
        if self.inputs.get("Variable").default_value:
            layout.prop(self, "datacube_coords", text="")

    @is_single_input_linked
    @has_datastructs
    def update(self):
        """Forward the variable and append the index selection to ``slicing``."""
        if "Variable" not in [socket.name for socket in self.outputs]:
            socket = self.outputs.new("NodeSocketString", "Variable")
            socket.default_value = self.inputs[0].default_value
        value = 0
        datastruct = self.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]
        if self.datacube_coords and self.datacube_coords in dataset.coords.keys():
            datastruct.slicing += encode_slicing_record(
                SLICING_ANY_VARIABLE,
                self.datacube_coords,
                str(value),
            )


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
        layout.prop(datastruct, "operations")
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

        # Refresh nodes already connected downstream so they copy the new
        # slicing string instead of waiting for the next link change.
        for link in self.outputs["Variable"].links:
            link.to_node.update()


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

    step: bpy.props.IntProperty(
        name="Step",
        description="Keep one surface sample every N indices (1 = full)",
        default=2,
        min=1,
        soft_max=20,
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
        if self.step > 1:
            _record_stride(datastruct, get_surface_dims(dataset), self.step)

        for link in self.outputs["xarray datacube"].links:
            link.to_node.update()
