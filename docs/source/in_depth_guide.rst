.. _in_depth_guide:

In-Depth Guide
##############

WIP

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
**Datacube Select**, **Subsample** or **Resolution** node in between) to
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
   variable along time; each frame is then a one-voxel-thick slab.

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
   Height of one voxel along the vertical axis. Changing it stretches the
   object without writing the files again.

**VDB folder**
   Where the files are written. The default, ``//blendernc_vdb/``, is a
   folder next to the ``.blend`` file. Each node writes into its own
   sub-folder and removes the files of its previous bake there. While the
   ``.blend`` file has never been saved, the files go to Blender's
   temporary folder, so save the file first if you want to keep them.

.. TODO: screenshot or short GIF of an animated (x, y, z, time) volume
   playing back in the viewport.
   Save as docs/videos/volume_animation.gif and uncomment:

   .. image:: ../videos/volume_animation.gif
      :width: 100%
      :alt: Animated volume

Placement
---------

When the horizontal coordinates are evenly spaced, the voxels are placed
on them: the object's location is the first coordinate value and its scale
is the spacing. The volume then lines up with a **Datacube Grid** baked
from the same coordinates. Uneven or curvilinear (2D) coordinates fall
back to one Blender unit per voxel. The vertical axis always counts voxels,
multiplied by **Vertical scale**.

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

.. TODO: screenshot of the "<variable> volume" material in the shader
   editor. Save as docs/images/volume_material.png and uncomment:

   .. image:: ../images/volume_material.png
      :width: 100%
      :alt: Default volume material
