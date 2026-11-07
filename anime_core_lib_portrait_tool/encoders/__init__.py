"""Small adapters for external DDS encoders; no executable discovery."""

from . import nvtt, texconv


ENCODERS = {"nvtt": nvtt.encode, "texconv": texconv.encode}
