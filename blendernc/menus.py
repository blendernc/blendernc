import bpy

from .nodes import (
    DatacubeAnimateTexture,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeImport,
    DatacubeResolution,
    DatacubeSelect,
    DatacubeSlice,
    DatacubeSubsample,
    DatacubeTexture,
    DatacubeVariable,
    DatacubeVolume,
    DebugNode,
)


class BlenderNCNodeImport(bpy.types.Menu):
    """ "Import" sub-menu with the datacube import and variable nodes."""

    bl_idname = "NODE_MT_category_blendernc_import"
    bl_label = "Import"

    def draw(self, context):
        """Draw the import node entries."""
        self.layout.operator("node.add_node", text="Datacube Import").type = (
            DatacubeImport.bl_idname
        )
        self.layout.operator("node.add_node", text="Datacube Variable").type = (
            DatacubeVariable.bl_idname
        )


class BlenderNCNodeGrid(bpy.types.Menu):
    """ "Grid" sub-menu with the coordinate, grid and volume nodes."""

    bl_idname = "NODE_MT_category_blendernc_grid"
    bl_label = "Grid"

    def draw(self, context):
        """Draw the grid node entries."""
        self.layout.operator("node.add_node", text="Datacube Coords").type = (
            DatacubeCoords.bl_idname
        )

        self.layout.operator("node.add_node", text="Datacube Grid").type = (
            DatacubeGrid.bl_idname
        )
        self.layout.operator("node.add_node", text="Datacube Volume").type = (
            DatacubeVolume.bl_idname
        )


class BlenderNCNodeSelection(bpy.types.Menu):
    """ "Selection" sub-menu with the variable, select, slice and resolution nodes."""

    bl_idname = "NODE_MT_category_blendernc_selection"
    bl_label = "Selection"

    def draw(self, context):
        """Draw the selection node entries."""
        self.layout.operator("node.add_node", text="Select Variable").type = (
            DatacubeVariable.bl_idname
        )
        self.layout.operator("node.add_node", text="Select Index").type = (
            DatacubeSelect.bl_idname
        )
        self.layout.operator("node.add_node", text="Slice Range").type = (
            DatacubeSlice.bl_idname
        )
        self.layout.operator("node.add_node", text="Subsample Coordinate").type = (
            DatacubeSubsample.bl_idname
        )
        self.layout.operator("node.add_node", text="Resolution").type = (
            DatacubeResolution.bl_idname
        )


class BlenderNCNodeTexture(bpy.types.Menu):
    """ "Texture" sub-menu with the static and animated texture nodes."""

    bl_idname = "NODE_MT_category_blendernc_texture"
    bl_label = "Texture"

    def draw(self, context):
        """Draw the texture node entries."""
        self.layout.operator("node.add_node", text="Texture").type = (
            DatacubeTexture.bl_idname
        )
        self.layout.operator("node.add_node", text="Animate Texture").type = (
            DatacubeAnimateTexture.bl_idname
        )


def add_custom_node_to_menu(self, context):
    """Append the BlenderNC menu to the node editor "Add" menu.

    Parameters
    ----------
    self : bpy.types.Menu
        The ``NODE_MT_add`` menu being drawn.
    context : bpy.types.Context
        Current Blender context; the menu is only added in a node editor.
    """
    space = context.space_data
    if space.type == "NODE_EDITOR" and space.tree_type == "BlenderNCNodeTree":
        self.layout.separator()
        self.layout.menu(BlenderNCNodeImport.bl_idname)
        self.layout.separator()
        self.layout.menu(BlenderNCNodeSelection.bl_idname)
        self.layout.menu(BlenderNCNodeGrid.bl_idname)
        self.layout.menu(BlenderNCNodeTexture.bl_idname)
        self.layout.separator()
        self.layout.operator("node.add_node", text="Debug Node").type = (
            DebugNode.bl_idname
        )
