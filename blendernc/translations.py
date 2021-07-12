#!/usr/bin/env python3
import bpy


def translate(text):
    return bpy.app.translations.pgettext(text)
