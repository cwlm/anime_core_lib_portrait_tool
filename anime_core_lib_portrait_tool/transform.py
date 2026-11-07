"""Read, compose and render a portrait on a fixed 1024px canvas."""
from dataclasses import dataclass
import math
from PIL import Image, ImageOps

CANVAS = (1024, 1024)
ANCHOR = (512, 175)
FACE_SIZE = (95, 92)
ANCHOR_X, ANCHOR_Y = (492, 546), (125, 258)


@dataclass(frozen=True)
class Placement:
    scale: float
    x: float
    y: float


def read_image(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGBA")


def centered(image):
    left, top, right, bottom = image.getchannel("A").getbbox() or (0, 0, *image.size)
    scale = min(1020 / (right - left), 1020 / (bottom - top))
    return Placement(scale, 512 - (left + right) * scale / 2,
                     512 - (top + bottom) * scale / 2)


def render(image, placement):
    s, x, y = placement.scale, placement.x, placement.y
    if s <= 0 or not all(map(math.isfinite, (s, x, y))):
        raise ValueError("缩放必须为正数，位置必须为有限数值")
    return image.convert("RGBa").transform(
        CANVAS, Image.Transform.AFFINE, (1/s, 0, -x/s, 0, 1/s, -y/s),
        resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0)).convert("RGBA")


def detect_faces(image):
    # Import the runtime first so imgutils cannot silently install it.
    import onnxruntime as ort
    if "CUDAExecutionProvider" in ort.get_available_providers() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    from imgutils.detect import detect_faces as detect
    return detect(image, model_name="face_detect_v1.4_s", conf_threshold=0.25, iou_threshold=0.7)


def estimate_transform(image):
    """Return a placement, or None when the image needs manual composition."""
    bounds = image.getchannel("A").point(lambda a: 255 if a >= 16 else 0).getbbox()
    if bounds is None:
        return None
    rgb = Image.alpha_composite(Image.new("RGBA", image.size, "white"), image).convert("RGB")
    faces = detect_faces(rgb)
    if not faces:
        return None
    def area(face):
        x0, y0, x1, y1 = face[0]
        return (x1 - x0) * (y1 - y0)
    candidates = [f for f in faces if f[2] >= 0.5] or faces
    face = max(candidates, key=lambda f: f[2] * math.sqrt(area(f)))
    if face[2] < 0.55 or any(f is not face and f[2] >= 0.6 and area(f) >= area(face)*0.5 for f in faces):
        return None
    x0, y0, x1, y1 = face[0]
    cx, cy = (x0+x1)/2, (y0+y1)/2
    left, top, right, bottom = bounds
    xr, yr = ANCHOR_X, ANCHOR_Y
    limits = [math.sqrt(math.prod(FACE_SIZE)/area(face)), 1020/(right-left), 1020/(bottom-top)]
    for distance, room in ((cx-left, xr[1]-2), (right-cx, 1022-xr[0]),
                           (cy-top, yr[1]-2), (bottom-cy, 1022-yr[0])):
        if distance > 0:
            limits.append(room/distance)
    scale = min(limits)
    ax = min(max(ANCHOR[0], xr[0], 2+(cx-left)*scale), xr[1], 1022-(right-cx)*scale)
    ay = min(max(ANCHOR[1], yr[0], 2+(cy-top)*scale), yr[1], 1022-(bottom-cy)*scale)
    return Placement(scale, ax-cx*scale, ay-cy*scale)
