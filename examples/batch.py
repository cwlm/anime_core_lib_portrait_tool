"""Local CSV batch example: automatic pass, then manual composition."""
import csv
import os
from pathlib import Path
import sys

sys.path.insert(0, r"E:\Modding\anime_core_lib_portrait_tool")
from anime_core_lib_portrait_tool.auto import prepare as automatic
from anime_core_lib_portrait_tool import load_layout

CSV = Path(r"E:\Modding\anime_core_lib_portrait_tool\examples\jobs.csv")
OPTIONS = dict(layout=load_layout(CSV.with_name("layout.json")), encoder="nvtt",
               encoder_path=r"C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools\nvtt_export.exe")


def run_batch(csv_path=CSV):
    csv_path = Path(csv_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        jobs = [(csv_path.parent / row["input"], csv_path.parent / row["output"])
                for row in csv.DictReader(stream)]
    pending, complete = [], True
    for source, output in jobs:
        if output.exists():
            print(f"跳过：{output}")
            continue
        try:
            if not automatic(source, output, **OPTIONS):
                pending.append((source, output))
            else:
                print(f"完成：{output}")
        except Exception as exc:
            print(f"失败：{source}：{exc}")
            complete = False
    for source, output in pending:
        from anime_core_lib_portrait_tool.manual import prepare as manual
        try:
            if not manual(source, output, **OPTIONS):
                return False
            print(f"完成：{output}")
        except Exception as exc:
            print(f"失败：{source}：{exc}")
            complete = False
    return complete


if __name__ == "__main__":
    os.environ["HF_HUB_CACHE"] = r"E:\Modding\portraits\models"
    os.environ["HF_HUB_OFFLINE"] = "1"
    raise SystemExit(0 if run_batch() else 1)
