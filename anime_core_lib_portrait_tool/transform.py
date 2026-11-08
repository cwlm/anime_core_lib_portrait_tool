"""Read, compose and render a portrait on a configured canvas."""
from dataclasses import dataclass
import math
from PIL import Image, ImageOps
from .config import Layout


@dataclass(frozen=True)
class Placement:
    scale: float
    x: float
    y: float


def read_image(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGBA")


def centered(image, *, layout=Layout()):
    width, height = layout.canvas
    margin = layout.margin
    left, top, right, bottom = image.getchannel("A").getbbox() or (0, 0, *image.size)
    scale = min((width-2*margin)/(right-left),(height-2*margin)/(bottom-top))
    return Placement(scale,width/2-(left+right)*scale/2,height/2-(top+bottom)*scale/2)


def render(image, placement, *, layout=Layout()):
    s, x, y = placement.scale, placement.x, placement.y
    if s <= 0 or not all(map(math.isfinite, (s, x, y))):
        raise ValueError("缩放必须为正数，位置必须为有限数值")
    return image.convert("RGBa").transform(
        layout.canvas, Image.Transform.AFFINE, (1/s, 0, -x/s, 0, 1/s, -y/s),
        resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0)).convert("RGBA")


def _detect(image, name, model, confidence, iou):
    # Import the runtime first so imgutils cannot silently install it.
    import onnxruntime as ort
    if "CUDAExecutionProvider" in ort.get_available_providers() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    from imgutils import detect
    return getattr(detect,name)(image,model_name=model,conf_threshold=confidence,iou_threshold=iou)


def detect_faces(image):
    return _detect(image,"detect_faces","face_detect_v1.4_s",0.25,0.7)


def detect_person(image):
    return _detect(image,"detect_person","person_detect_v1.3_s",0.3,0.5)


def _fit(box, bounds, layout):
    """Keep all content when possible; stop shrinking at 75% of the face scale."""
    x0, y0, x1, y1 = box
    cx, cy = (x0+x1)/2, (y0+y1)/2
    left, top, right, bottom = bounds
    xr, yr = layout.anchor_x, layout.anchor_y
    width, height = layout.canvas
    margin = layout.margin
    desired = math.sqrt(math.prod(layout.face_size)/((x1-x0)*(y1-y0)))
    limits = [desired,
              (width-2*margin)/(right-left),(height-2*margin)/(bottom-top)]
    for distance, room in ((cx-left,xr[1]-margin),(right-cx,width-margin-xr[0]),
                           (cy-top,yr[1]-margin),(bottom-cy,height-margin-yr[0])):
        if distance > 0:
            limits.append(room/distance)
    scale = max(min(limits),desired*0.75)

    def position(center, low, high, size, preferred, allowed):
        # These endpoints describe translations that retain the most content.
        # If the content is larger than the canvas, their order is reversed.
        near, far = sorted((margin+(center-low)*scale,size-margin-(high-center)*scale))
        lo = min(max(near,allowed[0]),allowed[1])
        hi = min(max(far,allowed[0]),allowed[1])
        return min(max(preferred,lo),hi)

    ax = position(cx,left,right,width,layout.anchor[0],xr)
    ay = position(cy,top,bottom,height,layout.anchor[1],yr)
    return Placement(scale,ax-cx*scale,ay-cy*scale)


def estimate_transform(image, *, layout=Layout()):
    """Shrink to preserve content, then translate and clip at the face-size floor."""
    bounds = image.getchannel("A").point(lambda a: 255 if a >= layout.alpha_core else 0).getbbox()
    if bounds is None:
        return None
    rgb = Image.alpha_composite(Image.new("RGBA",image.size,"white"),image).convert("RGB")
    faces = detect_faces(rgb)
    if not faces:
        return None
    def area(face):
        x0, y0, x1, y1 = face[0]
        return (x1-x0)*(y1-y0)
    candidates = [f for f in faces if f[2] >= 0.5]
    face = (max(candidates,key=lambda f: f[2]*math.sqrt(area(f)))
            if candidates else max(faces,key=lambda f: f[2]))
    if face[2] < layout.face_threshold or any(f is not face and f[2] >= 0.6 and area(f) >= area(face)*0.5 for f in faces):
        return None
    return _fit(face[0],bounds,layout)
