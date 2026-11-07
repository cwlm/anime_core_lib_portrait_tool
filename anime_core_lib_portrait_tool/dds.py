"""Encode via an explicitly supplied executable, then replace the destination."""
from pathlib import Path
import tempfile
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
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".dds-") as folder:
        folder = Path(folder)
        source, output = folder / "image.png", folder / "image.dds"
        image.save(source, format="PNG")
        ENCODERS[encoder](source, output, executable=executable)
        if not output.is_file():
            raise RuntimeError("编码器没有生成 DDS")
        # Commit only after encoding succeeds; failed encoding leaves the old DDS.
        output.replace(path)
