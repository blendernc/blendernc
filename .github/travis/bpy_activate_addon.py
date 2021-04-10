import bpy

# Register the addon and enable it
bpy.ops.preferences.addon_install(filepath='./blendernc.zip')
bpy.ops.preferences.addon_enable(module='blendernc')