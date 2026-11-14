import glob
from collections import defaultdict
from functools import wraps

import bpy

from .messages import report_error
from .node_utils import (
    basic_nodes,
    create_blenderncnodetree,
    create_links,
    create_nodes,
    disconnect_links,
    locations,
)
from .panels_draw import draw_var_and_coords, show_section
from .shader_utils import basic_shader_nodes, shader_locations


def is_linked(update_function):
    """Run an update only when the node has at least one linked input."""

    @wraps(update_function)
    def wrapper(self, context):
        """Proceed when an input is linked; otherwise clear the node and cancel.

        ``self`` is the operator; the node it acts on is looked up by name.
        """
        node_tree = bpy.data.node_groups.get(self.node_tree)
        node = node_tree.nodes.get(self.node_name) if node_tree else None
        if node is None:
            return report_error(self, f"Node {self.node_name!r} not found.")
        if any(input_socket.is_linked for input_socket in node.inputs):
            return update_function(self, context)
        _clear_datastruct(node.BNC_datastructs[0])
        node.outputs.clear()
        return report_error(
            self, "Node has no linked inputs. Connect to bake grid.", "WARNING"
        )

    return wrapper


def _clear_datastruct(datastruct):
    """Reset every string field of a ``BNC_data`` item.

    Parameters
    ----------
    datastruct : BNC_data
        Data item attached to a node.

    Returns
    -------
    BNC_data
        The same item with ``filename``, ``datafile`` and ``slicing`` set to
        empty strings.
    """
    datastruct.filename = ""
    datastruct.datafile = ""
    datastruct.slicing = ""
    return datastruct


def _clear_default_values(inputs):
    """Blank the ``default_value`` of every input socket except ``Object`` sockets.

    Parameters
    ----------
    inputs : bpy.types.NodeInputs
        Input sockets of a node.
    """
    for input_socket in inputs:
        if hasattr(input_socket, "default_value") and input_socket.bl_label != "Object":
            input_socket.default_value = ""


def _copy_datastruct(source, target):
    """Copy the string fields of one ``BNC_data`` item onto another.

    Parameters
    ----------
    source : BNC_data
        Item to copy from.
    target : BNC_data
        Item to copy into.

    Returns
    -------
    BNC_data
        ``target`` with ``filename``, ``datafile`` and ``slicing`` taken from
        ``source``.
    """
    target.filename = source.filename
    target.datafile = source.datafile
    target.slicing = source.slicing
    return target


def _update_datastruct_if_filename_exists(self, datastruct, input_socket):
    """Pull the upstream node's data item through a linked input socket.

    If the upstream node has a loaded dataset, its data item is copied onto
    ``datastruct``. Otherwise the link is removed and ``datastruct`` is
    cleared.

    Parameters
    ----------
    self : bpy.types.Node
        Node that owns ``input_socket``.
    datastruct : BNC_data
        Data item of ``self`` to update.
    input_socket : bpy.types.NodeSocket
        Linked input socket whose first link is inspected.

    Returns
    -------
    BNC_data
        The updated (or cleared) data item.
    """
    from_node = input_socket.links[0].from_node
    datastruct_from_node = from_node.BNC_datastructs[0]
    if datastruct_from_node.filename in datastruct_from_node.dict:
        datastruct = _copy_datastruct(datastruct_from_node, datastruct)
    else:
        self.id_data.links.remove(input_socket.links[0])
        datastruct = _clear_datastruct(datastruct)
    return datastruct


def _update_data_in_link(self, datastruct, input_socket):
    """Propagate data item and socket value from the upstream node of a link.

    Parameters
    ----------
    self : bpy.types.Node
        Node that owns ``input_socket``.
    datastruct : BNC_data
        Data item of ``self`` to update.
    input_socket : bpy.types.NodeSocket
        Linked input socket to read from.
    """
    from_node = input_socket.links[0].from_node
    from_socket = input_socket.links[0].from_socket
    if hasattr(from_node, "BNC_datastructs"):
        _update_datastruct_if_filename_exists(self, datastruct, input_socket)
    if hasattr(from_socket, "default_value"):
        input_socket.default_value = from_socket.default_value


def _connected_inputs(node):
    """Return the input sockets of a node that currently have a link.

    Parameters
    ----------
    node : bpy.types.Node
        Node to inspect.

    Returns
    -------
    list of bpy.types.NodeSocket
        Linked input sockets, in socket order.
    """
    connected_inputs = [
        input_socket for input_socket in node.inputs if input_socket.is_linked
    ]
    return connected_inputs


def _drop_mismatched_links(node):
    """Remove links between sockets of different types and log each one.

    A custom node tree accepts any link, but copying an ``Object`` into a
    ``String`` socket (or the other way round) raises ``TypeError`` when the
    value is synced. Links are compared by socket type identifier, so only
    like-for-like links survive.

    Parameters
    ----------
    node : bpy.types.Node
        Node whose input links are checked.
    """
    for input_socket in node.inputs:
        for link in list(input_socket.links):
            from_socket = link.from_socket
            if from_socket.bl_idname == input_socket.bl_idname:
                continue
            node.id_data.links.remove(link)
            report_error(
                node,
                f"{node.name}: {from_socket.bl_label} output "
                f"{from_socket.name!r} cannot feed {input_socket.bl_label} input "
                f"{input_socket.name!r}; link removed.",
                "WARNING",
            )


def is_single_input_linked(update_function):
    """Run an update only when the node has at least one linked input."""

    @wraps(update_function)
    def wrapper(self, *args, **kwargs):
        """Sync the node's data item with its linked inputs, then run the update."""
        _drop_mismatched_links(self)
        datastruct = self.BNC_datastructs[0]
        connected_inputs = _connected_inputs(self)
        for input_socket in connected_inputs:
            _update_data_in_link(self, datastruct, input_socket)

        if not connected_inputs:
            _clear_default_values(self.inputs)
            datastruct = _clear_datastruct(datastruct)

        return update_function(self, *args, **kwargs)

    return wrapper


def initialize_BNC_datastructs(update_function):
    """Initialize a new data item before running the update function."""

    @wraps(update_function)
    def wrapper(self, context):
        """Add an empty ``BNC_data`` item to the node, then run the update."""
        if hasattr(self, "BNC_datastructs"):
            item = self.BNC_datastructs.add()
            item.filename = ""
            item.datafile = ""
            item.dict = defaultdict()
            # This is a global dictionary that will store the datasets for all
            # the nodes and node_trees. It can be used to access the datasets
            # from any node or node_tree in the BlenderNC workflow.
        return update_function(self, context)

    return wrapper


def create_Shader_nodes(self, context):
    """Create the default shader nodes for the material.

    Parameters
        ----------
        self : bpy.types.PropertyGroup or bpy.types.Operator
            Caller holding a ``node_tree`` name attribute.
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        None
    """
    if not self.material.use_nodes:
        self.material.use_nodes = True
    node_tree = self.material.node_tree
    create_nodes(node_tree, basic_shader_nodes, shader_locations)
    create_links(node_tree, basic_shader_nodes)


def _create_UI_nodes(self, context):
    """Build the default ``BLENDERNC`` node tree driven by the 3D view panel.

    Creates the import, coordinate, variable and grid nodes. When the path in
    the UI properties is empty or matches no file, the import node is
    disconnected and the variable/coordinate panel section is removed. When
    the path is valid, the nodes are linked and the section is drawn.

    Parameters
    ----------
    self : bpy.types.PropertyGroup or bpy.types.Operator
        Caller holding a ``node_tree`` name attribute.
    context : bpy.types.Context
        Current Blender context.

    Returns
    -------
    bpy.types.Node
        The "Datacube Import" node of the tree.
    """
    UI_props = context.scene.BlenderNC_UI_Properties
    node_tree = create_blenderncnodetree(self.node_tree)
    datacube_file = UI_props.datacube_file
    create_nodes(node_tree, basic_nodes, locations)
    import_node = node_tree.nodes.get("Datacube Import")
    if not datacube_file or not glob.glob(datacube_file):
        if datacube_file:
            report_error(self, f"No file matches {datacube_file!r}.", "WARNING")
        disconnect_links(node_tree, import_node)
        show_section(draw_var_and_coords, False)
        return import_node
    import_node.datacube_file = datacube_file
    create_links(node_tree, basic_nodes)
    show_section(draw_var_and_coords, True)
    return import_node


def check_if_node_tree_exists(update_function):
    """Check if the node tree exists before running the update function."""

    @wraps(update_function)
    def wrapper(self, context):
        """Resolve ``node_tree`` and ``node_name`` on ``self``, then run the update."""
        if self.bl_idname == "BlenderNC_UI_Properties":
            self.node_tree = "BLENDERNC"
            _create_UI_nodes(self, context)
            return None
        elif self.bl_idname == "BLENDERNC_OT_import_mfdataset":
            self.node_tree = "BLENDERNC"
            node = _create_UI_nodes(self, context)
            self.node_name = node.name
        elif self.bl_idname == "BLENDERNC_OT_bake_from_attribute":
            self.node_tree = "BLENDERNC"
        else:
            self.node_tree = self.id_data.name
            self.node_name = self.name

        return update_function(self, context)

    return wrapper


def has_datastructs(update_function):
    """
    Check if the node has a BNC_datastructs attribute
    before running the update function.
    """

    @wraps(update_function)
    def wrapper(self, *args, **kwargs):
        """Run the update when a dataset is loaded; otherwise remove all outputs."""

        datastruct = getattr(self, "BNC_datastructs")[0]

        if hasattr(datastruct, "dict") and datastruct.filename:
            return update_function(self, *args, **kwargs)
        self.outputs.clear()

    return wrapper
