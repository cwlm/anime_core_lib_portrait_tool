"""Search portrait mappings and report composition decisions without rendering."""
from dataclasses import dataclass
from enum import StrEnum
import math

from PIL import Image

from . import detection
from ._geometry import SubjectMask
from .config import CompositionPolicy, Layout
from .detection import FaceDetection, PersonDetection
from .transform import AffineTransform


class CompositionStatus(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"


class ReasonCode(StrEnum):
    EMPTY_CONTENT = "empty_content"
    FACE_NOT_FOUND = "face_not_found"
    LOW_FACE_CONFIDENCE = "low_face_confidence"
    AMBIGUOUS_FACES = "ambiguous_faces"
    PERSON_NOT_FOUND = "person_not_found"
    PERSON_CLIPPED = "person_clipped"
    FACE_OUTSIDE_TARGET = "face_outside_target"
    FACE_CLIPPED = "face_clipped"
    FACE_SIZE_MISMATCH = "face_size_mismatch"
    EXCESSIVE_CROP = "excessive_crop"
    INSUFFICIENT_HEIGHT = "insufficient_height"
    SEARCH_EXHAUSTED = "search_exhausted"


_REASON_TEXT = {
    ReasonCode.EMPTY_CONTENT: "没有有效的 Alpha 内容",
    ReasonCode.FACE_NOT_FOUND: "未检出人脸",
    ReasonCode.LOW_FACE_CONFIDENCE: "主脸置信度低于阈值",
    ReasonCode.AMBIGUOUS_FACES: "多张可靠人脸，无法确定唯一主脸",
    ReasonCode.PERSON_NOT_FOUND: "未找到主脸对应的人物框",
    ReasonCode.PERSON_CLIPPED: "人物框超出画布",
    ReasonCode.FACE_OUTSIDE_TARGET: "脸部中心不在允许范围内",
    ReasonCode.FACE_CLIPPED: "脸部框超出画布",
    ReasonCode.FACE_SIZE_MISMATCH: "脸部尺寸超出允许范围",
    ReasonCode.EXCESSIVE_CROP: "主体裁切超过允许比例",
    ReasonCode.INSUFFICIENT_HEIGHT: "可见主体纵向占比不足",
    ReasonCode.SEARCH_EXHAUSTED: "当前搜索未找到合格映射",
}


@dataclass(frozen=True)
class CompositionMetrics:
    crop_x: float
    crop_y: float
    crop_pixels: float
    height_occupancy: float
    face_scale_ratio: float
    face_in_target: bool
    face_in_canvas: bool
    person_in_canvas: bool | None = None
    face_scale_min: float | None = None

    @property
    def max_crop(self):
        return max(self.crop_x, self.crop_y, self.crop_pixels)


@dataclass(frozen=True)
class CompositionResult:
    status: CompositionStatus
    transform: AffineTransform | None
    reasons: tuple[ReasonCode, ...] = ()
    metrics: CompositionMetrics | None = None

    @property
    def can_export(self):
        return self.status is CompositionStatus.AUTO and self.transform is not None

    @property
    def reason(self):
        """Human-readable diagnostics; callers route by status/reason enums."""
        return "；".join(_REASON_TEXT[code] for code in self.reasons) or "构图通过"


@dataclass(frozen=True)
class _Candidate:
    transform: AffineTransform
    metrics: CompositionMetrics
    anchor_distance: float


def _face_area(face):
    x0, y0, x1, y1 = face.box
    return (x1-x0)*(y1-y0)


def _select_face(faces, policy):
    if not faces:
        return None, ReasonCode.FACE_NOT_FOUND
    confident = [face for face in faces if face.confidence >= 0.5]
    face = (max(confident, key=lambda item: item.confidence*math.sqrt(_face_area(item)))
            if confident else max(faces, key=lambda item: item.confidence))
    if face.confidence < policy.face_threshold:
        return None, ReasonCode.LOW_FACE_CONFIDENCE
    if any(other is not face and other.confidence >= 0.6
           and _face_area(other) >= _face_area(face)*0.5 for other in faces):
        return None, ReasonCode.AMBIGUOUS_FACES
    return face, None


def _select_person(persons, face, policy):
    fx0, fy0, fx1, fy1 = face.box
    matched = []
    for person in persons:
        x0, y0, x1, y1 = person.box
        intersection = max(0, min(x1, fx1)-max(x0, fx0)) * max(0, min(y1, fy1)-max(y0, fy0))
        if intersection / _face_area(face) >= policy.person_face_overlap:
            matched.append(person)
    return max(matched, key=lambda person: person.confidence, default=None)


def _axis_positions(low, high, preferred, start, end, size, scale, margin, count):
    values = {preferred}
    if count > 1:
        values.update(low + (high-low)*i/(count-1) for i in range(count))
    fit_low = max(low, margin-start*scale)
    fit_high = min(high, size-margin-end*scale)
    if fit_low <= fit_high:
        values.add(min(max(preferred, fit_low), fit_high))
    else:
        values.add(min(max(size/2-(start+end)*scale/2, low), high))
    return sorted(values, key=lambda value: (abs(value-preferred), value))


def _placements(bounds, face_center, scale, layout, policy):
    left, top, right, bottom = bounds
    width, height = layout.canvas
    xs = _axis_positions(*layout.anchor_x, layout.anchor[0], left, right,
                         width, scale, layout.margin, policy.position_steps)
    ys = _axis_positions(*layout.anchor_y, layout.anchor[1], top, bottom,
                         height, scale, layout.margin, policy.position_steps)
    cx, cy = face_center
    for ax in xs:
        for ay in ys:
            yield (ax, ay), AffineTransform.similarity(
                scale=scale, x=ax-cx*scale, y=ay-cy*scale)


def _box_in_canvas(box, transform, canvas):
    x0, y0, x1, y1 = box
    width, height = canvas
    return all(0 <= tx <= width and 0 <= ty <= height
               for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
               for tx, ty in (transform.map_point(x, y),))


def _measure_candidate(subject, face, anchor, transform, scale, face_scale_ratio, layout,
                       *, person=None, face_scale_min=None):
    geometry = subject.measure(scale, anchor, layout.canvas)
    width, height = layout.canvas
    face_in_canvas = _box_in_canvas(face.box, transform, layout.canvas)
    face_in_target = (layout.anchor_x[0] <= anchor[0] <= layout.anchor_x[1]
                      and layout.anchor_y[0] <= anchor[1] <= layout.anchor_y[1])
    person_in_canvas = None
    height_occupancy = geometry.height_occupancy
    if person is not None:
        person_in_canvas = _box_in_canvas(person.box, transform, layout.canvas)
        _, top = transform.map_point(person.box[0], person.box[1])
        _, bottom = transform.map_point(person.box[2], person.box[3])
        height_occupancy = max(0, min(bottom, height)-max(top, 0)) / height
    return _Candidate(
        transform,
        CompositionMetrics(geometry.crop_x, geometry.crop_y, geometry.crop_pixels,
                           height_occupancy, face_scale_ratio,
                           face_in_target, face_in_canvas, person_in_canvas, face_scale_min),
        math.hypot((anchor[0]-layout.anchor[0])/width,
                   (anchor[1]-layout.anchor[1])/height),
    )


def evaluate_candidate(metrics, *, policy=CompositionPolicy()):
    """Apply the same final constraints to every search branch."""
    reasons = []
    if not metrics.face_in_target:
        reasons.append(ReasonCode.FACE_OUTSIDE_TARGET)
    if not metrics.face_in_canvas:
        reasons.append(ReasonCode.FACE_CLIPPED)
    if metrics.person_in_canvas is False:
        reasons.append(ReasonCode.PERSON_CLIPPED)
    if policy.face_scale_range is not None:
        low, high = policy.face_scale_range
        if metrics.face_scale_min is not None:
            low = metrics.face_scale_min
        if not low <= metrics.face_scale_ratio <= high:
            reasons.append(ReasonCode.FACE_SIZE_MISMATCH)
    if metrics.person_in_canvas is None and metrics.max_crop > policy.crop_limit:
        reasons.append(ReasonCode.EXCESSIVE_CROP)
    if metrics.height_occupancy < policy.min_height_occupancy:
        reasons.append(ReasonCode.INSUFFICIENT_HEIGHT)
    return tuple(reasons)


def _scale_samples(low, high, count, critical):
    if low > high:
        return ()
    values = {low, high}
    if count > 1 and low < high:
        ratio = high/low
        values.update(low*ratio**(i/(count-1)) for i in range(count))
    values.update(value for value in critical if low <= value <= high)
    return sorted(values)


def _contain_scale(bounds, layout):
    """Largest scale with some allowed face center retaining the full body."""
    left, top, right, bottom = bounds
    width, height = layout.canvas
    margin = layout.margin
    limits = [(width-2*margin)/(right-left), (height-2*margin)/(bottom-top)]
    for distance, room in ((-left, layout.anchor_x[1]-margin),
                           (right, width-margin-layout.anchor_x[0]),
                           (-top, layout.anchor_y[1]-margin),
                           (bottom, height-margin-layout.anchor_y[0])):
        if distance > 0:
            limits.append(room/distance)
    return min(limits)


def _generate_alpha_candidates(subject, face, target_scale, layout, policy):
    x0, y0, x1, y1 = face.box
    center = ((x0+x1)/2, (y0+y1)/2)
    relative = subject.relative_to(center)

    def at_ratio(ratio):
        scale = target_scale*ratio
        return [_measure_candidate(relative, face, anchor, transform, scale, ratio, layout)
                for anchor, transform in _placements(
                    relative.bounds, center, scale, layout, policy)]

    initial = at_ratio(1.0)
    yield from initial
    needs_growth = any(candidate.metrics.max_crop <= policy.crop_limit
                       and candidate.metrics.height_occupancy < policy.min_height_occupancy
                       for candidate in initial)
    needs_recovery = any(policy.crop_limit < candidate.metrics.max_crop
                         <= policy.crop_recovery_limit for candidate in initial)
    left, top, right, bottom = relative.bounds
    width, height = layout.canvas
    height_scale = policy.min_height_occupancy*height/(bottom-top)
    containment = _contain_scale(relative.bounds, layout)

    if needs_growth:
        # Even a full-width/height intersection must retain the required extent.
        upper = min(width/((1-policy.crop_limit)*(right-left)),
                    height/((1-policy.crop_limit)*(bottom-top)))/target_scale
        if policy.face_scale_range is not None:
            upper = min(upper, policy.face_scale_range[1])
        for ratio in _scale_samples(1.0, upper, policy.scale_steps, (height_scale/target_scale,)):
            if ratio > 1:
                yield from at_ratio(ratio)

    if needs_recovery:
        lower = max(min(containment/target_scale, 1.0), height_scale/target_scale)
        if policy.face_scale_range is not None:
            lower = max(lower, policy.face_scale_range[0])
        for ratio in _scale_samples(lower, 1.0, policy.scale_steps, (height_scale/target_scale,)):
            if ratio < 1:
                yield from at_ratio(ratio)


def _generate_person_candidates(subject, face, person, target_scale, layout, policy):
    x0, y0, x1, y1 = face.box
    center = ((x0+x1)/2, (y0+y1)/2)
    relative = subject.relative_to(center)
    px0, py0, px1, py1 = person.box
    # A partial face overlap is sufficient for matching, but both boxes must fit.
    bounds = (min(x0, px0)-center[0], min(y0, py0)-center[1],
              max(x1, px1)-center[0], max(y1, py1)-center[1])
    fit_ratio = _contain_scale(bounds, layout)/target_scale
    height_ratio = policy.min_height_occupancy*layout.canvas[1]/((py1-py0)*target_scale)
    lower, upper = height_ratio, fit_ratio
    face_scale_min = None
    if policy.face_scale_range is not None:
        face_scale_min = min(policy.face_scale_range[0], fit_ratio)
        lower = max(lower, face_scale_min)
        upper = min(upper, policy.face_scale_range[1])

    # Keep a fully contained candidate even if height and face-size rules conflict.
    ratios = {1.0, upper}
    ratios.update(_scale_samples(lower, upper, policy.scale_steps, (1.0, height_ratio)))
    for ratio in sorted(ratios):
        scale = target_scale*ratio
        for anchor, transform in _placements(bounds, center, scale, layout, policy):
            yield _measure_candidate(relative, face, anchor, transform, scale, ratio, layout,
                                     person=person, face_scale_min=face_scale_min)


def _success_rank(candidate):
    return (abs(math.log(candidate.metrics.face_scale_ratio)),
            candidate.anchor_distance, candidate.metrics.crop_pixels, candidate.metrics.max_crop)


def _failure_rank(candidate, policy):
    metrics = candidate.metrics
    crop_violation = (max(0, metrics.max_crop-policy.crop_limit)
                      if metrics.person_in_canvas is None else 0)
    violation = (crop_violation
                 + max(0, policy.min_height_occupancy-metrics.height_occupancy)
                 + int(not metrics.face_in_target) + int(not metrics.face_in_canvas))
    if policy.face_scale_range is not None:
        low, high = policy.face_scale_range
        if metrics.face_scale_min is not None:
            low = metrics.face_scale_min
        violation += max(0, low-metrics.face_scale_ratio, metrics.face_scale_ratio-high)
    return int(metrics.person_in_canvas is False), violation, *_success_rank(candidate)


def solve_composition(core, face, *, person=None, layout=Layout(), policy=CompositionPolicy()):
    """Search scale/position samples without rotation; retain rejected candidates."""
    subject = SubjectMask.from_core(core)
    target_scale = math.sqrt(math.prod(layout.face_size)/_face_area(face))
    best_auto, best_manual = None, None

    candidates = (_generate_person_candidates(subject, face, person, target_scale, layout, policy)
                  if person is not None else
                  _generate_alpha_candidates(subject, face, target_scale, layout, policy))
    for candidate in candidates:
        if not evaluate_candidate(candidate.metrics, policy=policy):
            if best_auto is None or _success_rank(candidate) < _success_rank(best_auto):
                best_auto = candidate
        elif best_manual is None or _failure_rank(candidate, policy) < _failure_rank(best_manual, policy):
            best_manual = candidate

    if best_auto is not None:
        return CompositionResult(CompositionStatus.AUTO, best_auto.transform, metrics=best_auto.metrics)
    reasons = (*evaluate_candidate(best_manual.metrics, policy=policy), ReasonCode.SEARCH_EXHAUSTED)
    return CompositionResult(CompositionStatus.MANUAL, best_manual.transform, reasons, best_manual.metrics)


def analyze_transform(image, *, layout=Layout(), policy=CompositionPolicy(),
                      faces: tuple[FaceDetection, ...] | None = None,
                      persons: tuple[PersonDetection, ...] | None = None):
    """Detect the main face and return a mapping plus an explicit routing decision.

    Explicit faces/persons avoid repeated detection. An unmatched main face returns
    REVIEW with an alpha-based candidate, so callers can render a warning preview.
    """
    core = image.getchannel("A").point(lambda alpha: 255 if alpha >= policy.alpha_core else 0)
    if core.getbbox() is None:
        return CompositionResult(CompositionStatus.MANUAL, None, (ReasonCode.EMPTY_CONTENT,))
    rgb = None
    if faces is None:
        rgb = Image.alpha_composite(Image.new("RGBA", image.size, "white"), image).convert("RGB")
        faces = detection.detect_faces(rgb)
    face, reason = _select_face(faces, policy)
    if reason is not None:
        return CompositionResult(CompositionStatus.MANUAL, None, (reason,))
    if persons is None:
        if rgb is None:
            rgb = Image.alpha_composite(Image.new("RGBA", image.size, "white"), image).convert("RGB")
        persons = detection.detect_person(rgb)
    person = _select_person(persons, face, policy)
    result = solve_composition(core, face, person=person, layout=layout, policy=policy)
    if person is None:
        return CompositionResult(CompositionStatus.REVIEW, result.transform,
                                 (ReasonCode.PERSON_NOT_FOUND, *result.reasons), result.metrics)
    return result


def estimate_transform(image, *, layout=Layout(), policy=CompositionPolicy(), faces=None, persons=None):
    result = analyze_transform(image, layout=layout, policy=policy, faces=faces, persons=persons)
    return result.transform if result.can_export else None
