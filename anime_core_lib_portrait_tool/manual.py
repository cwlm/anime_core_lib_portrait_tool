"""Drag and scale a portrait; save or cancel."""
from pathlib import Path
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QGraphicsItem, QGraphicsPixmapItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout)
from .dds import write_dds
from .transform import CANVAS, Placement, centered, read_image, render


class PortraitView(QGraphicsView):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(QRectF(0, 0, *CANVAS))
        self.setBackgroundBrush(QColor("#555555"))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.item = QGraphicsPixmapItem(QPixmap.fromImage(ImageQt(image)))
        self.item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.scene().addItem(self.item)
        pen = QPen(QColor("white"))
        pen.setCosmetic(True)
        border = self.scene().addRect(QRectF(0, 0, *CANVAS), pen)
        border.setZValue(1)
        border.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        p = centered(image)
        self.item.setScale(p.scale)
        self.item.setPos(p.x, p.y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        old = self.item.scale()
        scale = max(0.0001, min(100, old * 1.12 ** (event.angleDelta().y() / 120)))
        self.item.setPos(point + (self.item.pos() - point) * (scale / old))
        self.item.setScale(scale)
        event.accept()

    def placement(self):
        return Placement(self.item.scale(), self.item.x(), self.item.y())


class PortraitEditor(QDialog):
    def __init__(self, image, output, *, encoder, encoder_path, overwrite=False):
        super().__init__()
        self.image, self.output = image, output
        self.encoder, self.encoder_path, self.overwrite = encoder, encoder_path, overwrite
        self.saved = False
        self.setWindowTitle("立绘排版：拖动移动，滚轮缩放，Ctrl+S 保存")
        self.resize(820, 880)
        layout = QVBoxLayout(self)
        self.view = PortraitView(image)
        layout.addWidget(self.view)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        for title, action in (("保存 DDS", self.save), ("取消", self.reject)):
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(action)
            buttons.addWidget(button)
        shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        shortcut.activated.connect(self.save)

    def save(self):
        try:
            write_dds(self.output, render(self.image, self.view.placement()),
                      encoder=self.encoder, encoder_path=self.encoder_path, overwrite=self.overwrite)
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.saved = True
        self.accept()


def prepare(input_path, output_path, *, encoder, encoder_path, overwrite=False):
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ValueError("输入和输出不能相同")
    if Path(output_path).exists() and not overwrite:
        raise FileExistsError(output_path)
    image = read_image(input_path)
    app = QApplication.instance() or QApplication([])
    editor = PortraitEditor(image, output_path, encoder=encoder, encoder_path=encoder_path, overwrite=overwrite)
    editor.exec()
    return editor.saved
