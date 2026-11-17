.. _in_depth_guide:

In-Depth Guide
##############

WIP

.. _datacube_slice:

Datacube Slice
==============

The **Datacube Slice** node keeps a range of positions along one
coordinate of a variable: a latitude band, the upper levels of the ocean,
a few steps of a time series. You find it under
**Add > Selection > Slice Range** in the BlenderNC node editor.

Link a variable output to its ``Variable`` input, pick the coordinate and
choose how to give the range with **Slice by**:

**Index**
   **First** and **Last** are positions along the coordinate, counted from
   0 on the full coordinate as in **Datacube Select**, and both are kept.
   Bounds in the wrong order are swapped, and **Last** is clamped to the
   coordinate size.

**Value**
   **Minimum** and **Maximum** are in the coordinate's units, for example
   -30 to 30 for latitude; every position whose value lies between them is
   kept. Dates cannot be typed this way, so slice a time coordinate by
   index.

Picking a coordinate sets the bounds to its whole extent. Below them the
node shows the values and positions kept, or why nothing is sliced: a 2D
coordinate, or no value in the range.

The range combines with a **Subsample** or **Resolution** step on the same
dimension, in whichever order the nodes come: slicing positions 2 to 7 of a
coordinate subsampled by 2 keeps positions 2, 4 and 6.

.. TODO: screenshot of the Datacube Slice node in Value mode, between a
   Datacube Variable and a Datacube Volume node, showing the summary line.
   Save as docs/images/slice_node.png and uncomment:

   .. image:: ../images/slice_node.png
      :width: 60%
      :alt: Datacube Slice node

.. _datacube_volume:

Datacube Volume
===============

The **Datacube Volume** node turns a 3D or 4D variable into a Blender
*Volume* object, so a field with depth (ocean temperature, cloud water,
a time series stacked into a cube) can be rendered as voxels instead of a
surface. The variable is written to `OpenVDB <https://www.openvdb.org/>`_
files with the ``openvdb`` module that ships with Blender; no extra
package is needed.

You find the node under **Add > Grid > Datacube Volume** in the BlenderNC
node editor.

.. TODO: screenshot of the Datacube Volume node in the node editor, linked
   from a Datacube Variable node, showing all its settings.
   Save as docs/images/volume_node.png and uncomment:

   .. image:: ../images/volume_node.png
      :width: 60%
      :alt: Datacube Volume node

Connecting the node
-------------------

Link the variable output of a **Datacube Variable** node (or of a
**Datacube Select**, **Slice**, **Subsample** or **Resolution** node in
between) to
the ``Variable`` input, then press **Bake Volume**. The node creates the
Volume object and exposes it on its ``Object`` output.

How dimensions become voxels
----------------------------

The two horizontal dimensions (``lon``/``lat``, ``x``/``y`` and similar
names) become the voxel x and y axes. What happens to the remaining
dimensions depends on the variable:

=====================  ==================================================
Variable dimensions    Result
=====================  ==================================================
(x, y)                 Refused: use a **Datacube Texture** node.
(x, y, z)              One static volume, z running upwards.
(x, y, time)           One static *space-time cube*, time running upwards.
(x, y, z, time)        A volume animated along time, z running upwards.
More than 4            Refused: pick a slice with **Datacube Select**.
=====================  ==================================================

.. TODO: screenshot of a space-time cube baked from an (x, y, time)
   variable, next to the Datacube Grid baked from the same coordinates.
   Save as docs/images/volume_space_time_cube.png and uncomment:

   .. image:: ../images/volume_space_time_cube.png
      :width: 100%
      :alt: Space-time cube of a 3D variable

Settings
--------

**Volume name**
   Name of the Volume object to create or update. An existing object of
   another type (a mesh, for instance) is never overwritten.

**Animate along**
   Dimension spread over frames. *Auto* animates the time dimension of a
   4D variable and nothing for a 3D one. *None (static)* never animates,
   so a 4D variable is refused until a level is selected. Choosing a
   dimension explicitly lets you, for example, animate an (x, y, time)
   variable along time; each frame is then a one-voxel-thick slab. Only
   the dimensions left after the tree's slicing are listed.

**Frames**
   Only used when a dimension is animated.

   * *Bake all frames* writes one VDB file per step, and Blender plays them
     as a volume sequence: frame 0 shows the first step and the last step
     holds afterwards. Playback and rendering need no add-on, so this mode
     suits render farms. It takes the most disk space and bake time; use
     **Datacube Subsample** or **Datacube Resolution** to make it lighter.
   * *Current frame* writes only the step shown, and rewrites it whenever
     the frame changes. It uses little disk space, but BlenderNC must be
     installed wherever the scene is played or rendered.

**Vertical scale**
   Multiplies the vertical coordinate when it is evenly spaced (see
   `Placement`_); otherwise it is the height of one voxel. Changing it
   moves and stretches the object without writing the files again.

**VDB folder**
   Where the files are written. The default, ``//blendernc_vdb/``, is a
   folder next to the ``.blend`` file. Each node writes into its own
   sub-folder and removes the files of its previous bake there.
   Deleting the node deletes its sub-folder too, unless a Volume still
   reads files from it; the Volume object stays in the scene when the node
   is deleted, so its files are kept.

   While the ``.blend`` file has never been saved, the files go to
   Blender's temporary folder, which Blender deletes when it quits. The
   node shows a warning; save the file and bake again to keep them.

.. TODO: screenshot or short GIF of an animated (x, y, z, time) volume
   playing back in the viewport.
   Save as docs/videos/volume_animation.gif and uncomment:

   .. image:: ../videos/volume_animation.gif
      :width: 100%
      :alt: Animated volume

Placement
---------

The voxels are placed on the coordinates, so the volume lines up with a
**Datacube Grid** baked from the same coordinates:

* **Evenly spaced** horizontal coordinates set the object's location (the
  first value) and scale (the spacing). A descending coordinate, such as
  latitude from 90 to -90, is flipped so the scale stays positive.
* **Unevenly spaced** coordinates are resampled onto as many evenly spaced
  values over the same extent; each voxel takes the value at the nearest
  original position.
* **Curvilinear** coordinates (2D longitude and latitude, as in rotated or
  ocean-model grids) are resampled onto a regular grid over their extent,
  with as many points per axis as the original. Each voxel column takes
  the nearest original column, and columns outside the data stay empty.
  2D coordinates that only change along their own axis are used directly.

Resampling picks values; it never averages them. The node lists what was
resampled below its button, and the same note goes to the status bar and
the log.

An evenly spaced numeric vertical coordinate places the voxels the same
way, multiplied by **Vertical scale**. A coordinate marked
``positive = "down"`` (CF depth or pressure) is turned around, so deeper
levels sit lower, below zero. Unevenly spaced levels and dates (the time
axis of a space-time cube) give one voxel per level, of height
**Vertical scale**; uneven levels get a note on the node.

.. note::
   With depths in metres and horizontal coordinates in degrees, the volume
   is far taller than it is wide. Set a small **Vertical scale**, such as
   0.001, to flatten it.

Rebaking
--------

Like the grid, the volume follows the node tree. Changing the slicing
upstream (a different **Select** index, a new **Resolution** step), the
variable, **Animate along** or **Frames** bakes it again automatically.
Every bake uses new file names, because Blender keeps VDB grids in memory
by file path and would otherwise keep showing the old data.

Material
--------

The first bake assigns a material called ``<variable> volume``: an
*Attribute* node reads the grid, a *Map Range* node maps it from the
object's ``Min value`` to ``Max value`` custom properties onto 0 to 1, and
the result drives the density of a *Principled Volume*. Missing values and
the field minimum render as empty space. Colour, emission and the density
multiplier are left for you to set.

The range is computed over the whole variable at bake time. With the
scene's **Lock range** setting on (node editor sidebar, *BlenderNC* tab,
*Settings*), a rebake keeps the range already stored on the object, so the
colour scale stays fixed and the variable is not read twice.

.. TODO: screenshot of the "<variable> volume" material in the shader
   editor. Save as docs/images/volume_material.png and uncomment:

   .. image:: ../images/volume_material.png
      :width: 100%
      :alt: Default volume material
