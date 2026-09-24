import bpy

from .nodes import (
    DatacubeAnimateTexture,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeImport,
    DatacubeSelect,
    DatacubeSlice,
    DatacubeVariable,
    DebugNode,
)


class BlenderNCNodeMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_category_blendernc"
    bl_label = "BlenderNC"

    def draw(self, context):
        self.layout.menu(BlenderNCNodeImport.bl_idname)
        self.layout.separator()
        self.layout.menu(BlenderNCNodeSelection.bl_idname)
        self.layout.menu(BlenderNCNodeGrid.bl_idname)
        self.layout.menu(BlenderNCNodeAnimate.bl_idname)
        self.layout.separator()
        self.layout.operator("node.add_node", text="Debug Node").type = (
            DebugNode.bl_idname
        )


class BlenderNCNodeImport(bpy.types.Menu):
    bl_idname = "NODE_MT_category_blendernc_import"
    bl_label = "Import"

    def draw(self, context):
        self.layout.operator("node.add_node", text="Datacube Import").type = (
            DatacubeImport.bl_idname
        )
        self.layout.operator("node.add_node", text="Datacube Variables").type = (
            DatacubeVariable.bl_idname
        )
        # self.layout.separator()


class BlenderNCNodeGrid(bpy.types.Menu):
    bl_idname = "NODE_MT_category_blendernc_grid"
    bl_label = "Grid"

    def draw(self, context):
        self.layout.operator("node.add_node", text="Datacube Coords").type = (
            DatacubeCoords.bl_idname
        )

        self.layout.operator("node.add_node", text="Datacube Grid").type = (
            DatacubeGrid.bl_idname
        )


class BlenderNCNodeSelection(bpy.types.Menu):
    bl_idname = "NODE_MT_category_blendernc_selection"
    bl_label = "Selection"

    def draw(self, context):
        self.layout.operator("node.add_node", text="Select Variable").type = (
            DatacubeVariable.bl_idname
        )
        self.layout.operator("node.add_node", text="Select Index").type = (
            DatacubeSelect.bl_idname
        )
        self.layout.operator("node.add_node", text="Slice Coordinate").type = (
            DatacubeSlice.bl_idname
        )


class BlenderNCNodeAnimate(bpy.types.Menu):
    bl_idname = "NODE_MT_category_blendernc_animate"
    bl_label = "Animate"

    def draw(self, context):
        self.layout.operator("node.add_node", text="Animate Texture").type = (
            DatacubeAnimateTexture.bl_idname
        )


def add_custom_node_to_menu(self, context):
    space = context.space_data
    if space.type == "NODE_EDITOR":  # and space.tree_type == "BlenderNCNodeTree":
        self.layout.separator()
        self.layout.menu(BlenderNCNodeMenu.bl_idname)
