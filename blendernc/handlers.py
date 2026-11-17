#!/usr/bin/env python3
import bpy
from bpy.app.handlers import persistent
from bpy_extras import anim_utils

from .node_utils import get_all_nodes_by_idname
from .utils import UI_NODE_TREE, UI_STEP_NODE, update_step_UI
from .volume_utils import FRAMES_LIVE, write_live_frame


@persistent
def bNC_update_attributes(scene):
    """Write the current frame of each animated variable onto its mesh.

    Registered as a ``frame_change_pre`` and ``render_pre`` handler. Every
    "Datacube Animate Texture" node writes the step of its variable shown at
    ``scene.frame_current`` into the point attribute named after the
    variable (see :meth:`blendernc.nodes.DatacubeAnimateTexture.write_frame`).
    Half-connected or refused nodes are skipped, so playback never breaks.

    Parameters
    ----------
    scene : bpy.types.Scene
        Scene whose ``frame_current`` selects the slice.
    """
    for node in get_all_nodes_by_idname("BlenderNCNodeAnimateTexture"):
        node.write_frame(scene.frame_current)


@persistent
def bNC_update_volumes(scene):
    """Show the current frame on every volume baked in "Current frame" mode.

    Registered as a ``frame_change_pre`` and ``render_pre`` handler. Volumes
    baked with "Bake all frames" are VDB sequences that Blender plays on its
    own, so only Datacube Volume nodes in ``LIVE`` mode are visited.

    Parameters
    ----------
    scene : bpy.types.Scene
        Scene whose ``frame_current`` selects the frame.
    """
    for node in get_all_nodes_by_idname("BlenderNCNodeVolume"):
        if node.frame_mode == FRAMES_LIVE:
            write_live_frame(node, scene.frame_current)


# Path of the sidebar panel's step, relative to the scene.
PANEL_STEP_PATH = "BlenderNC_UI_Properties.step"


def _fcurves(id_data):
    """F-curves of the action assigned to ``id_data``, or an empty list."""
    anim = id_data.animation_data
    if anim is None or anim.action is None or anim.action_slot is None:
        return []
    bag = anim_utils.action_get_channelbag_for_slot(anim.action, anim.action_slot)
    return list(bag.fcurves) if bag else []


def is_animated(id_data, data_path):
    """True when ``data_path`` on ``id_data`` has an F-curve or a driver."""
    anim = id_data.animation_data
    if anim is not None and anim.drivers.find(data_path) is not None:
        return True
    return any(fcurve.data_path == data_path for fcurve in _fcurves(id_data))


def _apply_panel_step(scene):
    """Push an animated panel step to the resolution node; True if it changed.

    The scene is evaluated by Blender, so the panel value is already the
    animated one; only its update callback was skipped.
    """
    props = getattr(scene, "BlenderNC_UI_Properties", None)
    tree = bpy.data.node_groups.get(UI_NODE_TREE)
    node = tree.nodes.get(UI_STEP_NODE) if tree else None
    if props is None or node is None or not is_animated(scene, PANEL_STEP_PATH):
        return False
    changed = node.step != props.step
    update_step_UI(props, bpy.context)
    return changed


def _write_animated_value(tree, fcurve, frame):
    """Write one F-curve's value at ``frame`` so update callbacks run.

    Only scalar int, float and bool properties are handled; vectors, colours
    and enums are left alone. Returns ``True`` when the value changed.
    """
    owner_path, _, name = fcurve.data_path.rpartition(".")
    try:
        owner = tree.path_resolve(owner_path) if owner_path else tree
        current = getattr(owner, name)
    except (ValueError, AttributeError):
        return False
    if not isinstance(current, (bool, int, float)):
        return False
    raw = fcurve.evaluate(frame)
    value = raw if isinstance(current, float) else type(current)(round(raw))
    if value == current:
        return False
    setattr(owner, name, value)
    return True


def _apply_node_tree_animation(scene):
    """Evaluate keyframes on BlenderNC node trees; True if a value changed.

    These trees are not used by anything in the scene, so Blender never
    evaluates their animation; it is done here instead.
    """
    changed = False
    for tree in bpy.data.node_groups:
        if tree.bl_idname != "BlenderNCNodeTree":
            continue
        for fcurve in _fcurves(tree):
            changed |= _write_animated_value(tree, fcurve, scene.frame_current)
    return changed


@persistent
def bNC_apply_animated_steps(scene, depsgraph=None):
    """Apply keyframed values as if the user had typed them.

    Registered as a ``frame_change_post`` handler. A keyframed panel step is
    written by Blender without running its update callback, and keyframes on
    BlenderNC node trees are not evaluated at all; both are applied here, so
    the resolution node updates, the grid rebakes itself and animated
    textures are rewritten for the new mesh.

    Parameters
    ----------
    scene : bpy.types.Scene
        Scene whose frame changed.
    depsgraph : bpy.types.Depsgraph, optional
        Passed by Blender; unused.
    """
    panel_changed = _apply_panel_step(scene)
    if _apply_node_tree_animation(scene) or panel_changed:
        bNC_update_attributes(scene)
