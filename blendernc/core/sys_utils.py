import sys
from collections import deque
from collections.abc import Mapping, Set
from numbers import Number

ZERO_DEPTH_BASES = (str, bytes, Number, range, bytearray)


class get_size(object):
    """Recursively iterate to sum size of object & members."""

    @classmethod
    def size(cls, obj):
        size = cls.map_object(obj)
        size += cls.custom_instance(obj)
        return size

    @classmethod
    def map_object(cls, obj):
        size = sys.getsizeof(obj)
        if isinstance(obj, ZERO_DEPTH_BASES):
            pass  # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(cls.size(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, "items"):
            size += sum(cls.size(k) + cls.size(v) for k, v in getattr(obj, "items")())
        return size

    @classmethod
    def custom_instance(cls, obj):
        size = 0
        # Check for custom object instances - may subclass above too
        if hasattr(obj, "__dict__"):
            size = cls.size(vars(obj))
        if hasattr(obj, "__slots__"):  # can have __slots__ with __dict__
            size = sum(
                cls.size(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s)
            )
        return size
