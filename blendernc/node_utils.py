import bpy
import numpy as np


def create_basic_geometry_node():
    node_tree = create_geometrynodetree("BLENDERNC")

    create_node(node_tree, "BlenderNCNodeImport", location=(-300, 0))
    create_node(node_tree, "NodeGroupOutput", location=(300, 0))

    # APPLY TO CURRENT OBJECT
    obj = bpy.context.object
    if "BlenderNCModifier" in obj.modifiers:
        mod = obj.modifiers.get("BlenderNCModifier")
    else:
        mod = obj.modifiers.new("BlenderNCModifier", "NODES")
    mod.node_group = node_tree

    return node_tree


def create_node(node_tree, node_type, location=(0, 0), return_if_exists=True):
    node_names = [node.name for node in node_tree.nodes if node.bl_idname == node_type]
    if not node_names:
        # Create new node if it doesn't exist.
        node = node_tree.nodes.new(node_type)
    elif return_if_exists:
        # Return existing node if it already exists in the node tree
        node = node_tree.nodes.get(node_names[0])
    else:
        # Create new node
        node = node_tree.nodes.new(node_type)
    node.location = location
    return node


def create_geometrynodetree(nodetree_name):
    if nodetree_name in bpy.data.node_groups:
        nodetree = bpy.data.node_groups.get(nodetree_name)
    else:
        nodetree = bpy.data.node_groups.new(nodetree_name, "GeometryNodeTree")
    return nodetree


def create_nodes(node_tree, nodes):
    nodes["NodeGroupOutput"] = {"links": {}}
    node_types = list(nodes.keys()) if isinstance(nodes, dict) else list(nodes)

    node_types.append("NodeGroupOutput")
    locations = np.vstack(
        (np.linspace(-300, 300, len(node_types)), np.zeros(len(node_types)))
    ).T
    # Move below into decorator

    for i, node_type in enumerate(node_types):
        nodes[node_type]["node"] = create_node(
            node_tree, node_type, location=locations[i]
        )
        nodes[node_type]["name"] = nodes[node_type]["node"].name

    output_node = nodes["NodeGroupOutput"]["node"]
    if len(output_node.outputs)==0:
        geo_input = node_tree.interface.new_socket(
            name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )

        geo_output = node_tree.interface.new_socket(
            name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )

    create_links(node_tree, nodes)

    return nodes


def create_links(node_tree, nodes):
    for key, value in nodes.items():
        if "links" in value:
            for output_name, input_name in value["links"].items():
                input_node, socket = list(input_name.items())[0]
                node_tree.links.new(
                    nodes[key]["node"].outputs.get(output_name),
                    nodes[input_node]["node"].inputs.get(socket),
                )
