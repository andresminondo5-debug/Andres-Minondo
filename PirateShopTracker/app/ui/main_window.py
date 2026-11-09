"""Main window: live counters, session time, per-hour rate, stats tabs, overlay and calibration."""

import time
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QHeaderView,
)

from app import config
from app import detector as det
from app.engine import TrackerEngine, templates_ready
from app.storage import Storage
from app.ui.calibration import CalibrationDialog
from app.ui.overlay import OverlayWindow
from app.ui.theme import AMBER, BLUE, GOLD, GREEN, MUTED, PINK


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def per_hour(count: int, seconds: float) -> str:
    if seconds < 60:
        return "—"
    return f"{count / (seconds / 3600):,.0f}"


class CounterCard(QFrame):
    def __init__(self, title: str, color: str):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        self.value.setStyleSheet(f"color:{color};")
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class BarChart(QWidget):
    """Stacked bars: opens (blue) and breaks (pink) per day."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.setMinimumHeight(260)

    def set_rows(self, rows: list) -> None:
        self.rows = rows
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b0b14"))
        if not self.rows:
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, "Sin datos todavía. Tus cofres aparecerán aquí.")
            p.end()
            return
        margin = 40
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin
        peak = max(o + b for _, o, b in self.rows) or 1
        slot = w / len(self.rows)
        for i, (day, opens, breaks) in enumerate(self.rows):
            x = margin + i * slot + slot * 0.18
            bw = slot * 0.64
            h_open = h * opens / peak
            h_break = h * breaks / peak
            base = margin + h
            p.fillRect(QRectF(x, base - h_open, bw, h_open), QColor(BLUE))
            p.fillRect(QRectF(x, base - h_open - h_break, bw, h_break), QColor(PINK))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x - 12, base + 6, bw + 24, 20), Qt.AlignCenter, day[5:])
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(margin, 6, w, 22), Qt.AlignLeft, f"Pico diario: {peak:,} cofres")
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, settings: dict, storage: Storage, engine: TrackerEngine):
        super().__init__()
        self.settings = settings
        self.storage = storage
        self.engine = engine
        self._tick = 0

        self.setWindowTitle(config.APP_TITLE)
        self.resize(1120, 760)
        self.setMinimumSize(860, 620)

        self.overlay = OverlayWindow(settings, on_hidden=self._overlay_hidden)
        self._build_ui()

        if settings.get("overlay_visible"):
            self.overlay.show()
        self._update_overlay_button()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(500)
        self._refresh()
        self._refresh_stats()

    # ---- layout ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 22, 26, 18)
        layout.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("PIRATE SHOP CHEST TRACKER PRO")
        title.setObjectName("title")
        subtitle = QLabel("Fortnite · Pirate Shop · contador automático por captura de pantalla")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        self.status = QLabel("● Detenido")
        self.status.setObjectName("status")
        header.addWidget(self.status, 0, Qt.AlignVCenter)
        layout.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.card_open = CounterCard("📦  COFRES ABIERTOS", BLUE)
        self.card_break = CounterCard("⛏  COFRES DESTRUIDOS", PINK)
        self.card_total = CounterCard("🏴‍☠️  TOTAL DE COFRES", GOLD)
        self.card_time = CounterCard("⏱  TIEMPO DE SESIÓN", "#e6edf3")
        self.card_rate = CounterCard("📊  COFRES POR HORA", GREEN)
        for card in (self.card_open, self.card_break, self.card_total, self.card_time, self.card_rate):
            cards.addWidget(card)
        layout.addLayout(cards)

        buttons = QHBoxLayout()
        self.btn_track = QPushButton("▶  Iniciar seguimiento")
        self.btn_track.setObjectName("primary")
        self.btn_track.setCursor(Qt.PointingHandCursor)
        self.btn_track.clicked.connect(self._toggle_tracking)
        self.btn_overlay = QPushButton("Mostrar overlay")
        self.btn_overlay.setCursor(Qt.PointingHandCursor)
        self.btn_overlay.clicked.connect(self._toggle_overlay)
        self.btn_calibrate = QPushButton("⚙  Calibrar detector")
        self.btn_calibrate.setCursor(Qt.PointingHandCursor)
        self.btn_calibrate.clicked.connect(self._open_calibration)
        buttons.addWidget(self.btn_track)
        buttons.addWidget(self.btn_overlay)
        buttons.addWidget(self.btn_calibrate)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

        tabs = QTabWidget()
        tabs.addTab(self._build_summary_tab(), "Resumen")
        tabs.addTab(self._build_sessions_tab(), "Sesiones")
        tabs.addTab(self._build_chart_tab(), "Gráfica")
        layout.addWidget(tabs, 1)

        footer = QLabel(f"Datos guardados en: {config.data_dir()}")
        footer.setObjectName("subtitle")
        layout.addWidget(footer)

    def _stat_label(self):
        lbl = QLabel("0")
        lbl.setStyleSheet("font-size:24px; font-weight:800;")
        return lbl

    def _build_summary_tab(self):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(18)
        rows = [
            ("Cofres abiertos hoy", "today_open"),
            ("Cofres destruidos hoy", "today_break"),
            ("Total histórico de abiertos", "all_open"),
            ("Total histórico de destruidos", "all_break"),
            ("Tiempo total de seguimiento", "all_time"),
            ("Cofres por hora (histórico)", "all_rate"),
        ]
        self.summary_labels = {}
        for row, (caption, key) in enumerate(rows):
            cap = QLabel(caption)
            cap.setObjectName("section")
            value = self._stat_label()
            grid.addWidget(cap, row, 0)
            grid.addWidget(value, row, 1)
            self.summary_labels[key] = value
        grid.setRowStretch(len(rows), 1)
        return page

    def _build_sessions_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.sessions_table = QTableWidget(0, 6)
        self.sessions_table.setHorizontalHeaderLabels(
            ["Inicio", "Duración", "Abiertos", "Destruidos", "Total", "Por hora"]
        )
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.sessions_table)
        return page

    def _build_chart_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.chart = BarChart()
        legend = QLabel(f"<span style='color:{BLUE}'>■</span> Abiertos    "
                        f"<span style='color:{PINK}'>■</span> Destruidos    últimos 14 días")
        legend.setObjectName("subtitle")
        layout.addWidget(self.chart, 1)
        layout.addWidget(legend)
        return page

    # ---- actions -------------------------------------------------------------------

    def auto_start(self) -> None:
        """Called once at launch: start tracking if enabled and the detector is calibrated."""
        if self.settings.get("auto_start_tracking") and templates_ready():
            self.engine.start()

    def _toggle_tracking(self):
        if self.engine.running:
            self.engine.stop()
        elif not self.engine.start():
            QMessageBox.information(
                self, "Calibra primero",
                "Todavía no hay plantillas del detector.\n\n"
                "Pulsa «Calibrar detector», toma una captura con el aviso de cofre "
                "y guarda las dos plantillas.",
            )

    def _toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.settings["overlay_visible"] = False
        else:
            self.overlay.show()
            self.settings["overlay_visible"] = True
        self._update_overlay_button()
        config.save_settings(self.settings)

    def _overlay_hidden(self):
        self.settings["overlay_visible"] = False
        self._update_overlay_button()
        config.save_settings(self.settings)

    def _update_overlay_button(self):
        self.btn_overlay.setText("Ocultar overlay" if self.overlay.isVisible() else "Mostrar overlay")

    def _open_calibration(self):
        dialog = CalibrationDialog(self.engine, self.settings, self)
        dialog.exec()
        self._refresh()

    # ---- refresh -------------------------------------------------------------------

    def _refresh(self):
        snap = self.engine.snapshot()
        now = time.time()
        opens = snap["counts"]["chest_open"]
        breaks = snap["counts"]["chest_break"]
        total = opens + breaks
        started = snap["session_started"]
        seconds = (now - started) if started else 0.0

        self.card_open.set_value(f"{opens:,}")
        self.card_break.set_value(f"{breaks:,}")
        self.card_total.set_value(f"{total:,}")
        self.card_time.set_value(fmt_duration(seconds))
        self.card_rate.set_value(per_hour(total, seconds))

        if snap["running"] and snap["status"].startswith("Esperando"):
            color, dot = AMBER, "●"
        elif snap["running"]:
            color, dot = GREEN, "●"
        else:
            color, dot = MUTED, "●"
        self.status.setText(f"<span style='color:{color}'>{dot}</span> {snap['status']}")
        self.status.setTextFormat(Qt.RichText)
        self.btn_track.setText("■  Detener seguimiento" if snap["running"] else "▶  Iniciar seguimiento")
        self.btn_track.setObjectName("danger" if snap["running"] else "primary")
        self.btn_track.style().unpolish(self.btn_track)
        self.btn_track.style().polish(self.btn_track)

        self._update_notice(snap)
        if self.overlay.isVisible():
            self.overlay.set_values(opens, breaks, fmt_duration(seconds))

        self._tick += 1
        if self._tick % 4 == 0:
            self._refresh_stats()

    def _update_notice(self, snap: dict):
        if not templates_ready():
            self.notice.setStyleSheet(f"color:{AMBER}; font-weight:600;")
            self.notice.setText(
                "Detector sin calibrar: pulsa «Calibrar detector» y guarda las plantillas "
                "de cofre abierto y cofre destruido. Hasta entonces no se cuenta nada."
            )
        elif not self.settings.get("detector_validated"):
            self.notice.setStyleSheet(f"color:{AMBER}; font-weight:600;")
            self.notice.setText(
                "Detector calibrado pero aún sin validar con tus capturas o videos. "
                "Compruébalo en «Calibrar detector» antes de confiar en los números."
            )
        else:
            self.notice.setStyleSheet(f"color:{GREEN}; font-weight:600;")
            self.notice.setText("Detector calibrado y validado por ti.")

    def _refresh_stats(self):
        now = time.time()
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = self.storage.counts_since(today_start)
        totals = self.storage.totals()
        active = self.storage.active_seconds(now)
        all_open = totals.get("chest_open", 0)
        all_break = totals.get("chest_break", 0)

        self.summary_labels["today_open"].setText(f"{today.get('chest_open', 0):,}")
        self.summary_labels["today_break"].setText(f"{today.get('chest_break', 0):,}")
        self.summary_labels["all_open"].setText(f"{all_open:,}")
        self.summary_labels["all_break"].setText(f"{all_break:,}")
        self.summary_labels["all_time"].setText(fmt_duration(active))
        self.summary_labels["all_rate"].setText(per_hour(all_open + all_break, active))

        sessions = self.storage.sessions(now)
        self.sessions_table.setRowCount(len(sessions))
        for r, s in enumerate(sessions):
            total = s["open"] + s["break"]
            cells = [
                datetime.fromtimestamp(s["started_at"]).strftime("%d/%m %H:%M"),
                fmt_duration(s["duration"]) + ("  (en curso)" if s["open_now"] else ""),
                f"{s['open']:,}",
                f"{s['break']:,}",
                f"{total:,}",
                per_hour(total, s["duration"]),
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self.sessions_table.setItem(r, c, item)

        self.chart.set_rows(self.storage.daily(14))

    # ---- shutdown ----------------------------------------------------------------------

    def shutdown(self):
        self.timer.stop()
        self.engine.stop()
        self.overlay.hide()
        config.save_settings(self.settings)
        self.storage.close()
