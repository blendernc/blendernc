"""User-facing messages: one place that reports to Blender and logs.

Operators can show text in the status bar through ``report``; nodes,
property groups and plain helpers cannot, so for them the log file is the
only channel. Everything that is meant for the user goes through
:func:`report_error`, and operator ``execute`` methods are wrapped in
:func:`report_errors` so that the ``ValueError``/``OSError`` raised by the
helpers in :mod:`blendernc.utils` end as a report instead of a traceback.

When an operator is called from Python with ``bpy.ops``, Blender re-raises
an ``ERROR`` report as a ``RuntimeError`` carrying the same message.
"""

import logging
from functools import wraps

logger = logging.getLogger(__name__)


def report_error(owner, message, level="ERROR"):
    """Log ``message`` and show it to the user when ``owner`` can report.

    Operators have ``report``; nodes and property groups do not, so for them
    the log is the only channel.

    Parameters
    ----------
    owner : object
        Operator, node or property group the message originates from.
    message : str
        Text shown in the status bar and written to the log.
    level : str, optional
        ``"ERROR"`` (default) or ``"WARNING"``, used for both channels.

    Returns
    -------
    set
        ``{"CANCELLED"}``, so an operator can ``return report_error(...)``.
    """
    logger.log(logging.getLevelName(level), message)
    if hasattr(owner, "report"):
        owner.report({level}, message)
    return {"CANCELLED"}


def report_errors(execute):
    """Turn a ``ValueError`` or ``OSError`` from an operator into a report.

    The helpers in :mod:`blendernc.utils` raise these for user-facing
    problems (unreadable file, filenames that share no pattern, coordinates
    that cannot form a grid). At the operator boundary the exception becomes
    a status-bar message, a log entry and ``{"CANCELLED"}``.
    """

    @wraps(execute)
    def wrapper(self, context):
        """Run ``execute`` and convert the known exceptions into a report."""
        try:
            return execute(self, context)
        except (ValueError, OSError) as exc:
            return report_error(self, str(exc))

    return wrapper
