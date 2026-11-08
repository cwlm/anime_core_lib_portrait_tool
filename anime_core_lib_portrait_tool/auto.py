"""Single-image automatic processing; False means manual composition is needed."""
from pathlib import Path
import sys
from .dds import write_dds
from .config import CompositionPolicy, Layout
from .composition import CompositionStatus, analyze_transform
from .transform import read_image, render


def prepare(input_path, output_path, *, encoder, encoder_path, layout=Layout(),
            policy=CompositionPolicy(), overwrite=False):
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ValueError("输入和输出不能相同")
    image = read_image(input_path)
    result = analyze_transform(image, layout=layout, policy=policy)
    if not result.can_export:
        label = "待复核" if result.status is CompositionStatus.REVIEW else "转人工"
        detail = result.reason
        if result.metrics is not None:
            metrics = result.metrics
            detail += (f"；横向裁切 {metrics.crop_x:.1%}，纵向裁切 {metrics.crop_y:.1%}，"
                       f"有效像素裁切 {metrics.crop_pixels:.1%}，"
                       f"纵向占比 {metrics.height_occupancy:.1%}，"
                       f"脸部相对尺寸 {metrics.face_scale_ratio:.1%}")
        print(f"{label}：{input_path}；{detail}", file=sys.stderr, flush=True)
        return False
    write_dds(output_path, render(image,result.transform,layout=layout), encoder=encoder,
              encoder_path=encoder_path, overwrite=overwrite)
    return True
