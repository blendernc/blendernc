=================
Install BlenderNC
=================

.. note::
    BlenderNC is supported by versions of **Blender > 2.8**.

Setting up the Blender Python environment
=========================================

BlenderNC requires the following python modules to be installed in Blender's Python environment:

.. code-block:: python
    
    xarray
    xgcm
    cmocean
    matplotlib


To install the previous python modules in your Blender distribution execute the 
following commands depending on your OS:

macOS
-----

.. code-block:: bash

    cd /Applications/Blender.app/Contents/Resources/2.83/python/bin/
    ./python3.7m -m ensurepip
    ./python3.7m -m pip install xarray xgcm cmocean matplotlib scipy toolz netcdf4

Linux
-----

.. code-block:: bash

    cd /path/to/blender/2.83/python/bin/
    ./python3.7m -m ensurepip
    ./python3.7m -m pip install xarray xgcm cmocean matplotlib scipy toolz netcdf4

Windows
-------

.. code-block:: bash

    cd /path/to/blender/2.82/python/bin/
    python.exe -m ensurepip
    python.exe -m pip install xarray xgcm cmocean matplotlib scipy toolz netcdf4

Install Addon
=============

The addon is installed just like any other Blender addon:

* Download the open-source addon from the `GitHub <https://github.com/blendernc/blendernc>`_, 
  or download the `current version zip <https://github.com/blendernc/blendernc/archive/master.zip>`_ 
  (do not unzip it! Under macOS you might have to select "Download Linked File As..." to avoid automatic unzip).

* In Blender go to the user preferences and open the **Addons** tab.

* Once there, click **Install add-on from file** (bottom right corner)

* Navigate to the downloaded zip, select it, and click in install.

* Finally, check the box next to `BlenderNC` is enable.


.. image:: ../images/addon_settings.png
  :width: 80%
  :alt: Install Addon

Now you can follow the tutorials to import netCDFs into blender. 


Update BlenderNC
================

It is recommended to uninstall the old version first, before installing the new version of `BlenderNC`. Alternatively, 
enable the "Overwrite" option in Blender (enabled by default), before you navegate to the new addon zip file using the Blender's 
file explorer. Finally, restart Blender once the new version is installed.

Blender Compilation (optional)
==============================

Alternatively, to further configure Blender, you could install it using a `conda` environment 
by following the official `Blender installation website 
<https://wiki.blender.org/index.php/Dev:Doc/Building_Blender/>`_.

Create conda environment:

.. code-block:: bash

    conda create --prefix ~/path/to/python/root python=3.7
    conda activate ~/path/to/python/root
    conda install --file ./requirements.txt

Compile Blender:

.. code-block:: bash
    
    cmake -DPYTHON_VERSION=3.7  -DPYTHON_ROOT_DIR=~/path/to/python/root ../blender 

.. note::
    Make sure to use the same python version.

Another **not recomended** option is to symbolically link your python modules to blender:

On **macOS**, find the folder `modules` within the blender.app:

.. code-block:: bash

    cd /Applications/blender.app/Contents/Resources/2.8x/scripts/modules

Then link all the packages from your python environment folder:

.. code-block:: bash

    ln -s $PATH_PYTHON/lib/python3.6/site-packages/* .