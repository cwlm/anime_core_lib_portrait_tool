"""Canvas and composition settings shared by automatic and manual processing."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    canvas: tuple = (1024, 1024)
    anchor: tuple = (512, 175)
    face_size: tuple = (95, 92)
    anchor_x: tuple = (492, 546)
    anchor_y: tuple = (125, 258)
    margin: float = 2
    alpha_core: int = 16
    face_threshold: float = 0.55

    def __post_init__(self):
        for name in ("canvas","anchor","face_size","anchor_x","anchor_y"):
            value = tuple(getattr(self,name))
            if len(value) != 2:
                raise ValueError(f"{name} must contain two values")
            object.__setattr__(self,name,value)
        if any(not isinstance(v, int) or v <= 2*self.margin for v in self.canvas) or self.margin < 0:
            raise ValueError("画布宽高必须为正整数，且大于两侧边距")
        if min(self.face_size) <= 0 or not 1 <= self.alpha_core <= 255 or not 0 <= self.face_threshold <= 1:
            raise ValueError("脸部尺寸、Alpha 阈值或置信度无效")
        for size, anchor, (lo, hi) in zip(self.canvas, self.anchor, (self.anchor_x, self.anchor_y)):
            if not self.margin <= lo <= anchor <= hi <= size-self.margin or hi <= self.margin or lo >= size-self.margin:
                raise ValueError("锚点和活动范围必须位于画布内，并为两侧留出空间")


def load_layout(path=None):
    return Layout(**json.loads(Path(path).read_text(encoding="utf-8-sig"))) if path else Layout()
