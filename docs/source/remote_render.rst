================
Remote rendering
================

Blender and **BlenderNC** can be executed in background mode and remotely.

.. important::
    There are some limitations due to Blender when applying modifiers.

First, make sure Blender and BlenderNC are properly installed in the remote server. If the system has a GUI follow the normal instructions to install **BlenderNC**, otherwise, link or copy the addon to the default Blender addon path, both options can be found at :ref:`install_blendernc`.

.. note::
    Make sure to install the required modules ``xarray, numpy, etc.``.

.. toctree::
    :maxdepth: 1
    :caption: BlenderNC background mode!

    background


.. toctree::
    :maxdepth: 1
    :caption: HPC system

    nci