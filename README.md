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

手动窗口：左键拖动、滚轮缩放图片；Ctrl+滚轮缩放视图，中键或右键平移视图。右侧可输入缩放、顺时针角度及原图原点在画布上的位置，点击“保存 DDS”或 Ctrl+S 导出，取消不写文件。输入角度时绕原图原点旋转，滚轮缩放以鼠标位置为中心。辅助框不写入输出。

自动构图检测主脸，从脸部参考尺寸开始，在允许的脸部中心范围内搜索平移和等比缩放，不旋转图片。仅靠平移和缩放无法满足条件时转人工，由人工决定是否旋转。位置与缩放采用有限采样，通过的候选优先选择脸部尺寸接近参考值的映射，搜索失败不表示数学上不存在可行映射。

每个候选都检查主体横向、纵向和有效像素裁切率，三项均须不超过 20%，且画布内可见主体高度须至少占画布高度的 2/3。初始裁切已达标但高度不足时尝试放大；初始三项裁切均不超过 40% 时可尝试缩小补救。调整后重新检查全部条件，缩小后高度不足同样转人工。脸部中心始终使用 `anchor_x`／`anchor_y` 范围，脸部框不得裁出画布。

默认按 Alpha≥16 定义主体。横纵裁切率分别计算完整变换后主体包围框在对应轴上损失的长度比例；有效像素裁切率按原图像素区域落在画布外的面积计算，部分像素按裁去面积计入。主体包围框来自真实 Alpha 内容，透明背景不计入；分离的饰物等有效内容也会参与计算。求解只计算几何映射，最终从原图执行一次仿射变换。

未通过时 `auto.prepare()` 返回 False，命令行退出码为 2，控制台显示原因和指标。目前规则只产生自动通过或转人工；待复核状态已预留，尚未设置额外触发规则。

筛选在写入 DDS 前进行，未通过时保留现有输出。已有进度文件中标记为 `done` 的任务不会自动重新检测，需要另行安排复核；手动入口不受这些筛选条件限制。

## 自定义构图

自动和手动处理都可通过 `--layout layout.json` 加载配置，格式见 [examples/layout.json](examples/layout.json)。

`canvas` 为画布尺寸，`anchor` 为脸部中心，`face_size` 为脸部参考尺寸，`anchor_x`／`anchor_y` 为脸部中心活动范围，`margin` 为内容边距，单位均为输出像素。调整画布时需同步调整脸部位置和范围。

默认纵向范围为 `145～205`，策略中的 `position_steps=5` 表示每个轴均匀采样 5 个位置，因此纵向基础采样点为 `145、160、175、190、205`，间隔 15 像素。搜索还会加入目标位置及按内容边界计算的适配位置；自定义范围后，均匀采样间隔会随范围变化。

自动处理的规则与几何布局分开，通过 `--policy policy.json` 加载，示例见 [examples/policy.json](examples/policy.json)。`alpha_core`、`face_threshold`、三项裁切阈值及最低纵向占比属于 `CompositionPolicy`。`face_scale_range` 为相对于参考脸部尺寸的等比缩放范围，默认 `[0.75, 1.25]`；设为 `null` 时仅以参考尺寸作为优选目标。尺寸比例按脸部框面积的平方根匹配，保持人物纵横比例。自动旋转的 `max_rotation`、`angle_step`、`angle_refinement` 配置已移除。

旧 `content_quantile`、`review_bottom_threshold`、`manual_top_loss_threshold` 已移除；布局 JSON 中的 `alpha_core`／`face_threshold` 需移入策略 JSON。`--policy` 仅适用于自动模式。比例阈值使用严格边界：裁切大于上限或纵向占比小于下限时拒绝，未添加浮点容差。

## Python 接口

```python
from anime_core_lib_portrait_tool.auto import prepare

saved = prepare("source.png", "result.dds",
                encoder="texconv", encoder_path="C:/Tools/texconv.exe")
```

手动处理改为从 `anime_core_lib_portrait_tool.manual` 导入 `prepare`。自动处理返回 False 表示需手动构图；手动处理返回 False 表示取消，保存成功均返回 True，处理错误会抛出异常。

两个入口都支持 `layout=load_layout("layout.json")` 和 `overwrite=True`，自动入口另支持 `policy=load_policy("policy.json")`。配置、变换、构图结果及底层接口均可从包顶层导入。

```python
from anime_core_lib_portrait_tool import (
    CompositionPolicy, analyze_transform, read_image, render,
)

image = read_image("source.png")
result = analyze_transform(image, policy=CompositionPolicy())
if result.can_export:
    preview = render(image, result.transform)
else:
    print(result.status, result.reasons, result.metrics)
```

`analyze_transform()` 返回 `CompositionResult`：`status` 为 `CompositionStatus` 枚举，`reasons` 为 `ReasonCode` 元组，`reason` 为中文说明。`metrics` 包含三项裁切率、纵向占比、脸部相对尺寸及脸部位置检查结果。`transform` 即使未通过也可能保留最佳候选供预览；自动导出必须检查 `can_export`。没有主体或可靠主脸时，映射和指标均为 `None`。`estimate_transform()` 仅返回通过的映射，否则为 `None`；已有检测结果可用 `faces=tuple_of_face_detections` 传入，避免重复检测。

`AffineTransform` 替代旧 `Placement`，保存原图到画布的正向系数 `(a,b,c,d,e,f)`：`x'=a*x+b*y+c`、`y'=d*x+e*y+f`。自动构图只生成平移和等比缩放，`b=d=0`。仿射工具与手动界面仍支持旋转；图像 Y 轴向下，正角度为顺时针。`compose(other)` 表示先执行 `other` 再执行自身。只有 `render()` 向 Pillow 传入逆向矩阵。构图接口位于 `composition.py`，检测接口位于 `detection.py`，`transform.py` 仅负责几何与渲染。图片、模型或编码错误继续抛出异常。

现有 `tests/test_composition_review.py` 针对旧构图规则，尚未迁移到新接口。
