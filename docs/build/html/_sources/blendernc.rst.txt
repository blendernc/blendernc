=========
BlenderNC
=========

**BlenderNC** is a Blender add-on that allows to import netCDF files into 
Blender. It allows 2D and 3D visualization and generation of scientific data 
animations. The main development of *BlenderNC* is currently focus in 
geo-spatial data (i.e. Oceanographic - Atmospheric data), however, the framework 
should support the load of any netCDF.

.. image:: ../images/GEBCO_blendernc.png
  :width: 100%
  :alt: GEBCO Bathymetry (5400x2700 pixels)

==============
Install Add-on
==============
** BlenderNC works in Blender > 2.83 **

BlenderNC requires the following python modules:

.. code-block:: python
    
    xarray
    xgcm
    cmocean
    matplotlib


To install the previous python modules in your Blender distribution execute the 
following commands depending on your OS:

MAC
###
.. code-block:: bash

    cd /Applications/Blender_2.8x.app/Contents/Resources/2.83/python/bin/
    ./python3.7m -m ensurepip
    ./python3.7m -m pip install xarray xgcm cmocean matplotlib

Linux
#####
.. code-block:: bash

    cd /path/to/blender/2.83/python/bin/
    ./python3.7m -m ensurepip
    ./python3.7m -m pip install xarray xgcm cmocean matplotlib

Windows
#######

.. code-block:: bash

    cd /path/to/blender/2.82/python/bin/
    python.exe -m ensurepip
    python.exe -m pip install xarray xgcm cmocean matplotlib


Blender Compilation
###################

To furter configure Blender, you could install it using a `conda` environment 
by following the official [Blender installation website](https://wiki.blender.org/index.php/Dev:Doc/Building_Blender/) instructions:

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


==============
How to use it!
==============


