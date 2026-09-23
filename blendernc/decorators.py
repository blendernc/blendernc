import glob
from collections import defaultdict
from functools import wraps

import bpy

from .node_utils import (
    basic_nodes,
    create_blenderncnodetree,
    create_links,
    create_nodes,
)
from .panels_draw import draw_var_and_coords


def is_linked(update_function):
    """Run an update only when the node has at least one linked input."""

    @wraps(update_function)
    def wrapper(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree)
        node = node_tree.nodes.get(self.node_name)
        linked = any(input_socket.is_linked for input_socket in node.inputs)
        if linked:
            return update_function(self, context)
        else:
            datastruct = self.BNC_datastructs[0]
            datastruct.filename = ""
            datastruct.datafile = ""
            self.outputs.clear()
            self.report({"WARNING"}, "Node has no linked inputs. Connect to bake grid.")
            return {"CANCELLED"}

    return wrapper


def _clear_datastruct(datastruct):
    datastruct.filename = ""
    datastruct.datafile = ""
    datastruct.operations = ""
    datastruct.slicing = ""
    return datastruct


def _clear_default_values(inputs):
    for input_socket in inputs:
        if hasattr(input_socket, "default_value") and input_socket.bl_label != "Object":
            input_socket.default_value = ""


def _copy_datastruct(source, target):
    target.filename = source.filename
    target.datafile = source.datafile
    target.operations = source.operations
    target.slicing = source.slicing
    return target


def _update_datastruct_if_filename_exists(self, datastruct, input_socket):
    from_node = input_socket.links[0].from_node
    datastruct_from_node = from_node.BNC_datastructs[0]
    if datastruct_from_node.filename in datastruct_from_node.dict:
        datastruct = _copy_datastruct(datastruct_from_node, datastruct)
    else:
        self.id_data.links.remove(input_socket.links[0])
        datastruct = _clear_datastruct(datastruct)
    return datastruct


def _update_data_in_link(self, datastruct, input_socket):
    from_node = input_socket.links[0].from_node
    from_socket = input_socket.links[0].from_socket
    if hasattr(from_node, "BNC_datastructs"):
        datastruct = _update_datastruct_if_filename_exists(
            self, datastruct, input_socket
        )
    if hasattr(from_socket, "default_value"):
        input_socket.default_value = from_socket.default_value


def is_single_input_linked(update_function):
    """Run an update only when the node has at least one linked input."""

    @wraps(update_function)
    def wrapper(self, *args, **kwargs):
        datastruct = self.BNC_datastructs[0]
        connected_inputs = [
            input_socket for input_socket in self.inputs if input_socket.is_linked
        ]
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


def _create_UI_nodes(self, context):
    UI_props = context.scene.BlenderNC_UI_Properties
    if not UI_props.datacube_file:
        return
    node_tree = create_blenderncnodetree("BLENDERNC")
    create_nodes(node_tree, basic_nodes)
    Import_node = node_tree.nodes.get("Datacube Import")
    Import_node.datacube_file = UI_props.datacube_file
    create_links(node_tree, basic_nodes)

    if not bpy.types.BLENDERNC_UI_PT_3D_VIEW.is_extended():
        bpy.types.BLENDERNC_UI_PT_3D_VIEW.append(draw_var_and_coords)


def check_if_node_tree_exists(update_function):
    """Check if the node tree exists before running the update function."""

    @wraps(update_function)
    def wrapper(self, context):
        if self.bl_idname == "BlenderNC_UI_Properties":
            _create_UI_nodes(self, context)
            return
        elif self.bl_idname == "BLENDERNC_OT_import_mfdataset":
            _create_UI_nodes(self, context)
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

        datastruct = getattr(self, "BNC_datastructs")[0]

        if hasattr(datastruct, "dict") and datastruct.filename:
            return update_function(self, *args, **kwargs)
        else:
            for output in self.outputs:
                self.outputs.remove(output)

    return wrapper


def file_exists(update_function):
    """Check if the file exists before running the update function."""

    @wraps(update_function)
    def wrapper(filepath):
        if glob.glob(filepath):
            return update_function(filepath)
        else:
            raise FileNotFoundError("File {0} does not exist.".format(filepath))

    return wrapper
