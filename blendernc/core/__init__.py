"""Helpers that need no Blender: datasets, slicing, grids, fields and volumes.

Nothing in this package imports ``bpy`` or ``mathutils``, so it runs, and is
unit-tested, in plain Python (see ``tests/unit``). Code that reads or writes
Blender data lives in :mod:`blendernc.utils`, :mod:`blendernc.volume_utils`
and the other modules of :mod:`blendernc`.
"""
