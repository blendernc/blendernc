"""Shader helpers: the default texture material and colormap utilities.

Merges the colormap utilities that lived in ``utils_colorramp.py`` on the
``master`` branch. Colormaps are identified by a ``"name:library"`` string,
for example ``"thermal:cmocean"``, and written onto a Color Ramp whose
first element (at 0.0) is the fill value: missing data is written as 0 by
:func:`blendernc.utils.write_point_attribute`, so it lands on that colour.
"""

import importlib
import importlib.util

import bpy
import numpy as np

from .node_utils import create_links, create_nodes

basic_shader_nodes = {
    "Attribute": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "Value",
            }
        },
    },
    "Attribute.001": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "From Max",
            }
        },
    },
    "Attribute.002": {
        "type": "ShaderNodeAttribute",
        "links": {
            "Color": {
                "ShaderNodeMapRange": "From Min",
            }
        },
    },
    "ShaderNodeMapRange": {
        "links": {
            "Result": {
                "ShaderNodeValToRGB": "Factor",
            }
        }
    },
    "ShaderNodeValToRGB": {
        "links": {
            "Color": {
                "ShaderNodeBsdfPrincipled": "Base Color",
            }
        }
    },
    "ShaderNodeBsdfPrincipled": {},
    "ShaderNodeOutputMaterial": {},
}

shader_locations = [
    (-500, 200),
    (-500, -200),
    (-500, 0),
    (-300, 0),
    (-100, 0),
    (200, 0),
    (500, 0),
]


# --------------------------------------------------------------------------
# Colormap libraries
# --------------------------------------------------------------------------

# Libraries searched for colormaps, in menu order; missing ones are skipped.
COLORMAP_LIBRARIES = ("cmocean", "colorcet", "matplotlib")

# The colormap starts just above 0 so that 0 itself shows the fill colour.
FILL_VALUE_POSITION = 1e-5

COLORMAP_SEPARATOR = ":"


def _cmocean_names(module):
    return list(module.cm.cmapnames)


def _colorcet_names(module):
    return [name for name in module.cm_n if not name.endswith("_r")]


def _matplotlib_names(module):
    # cmocean registers its maps in matplotlib as "cmo.<name>"; they are
    # already listed under cmocean.
    return sorted(
        name
        for name in module.colormaps
        if not name.endswith("_r") and not name.startswith("cmo.")
    )


def _cmocean_lookup(module, name):
    return module.cm.cmap_d[name]


def _colorcet_lookup(module, name):
    return module.cm_n[name]


def _matplotlib_lookup(module, name):
    return module.colormaps[name]


# library -> (list the colormap names, look one colormap up by name)
_LIBRARY_API = {
    "cmocean": (_cmocean_names, _cmocean_lookup),
    "colorcet": (_colorcet_names, _colorcet_lookup),
    "matplotlib": (_matplotlib_names, _matplotlib_lookup),
}


def installed_colormap_libraries():
    """Names from :data:`COLORMAP_LIBRARIES` that can be imported."""
    return [lib for lib in COLORMAP_LIBRARIES if importlib.util.find_spec(lib)]


def available_colormaps():
    """Map each installed library to its colormap names, without ``_r`` copies.

    Returns
    -------
    dict
        ``{library: [name, ...]}`` in :data:`COLORMAP_LIBRARIES` order.
    """
    return {
        library: _LIBRARY_API[library][0](importlib.import_module(library))
        for library in installed_colormap_libraries()
    }


def get_colormap(library, name, reverse=False):
    """Return a matplotlib-style colormap: a callable from [0, 1] to RGBA.

    Parameters
    ----------
    library : str
        One of :data:`COLORMAP_LIBRARIES`.
    name : str
        Colormap name within ``library``.
    reverse : bool, optional
        Return the reversed colormap (``<name>_r``).
    """
    module = importlib.import_module(library)
    colormap = _LIBRARY_API[library][1](module, name)
    return colormap.reversed() if reverse else colormap


def encode_colormap(name, library):
    """Return the ``"name:library"`` identifier stored by the Colormap node."""
    return f"{name}{COLORMAP_SEPARATOR}{library}"


def decode_colormap(identifier):
    """Split a ``"name:library"`` identifier into ``(name, library)``."""
    name, _, library = identifier.rpartition(COLORMAP_SEPARATOR)
    return name, library


def default_colormap():
    """Identifier of the first colormap of the first installed library."""
    for library, names in available_colormaps().items():
        if names:
            return encode_colormap(names[0], library)
    return ""


# --------------------------------------------------------------------------
# Color ramps
# --------------------------------------------------------------------------


def apply_colormap(color_ramp, colormap, n_stops, fill_color=(0.0, 0.0, 0.0, 1.0)):
    """Rebuild ``color_ramp`` with ``n_stops`` samples of ``colormap``.

    Element 0 sits at 0.0 and holds ``fill_color``. The colormap's stops
    follow, evenly spaced from :data:`FILL_VALUE_POSITION` to 1.0, so a ramp
    has ``n_stops + 1`` elements.

    Parameters
    ----------
    color_ramp : bpy.types.ColorRamp
        Ramp to rewrite.
    colormap : callable
        Maps a float in [0, 1] to an RGBA tuple, as returned by
        :func:`get_colormap`.
    n_stops : int
        Number of colormap samples.
    fill_color : sequence of float, optional
        RGBA colour for value 0 (missing data).
    """
    elements = color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    elements[0].position = 0.0
    elements[0].color = fill_color

    samples = np.linspace(0.0, 1.0, n_stops)
    positions = samples.copy()
    positions[0] = FILL_VALUE_POSITION
    for position, sample in zip(positions, samples):
        elements.new(float(position)).color = colormap(float(sample))


def set_fill_color(color_ramp, color):
    """Set the colour shown for missing data (element 0 of the ramp)."""
    color_ramp.elements[0].color = color


# --------------------------------------------------------------------------
# Colorbar
# --------------------------------------------------------------------------

# White, emissive material used for colorbar text.
UI_MATERIAL = "BlenderNC_info"

COLORBAR_MATERIAL_NODES = {
    "ShaderNodeTexCoord": {"links": {"Generated": {"ShaderNodeMapping": "Vector"}}},
    "ShaderNodeMapping": {"links": {"Vector": {"cmapsNode": "Factor"}}},
    "cmapsNode": {"links": {"Color": {"ShaderNodeEmission": "Color"}}},
    "ShaderNodeEmission": {
        "links": {"Emission": {"ShaderNodeOutputMaterial": "Surface"}}
    },
    "ShaderNodeOutputMaterial": {},
}

COLORBAR_MATERIAL_LOCATIONS = [
    (-760, 250),
    (-580, 250),
    (-290, 250),
    (0, 250),
    (250, 250),
]


def ui_material():
    """Return the white emissive material for colorbar text, creating it once."""
    material = bpy.data.materials.get(UI_MATERIAL)
    if material is None:
        material = bpy.data.materials.new(UI_MATERIAL)
        material.use_nodes = True
        bsdf = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    return material


def colorbar_material(name, colormap_node):
    """Return an emissive material showing ``colormap_node``'s colormap.

    The material is created or reused under ``name``. Its generated texture
    coordinates run through a Mapping node into a Colormap node with the same
    settings as ``colormap_node``, so a plane with this material reads as a
    vertical colorbar.

    Parameters
    ----------
    name : str
        Material name.
    colormap_node : BlenderNC_NT_colormap
        Colormap node whose settings are copied.
    """
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    for node in [n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"]:
        tree.nodes.remove(node)
    nodes = {key: dict(value) for key, value in COLORBAR_MATERIAL_NODES.items()}
    create_nodes(tree, nodes, COLORBAR_MATERIAL_LOCATIONS)
    create_links(tree, nodes)

    mapping = nodes["ShaderNodeMapping"]["node"]
    mapping.inputs["Location"].default_value = (0.0, -0.6, 0.0)
    mapping.inputs["Rotation"].default_value = (0.0, np.pi / 4, 0.0)
    mapping.inputs["Scale"].default_value = (1.0, 2.8, 1.0)

    colormap = nodes["cmapsNode"]["node"]
    for setting in ("n_stops", "fcmap", "fv_color", "colormaps"):
        setattr(colormap, setting, getattr(colormap_node, setting))
    return material


# Density-only volume material: the grid named after the variable, mapped
# from the object's "Min value"/"Max value" range onto 0-1 density.
VOLUME_MATERIAL_NODES = {
    "Attribute": {
        "type": "ShaderNodeAttribute",
        "links": {"Factor": {"ShaderNodeMapRange": "Value"}},
    },
    "Attribute.001": {
        "type": "ShaderNodeAttribute",
        "links": {"Factor": {"ShaderNodeMapRange": "From Max"}},
    },
    "Attribute.002": {
        "type": "ShaderNodeAttribute",
        "links": {"Factor": {"ShaderNodeMapRange": "From Min"}},
    },
    "ShaderNodeMapRange": {
        "links": {"Result": {"ShaderNodeVolumePrincipled": "Density"}}
    },
    "ShaderNodeVolumePrincipled": {
        "links": {"Volume": {"ShaderNodeOutputMaterial": "Volume"}}
    },
    "ShaderNodeOutputMaterial": {},
}

VOLUME_MATERIAL_LOCATIONS = [
    (-500, 200),
    (-500, -200),
    (-500, 0),
    (-250, 0),
    (0, 0),
    (300, 0),
]


def volume_material(grid_name):
    """Return the density-only material for a volume grid, creating it once.

    The material is called ``"<grid_name> volume"``. An Attribute node reads
    the grid, a Map Range node maps it from the object's ``"Min value"`` to
    ``"Max value"`` custom properties onto 0-1, and the result drives the
    density of a Principled Volume. Colour is left to the user.

    Parameters
    ----------
    grid_name : str
        Name of the VDB grid, the variable name.
    """
    name = f"{grid_name} volume"
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    for node in [n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"]:
        tree.nodes.remove(node)
    nodes = {key: dict(value) for key, value in VOLUME_MATERIAL_NODES.items()}
    create_nodes(tree, nodes, VOLUME_MATERIAL_LOCATIONS)
    create_links(tree, nodes)

    nodes["Attribute"]["node"].attribute_name = grid_name
    for key, prop in (("Attribute.001", "Max value"), ("Attribute.002", "Min value")):
        attribute = nodes[key]["node"]
        attribute.attribute_type = "OBJECT"
        attribute.attribute_name = prop
    return material


def _text_object(name, parent, size):
    """Create a centred text object parented to ``parent``, in its collection."""
    curve = bpy.data.curves.new(name, type="FONT")
    curve.size = size
    curve.align_y = "CENTER"
    curve.materials.append(ui_material())
    text = bpy.data.objects.new(name, curve)
    text.parent = parent
    collections = parent.users_collection or (bpy.context.collection,)
    collections[0].objects.link(text)
    return text


def add_splines(n, cbar_plane):
    """Add ``n + 1`` tick-label text objects beside a colorbar plane.

    The labels are spread from -1 to 1 along the plane's Y axis and their
    location is locked; set each object's ``data.body`` to the tick value.

    Returns
    -------
    list of bpy.types.Object
    """
    labels = []
    for position in np.round(np.linspace(-1.0, 1.0, n + 1), 2):
        label = _text_object(f"text_{cbar_plane.name}", cbar_plane, size=1.0)
        label.location = (1.4, float(position), 0.0)
        label.lock_location = (True, True, True)
        label.scale = (1.7, 0.12, 1.2)
        labels.append(label)
    return labels


def add_units(cbar_plane):
    """Add the units text object centred above a colorbar plane."""
    units = _text_object(f"text_units_{cbar_plane.name}", cbar_plane, size=1.5)
    units.data.align_x = "CENTER"
    units.location = (0.0, 1.18, 0.0)
    units.scale = (1.7, 0.12, 1.2)
    return units
