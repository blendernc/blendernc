#!/usr/bin/env python3
import warnings

import bpy


# TODO Replace all messages with print_message.
# Possibly shift to class when blendernc is initiated. and move to logging.
class PrintMessage(object):
    def __init__(self, text, title, icon):
        self.message = text()
        self.title = title
        self.icon = icon

        self.print_message()

    def print_message(self):
        if not bpy.app.background:
            bpy.context.window_manager.popup_menu(
                self.message_contructor, title=self.title, icon=self.icon
            )
        else:
            message = u"Running in background mode,\n {0}".format(self.message)
            warnings.warn(message)

    def message_contructor(self, wm_self, context):
        # TODO improve this function.
        n = 60
        if len(self.message) > n:
            constructing_text = True
            line = 0
            counter = -1
            text = {}
            while constructing_text:
                if line == 0 and counter == -1:
                    text[line] = ""
                if counter == (n - 1) * (line + 1) and self.message[counter] == " ":
                    line += 1
                    text[line] = ""
                    counter += 1
                elif counter == (n - 1) * (line + 1) and self.message[counter] != " ":
                    split_text = self.message[line * n : (line + 1) * n].split(" ")[-1]
                    counter -= len(split_text)
                    text[line] = text[line].replace(split_text, "")
                    line += 1
                    text[line] = ""
                    counter += 1
                elif counter < len(self.message) - 1:
                    counter += 1
                else:
                    break

                text[line] = text[line] + self.message[counter]

            for key, line in text.items():
                wm_self.layout.label(text=line)

        else:
            wm_self.layout.label(text=self.message)


def asign_material():
    text = "Assign material to object!"
    return text


def load_after_restart():
    text = "This change will be loaded after restarting Blender or creating a new file."
    return text


def active_selection_preference():
    text = (
        "The active selection has preference over picked object. "
        + "Make sure you selected the right mesh to apply material."
    )
    return text


def unselected_object():
    text = "Select an object to apply material."
    return text


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
