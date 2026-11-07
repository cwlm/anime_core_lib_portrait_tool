# 透明立绘转 DDS

单图自动／手动处理工具，CSV 批处理作为独立示例放在 examples/。默认输出 1024×1024（可配置）、直通 Alpha、单层 BC3／DXT5 DDS。

## 安装

项目使用 pyproject.toml 和 Hatchling 管理依赖与打包，需要 Python 3.12 或更新版本。Windows 上完整自动处理目前使用 Python 3.12：自动检测库依赖 NumPy 1.x，暂不能在更新的 Python 上安装。

在项目目录按需安装，pip 默认选择稳定版：

```powershell
# 自动处理（CPU）和手动界面
python -m pip install --upgrade ".[auto,gui]"

# NVIDIA GPU 自动处理和手动界面
python -m pip install --upgrade ".[gpu,gui]"

# 仅图片读取、渲染和编码接口
python -m pip install --upgrade .
```

auto 和 gpu 二选一，避免同时安装 CPU 和 GPU 版 ONNX Runtime。开发时可加 -e 使用可编辑安装。

NVTT 或 texconv 自行安装，调用时必须传入名称和可执行文件路径。

```powershell
portrait auto --input source.png --output result.dds --encoder nvtt --encoder-path 'C:/Tools/nvtt_export.exe' --model-cache ./models
portrait manual --input source.png --output result.dds --encoder texconv --encoder-path 'C:/Tools/texconv.exe'
```

手动窗口：左键拖动／滚轮调整图片；Ctrl+滚轮缩放查看，中键或右键平移视图。“查看完整画布”重置视图，查看操作不改变输出构图。右侧可以输入缩放百分比及左上角 X／Y，“立绘居中”重置排版。白框是输出画布，橙框是脸部参考，青框是原图边界，紫框是可见内容边界；辅助框不写入 DDS。点击保存或 Ctrl+S 导出，取消不写文件；默认禁止覆盖，--overwrite 允许覆盖。

命令行默认离线。--model-cache 指定 Hugging Face 缓存；需要下载模型时自行设置 HF_HUB_OFFLINE=0。

## 批处理示例

全部批处理逻辑位于 examples/batch.py，正式包只提供单图接口。示例内已填写本机项目路径、NVTT 路径和模型缓存路径，按需直接修改。

```csv
input,output
images/source.png,output/result.dds
```

```powershell
& 'D:/Miniconda3/envs/ck3-resource/python.exe' -X utf8 examples/batch.py
```

示例图片 examples/images/source.png 来自本机素材，图片目录和输出目录均已加入 .gitignore，不提交到仓库或打入安装包。

路径相对 CSV 所在目录；CSV 使用 UTF-8，可带 BOM。先运行全部自动任务，再依次手动处理没有可靠主脸的图片。自动判定包括无脸、低分、大小相近的多脸和空透明图。文件读取、模型运行或编码异常会打印错误并继续其他任务，不打开手动窗口。

已有输出默认跳过；重跑会重新尝试没有输出的任务。取消手动窗口会停止人工队列。单图退出码为 0 已保存、2 需手动或取消、1 错误；批处理示例为 0 完成、1 有错误或取消。

## 画布与构图配置

默认画布为 1024×1024。自动和手动入口都支持 --layout，使用同一套画布、脸部参考及活动范围。配置示例见 examples/layout.json：

```powershell
portrait manual --input source.png --output result.dds --encoder nvtt --encoder-path 'C:/Tools/nvtt_export.exe' --layout examples/layout.json
```

修改 canvas 时，一并设置 anchor、face_size、anchor_x 和 anchor_y；坐标单位均为输出像素。margin 是内容边距，alpha_core 和 face_threshold 分别控制自动取景的 Alpha 阈值与主脸置信度。

Python 接口使用 load_layout(path) 或 Layout(...)；将 layout 传给 prepare、estimate_transform 和 render 即可。批处理示例已共用 examples/layout.json。

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

数值接口使用 Placement(scale, x, y)，坐标为 EXIF 转正后的原图坐标：输出 = 原图 × scale + 偏移。自动构图使用动漫人脸模型和 Alpha 内容边界；装饰面积较大的图片可能把人物缩得更小。

## 开发与构建

```powershell
python -B -m unittest discover -s tests -v
python -m pip install --upgrade build
python -m build
```

构建产物位于 dist/。依赖、可选功能和命令入口统一在 pyproject.toml 中声明。模型缓存、图片素材和外部编码器不打入安装包。
