"""CSV input,output: automatic pass, followed by manual composition."""
import csv
from pathlib import Path
from .auto import prepare as automatic


def run_batch(csv_path, *, encoder, encoder_path, overwrite=False):
    csv_path = Path(csv_path).resolve()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        jobs = [(csv_path.parent / row["input"], csv_path.parent / row["output"])
                for row in csv.DictReader(stream)]
    outputs = [output.resolve() for _, output in jobs]
    if len(set(outputs)) != len(outputs):
        raise ValueError("CSV 输出路径不能重复")
    if set(outputs) & {source.resolve() for source, _ in jobs}:
        raise ValueError("输出不能覆盖输入图片")
    pending, complete = [], True
    for source, output in jobs:
        if output.exists() and not overwrite:
            print(f"跳过已有输出：{output}")
            continue
        try:
            if not automatic(source, output, encoder=encoder, encoder_path=encoder_path, overwrite=overwrite):
                pending.append((source, output))
            else:
                print(f"完成：{output}")
        except Exception as exc:
            print(f"失败：{source}：{exc}")
            complete = False
    for source, output in pending:
        from .manual import prepare as manual
        try:
            if not manual(source, output, encoder=encoder, encoder_path=encoder_path, overwrite=overwrite):
                return False
            print(f"完成：{output}")
        except Exception as exc:
            print(f"失败：{source}：{exc}")
            complete = False
    return complete
