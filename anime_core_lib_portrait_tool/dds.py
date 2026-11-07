"""Encode via an explicitly supplied executable, then replace the destination."""
from pathlib import Path
import shutil
import uuid
from .encoders import ENCODERS


def write_dds(path, image, *, encoder, encoder_path, overwrite=False):
    path, executable = Path(path), Path(encoder_path).resolve()
    if encoder not in ENCODERS:
        raise ValueError("encoder 必须是 nvtt 或 texconv")
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if path.suffix.lower() != ".dds":
        raise ValueError("输出必须是 .dds")
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    parent = path.parent.resolve()
    folder = parent / (".dds-" + uuid.uuid4().hex)
    # Normal directory creation inherits the output directory's Windows ACL and
    # respects umask on Unix. TemporaryDirectory uses private directory permissions.
    folder.mkdir()
    try:
        source, output = folder / "image.png", folder / "image.dds"
        image.save(source, format="PNG")
        ENCODERS[encoder](source, output, executable=executable)
        if not output.is_file():
            raise RuntimeError("编码器没有生成 DDS")
        # Same filesystem: atomic rename without copying the encoded bytes.
        # Failed encoding or replacement leaves the old DDS intact.
        output.replace(path)
    finally:
        if folder.resolve().parent != parent:
            raise RuntimeError("临时目录超出输出目录，拒绝清理")
        shutil.rmtree(folder)
