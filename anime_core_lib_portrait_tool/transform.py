"""Affine geometry and one-pass rendering from the original portrait."""
from dataclasses import dataclass
import math
from PIL import Image, ImageOps
from .config import Layout


@dataclass(frozen=True)
class AffineTransform:
    """Map original-image coordinates to canvas coordinates.

    x' = a*x + b*y + c; y' = d*x + e*y + f.
    Image coordinates have a downward Y axis, so positive angles are clockwise.
    """
    a: float = 1
    b: float = 0
    c: float = 0
    d: float = 0
    e: float = 1
    f: float = 0

    def __post_init__(self):
        if not all(map(math.isfinite, self.coefficients)):
            raise ValueError("仿射变换系数必须为有限数值")

    @classmethod
    def similarity(cls, *, scale=1, angle=0, x=0, y=0):
        """Build an equal-scale rotation followed by translation."""
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("缩放必须为正的有限数值")
        radians = math.radians(angle)
        cosine, sine = math.cos(radians)*scale, math.sin(radians)*scale
        return cls(cosine, -sine, x, sine, cosine, y)

    @property
    def coefficients(self):
        return self.a, self.b, self.c, self.d, self.e, self.f

    @property
    def scale(self):
        """Return the scale of the transformed source X axis."""
        return math.hypot(self.a, self.d)

    @property
    def angle(self):
        """Return the clockwise source X-axis angle, in degrees."""
        return math.degrees(math.atan2(self.d, self.a))

    def map_point(self, x, y):
        return self.a*x + self.b*y + self.c, self.d*x + self.e*y + self.f

    def inverse(self):
        determinant = self.a*self.e - self.b*self.d
        if determinant == 0:
            raise ValueError("仿射变换不可逆")
        return AffineTransform(
            self.e/determinant, -self.b/determinant,
            (self.b*self.f - self.e*self.c)/determinant,
            -self.d/determinant, self.a/determinant,
            (self.d*self.c - self.a*self.f)/determinant,
        )

    def compose(self, other):
        """Return self after other: result(point) == self(other(point))."""
        return AffineTransform(
            self.a*other.a + self.b*other.d,
            self.a*other.b + self.b*other.e,
            self.a*other.c + self.b*other.f + self.c,
            self.d*other.a + self.e*other.d,
            self.d*other.b + self.e*other.e,
            self.d*other.c + self.e*other.f + self.f,
        )


def read_image(path):
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGBA")


def centered(image, *, layout=Layout()):
    width, height = layout.canvas
    margin = layout.margin
    left, top, right, bottom = image.getchannel("A").getbbox() or (0, 0, *image.size)
    scale = min((width-2*margin)/(right-left), (height-2*margin)/(bottom-top))
    return AffineTransform.similarity(
        scale=scale,
        x=width/2 - (left+right)*scale/2,
        y=height/2 - (top+bottom)*scale/2,
    )


def render(image, transform, *, layout=Layout()):
    """Resample the original image once; only Pillow receives the inverse map."""
    return image.convert("RGBa").transform(
        layout.canvas, Image.Transform.AFFINE, transform.inverse().coefficients,
        resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0),
    ).convert("RGBA")
