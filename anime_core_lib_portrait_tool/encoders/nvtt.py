"""NVIDIA Texture Tools adapter for straight-alpha, single-level BC3."""

import os
import subprocess


def encode(source_png, output_dds, *, executable):
    command = [str(executable), str(source_png), "--format", "bc3", "--quality", "production",
               "--no-mips", "--max-mip-count", "1", "--output", str(output_dds)]
    result = subprocess.run(command, capture_output=True, timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        message = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise OSError(f"nvtt 编码失败（退出码 {result.returncode}）：{message[-2000:]}")
