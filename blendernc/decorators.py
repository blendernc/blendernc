from collections import defaultdict
from functools import wraps

from .node_utils import create_basic_geometry_node


def is_single_input_linked(update_function):
    """Run an update only when the node has at least one linked input."""

    @wraps(update_function)
    def wrapper(self, *args, **kwargs):
        linked = any(input_socket.is_linked for input_socket in self.inputs)
        datastruct = self.BNC_datastructs[0]
        for input_socket in self.inputs:
            if input_socket.is_linked:
                from_node = input_socket.links[0].from_node
                from_socket = input_socket.links[0].from_socket
                if hasattr(self, "BNC_datastructs") and hasattr(
                    from_node, "BNC_datastructs"
                ):
                    datastruct_from_node = from_node.BNC_datastructs[0]
                    if datastruct_from_node.filename:
                        datastruct.filename = datastruct_from_node.filename
                        datastruct.datafile = datastruct_from_node.datafile
                    else:
                        self.id_data.links.remove(input_socket.links[0])
                        datastruct.filename = ""
                        datastruct.datafile = ""
                else:
                    input_socket.default_value = from_socket.default_value
            else:
                datastruct.filename = ""
                datastruct.datafile = ""
                self.outputs.clear()
        if linked:
            return update_function(self, *args, **kwargs)
        else:
            return

    return wrapper


def initialize_BNC_datastructs(update_function):
    """Initialize a new data item before running the update function."""

    @wraps(update_function)
    def wrapper(self, context):
        if hasattr(self, "BNC_datastructs"):
            item = self.BNC_datastructs.add()
            item.filename = ""
            item.datafile = ""
            item.dict = (
                defaultdict()
            )  # This is a global dictionary that will store the datasets for all the nodes and node_trees. It can be used to access the datasets from any node or node_tree in the BlenderNC workflow.
        return update_function(self, context)

    return wrapper


def check_if_node_tree_exists(update_function):
    """Check if the node tree exists before running the update function."""

    @wraps(update_function)
    def wrapper(self, context):
        if self.name == "Scene":
            node_tree = create_basic_geometry_node()
            node_tree.nodes.get("Datacube Import").datacube_file = (
                context.scene.datacube_file
            )
            return
        elif self.bl_idname == "BLENDERNC_OT_import_mfdataset":
            if self.node_name == "" or self.node_tree == "":
                node_tree = create_basic_geometry_node()
                self.node_tree = node_tree.name
                self.node_name = node_tree.nodes.get("Datacube Import").name
        else:
            self.node_tree = self.id_data.name
            self.node_name = self.name
        return update_function(self, context)

    return wrapper


def has_datastructs(update_function):
    """Check if the node has a BNC_datastructs attribute before running the update function."""

    @wraps(update_function)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, "BNC_datastructs"):
            datastruct = self.BNC_datastructs[0]
            if hasattr(datastruct, "dict") and datastruct.filename:
                return update_function(self, *args, **kwargs)
            else:
                for output in self.outputs:
                    self.outputs.remove(output)
        else:
            for output in self.outputs:
                self.outputs.remove(output)

    return wrapper
