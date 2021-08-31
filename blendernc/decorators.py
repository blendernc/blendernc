#!/usr/bin/env python3
import functools

import bpy

import blendernc.get_utils as bnc_gutils
from blendernc.messages import PrintMessage, unselected_datacube, unselected_variable


class NodesDecorators(object):
    """
    NodeDecorator
    """

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
            update = cls.shouldIupdate(node)
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

    @classmethod
    def shouldIupdate(cls, node):
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
            outn = node.outputs[0].links[0].to_node
            # Make sure to disconnect all nodes follwoing,
            # as well as to clear dataset.
            cls.desconnect_nodes(outn, node)
        else:
            raise AttributeError("Fail to find connections!")
        return update

    @staticmethod
    def get_nodes_desconnect(outn, node):
        node_out_list = [node]
        while outn:
            node_out_list.append(outn)
            # Exit while if output node is encounter.
            if not outn.outputs.keys():
                outn.blendernc_dataset_identifier = ""
                # TODO delete blendernc_dict from output.
                outn = ""
                node_out_list.pop()
            # Exit while if node is not linked.
            elif not outn.outputs[0].is_linked:
                outn = ""
            # Change outn to append in list.
            else:
                outn = outn.outputs[0].links[0].to_node
        return node_out_list

    @classmethod
    def desconnect_nodes(cls, outn, node):
        node_out_list = cls.get_nodes_desconnect(outn, node)
        # If only output is connected, disconnect it.
        for node_out in node_out_list:
            cls.unlink_output(node_out)
            # Only remove the identifier of the node from the global dictionary.
            if node_out.bl_idname == "datacubeNode":
                identifier = node_out.blendernc_dataset_identifier
                node_out.blendernc_dict.pop(identifier, None)
            # Purge dictionary form all other nodes.
            else:
                node_out.blendernc_dict = {}
                node_out.blendernc_dataset_identifier = ""

    @staticmethod
    def unlink_input(node):
        inputs_links = bnc_gutils.get_input_links(node)
        inputs_links.from_socket.unlink(inputs_links)

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
            if output.is_linked and output.links:
                output_links = output.links
                connections["output"].append(
                    [link.from_node.bl_idname for link in output_links]
                )
        return connections

    @classmethod
    def input_connections(cls, node):
        """
        Test only one incoming connection.
        """
        # TODO: Add function to check for multiple connectgions
        inputs_links = bnc_gutils.get_input_links(node)
        if node.bl_idname in ["datacubePath", "Datacube_tutorial"]:
            return True
        elif inputs_links.from_node.bl_idname == "datacubePath":
            cls.get_blendernc_file(node)
            return cls.get_dataset(node)
        elif inputs_links.from_node.bl_idname == "datacubeNode":
            # Copy from socket! Note that this socket is shared in memory at \
            # any point in the nodetree.
            # TODO: Create a custom property that allows to pass a dataset,
            # currently it seems that developers can't create new bpy.types.bpy_struct
            cls.get_data_from_socket(node)
        else:
            # Copy directly from node.
            cls.get_data_from_node(node)

        return cls.dataset_has_identifier(node)

    @classmethod
    def get_dataset(cls, node):
        if node.bl_idname == "datacubeNode":
            return cls.select_var_dataset(node)
        elif node.bl_idname == "datacubeInputGrid":
            return cls.select_grid_dataset(node)

    @staticmethod
    def get_data_from_socket(node):
        inputs_links = bnc_gutils.get_input_links(node)
        socket = inputs_links.from_socket
        node.blendernc_dataset_identifier = socket.unique_identifier
        if socket.unique_identifier in socket.dataset.keys():
            dataset = socket.dataset[node.blendernc_dataset_identifier].copy()
            node.blendernc_dict[node.blendernc_dataset_identifier] = dataset

    @staticmethod
    def get_data_from_node(node):
        inputs_links = bnc_gutils.get_input_links(node)
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
            # If var is not selected disconnect and return update == False
            if "selected_var" not in blendernc_dict[identifier].keys():
                # Force definition of selected variable.
                PrintMessage(unselected_variable, title="Error", icon="ERROR")
                cls.unlink_input(node)
                node.blendernc_dict.pop(identifier)
                return False
            # Else return update == True
            else:
                return True
        # Else user should select a file.
        else:
            # Exception for datacubeNode to update dataset
            PrintMessage(unselected_datacube, title="Error", icon="ERROR")
            cls.unlink_input(node)
            return False

    @classmethod
    def select_var_dataset(cls, node):
        inputs_links = bnc_gutils.get_input_links(node)
        if node.blendernc_file != inputs_links.from_socket.text:
            node.blendernc_file = inputs_links.from_socket.text
            bpy.ops.blendernc.datacubeload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            return False
        elif (
            node.blendernc_datacube_vars != "No var"
            and node.blendernc_datacube_vars != ""
        ):
            return True
        else:
            bpy.ops.blendernc.datacubeload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            return False

    @classmethod
    def select_grid_dataset(cls, node):
        inputs_links = bnc_gutils.get_input_links(node)
        identifier = node.blendernc_dataset_identifier
        if node.blendernc_file != inputs_links.from_socket.text:
            node.blendernc_file = inputs_links.from_socket.text
            bpy.ops.blendernc.datacubeload(
                file_path=node.blendernc_file,
                node_group=node.rna_type.id_data.name,
                node=node.name,
            )
            # Duplicate  variables to extract variables
            node.persistent_dict["Dataset"] = node.blendernc_dict[identifier][
                "Dataset"
            ].copy()
            return False
        elif (
            node.blendernc_grid_x != "No var" and node.blendernc_grid_y != "No var"
        ) and (node.blendernc_grid_x != "" and node.blendernc_grid_y != ""):
            return True
        else:
            bpy.ops.blendernc.datacubeload(
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
        inputs_links = bnc_gutils.get_input_links(node)
        if not node.blendernc_file:
            node.blendernc_file = inputs_links.from_node.blendernc_file

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
        """
        Dummy update
        """
        return


class DrawDecorators(object):
    """
    DrawDecorators
    """

    @classmethod
    def is_connected(cls, func):
        """ """

        @functools.wraps(func)
        def wrapper_update(node, context, layout):
            func_globals = func.__globals__
            if (
                node.inputs[0].is_linked
                and node.inputs[0].links
                and node.blendernc_dataset_identifier
            ):
                blendernc_dict = node.inputs[0].links[0].from_node.blendernc_dict
                if blendernc_dict:
                    # Return provided function to compute its contents.
                    func_globals["blendernc_dict"] = blendernc_dict
                    return func(node, context, layout)
                else:
                    pass
            else:
                pass

        return wrapper_update


class MemoryDecorator(object):
    """ """

    def nodetrees_cached(func):
        """ """

        @functools.wraps(func)
        def unique_identifier(*args, **kwargs):
            scene = bpy.context.scene
            n = MemoryDecorator.number_cached_frames(scene)
            if n != 1:
                kwargs = {"n": n, "scene": scene}
                return func(*args, **kwargs)
            else:
                pass

        return unique_identifier

    def number_cached_frames(scene):
        nodetrees = bnc_gutils.get_blendernc_nodetrees()
        n = 0
        for node in nodetrees:
            # Make sure the datacube_cache is loaded.
            if node.name in scene.datacube_cache.keys():
                cache = scene.datacube_cache[node.name]
                for key, item in cache.items():
                    n += len(item)
        return n


class MathDecorator(object):
    """ """

    def math_operation(func):
        """ """

        @functools.wraps(func)
        def which_calculation(*args, **kwargs):
            # Get all identifiers of the node
            self = args[0]
            unique_identifier = self.blendernc_dataset_identifier
            unique_data_dict_node = self.blendernc_dict[unique_identifier]
            parent_node = self.inputs[0].links[0].from_node
            # Extract parent dataset
            dataset_parent = parent_node.blendernc_dict[unique_identifier][
                "Dataset"
            ].copy()
            # Computation name list
            computation_types = self.inputs.keys()
            # Compute with node
            if "Float" in computation_types and "Dataset" in computation_types:
                float = self.inputs.get("Float").Float
                dataset = func(self, dataset_parent, float)
            elif "Dataset" in computation_types and len(computation_types) == 2:
                input_from_node = self.inputs[-1].links[0].from_node
                dataset_other = (
                    self.inputs[-1]
                    .links[0]
                    .from_node.blendernc_dict[
                        input_from_node.blendernc_dataset_identifier
                    ]
                )
                varname_other = dataset_other["selected_var"]["selected_var_name"]

                sel_var = unique_data_dict_node["selected_var"]
                var_name = sel_var["selected_var_name"]

                dataarray_link_1 = unique_data_dict_node["Dataset"][var_name]
                dataarray_link_2 = dataset_other["Dataset"][varname_other]

                dataset = func(self, dataarray_link_1, dataarray_link_2, var_name)
            elif "Dataset" in computation_types and len(computation_types) == 1:
                dataset = func(self, dataset_parent)

            unique_data_dict_node["Dataset"] = dataset
            return unique_data_dict_node

        return which_calculation
