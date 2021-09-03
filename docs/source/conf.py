# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

# sys.path.append(os.path.abspath(".."))
sys.path.append(os.path.abspath("../../"))
sys.path.append(os.path.abspath("../../blendernc"))

# -- Project information -----------------------------------------------------

project = "blendernc"
copyright = "2021, BlenderNC"
author = "Josue Martinez-Moreno"

# The full version, including alpha/beta/rc tags
release = "0.4.9"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinxcontrib.yt",
    "sphinx.ext.autosectionlabel",
    "numpydoc",
    # "sphinx_autodoc_typehints",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The root document.
root_doc = "index"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# suppress_warnings = True

# Mock bpy import
autodoc_mock_imports = [
    "bpy",
    "nodeitems_utils",
    "nodeitems_builtins",
    "addon_utils",
    "bpy_extras",
    "addon_updater_ops",
]

autosummary_generate = True

numpydoc_show_class_members = False

autodoc_typehints = "description"  # show type hints in doc body instead of signature
autoclass_content = "both"  # get docstring from class level and init simultaneously
