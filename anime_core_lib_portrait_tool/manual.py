"""Manual composition with numeric placement, view navigation and guides."""
from pathlib import Path
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDoubleSpinBox,
    QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout)
from .config import Layout
from .dds import write_dds
from .transform import Placement, centered, read_image, render


DEFAULT_LAYOUT = Layout(anchor=(494.5,154.5), face_size=(123,113))


class PortraitView(QGraphicsView):
    placement_changed = Signal(object)

    def __init__(self, image, *, layout=DEFAULT_LAYOUT, parent=None):
        super().__init__(parent)
        self.config = layout
        self._pan, self._view_changed = None, False
        self.setScene(QGraphicsScene(self))
        extent = max(*image.size, *layout.canvas) * 4
        self.setSceneRect(-extent, -extent, extent*3, extent*3)
        self.setBackgroundBrush(QColor("#444444"))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.item = QGraphicsPixmapItem(QPixmap.fromImage(ImageQt(image)))
        self.item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.scene().addItem(self.item)
        self.outline(QRectF(0,0,*layout.canvas), "white")
        ax, ay = layout.anchor
        fw, fh = layout.face_size
        left, top, right, bottom = image.getchannel("A").getbbox() or (0,0,*image.size)
        self.guides = [
            self.outline(QRectF(ax-fw/2,ay-fh/2,fw,fh), "#e89b16"),
            self.outline(QRectF(0,0,*image.size), "#45c9ed", self.item),
            self.outline(QRectF(left,top,right-left,bottom-top), "#b58aee", self.item),
        ]
        width, height = layout.canvas
        self.grid_lines = []
        pen = QPen(QColor(255,255,255,160))
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        for division in (1/3, 2/3):
            for coordinates in ((width*division,0,width*division,height),
                                (0,height*division,width,height*division)):
                line = self.scene().addLine(*coordinates,pen)
                line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                line.setZValue(1)
                self.grid_lines.append(line)
        self.set_placement(centered(image, layout=layout))

    def outline(self, rect, color, parent=None):
        item = QGraphicsRectItem(rect, parent)
        pen = QPen(QColor(color))
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        if parent is None:
            self.scene().addItem(item)
        item.setZValue(1)
        return item

    def fit_view(self):
        self.fitInView(QRectF(0,0,*self.config.canvas).adjusted(-20,-20,20,20),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._view_changed = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._view_changed:
            self.fit_view()

    def wheelEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        factor = 1.12 ** max(-5, min(5, event.angleDelta().y()/120))
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            old = self.transform().m11()
            factor = max(0.02,min(32,old*factor))/old
            self.scale(factor,factor)
            moved = self.mapToScene(event.position().toPoint())
            self.translate(moved.x()-point.x(),moved.y()-point.y())
            self._view_changed = True
        else:
            p = self.placement()
            scale = max(0.00001,min(10000,p.scale*factor))
            self.set_placement(Placement(scale,point.x()+(p.x-point.x())*scale/p.scale,
                                         point.y()+(p.y-point.y())*scale/p.scale))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.MiddleButton,Qt.MouseButton.RightButton):
            self._pan = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            current = event.position().toPoint()
            delta = current-self._pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            self._pan, self._view_changed = current, True
            event.accept()
        else:
            super().mouseMoveEvent(event)
            self.placement_changed.emit(self.placement())

    def mouseReleaseEvent(self, event):
        if self._pan is not None and event.button() in (Qt.MouseButton.MiddleButton,Qt.MouseButton.RightButton):
            self._pan = None
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def set_placement(self, placement):
        self.item.setScale(placement.scale)
        self.item.setPos(placement.x,placement.y)
        self.placement_changed.emit(placement)

    def placement(self):
        return Placement(self.item.scale(),self.item.x(),self.item.y())


class PortraitEditor(QDialog):
    def __init__(self, image, output, *, encoder, encoder_path, layout=DEFAULT_LAYOUT, overwrite=False):
        super().__init__()
        self.image, self.output, self.config = image, output, layout
        self.encoder, self.encoder_path, self.overwrite = encoder, encoder_path, overwrite
        self.saved = False
        self.setWindowTitle("立绘排版")
        self.resize(1000,820)
        window = QVBoxLayout(self)
        body = QHBoxLayout()
        window.addLayout(body)
        self.view = PortraitView(image,layout=layout)
        body.addWidget(self.view,1)
        side = QVBoxLayout()
        body.addLayout(side)
        side.addWidget(QLabel(f"输出 {layout.canvas[0]} × {layout.canvas[1]}\n"
                             "左键拖动／滚轮缩放图片\nCtrl+滚轮缩放查看\n中键／右键移动视图"))
        form = QFormLayout()
        side.addLayout(form)
        self.scale_box, self.x_box, self.y_box = QDoubleSpinBox(),QDoubleSpinBox(),QDoubleSpinBox()
        for title, field, limits, suffix in (
            ("缩放",self.scale_box,(0.001,1000000)," %"),
            ("左上角 X",self.x_box,(-10000000,10000000)," px"),
            ("左上角 Y",self.y_box,(-10000000,10000000)," px")):
            field.setRange(*limits)
            field.setDecimals(3)
            field.setSuffix(suffix)
            field.setKeyboardTracking(False)
            field.valueChanged.connect(self.edit_transform)
            form.addRow(title,field)
        self.view.placement_changed.connect(self.sync_controls)
        self.sync_controls(self.view.placement())
        guides = QCheckBox("显示辅助框")
        guides.setChecked(True)
        guides.toggled.connect(lambda visible: [item.setVisible(visible) for item in self.view.guides])
        side.addWidget(guides)
        grid = QCheckBox("显示九宫格线")
        grid.setChecked(True)
        grid.toggled.connect(lambda visible: [item.setVisible(visible) for item in self.view.grid_lines])
        side.addWidget(grid)
        ax, ay = layout.anchor
        side.addWidget(QLabel(f"白：输出画布／九宫格线\n橙：脸部参考\n"
                             f"参考中心 ({ax:g}, {ay:g})\n"
                             "青：原图边界\n紫：可见内容边界\n画布外内容会被裁切"))
        for title, action in (
            ("查看完整画布",self.view.fit_view),
            ("立绘居中",lambda: self.view.set_placement(centered(image,layout=layout))),
            ("保存 DDS",self.save),("取消",self.reject)):
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(action)
            side.addWidget(button)
        side.addStretch()
        shortcut = QShortcut(QKeySequence.StandardKey.Save,self)
        shortcut.activated.connect(self.save)

    def sync_controls(self, placement):
        for field, value in ((self.scale_box,placement.scale*100),
                             (self.x_box,placement.x),(self.y_box,placement.y)):
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)

    def edit_transform(self):
        self.view.set_placement(Placement(self.scale_box.value()/100,self.x_box.value(),self.y_box.value()))

    def save(self):
        try:
            write_dds(self.output,render(self.image,self.view.placement(),layout=self.config),
                      encoder=self.encoder,encoder_path=self.encoder_path,overwrite=self.overwrite)
        except Exception as exc:
            QMessageBox.warning(self,"保存失败",str(exc))
            return
        self.saved = True
        self.accept()


def prepare(input_path, output_path, *, encoder, encoder_path, layout=DEFAULT_LAYOUT, overwrite=False):
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ValueError("输入和输出不能相同")
    if Path(output_path).exists() and not overwrite:
        raise FileExistsError(output_path)
    image = read_image(input_path)
    app = QApplication.instance() or QApplication([])
    editor = PortraitEditor(image,output_path,encoder=encoder,encoder_path=encoder_path,
                            layout=layout,overwrite=overwrite)
    editor.exec()
    return editor.saved
