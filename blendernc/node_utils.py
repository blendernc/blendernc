import bpy

# Node tree built and driven by the 3D view panel. Trees the user creates in
# the node editor can have any name.
UI_NODE_TREE = "BLENDERNC"

basic_nodes = {
    "BlenderNCNodeImport": {
        "links": {
            "xarray datacube": {
                "BlenderNCNodeResolution": "xarray datacube",
            }
        }
    },
    "BlenderNCNodeResolution": {
        "links": {
            "xarray datacube": {
                "BlenderNCNodeCoords": "xarray datacube",
                "BlenderNCNodeVariable": "xarray datacube",
            }
        }
    },
    "BlenderNCNodeCoords": {},
    "BlenderNCNodeVariable": {},
    "BlenderNCNodeGrid": {},
    "BlenderNCNodeTexture": {},
}

locations = [
    (-400, 0),
    (-200, 0),
    (0, 100),
    (0, -100),
    (200, 100),
    (400, -100),
]


# Node updates do real work: dask computes, mesh writes, bakes. They are
# switched off while the add-on unregisters, because Blender runs ``update``
# on every node as the classes disappear, after Python has already shut down
# its thread pools ("cannot schedule new futures after shutdown").
_node_updates_enabled = True


def enable_node_updates(enabled=True):
    """Allow (default) or suspend the work done in node ``update`` methods."""
    global _node_updates_enabled
    _node_updates_enabled = enabled


def node_updates_enabled():
    """Return ``False`` while node updates are suspended."""
    return _node_updates_enabled


def get_all_nodes_by_idname(bl_idname):
    """Yield every node of a given type across all node groups.

    Parameters
    ----------
    bl_idname : str
        Node type identifier to match.

    Yields
    ------
    bpy.types.Node
        Each matching node in ``bpy.data.node_groups``.
    """
    for node_tree in bpy.data.node_groups:
        for node in node_tree.nodes:
            if node.bl_idname == bl_idname:
                yield node


def create_node(node_tree, node_type, location=(0, 0), name=None):
    """Create a node in a tree, or return the existing one it stands for.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree in which to create the node.
    node_type : str
        Node type identifier (``bl_idname``).
    location : tuple of float, optional
        Position of the node in the editor, by default ``(0, 0)``.
    name : str, optional
        Name given to the node. With a name, the node called ``name`` is
        reused when it has this type, which lets a tree hold several nodes
        of one type. Without one, the first node of this type is reused and
        it keeps Blender's default name.

    Returns
    -------
    bpy.types.Node
        The created or existing node, moved to ``location``.
    """
    if name is None:
        node = next((n for n in node_tree.nodes if n.bl_idname == node_type), None)
    else:
        node = node_tree.nodes.get(name)
        if node is not None and node.bl_idname != node_type:
            node = None  # the name belongs to another kind of node
    if node is None:
        node = node_tree.nodes.new(node_type)
        if name is not None:
            node.name = name
    node.location = location
    return node


def create_blenderncnodetree(nodetree_name, node_type="BlenderNCNodeTree"):
    """Return the node group with the given name, creating it if needed.

    Parameters
    ----------
    nodetree_name : str
        Name of the node group.
    node_type : str, optional
        Tree type used when creating, by default ``"BlenderNCNodeTree"``.

    Returns
    -------
    bpy.types.NodeTree
        The existing or newly created node group.
    """
    if nodetree_name in bpy.data.node_groups:
        nodetree = bpy.data.node_groups.get(nodetree_name)
    else:
        nodetree = bpy.data.node_groups.new(nodetree_name, node_type)
    return nodetree


def _row_locations(count, spread=300):
    """Evenly spaced ``(x, 0)`` positions from ``-spread`` to ``spread``."""
    if count < 2:
        return [(0, 0)] * count
    step = 2 * spread / (count - 1)
    return [(-spread + i * step, 0) for i in range(count)]


def _ensure_geometry_interface(node_tree):
    """Give a geometry node tree its ``Geometry`` input and output sockets once."""
    if node_tree.interface.items_tree:
        return
    for in_out in ("INPUT", "OUTPUT"):
        node_tree.interface.new_socket(
            name="Geometry", in_out=in_out, socket_type="NodeSocketGeometry"
        )


def create_nodes(node_tree, nodes, locations=None):
    """Create the nodes of a mapping, or return those that already exist.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree in which to create the nodes. A geometry node tree also gets a
        group output node and ``Geometry`` interface sockets.
    nodes : dict
        Mapping of identifier to a dict describing one node. The identifier
        is the node type (``bl_idname``) unless the dict has a ``"type"``
        entry; then the identifier is a free name and becomes the node's
        name, so two entries may share a type::

            {
                "ShaderNodeAttribute": {"links": {"Fac": {"Low": "Value"}}},
                "Low": {"type": "ShaderNodeMapRange", "links": {...}},
                "High": {"type": "ShaderNodeMapRange"},
            }

        ``"links"`` is described in :func:`create_links` and refers to other
        entries by their identifier. Each entry is updated in place with the
        created ``"node"``.
    locations : list of tuple, optional
        One ``(x, y)`` position per node, in mapping order. By default the
        nodes are spread along a row.

    Returns
    -------
    dict
        The same ``nodes`` mapping, populated with node references.
    """
    if node_tree.bl_idname == "GeometryNodeTree":
        nodes.setdefault("NodeGroupOutput", {"links": {}})
        _ensure_geometry_interface(node_tree)

    if locations is None:
        locations = _row_locations(len(nodes))

    for (key, entry), location in zip(nodes.items(), locations, strict=True):
        node_type = entry.get("type", key)
        name = key if "type" in entry else None
        entry["node"] = create_node(node_tree, node_type, location, name)

    return nodes


def create_links(node_tree, nodes):
    """Create the links described in a node mapping.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding the nodes.
    nodes : dict
        Mapping of identifier to a dict with a ``"node"`` reference and an
        optional ``"links"`` entry of the form
        ``{output_socket_name: {target_identifier: input_socket_name}}``,
        where identifiers are the keys of ``nodes`` (see :func:`create_nodes`).
    """
    for key, value in nodes.items():
        if "links" in value:
            for output_name, input_name in value["links"].items():
                for input_node, socket in input_name.items():
                    create_link(
                        node_tree,
                        nodes[key]["node"],
                        nodes[input_node]["node"],
                        output_name,
                        socket,
                    )


def create_link(node_tree, node_out, node_in, output_name, input_name):
    """Link two sockets by name unless that link exists or a socket is missing.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node providing the output socket.
    node_in : bpy.types.Node
        Node receiving the link on an input socket.
    output_name : str
        Name of the output socket on ``node_out``.
    input_name : str
        Name of the input socket on ``node_in``.
    """
    out_socket = node_out.outputs.get(output_name)
    in_socket = node_in.inputs.get(input_name)
    if out_socket is None or in_socket is None:
        return
    if not does_link_exists(node_tree, node_out, node_in, output_name, input_name):
        node_tree.links.new(out_socket, in_socket)


def does_link_exists(node_tree, node_out, node_in, output_name, input_name):
    """Check whether a link between two named sockets exists.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node providing the output socket.
    node_in : bpy.types.Node
        Node receiving the link.
    output_name : str
        Name of the output socket on ``node_out``.
    input_name : str
        Name of the input socket on ``node_in``.

    Returns
    -------
    bool
        ``True`` if such a link exists.
    """
    for link in node_tree.links:
        if (
            link.from_node == node_out
            and link.to_node == node_in
            and link.from_socket.name == output_name
            and link.to_socket.name == input_name
        ):
            return True
    return False


def delete_link(node_tree, node_out, node_in, input_name):
    """Remove the link from ``node_out`` into a named input of ``node_in``.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node on the output side of the link.
    node_in : bpy.types.Node
        Node on the input side of the link.
    input_name : str
        Name of the input socket on ``node_in`` to disconnect.
    """
    for link in list(node_tree.links):
        if (
            link.from_node == node_out
            and link.to_node == node_in
            and link.to_socket.name == input_name
        ):
            node_tree.links.remove(link)


def sync_string_outputs(node, names):
    """Make ``node``'s outputs one string socket per name, in that order.

    Sockets whose name is still listed keep their links and value; the others
    are removed with their links, and missing ones are added with the name as
    their value. A node fed a new dataset thus shows that dataset's names
    only, instead of appending them to the previous ones.

    Parameters
    ----------
    node : bpy.types.Node
        Node whose outputs are synced.
    names : list of str
        Output names, in the order they should appear.
    """
    for socket in [socket for socket in node.outputs if socket.name not in names]:
        node.outputs.remove(socket)
    present = {socket.name for socket in node.outputs}
    for name in names:
        if name not in present:
            node.outputs.new("NodeSocketString", name).default_value = name
    _order_outputs(node, names)


def _order_outputs(node, names):
    """Move ``node``'s outputs, all named in ``names``, into that order."""
    for position, name in enumerate(names):
        current = [socket.name for socket in node.outputs].index(name)
        if current != position:
            node.outputs.move(current, position)


def disconnect_links(node_tree, node):
    """Remove every link attached to a node.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding the node.
    node : bpy.types.Node
        Node whose incoming and outgoing links are removed.
    """
    for link in list(node_tree.links):
        if link.from_node == node or link.to_node == node:
            node_tree.links.remove(link)
