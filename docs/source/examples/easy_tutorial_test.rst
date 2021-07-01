=====================
BlenderNC node editor
=====================

.. important::
   This second example, introduces the BlenderNC node editor, where each node allows you to do a particular task (i.e. loading data, rendering image, purging cache, etc). All the magic of BlenderNC happens at the node editor.


Load data!
----------

Open Blender (>2.83), in the 3D view, open the `sidebar` by pressing "n".

- Switch to the BlenderNC panel and click on ``Load netCDF``. Then click the folder icon, navigate and select the GEBCO bathymetry netCDF.

- Select variable (``elevation``):

- Let's increase the resolution to 100%:

- Click in the check box next to ``Animate netCDF``

- Now, we can apply the material BlenderNC just created, but first, lets delete the default cube (shortuct ``x``), create a sphere (shortcut ``shift + a`` - ``Mesh -> UV Sphere``), and scale it to ``2x`` (shortcut ``s + 2 + return``)

- Select sphere by clicking over it, then click apply material (highlighted in blue above).

There will be no visible change until we switch to a rendered 3D viewport (``Z`` and click over ) or render the camera (shortcut ``F12``).

Press ``0`` in your number path to change your view to the camera view. If you are using a laptop, you can emulate a number path by following the instructions in this `link <https://docs.blender.org/manual/en/latest/editors/preferences/input.html>`_!

Once you are in the camera mode, press ``Spacebar`` on your keyboard to play the animation. Voila! now we have a netCDF animation.