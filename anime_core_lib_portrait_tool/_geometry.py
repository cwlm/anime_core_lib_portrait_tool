"""Exact scale/translation geometry for alpha-threshold pixel rectangles."""
from dataclasses import dataclass
import math
import re


Bounds = tuple[float, float, float, float]
_FOREGROUND = re.compile(b"\xff+")


@dataclass(frozen=True)
class GeometryMetrics:
    crop_x: float
    crop_y: float
    crop_pixels: float
    height_occupancy: float


@dataclass(frozen=True)
class _RelativeRun:
    bounds: Bounds
    area: int


@dataclass(frozen=True)
class SubjectMask:
    """Runs are (left, right, row), with each row one source pixel high."""

    runs: tuple[tuple[int, int, int], ...]
    area: int

    @classmethod
    def from_core(cls, core):
        """Read a nonempty L image whose foreground pixels equal 255."""
        raw = core.tobytes()
        width = core.width
        runs = tuple(
            (match.start() - start, match.end() - start, y)
            for y in range(core.height)
            for start in (y * width,)
            for match in _FOREGROUND.finditer(raw, start, start + width)
        )
        return cls(runs, sum(right - left for left, right, _ in runs))

    def relative_to(self, center):
        """Express the source pixel rectangles relative to the face center."""
        cx, cy = center
        runs = tuple(_RelativeRun((left-cx, y-cy, right-cx, y+1-cy), right-left)
                     for left, right, y in self.runs)
        bounds = (min(run.bounds[0] for run in runs),
                  min(run.bounds[1] for run in runs),
                  max(run.bounds[2] for run in runs),
                  max(run.bounds[3] for run in runs))
        return RelativeMask(runs, bounds, self.area)


@dataclass(frozen=True)
class RelativeMask:
    """Foreground rectangles relative to a source face center."""

    runs: tuple[_RelativeRun, ...]
    bounds: Bounds
    area: int

    def measure(self, scale, anchor, canvas):
        """Measure output = scale * source_offset + target_face_anchor."""
        ax, ay = anchor
        width, height = canvas
        left, top, right, bottom = self.bounds
        left, right = left * scale + ax, right * scale + ax
        top, bottom = top * scale + ay, bottom * scale + ay
        crop_x = _span_loss(left, right, width)
        crop_y = _span_loss(top, bottom, height)
        if left >= 0 and top >= 0 and right <= width and bottom <= height:
            return GeometryMetrics(0.0, 0.0, 0.0, (bottom - top) / height)
        if right <= 0 or bottom <= 0 or left >= width or top >= height:
            return GeometryMetrics(crop_x, crop_y, 1.0, 0.0)

        scale_squared = scale * scale
        retained_areas = []
        visible_top, visible_bottom = float(height), 0.0
        for run in self.runs:
            x0, y0, x1, y1 = run.bounds
            x0, x1 = x0 * scale + ax, x1 * scale + ax
            y0, y1 = y0 * scale + ay, y1 * scale + ay
            if x1 <= 0 or y1 <= 0 or x0 >= width or y0 >= height:
                continue
            if x0 >= 0 and y0 >= 0 and x1 <= width and y1 <= height:
                retained_areas.append(run.area * scale_squared)
                visible_top = min(visible_top, y0)
                visible_bottom = max(visible_bottom, y1)
                continue

            visible_left, visible_right = max(x0, 0.0), min(x1, width)
            run_top, run_bottom = max(y0, 0.0), min(y1, height)
            area = (visible_right-visible_left)*(run_bottom-run_top)
            if area > 0:
                retained_areas.append(area)
                visible_top = min(visible_top, run_top)
                visible_bottom = max(visible_bottom, run_bottom)

        retained = math.fsum(retained_areas)
        crop_pixels = _unit_interval(1 - retained / (self.area * scale_squared))
        occupancy = (visible_bottom - visible_top) / height if retained_areas else 0.0
        return GeometryMetrics(crop_x, crop_y, crop_pixels, occupancy)


def _unit_interval(value):
    """Remove floating point overshoot from normalized geometric ratios."""
    return min(1.0, max(0.0, value))


def _span_loss(low, high, extent):
    retained = max(0.0, min(high, extent) - max(low, 0.0))
    return _unit_interval(1 - retained / (high - low))


