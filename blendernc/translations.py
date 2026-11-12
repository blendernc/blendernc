#!/usr/bin/env python3
import bpy


def translate(text):
    """Translate a UI string using Blender's active translation.

    Parameters
    ----------
    text : str
        Source string.

    Returns
    -------
    str
        Translated string, or ``text`` when no translation exists.
    """
    return bpy.app.translations.pgettext(text)
