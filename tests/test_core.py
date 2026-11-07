"""Core behavior only: composition, encoding and the two-stage workflow."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from anime_core_lib_portrait_tool import Placement, read_image, render, estimate_transform, write_dds, Layout, load_layout
from anime_core_lib_portrait_tool import auto, manual
from examples import batch


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "source.png", self.root / "out.dds"
        self.image = Image.new("RGBA", (200, 300))
        ImageDraw.Draw(self.image).rectangle((40, 10, 160, 280), fill=(240, 50, 20, 180))
        self.image.save(self.source)
        self.tool = self.root / "encoder.exe"
        self.tool.write_bytes(b"test double")
        self.options = dict(encoder="nvtt", encoder_path=self.tool)

    def test_composition_and_premultiplied_alpha(self):
        with patch("anime_core_lib_portrait_tool.transform.detect_faces", return_value=[([80,30,120,70], "face", 0.95)]):
            p = estimate_transform(self.image)
        self.assertTrue(492 <= 100*p.scale+p.x <= 546)
        self.assertTrue(125 <= 50*p.scale+p.y <= 258)
        self.assertEqual(render(self.image, p).size, (1024, 1024))
        edge = Image.new("RGBA", (5,5), (0,0,255,0))
        edge.putpixel((2,2), (255,0,0,255))
        result = render(edge, Placement(2.3, 0.4, 0.4))
        pixels = [result.getpixel((x,y)) for y in range(15) for x in range(15)
                  if 0 < result.getpixel((x,y))[3] < 255]
        self.assertTrue(pixels)
        self.assertTrue(all(pixel[2] == 0 for pixel in pixels))

    def test_no_face_or_ambiguous_face_goes_to_manual_without_writing(self):
        for faces in ([], [([50,20,90,60],"face",0.9),([110,20,150,60],"face",0.9)]):
            with patch("anime_core_lib_portrait_tool.transform.detect_faces", return_value=faces):
                self.assertFalse(auto.prepare(self.source, self.output, **self.options))
        self.assertFalse(self.output.exists())

    def test_both_encoders_and_failed_encoding_preserve_old_output(self):
        def encode(command, **kwargs):
            if "--output" in command:
                source, target = Path(command[1]), Path(command[-1])
                self.assertIn("--no-mips", command)
            else:
                source = Path(command[-1])
                target = Path(command[command.index("-o")+1]) / "image.dds"
                self.assertIn("-dx9", command)
            with Image.open(source) as image:
                image.save(target, format="DDS", pixel_format="DXT5")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        for name in ("nvtt", "texconv"):
            with patch("subprocess.run", side_effect=encode):
                write_dds(self.output, render(self.image, Placement(1,0,0)),
                          encoder=name, encoder_path=self.tool, overwrite=True)
            with Image.open(self.output) as image:
                self.assertEqual(image.size, (1024,1024))
        before = self.output.read_bytes()
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([],1,b"",b"failed")):
            with self.assertRaises(OSError):
                write_dds(self.output, self.image, **self.options, overwrite=True)
        self.assertEqual(self.output.read_bytes(), before)

    def test_csv_finishes_auto_pass_before_manual_and_skips_existing_outputs(self):
        other = self.root / "other.png"
        self.image.save(other)
        csv = self.root / "jobs.csv"
        csv.write_text("input,output\nsource.png,out.dds\nother.png,other.dds\n", encoding="utf-8-sig")
        events = []
        def automatic(source, output, **kwargs):
            events.append("auto")
            return False
        def hand(source, output, **kwargs):
            events.append("manual")
            output.write_bytes(b"DDS")
            return True
        with patch.object(batch,"automatic",automatic), patch.object(manual,"prepare",hand), patch.dict(batch.OPTIONS,self.options):
            self.assertTrue(batch.run_batch(csv))
            self.assertEqual(events, ["auto","auto","manual","manual"])
            batch.run_batch(csv)
            self.assertEqual(len(events), 4)

    def test_batch_cancel_stops_remaining_manual_tasks(self):
        csv = self.root / "jobs.csv"
        csv.write_text("input,output\nsource.png,a.dds\nsource.png,b.dds\n", encoding="utf-8")
        with patch.object(batch,"automatic",return_value=False), patch.object(manual,"prepare",return_value=False) as hand:
            self.assertFalse(batch.run_batch(csv))
        self.assertEqual(hand.call_count, 1)

    def test_manual_drag_and_mouse_anchored_zoom(self):
        view = manual.PortraitView(self.image)
        view.resize(700,700)
        view.show()
        self.addCleanup(view.close)
        self.app.processEvents()
        p = view.placement()
        point = view.mapFromScene(QPointF(512,512))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(view.viewport(), point+QPoint(30,20))
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=point+QPoint(30,20))
        self.assertGreater(view.placement().x, p.x)
        p = view.placement()
        location = QPointF(point)
        scene = view.mapToScene(point)
        event = QWheelEvent(location,location,QPoint(),QPoint(0,120),
                            Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase,False)
        view.wheelEvent(event)
        after = view.placement()
        self.assertAlmostEqual((scene.x()-p.x)/p.scale, (scene.x()-after.x)/after.scale)

    def test_manual_save_and_cancel(self):
        def save(editor):
            QTimer.singleShot(0, editor.save)
            return QDialog.exec(editor)
        with patch.object(manual.PortraitEditor,"exec",save), patch.object(manual,"write_dds") as encode:
            self.assertTrue(manual.prepare(self.source, self.output, **self.options))
        self.assertEqual(encode.call_args.args[1].size, (1024,1024))
        with patch.object(manual.PortraitEditor,"exec",lambda editor: editor.reject()):
            self.assertFalse(manual.prepare(self.source, self.output, **self.options))

    def test_failed_manual_save_can_be_retried(self):
        editor = manual.PortraitEditor(self.image,self.output,**self.options)
        self.addCleanup(editor.close)
        with patch.object(manual,"write_dds",side_effect=[OSError("failure"),None]), patch.object(manual.QMessageBox,"warning"):
            editor.save()
            self.assertFalse(editor.saved)
            editor.save()
            self.assertTrue(editor.saved)


    def test_custom_layout_reaches_automatic_and_manual_output(self):
        from dataclasses import asdict
        import json
        layout = Layout(canvas=(640,360),anchor=(320,80),face_size=(40,40),
                        anchor_x=(250,390),anchor_y=(60,120),margin=4)
        path = self.root/"layout.json"
        path.write_text(json.dumps(asdict(layout)),encoding="utf-8")
        self.assertEqual(load_layout(path),layout)
        with patch("anime_core_lib_portrait_tool.transform.detect_faces",return_value=[([80,30,120,70],"face",0.95)]), patch.object(auto,"write_dds") as encode:
            self.assertTrue(auto.prepare(self.source,self.output,layout=layout,**self.options))
            self.assertEqual(encode.call_args.args[1].size,layout.canvas)
        editor = manual.PortraitEditor(self.image,self.output,layout=layout,**self.options)
        self.addCleanup(editor.close)
        with patch.object(manual,"write_dds") as encode:
            editor.save()
            self.assertEqual(encode.call_args.args[1].size,layout.canvas)

    def test_view_zoom_and_pan_do_not_change_composition(self):
        view = manual.PortraitView(self.image)
        view.resize(700,700)
        view.show()
        self.addCleanup(view.close)
        self.app.processEvents()
        placement = view.placement()
        point = QPoint(300,300)
        old_zoom = view.transform().m11()
        event = QWheelEvent(QPointF(point),QPointF(point),QPoint(),QPoint(0,120),
                            Qt.MouseButton.NoButton,Qt.KeyboardModifier.ControlModifier,
                            Qt.ScrollPhase.NoScrollPhase,False)
        view.wheelEvent(event)
        self.assertGreater(view.transform().m11(),old_zoom)
        origin = view.mapToScene(point)
        QTest.mousePress(view.viewport(),Qt.MouseButton.MiddleButton,pos=point)
        QTest.mouseMove(view.viewport(),point+QPoint(30,20))
        QTest.mouseRelease(view.viewport(),Qt.MouseButton.MiddleButton,pos=point+QPoint(30,20))
        self.assertNotEqual(view.mapToScene(point),origin)
        self.assertEqual(view.placement(),placement)
        view.fit_view()
        self.assertEqual(view.placement(),placement)

    def test_numeric_fields_sync_without_exporting(self):
        editor = manual.PortraitEditor(self.image,self.output,**self.options)
        self.addCleanup(editor.close)
        editor.show()
        self.app.processEvents()
        with patch.object(manual,"write_dds") as encode:
            editor.scale_box.setValue(150)
            editor.x_box.setValue(-20)
            editor.y_box.setValue(30)
            self.assertEqual(editor.view.placement(),Placement(1.5,-20,30))
            editor.view.set_placement(Placement(2,15,-7))
            self.assertEqual((editor.scale_box.value(),editor.x_box.value(),editor.y_box.value()),(200,15,-7))
            QTest.keyClick(editor.x_box,Qt.Key.Key_Return)
            self.assertFalse(editor.saved)
            encode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
