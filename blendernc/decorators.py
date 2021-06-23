#!/usr/bin/env python3
import functools

import bpy

from .messages import unselected_nc_var, unselected_variable


class NodesDecorators(object):
    @classmethod
    def node_connections(cls, func):
        """
        Test node connections of nodes.
        First it tests who is the node connected to,
        then it updates portions depending on the
        corresponding connections.
        If all tests are correct, then the function is preupdated
        (i.e. Defines the node properties).
        """

        @functools.wraps(func)
        def wrapper_update(node):
            update = False
            # Who am I connected?
            connections = cls.amIconnected(node)
            # Test types of connections.
            if not connections["input"] and not connections["output"]:
                pass
            elif connections["input"] and connections["output"]:
                update = cls.input_connections(node)
            elif connections["input"]:
                update = cls.input_connections(node)
            elif connections["output"]:
                # If only output is connected, disconnect it.
                cls.unlink_output(node)
            else:
                raise AttributeError("Fail to find connections!")

            if update:
                # Return provided function to compute its contents.
                return func(node)
            else:
                # Dummy update.
                return cls.dummy_update(node)

        # TODO add support to purge, delete or refresh
        # cache based on type of node. Instead of having them all
        # over the place.
        return wrapper_update

    # Example of dummy decorator.
    @staticmethod
    def dummy(func):
        @functools.wraps(func)
        def wrapper_dummy(self, *args, **kwargs):
            # Do something here
            return func(self, *args, **kwargs)

        return wrapper_dummy

    @staticmethod
    def unlink_input(node):
        node.inputs[0].links[0].from_socket.unlink(node.inputs[0].links[0])

    @staticmethod
    def unlink_output(node):
        links = node.outputs[0].links
        for link in links:
            link.from_socket.unlink(link)

    @staticmethod
    def amIconnected(node):
        # Connections dictionary
        connections = {"input": [], "output": []}
        # Test input
        inputs = [ii for ii in node.inputs] if node.inputs else node.inputs
        for input in inputs:
            if input.is_linked and input.links:
                input_links = input.links[0]
                connections["input"].append(input_links.from_node.bl_idname)
        # Test output
        outputs = [ii for ii in node.outputs] if node.outputs else node.outputs
        # This condition is to avoid errors after init each node.
        for output in outputs:
            if output.keys():
                if output.is_linked and output.links:
                    output_links = output.links
                    connections["output"].append(
                        [link.from_node.bl_idname for link in output_links]
                    )
        # print(connections)
        return connections

    @classmethod
    def input_connections(cls, node):
        """
        Test only one incomming connection.
        """
        # TODO: Add function to check for multiple connectgions
        inputs = node.inputs[0]
        inputs_links = inputs.links[0]
        if node.bl_idname == "netCDFPath":
            return True
        elif node.bl_idname == "Datacube_tutorial":
            return True
        elif (
            inputs_links.from_node.bl_idname == "netCDFPath"
            and node.bl_idname == "netCDFNode"
        ):
            cls.get_blendernc_file(node)
            return cls.select_var_dataset(node)
        elif (
            inputs_links.from_node.bl_idname == "netCDFPath"
            and node.bl_idname == "netCDFinputgrid"
        ):
            cls.get_blendernc_file(node)
            return cls.select_grid_dataset(node)
        elif inputs_links.from_node.bl_idname == "netCDFNode":
            # Copy from socket! Note that this socket is shared in memory at \
            # any point in the nodetree.
            # TODO: Create a custom property that allows to pass a dataset,
            # currently it seems that developers can't create new bpy.types.bpy_struct
            cls.get_data_from_socket(node)
        else:
            # Copy directly from node.
            cls.get_data_from_node(node)

        return cls.dataset_has_identifier(node)

    @staticmethod
    def get_data_from_socket(node):
        inputs = node.inputs[0]
        inputs_links = inputs.links[0]
        socket = inputs_links.from_socket
        node.blendernc_dataset_identifier = socket.unique_identifier
        if socket.unique_identifier in socket.dataset.keys():
            dataset = socket.dataset[node.blendernc_dataset_identifier].copy()
            node.blendernc_dict[node.blendernc_dataset_identifier] = dataset

    @staticmethod
    def get_data_from_node(node):
        inputs = node.inputs[0]
        inputs_links = inputs.links[0]
        node_parent = inputs_links.from_node
        node.blendernc_dataset_identifier = node_parent.blendernc_dataset_identifier
        if (
            node_parent.blendernc_dataset_identifier
            in node_parent.blendernc_dict.keys()
        ):
            dataset = node_parent.blendernc_dict[
                node.blendernc_dataset_identifier
            ].copy()
            node.blendernc_dict[node.blendernc_dataset_identifier] = dataset

    @classmethod
    def dataset_has_identifier(cls, node):
        identifier = node.blendernc_dataset_identifier
        blendernc_dict = node.blendernc_dict
        # If identifier exist a file has been selected.
        if identifier in blendernc_dict.keys():
            # If var is not selected disconect and return update == False
            if "selected_var" not in blendernc_dict[identifier].keys():
                # Force definition of selected variable.
                bpy.context.window_manager.popup_menu(
                    unselected_nc_var, title="Error", icon="ERROR"
                )
                cls.unlink_input(node)
                node.blendernc_dict.pop(identifier)
                return False
            # Else return update == True
            else:
                return True
        # Else user should select a file.
        else:
            # Exception for netCDFNode to update dataset
            bpy.context.window_manager.popup_menu(
                unselected_variable, title="Error", icon="ERROR"
            )
            cls.unlink_input(node)
            return False

    @classmethod
    def select_var_dataset(cls, node):
        if node.blendernc_file != node.inputs[0].links[0].from_socket.text:
            node.blendernc_file = node.inputs[0].links[0].from_socket.text
            bpy.ops.blendernc.ncload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            return False
        elif (
            node.blendernc_netcdf_vars != "No var" and node.blendernc_netcdf_vars != ""
        ):
            return True
        else:
            bpy.ops.blendernc.ncload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            return False

    @classmethod
    def select_grid_dataset(cls, node):
        identifier = node.blendernc_dataset_identifier
        if node.blendernc_file != node.inputs[0].links[0].from_socket.text:
            node.blendernc_file = node.inputs[0].links[0].from_socket.text
            bpy.ops.blendernc.ncload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            # Duplicate  variables to extract variables
            node.persistent_dict["Dataset"] = node.blendernc_dict[identifier][
                "Dataset"
            ].copy()
            return False
        elif node.blendernc_grid_x != "" and node.blendernc_grid_y != "":
            return True
        else:
            bpy.ops.blendernc.ncload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            # Duplicate  variables to extract variables
            node.persistent_dict["Dataset"] = node.blendernc_dict[identifier][
                "Dataset"
            ].copy()
            return False

    @staticmethod
    def get_blendernc_file(node):
        # TODO disconnect if not connected to proper node.
        if not node.blendernc_file:
            node.blendernc_file = node.inputs[0].links[0].from_node.blendernc_file

    @staticmethod
    def output_connections(node):
        """
        Test all output connections.
        """
        pass
        # outputs = node.outputs[0]
        # outputs_links = outputs.links

    @staticmethod
    def dummy_update(node):
        return
