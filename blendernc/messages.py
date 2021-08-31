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


def huge_image():
    text = "Image is larger than 4096x4096 pixels, reduce the resolution."
    return text


def drop_dim():
    text = "4D field, drop a dimension or select a slice"
    return text


def unselected_object():
    text = "Select an object to apply material."
    return text


def select_file():
    text = "Select a file!"
    return text


def no_cached_image():
    text = "Images haven't been cached."
    return text


def no_cached_nodes():
    text = "NodeTree hasn't been cached."
    return text


def client_exists():
    text = "Client exists; a new client will be created."
    return text


def increase_resolution():
    text = "Increase resolution."
    return text


def unselected_datacube():
    text = "Select a variable from the datacube."
    return text


def unselected_variable():
    text = "Reselect a variable from the datacube."
    return text


def unselected_dim(self, context):
    self.layout.label(text="Select a dimension to drop.")


def unselected_coord(self, context):
    self.layout.label(text="Select a coordinate to drop.")
