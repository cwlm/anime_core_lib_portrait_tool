"""Canvas geometry and automatic composition policy."""
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    canvas: tuple = (1024, 1024)
    anchor: tuple = (512, 175)
    face_size: tuple = (95, 92)
    anchor_x: tuple = (492, 546)
    anchor_y: tuple = (125, 258)
    margin: float = 2

    def __post_init__(self):
        for name in ("canvas","anchor","face_size","anchor_x","anchor_y"):
            value = tuple(getattr(self,name))
            if len(value) != 2:
                raise ValueError(f"{name} must contain two values")
            if not all(math.isfinite(v) for v in value):
                raise ValueError(f"{name} must contain finite values")
            object.__setattr__(self,name,value)
        if not math.isfinite(self.margin) or self.margin < 0 or any(
                not isinstance(v, int) or v <= 2*self.margin for v in self.canvas):
            raise ValueError("画布宽高必须为正整数，且大于两侧边距")
        if min(self.face_size) <= 0:
            raise ValueError("脸部参考尺寸必须为正数")
        for size, anchor, (lo, hi) in zip(self.canvas, self.anchor, (self.anchor_x, self.anchor_y)):
            if not self.margin <= lo <= anchor <= hi <= size-self.margin or hi <= self.margin or lo >= size-self.margin:
                raise ValueError("锚点和活动范围必须位于画布内，并为两侧留出空间")


@dataclass(frozen=True)
class CompositionPolicy:
    alpha_core: int = 16
    face_threshold: float = 0.55
    crop_limit: float = 0.20
    crop_recovery_limit: float = 0.40
    min_height_occupancy: float = 2/3
    face_scale_range: tuple | None = (0.75, 1.25)
    position_steps: int = 3
    scale_steps: int = 9

    def __post_init__(self):
        if not isinstance(self.alpha_core, int) or not 1 <= self.alpha_core <= 255:
            raise ValueError("Alpha 阈值必须为 [1,255] 内的整数")
        if not 0 <= self.face_threshold <= 1:
            raise ValueError("脸部置信度阈值须在 [0,1]")
        if not 0 <= self.crop_limit < 1 or not self.crop_limit <= self.crop_recovery_limit <= 1:
            raise ValueError("裁切阈值须满足 0 ≤ 常规阈值 < 1，且常规阈值 ≤ 补救阈值 ≤ 1")
        if not 0 < self.min_height_occupancy <= 1:
            raise ValueError("最低纵向占比须在 (0,1]")
        if self.face_scale_range is not None:
            value = tuple(self.face_scale_range)
            if len(value) != 2 or not all(math.isfinite(v) for v in value) or not 0 < value[0] <= 1 <= value[1]:
                raise ValueError("脸部尺寸范围须为两个有限比例，且满足 0 < 下限 ≤ 1 ≤ 上限")
            object.__setattr__(self, "face_scale_range", value)
        if any(not isinstance(v, int) or v < 1 for v in (self.position_steps, self.scale_steps)):
            raise ValueError("位置和缩放采样数必须为正整数")


def load_layout(path=None):
    return Layout(**json.loads(Path(path).read_text(encoding="utf-8-sig"))) if path else Layout()


def load_policy(path=None):
    return CompositionPolicy(**json.loads(Path(path).read_text(encoding="utf-8-sig"))) if path else CompositionPolicy()
