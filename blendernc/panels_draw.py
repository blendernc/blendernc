#!/usr/bin/env python3
from .node_utils import create_blenderncnodetree


def draw_var_and_coords(self, context):
    scene = context.scene
    UI_props = scene.BlenderNC_UI_Properties
    node_tree = create_blenderncnodetree("BLENDERNC")
    # Select variables menu

    self.layout.label(text="Select coords:", icon="WORLD_DATA")
    coord_node = node_tree.nodes.get("Datacube Coords")
    coords = [
        (output_socket.name, output_socket.name, "", index)
        for index, output_socket in enumerate(coord_node.outputs)
    ]
    expand = True if len(coords) <= 3 else False
    split = self.layout.split(factor=0.05)
    row = split.row()
    row.label(text="X:")
    row = split.row()
    row.prop(UI_props, "X", expand=expand)
    split = self.layout.split(factor=0.05)
    row = split.row()
    row.label(text="Y:")
    row = split.row()
    row.prop(UI_props, "Y", expand=expand)
    split = self.layout.split(factor=0.05)
    row = split.row()
    row.label(text="Z:")
    row = split.row()
    row.prop(UI_props, "Z", expand=expand)

    # self.layout.label(text=", ".join(coords), icon="WORLD_DATA")

    self.layout.label(text="Select variable:", icon="WORLD_DATA")
    self.layout.prop(UI_props, "variable", text="")
