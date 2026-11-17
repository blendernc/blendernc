import logging

import bpy

from .blendernc.blendernc import register as BNC_register
from .blendernc.blendernc import unregister as BNC_unregister

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def log_path():
    """Absolute path of the BlenderNC log file."""
    return bpy.utils.extension_path_user(__package__, path="log.txt")


def setup_logging(level=logging.INFO):
    """Write BlenderNC log messages to ``log.txt`` in the extension's user dir.

    Only the package logger is configured, so other add-ons and libraries
    are unaffected. Calling it twice (add-on reload) is a no-op.
    """
    if logger.handlers:
        return
    log_dir = bpy.utils.extension_path_user(__package__, create=True)
    handler = logging.FileHandler(f"{log_dir}/log.txt", encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.info("Logging initialized")
    print(f"BlenderNC log: {log_path()}")


def teardown_logging():
    """Detach and close the handlers added by :func:`setup_logging`."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def register():
    """Configure logging, then register BlenderNC with Blender."""
    setup_logging()
    BNC_register()


def unregister():
    """Unregister BlenderNC, then release the log file."""
    BNC_unregister()
    teardown_logging()
