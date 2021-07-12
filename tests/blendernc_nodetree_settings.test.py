import os
import sys
import unittest
from io import StringIO

import bpy
import test_utils as tutils


@tutils.refresh_state
def create_nodes(file, var):
    node_groups = bpy.data.node_groups
    if tutils.is_blendernc_in_nodetree(node_groups):
        node_groups.remove(node_groups["BlenderNC"])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    # Create nodes
    nodes = ["netCDFPath", "netCDFNode", "netCDFResolution", "netCDFOutput"]

    node_names = tutils.create_nodes(nodes)

    node_tree = bpy.data.node_groups["BlenderNC"]
    existing_nodes = [node_tree.nodes[node] for node in node_names]
    # Now let's change properties.
    props = tutils.build_dict_blendernc_prop(existing_nodes)

    props["netCDF Path"]["blendernc_file"] = file
    props["netCDF input"]["blendernc_netcdf_vars"] = var
    props["Resolution"]["bendernc_resolution"] = 80
    props["Output"]["update_on_frame_change"] = True

    tutils.join_nodes(node_tree, existing_nodes, props)

    # Create new image
    bpy.ops.image.new(
        name="BlenderNC_default",
        width=1024,
        height=1024,
        color=(0.0, 0.0, 0.0, 1.0),
        alpha=True,
        generated_type="BLANK",
        float=True,
    )

    # Assign new image to node
    existing_nodes[-1].image = bpy.data.images.get("BlenderNC_default")


class Capturing(list):
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout


class Test_translation(unittest.TestCase):
    def setUp(self) -> None:
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        create_nodes(file, var)
        return super().setUp()

    def test_animation_setting_extend(self):
        bpy.context.scene.blendernc_animation_type = "EXTEND"
        frames = [3, 4, 5]
        loaded_frames = []
        for frame in frames:
            with Capturing() as output:
                bpy.context.scene.frame_set(frame)
            if output:
                loaded_frames.append(int(output[-3].split(" ")[-2]))
            print("\n".join(output))
        self.assertEqual(loaded_frames, [3, 4, 4])

    def test_animation_setting_none(self):
        loaded_frames = []
        bpy.context.scene.blendernc_animation_type = "NONE"
        frames = [3, 4, 5]
        for frame in frames:
            with Capturing() as output:
                bpy.context.scene.frame_set(frame)
            if output:
                loaded_frames.append(int(output[-3].split(" ")[-2]))
            print("\n".join(output))
        # self.assertEqual(loaded_frames, [3,4])

    def test_animation_setting_loop(self):
        loaded_frames = []
        bpy.context.scene.blendernc_animation_type = "LOOP"
        frames = [3, 4, 5]
        for frame in frames:
            with Capturing() as output:
                bpy.context.scene.frame_set(frame)
            if output:
                loaded_frames.append(int(output[-3].split(" ")[-2]))
            print("\n".join(output))
        self.assertEqual(loaded_frames, [3, 4, 0])

    def test_memory_frames(self):
        bpy.context.scene.blendernc_memory_handle = "FRAMES"
        bpy.context.scene.blendernc_frames = 1
        frames = [2, 3, 4]
        removed_frames = []
        for frame in frames:
            with Capturing() as output:
                bpy.context.scene.frame_set(frame)
            if "Removed" in output[-1]:
                removed_frames.append(int(output[-1].split(": ")[-1]))
            print("\n".join(output))
        self.assertEqual(removed_frames, [2, 3])

    def test_memory_dynamic(self):
        bpy.context.scene.blendernc_memory_handle = "DYNAMIC"
        bpy.context.scene.blendernc_avail_mem_purge = 70
        frames = [2, 3, 4]
        removed_frames = []
        for frame in frames:
            with Capturing() as output:
                bpy.context.scene.frame_set(frame)
            if "Removed" in output[-1]:
                removed_frames.append(int(output[-1].split(": ")[-1]))
            print("\n".join(output))
        self.assertEqual(removed_frames, [2, 3])


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_translation)
unittest.TextTestRunner().run(suite)
