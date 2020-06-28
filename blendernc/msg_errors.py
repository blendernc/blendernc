import bpy

def unselected_nc_file(self, context):
    self.layout.label(text="Select a netCDF file.")

def unselected_nc_var(self, context):
    self.layout.label(text="Select a variable from the netCDF file.")

def huge_image(self, context):
    self.layout.label(text="Image is larger than 4096x4096 pixels, reduce the resolution.")
