"""
Sanic-Redis init file
"""

from .core import SanicRedis

try:
    from importlib.metadata import version

    __version__ = version("sanic-redis")
except ImportError:
    __version__ = "unknown"

__all__ = ["SanicRedis", "__version__"]
