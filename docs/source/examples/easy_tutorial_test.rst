=====================
BlenderNC node editor
=====================

.. important:: This second example, introduces the BlenderNC node editor, where each node allows you to do a particular task (i.e. loading data, rendering image, purging cache, etc). All the maginc of BlenderNC happens at the node editor.


Load data!
----------

Open Blender (>2.83), in the 3D view open the `sidebar` by pressing "n".

- Switch to the BlenderNC panel and click on ``Load netCDF``. Then click the folder icon, navegate and select a the GEBCO bathymetry netCDF.


- Select variable (``elevation``):


- Let's increase the resolution to 100%:


- Click in the check box next to ``Animate netCDF``


- Now, we can apply the material BlenderNC just created, but first, lets delete the default cube (shortuct ``x``), create a sphere (shortcut ``shift + a`` - ``Mesh -> UV Sphere``), and scale it to ``2x`` (shortcut ``s + 2 + return``)



- Select sphere by clicking over it, then click apply material (highlighted in blue above).

There will be no visible change until we switch to a rendered 3D viewport (``Z`` and click over ) or render the camera (shortcut ``F12``).



Press ``0`` in your numberpath to change your view to the camera view. If you are using a laptop, you can emulate a numberpath by following the instructions in this `link <https://docs.blender.org/manual/en/latest/editors/preferences/input.html>`__!


Once you are in the camera mode, press ``Spacebar`` in your keyboard to play animation. Voila! now we have a netCDF animation.



.. [Dataset]
        Merchant, C.J., Embury, O., Bulgin, C.E., Block, T., Corlett, G.K., Fiedler, E., Good, S.A., Mittaz, J., Rayner, N.A., Berry, D., Eastwood, S., Taylor, M., Tsushima, Y., Waterfall, A., Wilson, R. and Donlon, C. (2019), Satellite-based time-series of sea-surface temperature since 1981 for climate applications. Scientific Data 6, 223, doi:10.1038/s41597-019-0236-x