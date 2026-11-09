"""Calibration: build the chest templates from real screenshots or video frames, then test them.

The detector is never marked as validated until you check its results on your own footage.
"""

import cv2
import numpy as np
import mss
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
)

from app import config
from app import detector as det
from app.engine import TrackerEngine

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".webm")


class SelectableImage(QLabel):
    """Shows the frame at its real size; drag a rectangle over it to select a template."""

    def __init__(self):
        super().__init__()
        self._start = None
        self._end = None
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    def selection(self):
        if self._start is None or self._end is None:
            return None
        return QRect(self._start, self._end).normalized()

    def clear_selection(self):
        self._start = self._end = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap() is not None:
            self._start = event.position().toPoint()
            self._end = self._start
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        rect = self.selection()
        if rect is not None:
            p = QPainter(self)
            p.setPen(QPen(QColor("#f5b301"), 2))
            p.setBrush(QColor(245, 179, 1, 60))
            p.drawRect(rect)
            p.end()


class CalibrationDialog(QDialog):
    def __init__(self, engine: TrackerEngine, settings: dict, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.settings = settings
        self.frame = None          # BGR image currently shown
        self.video_path = None
        self.setWindowTitle("Calibrar detector")
        self.resize(1040, 760)

        root = QVBoxLayout(self)

        guide = QLabel(
            "1) Toma una captura de pantalla del juego, o abre una imagen o video.  "
            "2) Arrastra un recuadro pequeño sobre el aviso del cofre.  "
            "3) Guárdalo como ABIERTO o DESTRUIDO.  4) Prueba el detector."
        )
        guide.setWordWrap(True)
        guide.setObjectName("subtitle")
        root.addWidget(guide)

        top = QHBoxLayout()
        self.btn_screen = QPushButton("📷 Captura de pantalla")
        self.btn_file = QPushButton("🖼 Abrir imagen o video")
        self.spin_second = QSpinBox()
        self.spin_second.setRange(0, 36000)
        self.spin_second.setSuffix(" s")
        self.spin_second.setToolTip("Segundo del video que se mostrará")
        top.addWidget(self.btn_screen)
        top.addWidget(self.btn_file)
        top.addWidget(QLabel("Segundo del video:"))
        top.addWidget(self.spin_second)
        top.addStretch(1)
        root.addLayout(top)

        self.image = SelectableImage()
        scroll = QScrollArea()
        scroll.setWidget(self.image)
        scroll.setWidgetResizable(False)
        scroll.setMinimumHeight(340)
        root.addWidget(scroll, 1)

        save_row = QHBoxLayout()
        self.btn_save_open = QPushButton("Guardar selección como ABIERTO")
        self.btn_save_break = QPushButton("Guardar selección como DESTRUIDO")
        save_row.addWidget(self.btn_save_open)
        save_row.addWidget(self.btn_save_break)
        root.addLayout(save_row)

        test_row = QHBoxLayout()
        self.btn_test = QPushButton("▶ Probar en esta imagen")
        self.btn_scan = QPushButton("▶ Escanear video completo")
        test_row.addWidget(self.btn_test)
        test_row.addWidget(self.btn_scan)
        test_row.addStretch(1)
        root.addLayout(test_row)

        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(140)
        self.results.setPlainText("Sin resultados todavía.")
        root.addWidget(self.results)

        self.chk_validated = QCheckBox(
            "Confirmo que el detector acertó en mis capturas o videos reales"
        )
        self.chk_validated.setChecked(bool(settings.get("detector_validated")))
        root.addWidget(self.chk_validated)

        bottom = QHBoxLayout()
        self.lbl_templates = QLabel()
        self.lbl_templates.setObjectName("subtitle")
        bottom.addWidget(self.lbl_templates)
        bottom.addStretch(1)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        root.addLayout(bottom)

        self.btn_screen.clicked.connect(self.capture_screen)
        self.btn_file.clicked.connect(self.open_file)
        self.btn_save_open.clicked.connect(lambda: self.save_selection("chest_open"))
        self.btn_save_break.clicked.connect(lambda: self.save_selection("chest_break"))
        self.btn_test.clicked.connect(self.test_frame)
        self.btn_scan.clicked.connect(self.scan_video)
        self.chk_validated.toggled.connect(self._set_validated)

        self._refresh_template_label()

    # ---- helpers -------------------------------------------------------------

    def _refresh_template_label(self):
        parts = []
        for kind in det.KINDS:
            ok = config.template_path(kind).exists()
            parts.append(f"{det.LABELS[kind]}: {'lista' if ok else 'falta'}")
        self.lbl_templates.setText("Plantillas → " + "  ·  ".join(parts))

    def _show_frame(self, frame_bgr: np.ndarray):
        self.frame = frame_bgr
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        image = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        self.image.setPixmap(QPixmap.fromImage(image))
        self.image.setFixedSize(w, h)
        self.image.clear_selection()

    def _set_validated(self, checked: bool):
        self.settings["detector_validated"] = bool(checked)
        config.save_settings(self.settings)

    def _load_templates_now(self):
        paths = {k: config.template_path(k) for k in det.KINDS}
        templates = det.load_templates(paths)
        missing = [det.LABELS[k] for k in det.KINDS if k not in templates]
        return templates, missing

    # ---- frame sources -------------------------------------------------------------

    def capture_screen(self):
        self.hide()
        QApplication.processEvents()
        try:
            with mss.mss() as sct:
                shot = np.array(sct.grab(sct.monitors[1]))
        finally:
            self.show()
        self._show_frame(cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR))
        self.video_path = None
        self.results.setPlainText("Captura tomada. Arrastra un recuadro sobre el aviso del cofre.")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir imagen o video", "",
            "Imágenes o video (*.png *.jpg *.jpeg *.bmp *.mp4 *.mkv *.avi *.mov *.webm)",
        )
        if not path:
            return
        if path.lower().endswith(VIDEO_EXT):
            cap = cv2.VideoCapture(path)
            cap.set(cv2.CAP_PROP_POS_MSEC, self.spin_second.value() * 1000)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                QMessageBox.warning(self, "Video", "No se pudo leer ese segundo del video.")
                return
            self.video_path = path
            self._show_frame(frame)
        else:
            frame = cv2.imread(path, cv2.IMREAD_COLOR)
            if frame is None:
                QMessageBox.warning(self, "Imagen", "No se pudo abrir esa imagen.")
                return
            self.video_path = None
            self._show_frame(frame)
        self.results.setPlainText("Imagen lista. Arrastra un recuadro sobre el aviso del cofre.")

    # ---- templates --------------------------------------------------------------------

    def save_selection(self, kind: str):
        if self.frame is None:
            QMessageBox.information(self, "Sin imagen", "Primero toma una captura o abre una imagen.")
            return
        rect = self.image.selection()
        if rect is None or rect.width() < 8 or rect.height() < 8:
            QMessageBox.information(self, "Selección", "Arrastra un recuadro de al menos 8×8 píxeles.")
            return
        h, w = self.frame.shape[:2]
        x0, y0 = max(0, rect.left()), max(0, rect.top())
        x1, y1 = min(w, rect.right() + 1), min(h, rect.bottom() + 1)
        crop = self.frame[y0:y1, x0:x1]
        out = config.template_path(kind)
        cv2.imwrite(str(out), crop)
        self._refresh_template_label()
        self.results.setPlainText(
            f"Plantilla guardada: {det.LABELS[kind]} ({crop.shape[1]}×{crop.shape[0]} px)\n"
            f"Archivo: {out}\n\nAhora pulsa «Probar en esta imagen» con una captura donde se vea el evento."
        )
        self.engine.reload_templates()

    # ---- testing --------------------------------------------------------------------------

    def test_frame(self):
        if self.frame is None:
            QMessageBox.information(self, "Sin imagen", "Primero toma una captura o abre una imagen.")
            return
        templates, missing = self._load_templates_now()
        if missing:
            self.results.setPlainText("Faltan plantillas: " + ", ".join(missing))
            return
        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        thr = float(self.settings["threshold"])
        scores = det.Detector(templates, thr, 0).scores(gray)
        lines = [f"Umbral: {thr:.2f}"]
        for kind in det.KINDS:
            s = scores.get(kind, 0.0)
            verdict = "COINCIDE" if s >= thr else "no coincide"
            lines.append(f"{det.LABELS[kind]:<16} score {s:.3f}   {verdict}")
        self.results.setPlainText("\n".join(lines))

    def scan_video(self):
        if not self.video_path:
            QMessageBox.information(self, "Video", "Abre un video para escanearlo completo.")
            return
        templates, missing = self._load_templates_now()
        if missing:
            self.results.setPlainText("Faltan plantillas: " + ", ".join(missing))
            return
        self.results.setPlainText("Escaneando video… (puede tardar)")
        QApplication.processEvents()
        try:
            events = det.scan_video(
                self.video_path, templates,
                float(self.settings["threshold"]), float(self.settings["cooldown_seconds"]),
                every_n=2, progress=lambda f: QApplication.processEvents(),
            )
        except OSError as exc:
            self.results.setPlainText(str(exc))
            return
        if not events:
            self.results.setPlainText(
                "No se detectó ningún evento. Si el video sí tiene cofres, recorta mejor la plantilla "
                "o baja el umbral."
            )
            return
        lines = [f"Eventos detectados: {len(events)}"]
        counts = {k: 0 for k in det.KINDS}
        for seconds, kind, score in events:
            counts[kind] += 1
            lines.append(f"{seconds:8.2f} s   {det.LABELS[kind]:<16} score {score:.3f}")
        lines.insert(1, f"Abiertos: {counts['chest_open']}   Destruidos: {counts['chest_break']}")
        lines.append("\nRevisa estos tiempos en el video. Si coinciden, marca la casilla de validación.")
        self.results.setPlainText("\n".join(lines))
