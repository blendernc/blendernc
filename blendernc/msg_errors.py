import bpy

def unselected_nc_file(self, context):
    self.layout.label(text="Select a netCDF file.")

def unselected_nc_var(self, context):
    self.layout.label(text="Select a variable from the netCDF file.")

def unselected_nc_dim(self, context):
    self.layout.label(text="Select a dimension to drop.")

def unselected_nc_coord(self, context):
    self.layout.label(text="Select a coordinate to drop.")

def huge_image(self, context):
    self.layout.label(text="Image is larger than 4096x4096 pixels, reduce the resolution.")

def drop_dim(self, context):
    self.layout.label(text="4D field, drop a dimension or select a slice")
