===================
Import ECMWF netCDF
===================

.. raw:: html

    <style>
        .purple {color:purple}
    </style>


.. role:: purple

.. important::
    It is important to be familiar with the simple UI of BlenderNC (:ref:`beginner_mode`) to follow this tutorial.


Some data has been provided by ECMWF, and it is included at the main `BlenderNC <https://github.com/blendernc/blendernc>`_ repository in the path ``blendernc/test/dataset``.

::

    blendernc
    └── tests
        └── dataset
            ├── ECMWF_data.grib
            ├── ECMWF_data.nc
            ├── ssh_1995-01.nc
            └── ssh_1995-01.zarr

This example will use the file ``ECMWF_data.nc``, follow closely the previous tutorial :ref:`simple_example`, and explore the BlenderNC.


Import data!
------------

Open Blender (>2.83), in the 3D view, open the `sidebar` by pressing "n".

- Switch to the BlenderNC panel and click on ``Load netCDF``. Then click the folder icon, navigate and select the ecmwdf netcdf dataset: ``blendernc/test/dataset/ssh_1995-01.nc``

.. image:: ../../images/ecmwf_example/select_dataset.png
  :width: 100%
  :class: with-shadow float-left

- Select the variable ``t2m`` from this dataset (Air-Temperature at 2 meters):

.. image:: ../../images/ecmwf_example/select_variable.png
  :width: 100%
  :class: with-shadow float-left

- Click over the animation checkbox to allow the dataset to be animated.

.. image:: ../../images/ecmwf_example/select_animate.png
  :width: 100%
  :class: with-shadow float-left

- Let's increase the resolution to 100%:

.. image:: ../../images/ecmwf_example/change_resolution.png
  :width: 100%
  :class: with-shadow float-left

- Now, we can apply the material BlenderNC just created, but first, lets delete the default cube (shortuct ``x``), create a sphere (shortcut ``shift + a`` - ``Mesh -> UV Sphere``), and scale it to ``2x`` (shortcut ``s + 2 + return``)

- Select sphere by clicking over it, then click apply material (highlighted in blue above). There will be no visible change until we switch to a rendered 3D viewport (``Z`` and click over ) or render the camera (shortcut ``F12``). Press ``0`` in your number path to change your view to the camera view. If you are using a laptop, you can emulate a number path by following the instructions in this `link <https://docs.blender.org/manual/en/latest/editors/preferences/input.html>`__!

.. image:: ../../images/ecmwf_example/3D_view.png
  :width: 100%
  :class: with-shadow float-left

.. note::
    So far there is noting new, but the render preview looks awful, we will fix it using the BlenderNC nodetree.

BlenderNC nodetree
------------------

Let's switch to the BlenderNC nodetree, we have two options:

- Switch to :purple:`BlenderNC workspace` (recomended):

.. image:: ../../images/ecmwf_example/change_workspace.png
  :width: 100%
  :class: with-shadow float-left

- or switch viewport to the BlenderNC nodetree:

.. image:: ../../images/ecmwf_example/change_nodetree.png
  :width: 100%
  :class: with-shadow float-left

By default, the `3D view` **BlenderNC** panel will create 4 nodes ``netCDF Path, netCDF input, Resolution, Output``, as seen below:

.. image:: ../../images/ecmwf_example/selected_nodetree.png
  :width: 100%
  :class: with-shadow float-left

.. note::
  The node ``netCDF input`` changes name to the current loaded filename.

