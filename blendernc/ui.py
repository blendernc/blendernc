"""Callbacks behind the BlenderNC 3D view panel.

The panel drives a node tree of its own, :data:`~blendernc.node_utils.UI_NODE_TREE`,
built by :func:`build_ui_tree` from ``basic_nodes``. The scene properties in
:class:`blendernc.properties.BlenderNC_UI_Properties` call the functions
here when the user picks a file, the axes or a variable; they link the
matching nodes, bake the grid and show or hide the panel sections drawn by
:mod:`blendernc.panels_draw`.
"""

import glob

import bpy

from .messages import report_error
from .node_utils import (
    UI_COORDS_NODE,
    UI_GRID_NODE,
    UI_IMPORT_NODE,
    UI_NODE_TREE,
    UI_TEXTURE_NODE,
    UI_VARIABLE_NODE,
    basic_nodes,
    create_blenderncnodetree,
    create_link,
    create_links,
    create_nodes,
    delete_link,
    disconnect_links,
    locations,
)
from .panels_draw import (
    draw_resolution_grid_and_texture,
    draw_var_and_coords,
    show_section,
)
from .utils import (
    NO_SELECTION,
    assign_material,
    coordinate_items,
    empty_item,
    get_dataset,
    get_possible_variables,
    grid_material,
    keep_enum_items,
)

# A grid needs at least two axes (see get_2D_coords).
MIN_GRID_AXES = 2


# --------------------------------------------------------------------------
# Panel tree and file
# --------------------------------------------------------------------------


def build_ui_tree(context, owner=None):
    """Build the panel's node tree and load the panel's file into it.

    Creates the import, coordinate, variable, grid and texture nodes when
    missing. When the panel's path is empty or matches no file, the import
    node is disconnected and the variable/coordinate section is removed;
    otherwise the path goes to the import node, the nodes are linked and the
    section is drawn.

    Parameters
    ----------
    context : bpy.types.Context
        Current Blender context.
    owner : object, optional
        Operator or property group to report a missing file to; see
        :func:`blendernc.messages.report_error`.

    Returns
    -------
    bpy.types.Node
        The "Datacube Import" node of the tree.
    """
    datacube_file = context.scene.BlenderNC_UI_Properties.datacube_file
    node_tree = create_blenderncnodetree(UI_NODE_TREE)
    nodes = create_nodes(node_tree, basic_nodes, locations)
    import_node = node_tree.nodes.get(UI_IMPORT_NODE)
    if not datacube_file or not glob.glob(datacube_file):
        if datacube_file:
            report_error(owner, f"No file matches {datacube_file!r}.", "WARNING")
        disconnect_links(node_tree, import_node)
        show_section(draw_var_and_coords, False)
        return import_node
    import_node.datacube_file = datacube_file
    create_links(node_tree, nodes)
    show_section(draw_var_and_coords, True)
    return import_node


def update_datacube_file_UI(self, context):
    """Callback of the panel's path: rebuild the panel's tree around it."""
    build_ui_tree(context, self)


def use_import_node(operator, context):
    """Point the import operator at the node it should load into.

    The file browser on a Datacube Import node passes that node and its tree,
    whatever the tree is called, and both are kept. The 3D view panel passes
    neither, so the panel's tree is built and its import node is used. A
    script that names the panel's tree before it exists gets the same.

    Parameters
    ----------
    operator : bpy.types.Operator
        The import operator, with ``node_tree`` and ``node_name`` attributes.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = bpy.data.node_groups.get(operator.node_tree)
    if node_tree is not None and operator.node_name in node_tree.nodes:
        return
    if operator.node_tree in ("", UI_NODE_TREE):
        operator.node_tree = UI_NODE_TREE
        operator.node_name = build_ui_tree(context, operator).name


# --------------------------------------------------------------------------
# Enum items
# --------------------------------------------------------------------------


def _get_ui_node(label):
    """Return the node called ``label`` in the panel's node tree, or ``None``."""
    node_tree = create_blenderncnodetree(UI_NODE_TREE)
    return node_tree.nodes.get(label)


@keep_enum_items
def get_possible_variables_UI(self, context):
    """Enum items callback for the variable selector in the 3D view panel.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the enum.
    context : bpy.types.Context
        Current Blender context.

    Returns
    -------
    list of tuple
        Enum items from the "Datacube Variable" node of the ``BLENDERNC``
        tree, or a single empty item when the node or dataset is missing.
    """
    node = _get_ui_node(UI_VARIABLE_NODE)
    if node is None:
        return empty_item()
    return get_possible_variables(node, context)


@keep_enum_items
def get_possible_coordinates_UI(self, context):
    """Enum items callback for the X, Y and Z selectors in the 3D view panel.

    An unnamed ``NO_SELECTION`` entry comes first, so the user can unlink an
    axis, followed by the coordinates of the "Datacube Coords" node's
    dataset.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the enum.
    context : bpy.types.Context
        Current Blender context.

    Returns
    -------
    list of tuple
        Enum items, only the empty one without a node or dataset.
    """
    node = _get_ui_node(UI_COORDS_NODE)
    dataset = get_dataset(node.BNC_datastructs[0]) if node else None
    items = coordinate_items(dataset) if dataset is not None else []
    return empty_item("") + items


# --------------------------------------------------------------------------
# Axes, variable and texture
# --------------------------------------------------------------------------


def update_variable_UI(self, context):
    """Link the variable chosen in the 3D view panel to the texture node.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the ``variable`` enum.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = bpy.data.node_groups.get(UI_NODE_TREE)
    if node_tree is None or node_tree.nodes.get(UI_VARIABLE_NODE) is None:
        return
    sync_texture_section(self, node_tree)


def update_coords_links_UI(self, context):
    """Link or unlink coordinate outputs to the grid node from the panel enums.

    For each of ``X``, ``Y`` and ``Z``, the selected coordinate output of the
    "Datacube Coords" node is linked to the matching grid input, or the
    existing link is removed when ``NO_SELECTION`` is selected.

    Parameters
    ----------
    self : BlenderNC_UI_Properties
        Property group owning the axis enums.
    context : bpy.types.Context
        Current Blender context.
    """
    node_tree = create_blenderncnodetree(UI_NODE_TREE)
    coord_node = node_tree.nodes.get(UI_COORDS_NODE)
    grid_node = node_tree.nodes.get(UI_GRID_NODE)
    if not coord_node or not grid_node:
        return

    for axis in ("X", "Y", "Z"):
        selected = getattr(self, axis)
        if selected == NO_SELECTION:
            delete_link(node_tree, coord_node, grid_node, axis)
        else:
            create_link(node_tree, coord_node, grid_node, selected, axis)
    sync_texture_section(self, node_tree)


def _enough_axes(UI_props):
    """True when the panel has enough axes selected to bake a grid."""
    axes = [getattr(UI_props, axis) for axis in ("X", "Y", "Z")]
    selected_axes = [axis for axis in axes if axis and axis != NO_SELECTION]
    return len(selected_axes) >= MIN_GRID_AXES


def sync_texture_section(UI_props, node_tree):
    """Show the resolution/texture section and wire the texture when ready.

    The section, the grid bake and the texture links only make sense once
    both a variable and the coordinates are chosen; otherwise the section is
    hidden and the texture node is unlinked. Called from both the variable
    and the coordinate selectors, since either may be chosen last. The grid
    is only baked when its coordinates or step changed: picking another
    variable relinks the texture and swaps the material, the mesh stays.
    The texture is linked to the variable node's output carrying the chosen
    variable (see :meth:`blendernc.nodes.DatacubeVariable.pick`).
    """
    var_node = node_tree.nodes.get(UI_VARIABLE_NODE)
    grid_node = node_tree.nodes.get(UI_GRID_NODE)
    texture_node = node_tree.nodes.get(UI_TEXTURE_NODE)
    if var_node is None:
        return
    variable_output = var_node.pick(UI_props.variable)
    ready = variable_output is not None and _enough_axes(UI_props)
    show_section(draw_resolution_grid_and_texture, ready)
    if grid_node is None or texture_node is None:
        return
    if not ready:
        delete_link(node_tree, var_node, texture_node, "Variable")
        delete_link(node_tree, grid_node, texture_node, "Object")
        return
    _bake_ui_grid(node_tree, grid_node)
    create_link(node_tree, grid_node, texture_node, "Object", "Object")
    create_link(node_tree, var_node, texture_node, variable_output.name, "Variable")
    _follow_variable_material(grid_node)


def _bake_ui_grid(node_tree, grid_node):
    """Bake the panel's grid when its coordinates or step changed.

    A failed bake has already been reported and logged by the operator,
    which ``bpy.ops`` turns into a ``RuntimeError``; it must not escape the
    property callback that called this.
    """
    if not any(socket.is_linked for socket in grid_node.inputs):
        return
    if not grid_node.needs_bake():
        return
    try:
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid_node.name, node_tree=node_tree.name
        )
    except RuntimeError:
        pass


def _follow_variable_material(grid_node):
    """Give the panel's grid the material of the variable now linked.

    A bake does this through the Set Material node; without a bake the
    first material slot is set here instead: the material named after the
    texture's variable, as made by "Apply Material", or none.
    """
    obj = bpy.data.objects.get(grid_node.baked_object)
    if obj is not None and obj.type == "MESH":
        assign_material(obj.data, grid_material(grid_node))
