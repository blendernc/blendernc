#!/usr/bin/env python3
import bpy

from .node_utils import create_blenderncnodetree


def show_section(draw_func, show):
    """Append ``draw_func`` to the BlenderNC panel exactly once, or remove it.

    ``Panel.remove`` ignores functions that are not appended, so removing
    first keeps a single copy however often this is called. Checking
    ``Panel.is_extended()`` would not do: it is true as soon as *any* section
    is appended.
    """
    panel = bpy.types.BLENDERNC_UI_PT_3D_VIEW
    panel.remove(draw_func)
    if show:
        panel.append(draw_func)


def draw_var_and_coords(self, context):
    """Draw the coordinate (X, Y, Z) and variable selectors in the 3D view panel.

    Appended to ``BLENDERNC_UI_PT_3D_VIEW`` once a datacube has been loaded.
    The enums expand into radio buttons when there are three or fewer
    coordinates.

    Parameters
    ----------
    self : bpy.types.Panel
        Panel being drawn.
    context : bpy.types.Context
        Current Blender context.
    """
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

    self.layout.label(text="Select variable:", icon="WORLD_DATA")
    self.layout.prop(UI_props, "variable", text="")


def draw_resolution_grid_and_texture(self, context):
    """Draw the resolution, grid, and texture options in the 3D view panel.

    Appended to ``BLENDERNC_UI_PT_3D_VIEW`` once a datacube has been loaded.

    Parameters
    ----------
    self : bpy.types.Panel
        Panel being drawn.
    context : bpy.types.Context
        Current Blender context.
    """
    scene = context.scene
    UI_props = scene.BlenderNC_UI_Properties

    self.layout.label(text="Resolution and Grid:", icon="MOD_SUBSURF")
    node_tree = create_blenderncnodetree("BLENDERNC")
    step_node = node_tree.nodes.get("Datacube Resolution")
    if step_node is not None:
        row = self.layout.row(align=True)
        row.prop(step_node, "suggested_step", text="Suggest step")
        if step_node.suggested_step:
            row.label(text=f"Step {step_node.step}")
        else:
            row.prop(UI_props, "step", text="Step")
    else:
        self.layout.prop(UI_props, "step", text="Steps for coords")
    self.layout.operator("blendernc.bake_from_attribute", text="Apply Texture")
