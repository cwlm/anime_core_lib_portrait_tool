"""DirectXTex adapter for legacy-header, single-level BC3."""

import os
from pathlib import Path
import subprocess


def encode(source_png, output_dds, *, executable):
    source_png, output_dds = Path(source_png), Path(output_dds)
    command = [str(executable), "-nologo", "-f", "BC3_UNORM", "-m", "1", "-dx9", "-y",
               "-o", str(output_dds.parent), str(source_png)]
    result = subprocess.run(command, capture_output=True, timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        message = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise OSError(f"texconv 编码失败（退出码 {result.returncode}）：{message[-2000:]}")
    generated = output_dds.parent / (source_png.stem + ".dds")
    if generated != output_dds:
        generated.replace(output_dds)
