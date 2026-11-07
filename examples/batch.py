import csv
import os
from pathlib import Path
import sys

# 直接从源码运行时使用本机项目路径，按需修改。
sys.path.insert(0, r"E:\Modding\anime_core_lib_portrait_tool")
from anime_core_lib_portrait_tool.auto import prepare as automatic
from anime_core_lib_portrait_tool import load_layout

CSV = Path(r"E:\Modding\anime_core_lib_portrait_tool\examples\jobs.csv")
# 两种处理方式共用布局；布局文件在上述 CSV 旁，编码器路径按本机安装位置修改。
OPTIONS = dict(layout=load_layout(CSV.with_name("layout.json")), encoder="nvtt",
               encoder_path=r"C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools\nvtt_export.exe")


def run_batch(csv_path=CSV):
    csv_path = Path(csv_path)
    # CSV 可带 UTF-8 BOM，列名为 input、output；路径相对 CSV 所在目录。
    # 例如：images/source.png,output/result.dds
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        jobs = [(csv_path.parent / row["input"], csv_path.parent / row["output"])
                for row in csv.DictReader(stream)]
    pending, complete = [], True
    for source, output in jobs:
        # 重跑时只处理尚未生成输出的任务。
        if output.exists():
            print(f"跳过：{output}")
            continue
        try:
            # 无可靠主脸时加入人工队列，等全部自动任务结束后再处理。
            if not automatic(source, output, **OPTIONS):
                pending.append((source, output))
            else:
                print(f"完成：{output}")
        except Exception as exc:
            # 读取、模型或编码异常只记录失败，不转入人工队列。
            print(f"失败：{source}：{exc}")
            complete = False
    for source, output in pending:
        # 只有需要人工处理时才加载 GUI 依赖。
        from anime_core_lib_portrait_tool.manual import prepare as manual
        try:
            if not manual(source, output, **OPTIONS):
                # 用户取消时停止后续人工任务。
                return False
            print(f"完成：{output}")
        except Exception as exc:
            print(f"失败：{source}：{exc}")
            complete = False
    return complete


if __name__ == "__main__":
    # 在项目目录执行 python -X utf8 examples/batch.py。
    # 使用本机模型缓存；需要下载模型时将 HF_HUB_OFFLINE 改为 "0"。
    os.environ["HF_HUB_CACHE"] = r"E:\Modding\portraits\models"
    os.environ["HF_HUB_OFFLINE"] = "1"
    # 退出码：0 全部完成，1 有错误或取消。
    raise SystemExit(0 if run_batch() else 1)
