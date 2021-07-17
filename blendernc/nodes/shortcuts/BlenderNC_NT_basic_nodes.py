#!/usr/bin/env python3
# Imports
import bpy


class BlenderNC_NT_basic_nodes(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeBasicNodes"
    # Label for nice name display
    bl_label = "Create Basic Nodes"
    blb_type = "NETCDF"

    def init(self, context):
        node_tree = self.rna_type.id_data
        path = node_tree.nodes.new("datacubePath")
        path.location = (-300, 0)
        inp = node_tree.nodes.new("datacubeNode")
        inp.location = (-100, 0)
        res = node_tree.nodes.new("datacubeResolution")
        res.location = (100, 0)
        out = node_tree.nodes.new("datacubeOutput")
        out.location = (300, 0)
        node_tree.nodes.remove(self)
