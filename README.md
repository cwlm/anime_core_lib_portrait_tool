# 透明立绘转 DDS

将透明立绘自动或手动构图后导出为 DDS，每次处理一张图片。默认输出 1024×1024、BC3／DXT5，保留透明度。

## 安装

需要 Python 3.12+；Windows 自动处理请使用 Python 3.12。

```powershell
# 自动处理（CPU）和手动界面
python -m pip install --upgrade "anime-core-lib-portrait-tool[auto,gui]"

# NVIDIA GPU 自动处理和手动界面
python -m pip install --upgrade "anime-core-lib-portrait-tool[gpu,gui]"

# 仅图片读取、渲染和编码接口
python -m pip install --upgrade anime-core-lib-portrait-tool
```

auto 和 gpu 二选一。另需自行安装 NVTT 或 texconv，并在调用时指定可执行文件路径。

从源码安装（GPU 环境将 auto 换为 gpu）：

```powershell
git clone https://github.com/cwlm/anime_core_lib_portrait_tool.git
cd anime_core_lib_portrait_tool
python -m pip install -e ".[auto,gui]"
```

## 命令行

```powershell
portrait auto --input source.png --output result.dds --encoder nvtt --encoder-path 'C:/Tools/nvtt_export.exe' --model-cache ./models
portrait manual --input source.png --output result.dds --encoder texconv --encoder-path 'C:/Tools/texconv.exe'
```

默认不覆盖已有文件，添加 `--overwrite` 可覆盖。自动处理无法确定主脸时需自行改用 manual；退出码为 0 已保存、2 需手动或已取消、1 错误。

自动处理需要模型缓存，`--model-cache` 指定缓存目录。命令行默认离线，首次下载模型时先在 PowerShell 执行 `$env:HF_HUB_OFFLINE = "0"`。

手动窗口：左键拖动、滚轮缩放图片；Ctrl+滚轮缩放视图，中键或右键平移视图。右侧可输入缩放和位置，点击“保存 DDS”或 Ctrl+S 导出，取消不写文件。辅助框不写入输出。

## 自定义构图

自动和手动处理都可通过 `--layout layout.json` 加载配置，格式见 [examples/layout.json](examples/layout.json)。

`canvas` 为画布尺寸，`anchor` 为脸部中心，`face_size` 为脸部参考尺寸，`anchor_x`／`anchor_y` 为脸部中心活动范围，`margin` 为内容边距，单位均为输出像素。调整画布时需同步调整脸部位置和范围。

## Python 接口

```python
from anime_core_lib_portrait_tool.auto import prepare

saved = prepare("source.png", "result.dds",
                encoder="texconv", encoder_path="C:/Tools/texconv.exe")
```

手动处理改为从 `anime_core_lib_portrait_tool.manual` 导入 `prepare`。自动处理返回 False 表示需手动构图；手动处理返回 False 表示取消，保存成功均返回 True，处理错误会抛出异常。

两个入口都支持 `layout=load_layout("layout.json")` 和 `overwrite=True`。`load_layout`、`Layout` 以及底层接口 `read_image`、`estimate_transform`、`render`、`write_dds` 可从包顶层导入。
