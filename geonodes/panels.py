import bpy

class GeoNodes_UI_PT_3dview(bpy.types.Panel):
    bl_idname = "NCLOAD_PT_Panel"
    bl_label = "GeoNodes"
    bl_category = "GeoNodes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator('geonodes.ncload', text="Load NetCDF")

