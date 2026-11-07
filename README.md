# 透明立绘转 DDS

只保留单图自动／手动处理，以及 CSV 批处理。输出固定为 1024×1024、直通 Alpha、单层 BC3／DXT5 DDS。

## 使用

安装基础依赖；按需安装自动检测和 GUI 依赖：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-auto.txt
python -m pip install -r requirements-gui.txt
```

NVTT 或 texconv 自行安装，调用时必须传入名称和可执行文件路径。

```powershell
python portrait.py auto --input source.png --output result.dds --encoder nvtt --encoder-path 'C:/Tools/nvtt_export.exe' --model-cache ./models
python portrait.py manual --input source.png --output result.dds --encoder texconv --encoder-path 'C:/Tools/texconv.exe'
python batch.py jobs.csv --encoder nvtt --encoder-path 'C:/Tools/nvtt_export.exe' --model-cache ./models
```

手动窗口：左键拖动，滚轮缩放，点击保存或 Ctrl+S 导出；取消不写文件。保存失败可以重试。默认禁止覆盖，--overwrite 允许覆盖。

命令行默认离线。--model-cache 指定 Hugging Face 缓存；需要下载模型时自行设置 HF_HUB_OFFLINE=0。已有 GPU 环境不需要再安装 requirements-auto.txt 中的 CPU 版 onnxruntime。

## CSV

```csv
input,output
images/a.png,output/a.dds
images/b.png,output/b.dds
```

路径相对 CSV 所在目录；CSV 使用 UTF-8，可带 BOM。先运行全部自动任务，再依次手动处理没有可靠主脸的图片。自动判定包括无脸、低分、大小相近的多脸和空透明图。文件读取、模型运行或编码异常会打印错误并继续其他任务，不打开手动窗口。

已有输出默认跳过；重跑会重新尝试没有输出的任务。没有状态文件、指纹或报告。手动取消停止人工队列。单图退出码为 0 已保存、2 需手动或取消、1 错误；批处理为 0 完成、1 有错误或取消、130 键盘中断。

## Python 接口

```python
from anime_core_lib_portrait_tool.auto import prepare
from anime_core_lib_portrait_tool import read_image, estimate_transform, render, write_dds

prepare("source.png", "result.dds",
        encoder="texconv", encoder_path="C:/Tools/texconv.exe")

image = read_image("source.png")
placement = estimate_transform(image)  # 无可靠主脸时返回 None
if placement is not None:
    candidate = render(image, placement)
    write_dds("other.dds", candidate,
              encoder="nvtt", encoder_path="C:/Tools/nvtt_export.exe")
```

数值接口使用 Placement(scale, x, y)，坐标为 EXIF 转正后的原图坐标：输出 = 原图 × scale + 偏移。自动构图只使用动漫人脸模型和 Alpha 内容边界，保留原有主脸选择及锚点活动范围。删除了人物辅助检测，因此装饰面积较大的图片可能把人物缩得更小。

## 文件

- portrait.py / batch.py：两个命令入口。
- anime_core_lib_portrait_tool/transform.py：读取、自动构图、渲染。
- anime_core_lib_portrait_tool/auto.py / manual.py：单图自动／手动流程。
- anime_core_lib_portrait_tool/dds.py / encoders/：两种外部编码器，编码成功后替换最终文件。
- anime_core_lib_portrait_tool/batch.py / cli.py：CSV 循环和命令行参数。
- tests/test_core.py：核心流程检查，运行 python -B -m unittest discover -s tests -v。
- 模型缓存与游戏素材不包含在本目录中，使用 --model-cache 指定模型缓存位置。
