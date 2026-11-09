"""Small transparent always-on-top counter. Drag it, resize it, or hide it with the × button."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizeGrip, QVBoxLayout, QWidget

from app import config
from app.ui.theme import BLUE, GOLD, MUTED, PINK, PURPLE


class OverlayWindow(QWidget):
    def __init__(self, settings: dict, on_hidden):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(config.APP_TITLE)
        self.settings = settings
        self._on_hidden = on_hidden
        self._drag_offset = None
        self.setMinimumSize(220, 120)
        x, y, w, h = settings["overlay_geometry"]
        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(float(settings.get("overlay_opacity", 0.9)))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 6)

        top = QHBoxLayout()
        title = QLabel("PIRATE TRACKER")
        title.setStyleSheet(f"color:{GOLD}; font-weight:800; letter-spacing:1px; font-size:12px;")
        top.addWidget(title)
        top.addStretch(1)
        close = QPushButton("×")
        close.setFixedSize(26, 26)
        close.setCursor(Qt.PointingHandCursor)
        close.setStyleSheet("QPushButton{padding:0; border-radius:13px; font-size:16px;}")
        close.clicked.connect(self.hide_overlay)
        top.addWidget(close)
        root.addLayout(top)

        row = QHBoxLayout()
        self.lbl_open = self._stat("ABIERTOS", BLUE)
        self.lbl_break = self._stat("DESTRUIDOS", PINK)
        self.lbl_total = self._stat("TOTAL", GOLD)
        for box in (self.lbl_open, self.lbl_break, self.lbl_total):
            row.addLayout(box[0])
        root.addLayout(row)

        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        self.lbl_time.setAlignment(Qt.AlignLeft)
        bottom = QHBoxLayout()
        bottom.addWidget(self.lbl_time)
        bottom.addStretch(1)
        bottom.addWidget(QSizeGrip(self), 0, Qt.AlignBottom | Qt.AlignRight)
        root.addLayout(bottom)

    def _stat(self, caption: str, color: str):
        box = QVBoxLayout()
        cap = QLabel(caption)
        cap.setStyleSheet(f"color:{MUTED}; font-size:10px; font-weight:700;")
        value = QLabel("0")
        value.setStyleSheet(f"color:{color}; font-size:26px; font-weight:800;")
        box.addWidget(cap)
        box.addWidget(value)
        return box, value

    # ---- values ----------------------------------------------------------------

    def set_values(self, opens: int, breaks: int, time_text: str) -> None:
        self.lbl_open[1].setText(f"{opens:,}")
        self.lbl_break[1].setText(f"{breaks:,}")
        self.lbl_total[1].setText(f"{opens + breaks:,}")
        self.lbl_time.setText(time_text)

    # ---- visibility and persistence ---------------------------------------------

    def hide_overlay(self) -> None:
        self.hide()
        self._on_hidden()

    def _save_geometry(self) -> None:
        g = self.geometry()
        self.settings["overlay_geometry"] = [g.x(), g.y(), g.width(), g.height()]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._save_geometry()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._save_geometry()

    # ---- drawing and dragging -------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(PURPLE), 1.5))
        p.setBrush(QColor(10, 10, 22, 215))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 16, 16)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
