"""Render a datacube variable with BlenderNC without opening the Blender UI.

Usage (the arguments after ``--`` belong to this script, not to Blender)::

    blender -b --python render_datacube.py -- DATACUBE VARIABLE OUTPUT [options]

Example::

    blender -b --python render_datacube.py -- \\
        tests/dataset/ssh_1995-01.nc adt renders/ssh.png --step 4 --frame 0

Add ``--animate`` to render every index of the animated coordinate (for
example ``time``) as a numbered image sequence under OUTPUT.
"""

import argparse
import sys

import bpy


def parse_args():
    """Read the arguments that follow ``--`` on the Blender command line."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datacube", help="path or glob pattern of the datacube")
    parser.add_argument("variable", help="variable to render")
    parser.add_argument("output", help="image path, or prefix with --animate")
    parser.add_argument("--x", default="longitude", help="coordinate for X")
    parser.add_argument("--y", default="latitude", help="coordinate for Y")
    parser.add_argument("--step", type=int, default=1, help="surface stride")
    parser.add_argument("--frame", type=int, default=0, help="index to render")
    parser.add_argument("--animate", action="store_true", help="render all")
    parser.add_argument("--vmin", type=float, default=-1.5)
    parser.add_argument("--vmax", type=float, default=1.5)
    parser.add_argument("--samples", type=int, default=16)
    return parser.parse_args(argv)


def build_node_tree(args):
    """Create the BlenderNC node tree and return the grid and animate nodes."""
    tree = bpy.data.node_groups.new("BLENDERNC", "BlenderNCNodeTree")
    import_node = tree.nodes.new("BlenderNCNodeImport")
    resolution = tree.nodes.new("BlenderNCNodeResolution")
    coords = tree.nodes.new("BlenderNCNodeCoords")
    variable = tree.nodes.new("BlenderNCNodeVariable")
    grid = tree.nodes.new("BlenderNCNodeGrid")
    animate = tree.nodes.new("BlenderNCNodeAnimateTexture")

    # Setting the path loads the dataset lazily through xarray.
    import_node.datacube_file = args.datacube

    # Stride the horizontal dimensions before any node reads the data.
    resolution.step = args.step
    datacube = "xarray datacube"
    tree.links.new(import_node.outputs[datacube], resolution.inputs[datacube])
    tree.links.new(resolution.outputs[datacube], coords.inputs[datacube])
    tree.links.new(resolution.outputs[datacube], variable.inputs[datacube])

    # The chosen variable becomes an output socket named after it.
    variable.datacube_vars = args.variable

    tree.links.new(coords.outputs[args.x], grid.inputs["X"])
    tree.links.new(coords.outputs[args.y], grid.inputs["Y"])

    # Bake the mesh, then let the grid node expose the object it created.
    grid.grid_obj_name = "Grid"
    bpy.ops.blendernc.create_grid_from_coords(node_name=grid.name, node_tree=tree.name)
    grid.update()

    tree.links.new(grid.outputs["Object"], animate.inputs["Object"])
    tree.links.new(variable.outputs[args.variable], animate.inputs["Variable"])
    return bpy.data.objects[grid.grid_obj_name]


def add_material(obj, variable, vmin, vmax):
    """Colour the mesh from the per-point attribute written by the handler."""
    mat = bpy.data.materials.new("BlenderNC")
    nodes, links = mat.node_tree.nodes, mat.node_tree.links

    attribute = nodes.new("ShaderNodeAttribute")
    attribute.attribute_name = variable
    remap = nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = vmin
    remap.inputs["From Max"].default_value = vmax
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.0, 0.1, 0.6, 1.0)
    ramp.color_ramp.elements[1].color = (0.9, 0.2, 0.0, 1.0)
    emission = nodes.new("ShaderNodeEmission")

    links.new(attribute.outputs["Fac"], remap.inputs["Value"])
    links.new(remap.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], nodes["Material Output"].inputs["Surface"])

    # The baked grid already has one empty material slot that every face uses,
    # so the material has to replace that slot rather than be appended.
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def setup_scene(obj, samples):
    """Remove the startup objects and frame the grid with a top-down camera."""
    scene = bpy.context.scene
    for name in ("Cube", "Light"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])

    camera = bpy.data.cameras.new("Camera")
    camera.type = "ORTHO"
    cam = bpy.data.objects.new("Camera", camera)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Centre an orthographic camera above the mesh; its height does not matter.
    lower, upper = obj.bound_box[0], obj.bound_box[6]
    cam.location = ((lower[0] + upper[0]) / 2, (lower[1] + upper[1]) / 2, 10)
    aspect = obj.dimensions.x / obj.dimensions.y
    scene.render.resolution_x = 1440
    scene.render.resolution_y = int(1440 / aspect)
    camera.ortho_scale = obj.dimensions.x

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.view_settings.view_transform = "Standard"
    return scene


def render(scene, args):
    """Render one frame, or the whole animated coordinate with ``--animate``."""
    scene.render.filepath = args.output
    if not args.animate:
        # frame_change_pre runs the BlenderNC handler, which writes the attribute.
        scene.frame_set(args.frame)
        bpy.ops.render.render(write_still=True)
        return
    scene.frame_start, scene.frame_end = 0, animated_length(args) - 1
    bpy.ops.render.render(animation=True)
    print(f"Rendered frames {scene.frame_start} to {scene.frame_end}")


def animated_length(args):
    """Number of indices along the coordinate that is not part of the grid."""
    import xarray as xr

    data = xr.open_mfdataset(args.datacube)[args.variable]
    others = [dim for dim in data.dims if dim not in (args.x, args.y)]
    return int(data.sizes[others[0]]) if others else 1


def main():
    """Entry point when run through ``blender -b --python``."""
    args = parse_args()
    obj = build_node_tree(args)
    add_material(obj, args.variable, args.vmin, args.vmax)
    scene = setup_scene(obj, args.samples)
    render(scene, args)


if __name__ == "__main__":
    main()
