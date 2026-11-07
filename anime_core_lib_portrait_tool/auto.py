"""Single-image automatic processing; False means manual composition is needed."""
from pathlib import Path
from .dds import write_dds
from .transform import read_image, estimate_transform, render


def prepare(input_path, output_path, *, encoder, encoder_path, overwrite=False):
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ValueError("输入和输出不能相同")
    image = read_image(input_path)
    placement = estimate_transform(image)
    if placement is None:
        return False
    write_dds(output_path, render(image, placement), encoder=encoder,
              encoder_path=encoder_path, overwrite=overwrite)
    return True
