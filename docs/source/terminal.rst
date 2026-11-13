.. _terminal_guide:

=================================
Using BlenderNC from the terminal
=================================

Everything BlenderNC does in the node editor can be driven from a Python
script that Blender runs in *background mode*, without opening a window. This
is how you render on a server, batch-process many files, or reproduce a
figure from a script checked into a repository.

This page covers three things:

1. installing BlenderNC without the user interface,
2. the Python calls that correspond to each node, and
3. a complete, tested script that loads a datacube and renders it.

.. note::
   All commands below were run with Blender 5.2 LTS. ``blender`` stands for
   the Blender executable, which is ``blender`` on Linux,
   ``/Applications/Blender.app/Contents/MacOS/Blender`` on macOS and
   ``"C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe"`` on
   Windows. Defining an alias saves typing:

   .. code-block:: bash

      alias blender=/Applications/Blender.app/Contents/MacOS/Blender


Installing without the user interface
=====================================

Blender ships a command line for extensions. From a checkout of the
repository, build the extension package and install it into the user
repository in two commands:

.. code-block:: bash

   # 1. Download the dependency wheels and list them in blender_manifest.toml
   python update_wheels.py

   # 2. Build the zip (written as blendernc-<version>.zip in dist/)
   blender --command extension build --source-dir . --output-dir dist

   # 3. Install it and enable it
   blender --command extension install-file -r user_default -e dist/blendernc-0.8.0.zip

Check the result:

.. code-block:: bash

   blender --command extension list | grep -i blendernc
   # blendernc [installed]: "BlenderNC", This extension allows to import geocubes into blender

Dependencies
------------

BlenderNC needs ``xarray``, ``dask``, ``netCDF4`` and the other packages in
``requirements.txt`` to be importable by Blender's own Python. There are three
ways to get there; pick one.

- **Bundled wheels (recommended for a self-contained install).** Running
  ``python update_wheels.py`` before building fills the ``wheels`` list of the
  manifest, and Blender installs them together with the extension.
- **Blender's user modules folder.** Install the requirements into the
  ``scripts/modules`` folder of your Blender user directory, for example
  ``~/Library/Application Support/Blender/5.2/scripts/modules`` on macOS:

  .. code-block:: bash

     python -m pip install -r requirements.txt --target "<blender user dir>/scripts/modules"

- **A system Python environment.** Start Blender with
  ``--python-use-system-env`` and set ``PYTHONPATH`` to an environment whose
  Python version matches Blender's (3.13 for Blender 5.2). This is what the
  test suite and the Docker image do; see :ref:`remote_render`.

Running from a checkout without installing
------------------------------------------

For development, or inside containers, the add-on can be loaded straight from
the repository. The top-level ``blendernc`` package is importable when the
checkout is on ``PYTHONPATH``, and ``--addons`` enables it for this session
only:

.. code-block:: bash

   cd /path/to/blendernc
   PYTHONPATH=$PWD blender -b --addons blendernc --python-use-system-env --python my_script.py

This is also how ``tests/run_tests.py`` launches each test file.


Running a script
================

The general form is:

.. code-block:: bash

   blender -b --python my_script.py -- arg1 arg2 ...

- ``-b`` (``--background``) runs without a window and quits when the script
  ends.
- ``--python`` runs a file; ``--python-expr "..."`` runs a one-liner instead.
- Everything after ``--`` is ignored by Blender and left for your script in
  ``sys.argv``.
- Add ``--python-exit-code 1`` before ``--python`` so that an exception in
  your script makes Blender exit with a non-zero status. Without it a failed
  script still returns 0, which hides errors from shell pipelines and CI.

A quick check that the add-on is active:

.. code-block:: bash

   blender -b --python-expr "import bpy; print([k for k in bpy.context.preferences.addons.keys() if k.endswith('.blendernc')])"
   # ['bl_ext.user_default.blendernc']


BlenderNC nodes from Python
===========================

Each node in the editor is a Blender node type that you create with
``tree.nodes.new(<bl_idname>)`` in a tree of type ``BlenderNCNodeTree``.

.. list-table::
   :header-rows: 1
   :widths: 24 28 48

   * - Node
     - ``bl_idname``
     - Properties and sockets you set from a script
   * - Datacube Import
     - ``BlenderNCNodeImport``
     - ``datacube_file`` (path or glob pattern). Output ``xarray datacube``.
   * - Datacube Resolution
     - ``BlenderNCNodeResolution``
     - ``step`` strides every horizontal dimension. While ``suggested_step``
       is on (the default) the node picks the smallest step that keeps each
       dimension within 1000 samples; set it to ``False`` before assigning
       ``step``. In and out ``xarray datacube``.
   * - Datacube Subsample
     - ``BlenderNCNodeSubsample``
     - ``datacube_coords`` and ``step`` stride one coordinate. In and out
       ``Variable``.
   * - Datacube Coords
     - ``BlenderNCNodeCoords``
     - One string output per coordinate of the dataset.
   * - Datacube Variable
     - ``BlenderNCNodeVariable``
     - ``datacube_vars`` selects a variable; an output socket with that name
       appears.
   * - Datacube Select
     - ``BlenderNCNodeSelect``
     - ``datacube_coords`` picks the coordinate and ``index`` the position
       kept along it (clamped to the coordinate size). In and out
       ``Variable``.
   * - Datacube Grid
     - ``BlenderNCNodeGrid``
     - Inputs ``X``, ``Y``, ``Z`` take coordinate outputs; ``grid_obj_name``
       names the mesh. Baked with
       ``bpy.ops.blendernc.create_grid_from_coords``. Output ``Object``.
   * - Datacube Texture
     - ``BlenderNCNodeTexture``
     - Inputs ``Object`` and ``Variable``. A 2-D variable is written once to
       a point attribute of the mesh named after it, and removed again when
       ``Variable`` is unlinked. A 3-D or 4-D variable is refused and
       ``message`` says which node to use instead.
   * - Datacube Animate Texture
     - ``BlenderNCNodeAnimateTexture``
     - Inputs ``Object`` and ``Variable``. On every frame change the
       variable is written to a point attribute of the mesh named after it.

Three details matter when scripting:

- **Set the path before linking.** Assigning ``datacube_file`` loads the
  dataset. Links created afterwards propagate it to the connected nodes.
- **Bake once; the grid then follows the tree.** The create-grid operator
  builds the mesh and exposes it on the ``Object`` output. Changing the
  resolution or subsample step afterwards rebakes the grid automatically and
  rewrites the textures linked to it.
- **Nothing is written to the mesh until a frame changes.** The animate node
  works through a ``frame_change_pre`` handler. Call
  ``scene.frame_set(index)`` for a still, or render an animation and every
  frame is updated for you.


Complete example
================

The script below is kept at ``docs/source/scripts/render_datacube.py`` and
is run as part of the documentation checks. It builds the node tree above,
bakes the grid, colours the mesh from the point attribute with a shader
``Attribute`` node, frames it with an orthographic camera and renders with
Cycles on the CPU.

.. code-block:: bash

   blender -b --python-exit-code 1 --python docs/source/scripts/render_datacube.py -- \
       tests/dataset/ssh_1995-01.nc adt renders/ssh.png --step 4 --frame 2

.. image:: ../images/headless_ssh.png
   :width: 100%
   :alt: Absolute dynamic topography rendered from the terminal

Rendering every index of the animated coordinate, here the five time steps of
the test file, produces a numbered sequence:

.. code-block:: bash

   blender -b --python-exit-code 1 --python docs/source/scripts/render_datacube.py -- \
       tests/dataset/ssh_1995-01.nc adt renders/ssh_ --step 8 --animate
   # renders/ssh_0000.png ... renders/ssh_0004.png

Options:

``--x``, ``--y``
   Names of the coordinates mapped to the grid axes. The defaults are
   ``longitude`` and ``latitude``; use ``--x lon --y lat`` or ``--x nav_lon``
   as your file requires.
``--step``
   Horizontal stride applied through the Resolution node. The test file is
   1440 by 720 points; ``--step 4`` bakes a 360 by 180 grid in about four
   seconds.
``--frame`` / ``--animate``
   Render one index of the animated coordinate, or all of them.
``--vmin`` / ``--vmax``
   Value range mapped to the colour ramp.
``--samples``
   Cycles samples. Emission shading converges with very few.

.. literalinclude:: scripts/render_datacube.py
   :language: python
   :linenos:


Things that catch people out
============================

- **Coordinate names differ between files.** Inspect them first:

  .. code-block:: bash

     blender -b --python-expr "import xarray as xr; print(xr.open_mfdataset('file.nc'))"

- **Longitudes from 0 to 360** put the mesh entirely at positive X. The
  example centres the camera on the mesh bounds, so this does not matter
  there, but a hand-placed camera at the origin only sees half of the data.
- **Missing values are filled with zero** before they reach the mesh, which
  is why land appears at the middle of the colour ramp in the image above.
- **The baked mesh has one empty material slot.** Replace ``materials[0]``
  rather than appending, or your material is never used.
- **Use Cycles or Workbench on machines without a display.** EEVEE needs a
  GPU context and fails in background mode on headless servers.
- **Log file.** BlenderNC writes to ``log.txt`` in the extension's user
  directory. Its location is printed on startup and can be queried with
  ``bpy.utils.extension_path_user("<bl_ext.repo.blendernc>", path="log.txt")``.


Running the test suite
======================

The tests are plain ``unittest`` files executed inside Blender. From the
``tests`` directory:

.. code-block:: bash

   cd tests
   PYTHONPATH=.. python run_tests.py blender test

The first argument is the Blender executable, the second the suffix of the
test files to run (``*.test.py``). Each file starts its own Blender process
and the runner raises if any of them fails.
