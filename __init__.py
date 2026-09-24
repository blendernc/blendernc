import logging
import os

from .blendernc.blendernc import register as register
from .blendernc.blendernc import unregister as unregister


def setup_logging():
    """Configure logging to write to a file in the script's directory."""
    log_file = os.path.join(os.path.dirname(__file__), "log.txt")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Logging initialized")


if __name__ == "__main__":
    setup_logging()
    register()
    unregister()
