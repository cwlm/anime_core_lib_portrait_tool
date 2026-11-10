"""Model-backed anime face and person detection."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceDetection:
    box: tuple[float, float, float, float]
    confidence: float


@dataclass(frozen=True)
class PersonDetection:
    box: tuple[float, float, float, float]
    confidence: float


def _detect(image, name, model, confidence, iou):
    # Import the runtime first so imgutils cannot silently install it.
    import onnxruntime as ort
    if "CUDAExecutionProvider" in ort.get_available_providers() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    from imgutils import detect
    return getattr(detect, name)(image, model_name=model,
                                conf_threshold=confidence, iou_threshold=iou)


def detect_faces(image):
    return tuple(FaceDetection(tuple(float(v) for v in box), float(confidence))
                 for box, _, confidence in _detect(
                     image, "detect_faces", "face_detect_v1.4_s", 0.25, 0.7))


def detect_person(image):
    return tuple(PersonDetection(tuple(float(v) for v in box), float(confidence))
                 for box, _, confidence in _detect(
                     image, "detect_person", "person_detect_v1.3_s", 0.3, 0.5))
