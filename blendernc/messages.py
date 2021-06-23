#!/usr/bin/env python3


def load_after_restart(self, context):
    self.layout.label(text="This change will be loaded after restarting Blender")
    self.layout.label(text="or creating a new file.")


def active_selection_preference(self, context):
    self.layout.label(text="The active selection has preference over picked object.")
    self.layout.label(text="Make sure you selected the right mesh to apply material.")


def unselected_object(self, context):
    self.layout.label(text="Select an object to apply material.")


def increase_resolution(self, context):
    self.layout.label(text="Increase resolution.")


def unselected_nc_file(self, context):
    self.layout.label(text="Select a netCDF file.")


def unselected_variable(self, context):
    self.layout.label(text="Select a variable file.")


def unselected_nc_var(self, context):
    self.layout.label(text="Select a variable from the netCDF file.")


def unselected_nc_dim(self, context):
    self.layout.label(text="Select a dimension to drop.")


def unselected_nc_coord(self, context):
    self.layout.label(text="Select a coordinate to drop.")


def huge_image(self, context):
    self.layout.label(
        text="Image is larger than 4096x4096 pixels, reduce the resolution."
    )


def drop_dim(self, context):
    self.layout.label(text="4D field, drop a dimension or select a slice")
