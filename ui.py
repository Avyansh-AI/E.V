from __future__ import annotations

import base64
import json
import html as html_lib
import math
import os
import platform
import random
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

import psutil
if platform.system() == "Windows":
    import winreg

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QMimeData, QObject, QPoint, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, QPropertyAnimation, QParallelAnimationGroup, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QIcon, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut, QTextOption,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider, QTextBrowser, QTextEdit,
    QGraphicsDropShadowEffect,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget, QProgressBar,
    QStackedWidget, QInputDialog, QMessageBox,
)

from discord_bot import DiscordBotService
from gesture_utils import estimate_gesture_state
from smart_home import SmartHomeService
from smart_home_page import EVHomePage, _DeviceTile
from workspace_store import store as workspace_store

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
APP_SETTINGS_FILE = CONFIG_DIR / "app_settings.json"
DISCORD_SETTINGS_FILE = CONFIG_DIR / "discord_bot.json"
LOGO_FILE  = BASE_DIR / "assets" / "ev_logo.png"
LOGO_ICO   = BASE_DIR / "assets" / "ev_logo.ico"
BACKGROUND_IMAGE_FILE = BASE_DIR / "assets" / "background.png"
MODEL_DOWNLOAD_URL = "https://storage.googleapis.com/mediapipe-assets/hand_landmarker.task"

# Single source of truth for the About / System pages.
APP_VERSION  = "1.0.0"
APP_BUILD    = "2026.06.29"
APP_RELEASED = "29 Jun 2026"

_DEFAULT_W, _DEFAULT_H = 1500, 840
_MIN_W,     _MIN_H     = 1180, 720
_SETTINGS_CATEGORIES = (
    ("general", "General"),
    ("ai", "AI"),
    ("voice", "Voice"),
    ("automation", "Automation"),
    ("integrations", "Integrations"),
    ("advanced", "Advanced"),
)

_LEFT_W  = 270
_RIGHT_W = 430

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

# ---------------------------------------------------------------------------
# E.V. design system
# ---------------------------------------------------------------------------
# One restrained palette: graphite surfaces, a single cool accent, mint for
# success/online, amber for warnings, rose for failures. Everything in the UI
# resolves back to these tokens so the interface stays visually coherent.
EV = {
    "bg":            "#04060a",   # application backdrop
    "bg_alt":        "#060910",   # backdrop gradient end
    "surface":       "rgba(12, 17, 24, 0.86)",
    "surface_solid": "#0b1017",
    "surface_high":  "rgba(18, 25, 34, 0.92)",
    "surface_low":   "rgba(8, 12, 18, 0.72)",
    "border":        "rgba(255, 255, 255, 0.07)",
    "border_strong": "rgba(255, 255, 255, 0.13)",
    "accent":        "#5cd3ff",
    "accent_soft":   "rgba(92, 211, 255, 0.14)",
    "accent_line":   "rgba(92, 211, 255, 0.34)",
    "accent_glow":   "rgba(92, 211, 255, 0.22)",
    "violet":        "#9db0ff",
    "success":       "#3ddc97",
    "success_soft":  "rgba(61, 220, 151, 0.14)",
    "warning":       "#ffb648",
    "warning_soft":  "rgba(255, 182, 72, 0.14)",
    "danger":        "#ff5f6d",
    "danger_soft":   "rgba(255, 95, 109, 0.14)",
    "text":          "#eef4fa",
    "text_med":      "#b2bfcd",
    "text_dim":      "#78879a",
    "text_faint":    "#586375",
}

_UI_FONT = "Segoe UI"
_MONO_FONT = "Cascadia Mono" if _OS == "Windows" else "Menlo"
_SMALL_CAPS = 8


def ev_hex(token: str, fallback: str = "") -> str:
    """Return a design token value (hex or rgba string)."""
    return EV.get(token, fallback or token)


EV_QSS = f"""
* {{
    outline: none;
}}
QWidget {{
    color: {EV['text']};
    font-family: "{_UI_FONT}";
    font-size: 12px;
}}
QToolTip {{
    background: {EV['surface_solid']};
    color: {EV['text']};
    border: 1px solid {EV['border_strong']};
    padding: 6px 8px;
    border-radius: 6px;
}}
QScrollArea, QAbstractScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {EV['accent_line']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
}}
QFrame#EVCard {{
    background: {EV['surface']};
    border: 1px solid {EV['border']};
    border-radius: 16px;
}}
QFrame#EVCard:hover {{
    border: 1px solid {EV['border_strong']};
}}
QLabel#EVSectionLabel {{
    color: {EV['text_faint']};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.6px;
}}
QLineEdit, QComboBox, QSpinBox {{
    background: rgba(9, 13, 19, 0.92);
    color: {EV['text']};
    border: 1px solid {EV['border']};
    border-radius: 10px;
    min-height: 32px;
    padding: 0 10px;
    selection-background-color: {EV['accent_line']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {EV['accent_line']};
}}
QTextEdit, QTextBrowser, QPlainTextEdit {{
    background: transparent;
    border: none;
    color: {EV['text']};
    selection-background-color: {EV['accent_line']};
}}
QPushButton {{
    background: rgba(255, 255, 255, 0.04);
    color: {EV['text']};
    border: 1px solid {EV['border']};
    border-radius: 10px;
    padding: 8px 12px;
}}
QPushButton:hover {{
    background: {EV['accent_soft']};
    border: 1px solid {EV['accent_line']};
}}
QPushButton:pressed {{
    background: rgba(92, 211, 255, 0.22);
}}
QPushButton:disabled {{
    color: {EV['text_faint']};
    border: 1px solid {EV['border']};
    background: rgba(255, 255, 255, 0.02);
}}
QPushButton:checked {{
    background: {EV['accent_soft']};
    border: 1px solid {EV['accent_line']};
    color: {EV['text']};
}}
QCheckBox {{
    spacing: 8px;
    color: {EV['text_med']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {EV['border_strong']};
    background: rgba(255, 255, 255, 0.03);
}}
QCheckBox::indicator:checked {{
    background: {EV['accent']};
    border: 1px solid {EV['accent']};
}}
QProgressBar {{
    background: rgba(255, 255, 255, 0.06);
    border: none;
    border-radius: 4px;
    height: 6px;
}}
QProgressBar::chunk {{
    background: {EV['accent']};
    border-radius: 4px;
}}
QMenu {{
    background: {EV['surface_solid']};
    border: 1px solid {EV['border_strong']};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 16px 7px 12px;
    border-radius: 8px;
}}
QMenu::item:selected {{
    background: {EV['accent_soft']};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: rgba(255, 255, 255, 0.10);
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {EV['accent']};
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
"""


class C:
    """Legacy colour aliases mapped onto the E.V. design tokens."""

    BG        = EV["bg"]
    PANEL     = EV["surface_solid"]
    PANEL2    = EV["surface_low"]
    BORDER    = EV["border"]
    BORDER_B  = EV["border_strong"]
    BORDER_A  = "rgba(255, 255, 255, 0.10)"
    PRI       = EV["accent"]
    PRI_DIM   = "#8fe0ff"
    PRI_GHO   = EV["accent_soft"]
    ACC       = EV["accent"]
    ACC2      = EV["text"]
    GREEN     = EV["success"]
    GREEN_D   = "#2ec98a"
    RED       = EV["danger"]
    MUTED_C   = EV["warning"]
    TEXT      = EV["text"]
    TEXT_DIM  = EV["text_dim"]
    TEXT_MED  = EV["text_med"]
    WHITE     = EV["text"]
    DARK      = EV["bg"]
    BAR_BG    = "rgba(255, 255, 255, 0.08)"


class BackgroundWidget(QWidget):
    def __init__(self, image_path: Path | str | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._image_path = Path(image_path) if image_path else None
        self._background_pixmap = None
        self._load_background()

    def _load_background(self) -> None:
        if not self._image_path:
            return
        try:
            pix = QPixmap(str(self._image_path))
            if not pix.isNull():
                self._background_pixmap = pix
        except Exception:
            self._background_pixmap = None

    def paintEvent(self, event):
        if not self._background_pixmap:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()
        pix = self._background_pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (rect.width() - pix.width()) // 2
        y = (rect.height() - pix.height()) // 2
        painter.drawPixmap(x, y, pix)
        painter.fillRect(rect, QColor(2, 3, 5, 28))
        painter.end()
        return


class RemoteKeyOverlay(QWidget):
    closed = pyqtSignal()

    def __init__(self, url: str, key: str, auto: str, manual: str, parent=None):
        super().__init__(parent)
        self._on_new_key = None
        self._manual_url = manual or url
        self._auto_login_url = auto or url
        self._expiry = time.time() + 600

        # larger opaque panel with neon red glow
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 20, 18, 18)
        lay.setSpacing(12)
        # Make overlay large and opaque so it pops
        try:
            self.setFixedSize(560, 680)
            frame.setFixedSize(self.size())
        except Exception:
            self.setFixedSize(520, 640)
            frame.setFixedSize(self.size())
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(8,10,12,245);
                border: 2px solid {C.PRI};
                border-radius: 16px;
            }}
        """)
        # neon glow effect
        try:
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(48)
            glow.setColor(QColor(255,69,69,200))
            glow.setOffset(0, 0)
            frame.setGraphicsEffect(glow)
        except Exception:
            pass

        title = QLabel("Mobile Connect")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #fff; background: transparent;")
        lay.addWidget(title)

        subtitle = QLabel("Scan the QR code with your phone to connect.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(subtitle)

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(240, 240)
        self._qr_label.setStyleSheet("background: white; border-radius: 16px; padding: 8px;")
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        manual_hint = QLabel("Manual address")
        manual_hint.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        manual_hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(manual_hint)

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_lbl.setFont(QFont("Consolas", 9))
        self._url_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_lbl.setFont(QFont("Consolas", 34, QFont.Weight.Black))
        self._key_lbl.setStyleSheet(f"""
            color: {C.WHITE};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(40,6,6,220), stop:1 rgba(60,8,8,220));
            border: 2px solid {C.PRI};
            border-radius: 12px;
            padding: 12px;
            letter-spacing: 12px;
            font-weight: 900;
        """)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel("")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_lbl.setFont(QFont("Segoe UI", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._new_btn = QPushButton("NEW KEY")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setFixedHeight(34)
        self._new_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(92, 211, 255,22);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: rgba(92, 211, 255,44); }}
        """)
        self._new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(self._new_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(12,14,18,238);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
            QPushButton:hover {{ color: {C.WHITE}; border: 1px solid {C.PRI}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._update_qr(self._auto_login_url)
        self._tick()

        # Ensure the overlay has a sensible default size so positioning works.
        self.adjustSize()
        try:
            self.setFixedSize(max(360, self.width()), max(360, self.height()))
        except Exception:
            self.setFixedSize(420, 520)

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("NO URL")
            return
        try:
            import qrcode
            from io import BytesIO
            qr = qrcode.QRCode(box_size=5, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(pix.scaled(172, 172, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except ImportError:
            self._qr_label.setText("Install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._qr_label.setStyleSheet("color: #111; background: white; border-radius: 12px; padding: 6px;")
        except Exception:
            self._qr_label.setText("QR failed")

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        mins, secs = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in {mins:02d}:{secs:02d}")
        if remaining <= 0:
            self._do_close()

    def mark_connected(self) -> None:
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(55,255,95,20);
            border: 1px solid rgba(55,255,95,150);
            border-radius: 10px;
            padding: 8px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("OK")
        self._qr_label.setFont(QFont("Segoe UI", 34, QFont.Weight.Black))
        self._qr_label.setStyleSheet("color: #3ddc97; background: #041006; border-radius: 12px;")
        self._timer_lbl.setText("Phone connected. E.V. remote is ready.")

    def _refresh_key(self):
        if not self._on_new_key:
            return
        result = self._on_new_key()
        if not result:
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else url
        manual = result[3] if len(result) >= 4 else url
        self._manual_url = manual or url
        self._auto_login_url = auto or url
        self._url_lbl.setText(self._manual_url)
        self._key_lbl.setText(key)
        self._key_lbl.setStyleSheet(f"""
            color: {C.WHITE};
            background: rgba(92, 211, 255,28);
            border: 1px solid {C.PRI};
            border-radius: 10px;
            padding: 8px;
            letter-spacing: 9px;
        """)
        self._update_qr(self._auto_login_url)
        self._expiry = time.time() + 600
        self._ctimer.start(1000)
        self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


def _logo_icon() -> QIcon:
    return QIcon(str(LOGO_ICO if LOGO_ICO.exists() else LOGO_FILE))


def _logo_pixmap(size: int) -> QPixmap:
    pix = QPixmap(str(LOGO_FILE))
    if pix.isNull():
        return QPixmap(size, size)
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _framed_logo(size: int, icon_size: int | None = None, *, bg: str = "rgba(18,18,18,240)",
                 border: str = None, radius: int | None = None, inset: int = 6) -> QFrame:
    border = border or C.BORDER_B
    radius = radius if radius is not None else max(10, size // 4)
    icon_size = icon_size or max(8, size - inset * 2)
    frame = QFrame()
    frame.setFixedSize(size, size)
    frame.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: {radius}px;"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(inset, inset, inset, inset)
    lay.setSpacing(0)
    lbl = QLabel()
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setPixmap(_logo_pixmap(icon_size))
    lbl.setStyleSheet("background: transparent; border: none;")
    lay.addWidget(lbl)
    return frame


def _icon_pixmap(kind: str, size: int = 18) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(qcol(C.WHITE), max(2.2, size * 0.14), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "attach":
        # More readable paperclip shape
        p.drawArc(QRectF(size*0.22, size*0.14, size*0.42, size*0.58), 35*16, 290*16)
        p.drawArc(QRectF(size*0.42, size*0.24, size*0.28, size*0.44), 35*16, 290*16)
        p.drawLine(QPointF(size*0.28, size*0.56), QPointF(size*0.38, size*0.66))
    elif kind == "mic":
        # Clearer microphone silhouette
        p.drawRoundedRect(QRectF(size*0.31, size*0.14, size*0.38, size*0.48), size*0.16, size*0.16)
        p.drawLine(QPointF(size*0.50, size*0.62), QPointF(size*0.50, size*0.83))
        p.drawLine(QPointF(size*0.36, size*0.83), QPointF(size*0.64, size*0.83))
        p.drawLine(QPointF(size*0.42, size*0.70), QPointF(size*0.58, size*0.70))
    elif kind == "send":
        p.drawLine(QPointF(size*0.20, size*0.50), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.30), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.70), QPointF(size*0.70, size*0.50))

    p.end()
    return px


def _attach_pulse_glow(widget: QWidget, *, color: str = C.WHITE, blur_min: float = 12.0,
                       blur_max: float = 28.0, alpha: int = 180, period_ms: int = 2400) -> None:
    # Intentionally disabled for performance. Kept as a no-op so existing calls
    # do not need to change across the UI.
    return


def _quiet_run(*args, **kwargs):
    if _OS == "Windows":
        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(*args, **kwargs)


# ---------------------------------------------------------------------------
# Log line protocol
# ---------------------------------------------------------------------------
# main.py and the action modules speak to the UI through plain log lines. The
# prefixes below are the single contract between them, so every parser uses
# this one helper instead of slicing fixed offsets.
_LOG_PREFIXES = (
    ("you:",      ("user", "You")),
    ("e.v.:",     ("assistant", "E.V.")),
    ("ev:",       ("assistant", "E.V.")),
    ("ev ai:",    ("assistant", "E.V.")),
    ("assistant:", ("assistant", "E.V.")),
    ("file:",     ("file", "File")),
    ("err:",      ("error", "System")),
    ("error:",    ("error", "System")),
    ("warn:",     ("system", "System")),
    ("sys:",      ("system", "System")),
    ("system:",   ("system", "System")),
)


def parse_log_line(text: str) -> dict:
    """Split a log line into ``{"kind", "role", "name", "body"}``.

    ``kind`` is the raw prefix without the colon ("you", "err", ...) and is
    what UI code should branch on; ``role``/``name`` map to chat roles.
    """
    raw = (text or "").strip()
    if not raw:
        return {"kind": "empty", "role": "system", "name": "System", "body": ""}
    low = raw.lower()
    for prefix, (role, name) in _LOG_PREFIXES:
        if low.startswith(prefix):
            return {
                "kind": prefix[:-1],
                "role": role,
                "name": name,
                "body": raw[len(prefix):].strip(),
            }
    if raw.startswith("["):
        end = raw.find("]")
        if 0 < end < 24:
            return {
                "kind": "module",
                "role": "system",
                "name": raw[1:end].strip() or "System",
                "body": raw[end + 1:].strip(),
            }
    return {"kind": "plain", "role": "system", "name": "System", "body": raw}


# ---------------------------------------------------------------------------
# Error presentation
# ---------------------------------------------------------------------------
_ERROR_HINTS = (
    ("rate limit", "The AI service is rate limited right now."),
    ("resource_exhausted", "The AI service is rate limited right now."),
    ("quota", "The AI service quota has been reached."),
    ("429", "The AI service is rate limited right now."),
    ("api key", "The API key was rejected."),
    ("api_key", "The API key was rejected."),
    ("permission", "The AI service refused the request."),
    ("unauthor", "The credentials were refused."),
    ("connection", "E.V. couldn't reach the AI service."),
    ("timeout", "The request took too long and was cancelled."),
    ("timed out", "The request took too long and was cancelled."),
    ("network", "E.V. couldn't reach the network."),
    ("ssl", "The secure connection could not be established."),
    ("no such file", "That file or folder no longer exists."),
    ("filenotfound", "That file or folder no longer exists."),
    ("permissionerror", "Windows blocked access to that item."),
    ("access is denied", "Windows blocked access to that item."),
    ("playwright", "The browser engine could not start."),
    ("browser", "The browser could not complete that step."),
    ("microphone", "E.V. couldn't access the microphone."),
    ("audio", "E.V. couldn't access the audio device."),
    ("module", "A required component is missing."),
    ("import", "A required component is missing."),
    ("memory", "E.V. couldn't save to memory."),
    ("discord", "The Discord bridge is not reachable."),
)


def humanize_error(error: object) -> str:
    """Turn a raw exception/tool error into one calm, readable sentence."""
    text = str(error or "").strip()
    if not text:
        return "Something went wrong. E.V. can retry this."
    low = text.lower()
    for needle, sentence in _ERROR_HINTS:
        if needle in low:
            return sentence
    # Drop noisy technical wrappers, keep the first meaningful clause.
    cleaned = re.sub(r"^(exception|error|traceback)\s*:\s*", "", text, flags=re.I)
    cleaned = cleaned.replace("\n", " ").strip()
    first = re.split(r"(?<=[a-z0-9\)\]])\.\s", cleaned)[0]
    short = first[:160].strip()
    if not short:
        return "Something went wrong. E.V. can retry this."
    short = short[0].upper() + short[1:]
    if not short.endswith((".", "!", "?")):
        short += "."
    return short


def error_details(error: object) -> str:
    """Technical text for the Details drawer / debug mode."""
    if isinstance(error, BaseException):
        return f"{type(error).__name__}: {error}"
    return str(error or "").strip()


def _quote_cmd_arg(path: str) -> str:
    return f'"{path}"'


def _hidden_launch_args(*extra_args: str) -> list[str]:
    pythonw = Path(r"C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe")
    python = Path(sys.executable)
    main_py = BASE_DIR / "main.py"
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return [str(exe), *extra_args]
    if pythonw.exists():
        return [str(pythonw), str(main_py), *extra_args]
    return [str(python), str(main_py), *extra_args]

def _startup_run_value() -> str:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'{_quote_cmd_arg(str(exe))} --startup'
    pythonw = Path(r"C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe")
    main_py = BASE_DIR / "main.py"
    if pythonw.exists():
        return f'{_quote_cmd_arg(str(pythonw))} {_quote_cmd_arg(str(main_py))} --startup'
    return f'{_quote_cmd_arg(sys.executable)} {_quote_cmd_arg(str(main_py))} --startup'


def _startup_registry_key():
    if platform.system() != "Windows":
        return None
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def _current_boot_stamp() -> int:
    try:
        return int(psutil.boot_time())
    except Exception:
        return int(time.time())


def _launched_from_windows_startup() -> bool:
    return any(str(arg).strip().lower() == "--startup" for arg in sys.argv[1:])


def _default_app_settings() -> dict:
    return {
        "startup_animation_enabled": True,
        "last_boot_stamp": 0,
        "boot_sequence_played": False,
        "show_workspace_on_startup": False,
        "launcher_pos": None,
        "launch_minimized": False,
        "check_updates_on_startup": True,
        "default_ai_provider": "Gemini",
        "auto_provider_switch": True,
        "attention_message_prompts": True,
        "attention_call_prompts": True,
        "developer_mode_enabled": False,
        "developer_mode_workspace": "",
    }


def _default_discord_settings() -> dict:
    return {
        "bot_token": "",
        "enabled": False,
        "channel_id": "",
    }

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = _quiet_run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = _quiet_run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = _quiet_run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = _quiet_run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = _quiet_run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = _quiet_run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

def _or_available() -> bool:
    """True when an OpenRouter key is configured (fallback provider)."""
    try:
        if not API_FILE.exists():
            return False
        data = json.loads(API_FILE.read_text(encoding="utf-8"))
        return bool(str(data.get("openrouter_api_key") or "").strip())
    except Exception:
        return False


_CAM_OK_CACHE = {"ok": False, "ts": 0.0}


def _camera_available() -> bool:
    now = time.time()
    if now - _CAM_OK_CACHE["ts"] < 10.0:
        return bool(_CAM_OK_CACHE["ok"])

    ok = False
    cap = None
    try:
        import cv2  # optional dependency; used only for a quick camera probe

        indices = [0, 1, 2]
        if _OS == "Windows":
            for idx in indices:
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            ok = True
                            break
                finally:
                    if cap is not None:
                        cap.release()
                        cap = None
        else:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                ok = bool(ret and frame is not None)
    except Exception:
        ok = False
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    _CAM_OK_CACHE["ok"] = ok
    _CAM_OK_CACHE["ts"] = now
    return ok


class _GestureRenderCanvas(QWidget):
    CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17)
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self._landmarks: list[tuple[float, float, float]] = []
        self._hand_visible = False
        self._search_phase = 0
        self._target_opacity = 0.0
        self._skeleton_opacity = 0.0

    def set_landmarks(self, landmarks: list[tuple[float, float, float]]):
        self._landmarks = landmarks or []
        self.update()

    def set_hand_visible(self, visible: bool):
        self._hand_visible = visible
        self._target_opacity = 1.0 if visible else 0.0
        self.update()

    def set_search_phase(self, phase: int):
        self._search_phase = phase
        self.update()

    def _normalized_points(self, rect: QRectF) -> list[QPointF]:
        if not self._landmarks:
            return []
        xs = [p[0] for p in self._landmarks]
        ys = [p[1] for p in self._landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bbox_w = max_x - min_x
        bbox_h = max_y - min_y
        if bbox_w < 1e-4:
            bbox_w = 1e-4
        if bbox_h < 1e-4:
            bbox_h = 1e-4
        avail_w = rect.width() * 0.82
        avail_h = rect.height() * 0.82
        scale = min(avail_w / bbox_w, avail_h / bbox_h)
        center_x = rect.center().x()
        center_y = rect.center().y()
        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0
        points: list[QPointF] = []
        for x, y, _ in self._landmarks:
            px = center_x + (x - mid_x) * scale
            py = center_y + (y - mid_y) * scale
            points.append(QPointF(px, py))
        return points

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor(3, 4, 7))

        if self._hand_visible and len(self._landmarks) >= 21:
            # animate opacity toward target
            self._skeleton_opacity += (self._target_opacity - self._skeleton_opacity) * 0.24
            pts = self._normalized_points(rect)
            if pts:
                # soft glow
                glow_pen = QPen(QColor(255, 70, 70, int(120 * self._skeleton_opacity)), 18,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                for a, b in self.CONNECTIONS:
                    painter.drawLine(pts[a], pts[b])

                edge_pen = QPen(QColor(255, 110, 110, int(220 * self._skeleton_opacity)), 4,
                               Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(edge_pen)
                for a, b in self.CONNECTIONS:
                    painter.drawLine(pts[a], pts[b])

                for point in pts:
                    radius = 7.0
                    grad = QRadialGradient(point, radius * 2.2)
                    grad.setColorAt(0.0, QColor(255, 255, 255, int(240 * self._skeleton_opacity)))
                    grad.setColorAt(0.15, QColor(255, 130, 130, int(180 * self._skeleton_opacity)))
                    grad.setColorAt(1.0, QColor(255, 30, 30, int(16 * self._skeleton_opacity)))
                    painter.setBrush(QBrush(grad))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(point, radius * 1.4, radius * 1.4)
                    painter.setBrush(QColor(255, 255, 255, int(230 * self._skeleton_opacity)))
                    painter.drawEllipse(point, 3.5, 3.5)
        else:
            self._skeleton_opacity += (self._target_opacity - self._skeleton_opacity) * 0.24
            dot_count = (self._search_phase // 8) % 4
            message = "Searching for hand" + ("." * dot_count)
            painter.setPen(QColor(200, 200, 220, 180))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, message)

        painter.end()


class GestureCameraPreview(QFrame):
    def __init__(self, parent=None, *, compact: bool = False):
        super().__init__(parent)
        self._compact = bool(compact)
        self._expanded_compact = False
        self.setObjectName("GestureCameraPreview")
        self.setStyleSheet(
            f"""
            QFrame#GestureCameraPreview {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(9, 10, 14, 255),
                    stop:1 rgba(3, 4, 7, 255));
                border: 1px solid rgba(92, 211, 255, 0.24);
                border-radius: 16px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        self._cap = None
        self._timer = None
        self._hands = None
        self._use_tasks_api = False
        self._vision_module = None
        self._prev_pinch = False
        self._smoothed_cursor: tuple[float, float] | None = None
        self._smoothed_screen: tuple[float, float] | None = None
        self._smoothed_landmarks: list[tuple[float, float, float]] | None = None
        self._search_phase = 0
        self._smoothing_alpha = 0.8
        self._gesture_canvas_alpha = 0.0
        self._sensitivity = 1.0
        self._sensitivity_levels = {"Low": 0.8, "Medium": 1.0, "High": 1.4}
        self._invert_cursor_x = False
        self._invert_cursor_y = False
        self._cursor_calibration_x_min: float | None = None
        self._cursor_calibration_x_max: float | None = None
        self._cursor_calibration_y_min: float | None = None
        self._cursor_calibration_y_max: float | None = None
        self._last_screen_pos: tuple[int, int] | None = None
        self._cursor_anchor: tuple[float, float] | None = None

        lay = QVBoxLayout(self)
        if self._compact:
            lay.setContentsMargins(12, 8, 12, 8)
            lay.setSpacing(6)
        else:
            lay.setContentsMargins(14, 14, 14, 14)
            lay.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        self._title = QLabel("Hand tracking" if self._compact else "HAND TRACKING")
        title = self._title

        title.setFont(QFont(_UI_FONT, 9 if self._compact else 10, QFont.Weight.DemiBold if self._compact else QFont.Weight.Bold))
        title.setStyleSheet(f"color: {EV['text_med'] if self._compact else C.WHITE}; letter-spacing: 0.6px;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(12, 12)
        self._status_dot.setStyleSheet("border-radius: 6px; background: #ffb648;")
        header_row.addWidget(self._status_dot)

        self._status_text = QLabel("SEARCHING")
        self._status_text.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        self._status_text.setStyleSheet("color: #ffb648;")

        header_row.addWidget(self._status_text)

        self._sensitivity_select = QComboBox()
        self._sensitivity_select.addItems(["Low", "Medium", "High"])
        self._sensitivity_select.setCurrentText("Medium")
        self._sensitivity_select.setFixedWidth(70 if self._compact else 84)
        self._sensitivity_select.setStyleSheet(
            "QComboBox { background: rgba(255,255,255,0.05); color: #f4f6f8; border: 1px solid rgba(92, 211, 255,0.24); border-radius: 8px; padding: 4px 8px; }"
            "QComboBox::drop-down { border: none; }")
        self._sensitivity_select.currentTextChanged.connect(self._set_sensitivity_level)
        header_row.addWidget(self._sensitivity_select)
        lay.addLayout(header_row)

        self._hand_canvas = _GestureRenderCanvas(self)
        self._hand_canvas.setFixedHeight(220)
        self._hand_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self._hand_canvas)

        self._status_hint_label = QLabel("Initializing hand detection...")
        self._status_hint_label.setFont(QFont("Segoe UI", 8))
        self._status_hint_label.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._status_hint_label.setWordWrap(True)
        lay.addWidget(self._status_hint_label)

        footer = QGridLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setHorizontalSpacing(16)
        footer.setVerticalSpacing(8)

        self._status_value = QLabel("Searching")
        self._confidence_value = QLabel("0%")
        self._gesture_value = QLabel("None")
        self._cursor_value = QLabel("Inactive")

        for idx, (label_text, value_label) in enumerate([
            ("Status", self._status_value),
            ("Confidence", self._confidence_value),
            ("Gesture", self._gesture_value),
            ("Cursor", self._cursor_value),
        ]):
            label = QLabel(label_text.upper())
            label.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
            label.setStyleSheet(f"color: {C.TEXT_DIM};")
            value_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            value_label.setStyleSheet(f"color: {C.WHITE};")
            footer.addWidget(label, idx, 0)
            footer.addWidget(value_label, idx, 1)

        lay.addLayout(footer)

        self._expanded_height = 320
        self._collapsed_height = 64
        self._footer_widgets = [
            widget for widget in self.findChildren(QLabel)
            if widget not in (self._title, self._status_text, self._status_dot)
        ]

        if self._compact:
            # Rail mode: a slim status strip until the user asks for the camera.
            self.setFixedHeight(self._collapsed_height)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Click to open the camera preview")
            self._hand_canvas.hide()
            self._status_hint_label.hide()
            self._status_text.hide()
            for widget in self._footer_widgets:
                widget.hide()
            self._set_status("Tap to open the preview.", "offline")
        else:
            try:
                self.setFixedHeight(self._expanded_height)
            except Exception:
                pass
            self._set_status("Searching for hand...", "searching")
            self._start_camera()

    def closeEvent(self, event):
        self._stop_camera()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._compact and not self._expanded_compact:
                    self._expand_compact()
                else:
                    self._toggle_camera()
                event.accept()
                return
        except Exception:
            pass
        return super().mousePressEvent(event)

    def _expand_compact(self):
        self._expanded_compact = True
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip("Click to pause or resume the camera")
        self._hand_canvas.show()
        self._status_hint_label.show()
        self._status_text.show()
        self.setStyleSheet(
            f"""
            QFrame#GestureCameraPreview {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(9, 10, 14, 255),
                    stop:1 rgba(3, 4, 7, 255));
                border: 1px solid rgba(92, 211, 255, 0.24);
                border-radius: 16px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        for widget in self._footer_widgets:
            widget.show()
        self.setFixedHeight(self._expanded_height)
        self._start_camera()

    def _set_status(self, text: str, level: str = "searching"):
        self._status_hint_label.setText(text)
        self._status_value.setText(level.capitalize())
        colors = {
            "tracking": EV["success"],
            "searching": EV["warning"],
            "lost": EV["danger"],
            "offline": EV["text_dim"],
        }
        color = colors.get(level, EV["warning"])
        self._status_dot.setStyleSheet(f"border-radius: 6px; background: {color};")
        self._status_text.setText(level.upper())
        self._status_text.setStyleSheet(f"color: {color};")

    def _start_camera(self):
        if self._cap is not None:
            return
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY)
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            except Exception:
                pass
            if not cap.isOpened():
                cap.release()
                raise RuntimeError("camera unavailable")
            self._cap = cap
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(30)
            self._set_status("Camera ready. Move your hand to steer the cursor.", "searching")
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
            except Exception:
                pass
        except Exception as exc:
            self._set_status(f"Gesture camera is offline: {exc}", "lost")

        if self._cap is not None:
            try:
                self.setFixedHeight(self._expanded_height)
            except Exception:
                pass

    def _stop_camera(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self._hands is not None:
            try:
                self._hands.close()
            except Exception:
                pass
            self._hands = None

        try:
            self.setFixedHeight(self._collapsed_height)
        except Exception:
            pass
        self._set_status("Camera stopped", "lost")

    def _download_hand_landmarker_model(self, model_path: Path) -> bool:
        temp_path = model_path.with_suffix(model_path.suffix + ".download")
        try:
            import urllib.request

            self._set_status("Downloading gesture model...", "searching")
            model_path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(MODEL_DOWNLOAD_URL, timeout=60) as response:
                with open(temp_path, "wb") as out_file:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        out_file.write(chunk)
            temp_path.replace(model_path)
            return True
        except Exception as exc:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            self._set_status(
                f"Gesture model download failed: {exc}. "
                f"Put hand_landmarker.task into {model_path.parent} and restart.",
                "lost",
            )
            return False

    def _tick(self):
        if self._cap is None:
            return
        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._set_status("Camera feed dropped. Trying again…", "lost")
                return
            self._process_frame(frame)
        except Exception as exc:
            self._set_status(f"Gesture camera error: {exc}", "lost")

    def _process_frame(self, frame):
        try:
            import cv2
        except Exception as exc:
            self._set_status(f"Gesture camera unavailable: {exc}", "lost")
            return

        import importlib

        mp = None
        try:
            mp = importlib.import_module("mediapipe")
        except Exception:
            pass

        if mp is None:
            self._set_status(
                "Gesture camera unavailable: mediapipe not found. "
                "Install it into the app venv: .venv\\Scripts\\python.exe -m pip install mediapipe",
                "lost",
            )
            return

        if self._hands is None:
            HandsClass = None
            try:
                solutions = getattr(mp, "solutions", None)
                if solutions is not None and hasattr(solutions, "hands"):
                    HandsClass = solutions.hands.Hands
            except Exception:
                HandsClass = None

            if HandsClass is not None:
                try:
                    self._hands = HandsClass(
                        static_image_mode=False,
                        max_num_hands=1,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._use_tasks_api = False
                except Exception as exc:
                    self._set_status(f"Gesture init error: {exc}", "lost")
                    return
            else:
                vision = None
                try:
                    vision = importlib.import_module("mediapipe.tasks.python.vision")
                except Exception:
                    vision = None

                if vision is None or not hasattr(vision, "HandLandmarker"):
                    self._set_status(
                        "Gesture camera unavailable: mediapipe Tasks API not available. "
                        "Install mediapipe into the app venv and restart.",
                        "lost",
                    )
                    return

                model_dir = CONFIG_DIR / "models"
                model_dir.mkdir(parents=True, exist_ok=True)
                model_path = model_dir / "hand_landmarker.task"
                if not model_path.exists():
                    self._set_status("Downloading model", "searching")
                    if not self._download_hand_landmarker_model(model_path):
                        return

                try:
                    self._hands = vision.HandLandmarker.create_from_model_path(str(model_path))
                    self._use_tasks_api = True
                    self._vision_module = vision
                except Exception as exc:
                    self._set_status(f"Gesture init error: {exc}", "lost")
                    return

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks: list[tuple[float, float, float]] = []
        confidence = 0.0

        if self._use_tasks_api:
            try:
                import numpy as np
                image_lib = importlib.import_module("mediapipe.tasks.python.vision.core.image")
                mp_image = image_lib.Image(image_lib.ImageFormat.SRGB, np.ascontiguousarray(rgb))
                results = self._hands.detect(mp_image)
            except Exception as exc:
                self._set_status(f"Gesture task detect error: {exc}", "lost")
                return
            if getattr(results, "hand_landmarks", None):
                hand_landmarks = results.hand_landmarks[0]
                for landmark in hand_landmarks:
                    landmarks.append((landmark.x, landmark.y, landmark.z))
                confidence = 1.0 if landmarks else 0.0
        else:
            results = self._hands.process(rgb)
            if getattr(results, "multi_hand_landmarks", None):
                hand_landmarks = results.multi_hand_landmarks[0]
                for landmark in hand_landmarks.landmark:
                    landmarks.append((landmark.x, landmark.y, landmark.z))
            if getattr(results, "multi_handedness", None) and results.multi_handedness:
                try:
                    confidence = float(results.multi_handedness[0].classification[0].score)
                except Exception:
                    confidence = 1.0 if landmarks else 0.0

        gesture = estimate_gesture_state(landmarks, self._prev_pinch)
        if gesture.get("cursor"):
            norm = self._calibrate_and_smooth_cursor(gesture["cursor"])
            self._move_cursor(norm)
        if gesture.get("pinch_triggered"):
            self._trigger_click()
        self._prev_pinch = bool(gesture.get("pinch", False))

        self._render_hand(landmarks, gesture, confidence)

    def _render_hand(self, landmarks: list[tuple[float, float, float]], gesture: dict, confidence: float):
        has_hand = bool(landmarks and len(landmarks) >= 21)
        if has_hand:
            if self._smoothed_landmarks is None or len(self._smoothed_landmarks) != len(landmarks):
                self._smoothed_landmarks = landmarks.copy()
            else:
                alpha = 0.32
                smoothed: list[tuple[float, float, float]] = []
                for prev, current in zip(self._smoothed_landmarks, landmarks):
                    sx, sy, sz = prev
                    tx, ty, tz = current
                    smoothed.append((sx + alpha * (tx - sx), sy + alpha * (ty - sy), sz + alpha * (tz - sz)))
                self._smoothed_landmarks = smoothed
            self._hand_canvas.set_landmarks(self._smoothed_landmarks)
            self._hand_canvas.set_hand_visible(True)
            self._hand_canvas.set_search_phase(0)
            self._set_status("Hand detected and tracking.", "tracking")
            self._confidence_value.setText(f"{int(confidence * 100)}%")
            self._gesture_value.setText("Pinch" if gesture.get("pinch") else "Open Hand")
            self._cursor_value.setText("Active" if gesture.get("cursor") else "Inactive")
        else:
            self._hand_canvas.set_hand_visible(False)
            self._search_phase = (self._search_phase + 1) % 32
            self._hand_canvas.set_search_phase(self._search_phase)
            self._set_status("Searching for hand...", "searching")
            self._confidence_value.setText("0%")
            self._gesture_value.setText("None")
            self._cursor_value.setText("Inactive")

    def _calibrate_and_smooth_cursor(self, cursor: tuple[float, float]) -> tuple[float, float]:
        raw_x = float(cursor[0])
        raw_y = float(cursor[1])

        if self._invert_cursor_x:
            raw_x = 1.0 - raw_x
        if self._invert_cursor_y:
            raw_y = 1.0 - raw_y

        raw_x = max(0.0, min(1.0, raw_x))
        raw_y = max(0.0, min(1.0, raw_y))

        if self._cursor_anchor is None:
            self._cursor_anchor = (raw_x, raw_y)
            return (raw_x, raw_y)

        anchor_x, anchor_y = self._cursor_anchor
        mapped_x = raw_x
        mapped_y = raw_y

        if self._smoothed_cursor is None:
            self._smoothed_cursor = (mapped_x, mapped_y)
        else:
            sx, sy = self._smoothed_cursor
            a = self._smoothing_alpha
            self._smoothed_cursor = (sx + a * (mapped_x - sx), sy + a * (mapped_y - sy))

        return self._smoothed_cursor

    def _set_sensitivity_level(self, level: str) -> None:
        self._sensitivity = self._sensitivity_levels.get(level, self._sensitivity_levels["Medium"])

    def _move_cursor(self, cursor):
        try:
            import pyautogui
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            geom = screen.geometry()
            if not geom.isValid():
                return

            try:
                s = float(self._sensitivity)
            except Exception:
                s = 1.0

            nx = float(cursor[0])
            ny = float(cursor[1])
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))

            x = int(geom.left() + nx * geom.width())
            y = int(geom.top() + ny * geom.height())

            if self._smoothed_screen is None:
                self._smoothed_screen = (float(x), float(y))
            else:
                sx, sy = self._smoothed_screen
                a = max(0.18, min(0.36, self._smoothing_alpha))
                self._smoothed_screen = (sx + a * (x - sx), sy + a * (y - sy))

            target_x = int(round(self._smoothed_screen[0]))
            target_y = int(round(self._smoothed_screen[1]))
            dead_zone = max(3, int(min(geom.width(), geom.height()) * 0.004))

            if self._last_screen_pos is not None:
                last_x, last_y = self._last_screen_pos
                if abs(target_x - last_x) <= dead_zone and abs(target_y - last_y) <= dead_zone:
                    return

            self._last_screen_pos = (target_x, target_y)
            try:
                pyautogui.moveTo(target_x, target_y, duration=0)
            except Exception:
                pyautogui.moveTo(target_x, target_y, duration=0.01)
        except Exception:
            pass

    def _trigger_click(self):
        try:
            import pyautogui
            pyautogui.click(button="left")
        except Exception:
            pass

    def _toggle_camera(self):
        if self._cap is None:
            self._start_camera()
        else:
            self._stop_camera()


class ResponsiveCardRow(QWidget):
    """Three dashboard cards that reflow into a single column on narrow screens."""

    def __init__(self, cards: list[QWidget], *, wide_at: int = 700, parent=None):
        super().__init__(parent)
        self._cards = cards
        self._wide_at = wide_at
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(14)
        self._reflow(3)

    def _reflow(self, columns: int):
        if columns == self._columns:
            return
        self._columns = columns
        for card in self._cards:
            self._grid.removeWidget(card)
        for index, card in enumerate(self._cards):
            if columns >= 2:
                self._grid.addWidget(card, 0, index)
            else:
                self._grid.addWidget(card, index, 0)
        for column in range(3):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(3 if self.width() >= self._wide_at else 1)


def _active_net_label() -> str:
    try:
        stats = psutil.net_if_stats()
        active = []
        for name, info in stats.items():
            if getattr(info, "isup", False):
                active.append(name)
        if active:
            return active[0]
    except Exception:
        pass
    return "No active adapter"

class HudCanvas(QWidget):
    """E.V. voice core: a restrained orb that reflects the live voice state.

    States mirror the assistant state machine (``LISTENING``, ``THINKING``,
    ``EXECUTING``, ``SPEAKING``, ``MUTED``). Loudness comes from
    :meth:`push_level`, which the runtime feeds with the real audio envelope
    when a stream is available; without it the orb stays calm and simply
    breathes with the state.
    """

    RADIUS = 46          # ring radius in the internal 120x120 coordinate space
    _LEVELS = 72         # ring segments of the speaking waveform

    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted = False
        self.speaking = False
        self.state = "INITIALISING"

        self._face_path = face_path
        self._tick = 0
        self._phase = 0.0            # slow rotation for the focus arc
        self._breath = 0.0           # 0..1 breathing amount
        self._focus = 0.0            # 0..1 ambient accent strength
        self._level = 0.0            # smoothed audio envelope 0..1
        self._target_level = 0.0
        self._bars = [0.0] * self._LEVELS
        self._last_t = time.monotonic()

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(33)          # ~30 fps, one repaint per frame

    # -- public surface -----------------------------------------------------
    def push_level(self, level: float) -> None:
        """Feed a normalized (0..1) audio envelope for the live waveform."""
        try:
            self._target_level = max(0.0, min(1.0, float(level)))
        except Exception:
            self._target_level = 0.0

    def _accent(self) -> QColor:
        if self.muted:
            return QColor(EV["warning"])
        if self.state == "THINKING":
            return QColor(EV["violet"])
        if self.state in ("EXECUTING", "PROCESSING"):
            return QColor(EV["accent"])
        if self.speaking:
            return QColor(EV["accent"])
        if self.state == "LISTENING":
            return QColor(EV["accent"])
        return QColor(EV["text_dim"])

    # -- animation ----------------------------------------------------------
    def _step(self):
        now = time.monotonic()
        dt = max(0.001, min(0.1, now - self._last_t))
        self._last_t = now
        self._tick += 1

        if self.speaking:
            target_focus, focus_speed = 1.0, 1.10
        elif self.state == "THINKING":
            target_focus, focus_speed = 0.78, 0.55
        elif self.state in ("EXECUTING", "PROCESSING"):
            target_focus, focus_speed = 0.72, 0.30
        elif self.muted:
            target_focus, focus_speed = 0.34, 0.10
        else:
            target_focus, focus_speed = 0.62, 0.22

        self._focus += (target_focus - self._focus) * min(1.0, dt * 3.4)
        self._phase = (self._phase + dt * focus_speed * 90.0) % 360.0
        self._breath = (math.sin(now * (1.9 if self.speaking else 0.9)) + 1.0) * 0.5
        self._level += (self._target_level - self._level) * min(1.0, dt * 9.0)

        # ring waveform: real level drives amplitude, phase gives motion
        for i in range(self._LEVELS):
            wobble = 0.5 + 0.5 * math.sin(now * 2.4 + i * 0.42)
            floor = 0.06 if not self.muted else 0.03
            target = floor + self._level * (0.55 + 0.45 * wobble)
            if self.speaking and self._level < 0.02:
                target = floor + 0.16 * wobble
            self._bars[i] += (target - self._bars[i]) * min(1.0, dt * 7.0)
        self.update()

    # -- painting -----------------------------------------------------------
    def _accent_qss(self) -> str:
        return self._accent().name()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        side = min(W, H)
        if side <= 8:
            return
        p.translate(W / 2, H / 2)
        p.scale(side / 120.0, side / 120.0)

        accent = self._accent()
        breath = self._breath
        focus = self._focus
        radius = self.RADIUS + breath * (1.8 if self.speaking else 0.9)

        # 1. ambient bloom
        for step in range(6):
            spread = 26 - step * 3.6
            alpha = int((4 + focus * 7) * (1.0 - step / 7.0))
            if alpha <= 0:
                continue
            col = QColor(accent)
            col.setAlpha(alpha)
            p.setPen(QPen(col, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(-radius - spread, -radius - spread, (radius + spread) * 2, (radius + spread) * 2))

        # 2. inner disc: soft glass core
        disc = QRadialGradient(QPointF(0, -6), radius * 1.25)
        disc.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), int(38 + focus * 30)))
        disc.setColorAt(0.55, QColor(accent.red(), accent.green(), accent.blue(), int(12 + focus * 12)))
        disc.setColorAt(1.0, QColor(8, 12, 18, 0))
        p.setBrush(QBrush(disc))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))

        # 3. static outer ring
        ring = QColor(255, 255, 255)
        ring.setAlpha(30 + int(focus * 40))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, 0.9))
        p.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))

        # 4. voice ring: 72 segments whose length follows the envelope
        if self.speaking or self._level > 0.02:
            p.setPen(Qt.PenStyle.NoPen)
            span = 360.0 / self._LEVELS
            for i, level in enumerate(self._bars):
                angle = math.radians(i * span + self._phase * 0.25)
                inner = radius + 4.5
                outer = inner + 1.5 + level * 13.0
                col = QColor(accent)
                col.setAlpha(min(235, int(70 + level * 165)))
                p.setPen(QPen(col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(
                    QPointF(math.cos(angle) * inner, math.sin(angle) * inner),
                    QPointF(math.cos(angle) * outer, math.sin(angle) * outer),
                )
            p.setPen(Qt.PenStyle.NoPen)

        # 5. focus arc for thinking/executing
        if self.state in ("THINKING", "EXECUTING", "PROCESSING"):
            arc = QColor(accent)
            arc.setAlpha(220)
            p.setPen(QPen(arc, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(-radius - 2.2, -radius - 2.2, (radius + 2.2) * 2, (radius + 2.2) * 2)
            p.drawArc(rect, int(-self._phase * 16), int(84 * 16))
            ghost = QColor(255, 255, 255)
            ghost.setAlpha(46)
            p.setPen(QPen(ghost, 1.2))
            p.drawArc(rect, int((-self._phase + 168) * 16), int(46 * 16))

        # 6. centre wordmark + state
        p.setPen(QColor(EV["text"]))
        p.setFont(QFont(_UI_FONT, 15, QFont.Weight.DemiBold))
        p.drawText(QRectF(-60, -18, 120, 22), Qt.AlignmentFlag.AlignCenter, "E.V.")
        state_text, state_colour = self._state_caption()
        p.setPen(state_colour)
        p.setFont(QFont(_UI_FONT, 6, QFont.Weight.DemiBold))
        p.drawText(QRectF(-60, 3, 120, 14), Qt.AlignmentFlag.AlignCenter, state_text)

    def _state_caption(self) -> tuple[str, QColor]:
        if self.muted:
            return "MIC MUTED", QColor(EV["warning"])
        if self.speaking:
            return "SPEAKING", QColor(EV["accent"])
        if self.state == "THINKING":
            return "THINKING", QColor(EV["violet"])
        if self.state in ("EXECUTING", "PROCESSING"):
            return "WORKING", QColor(EV["accent"])
        if self.state == "LISTENING":
            return "LISTENING", QColor(EV["accent"])
        if self.state in ("INITIALISING", "OFFLINE"):
            return "STANDBY", QColor(EV["text_dim"])
        return self.state.upper(), QColor(EV["text_dim"])


class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0-100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class MessageCard(QFrame):
    def __init__(self, role: str, name: str, text: str, stamp: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MessageCard")
        accent_map = {
            "user": (C.BORDER_B, C.WHITE),
            "assistant": (C.PRI, C.PRI),
            "system": ("#4b8cff", "#4b8cff"),
            "file": ("#2ec98a", "#2ec98a"),
            "error": ("#ff9a5c", "#ff9a5c"),
        }
        border_col, left_col = accent_map.get(role, accent_map["system"])
        self.setStyleSheet(
            f"""
            QFrame#MessageCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13, 15, 20, 246),
                    stop:1 rgba(5, 6, 9, 238));
                border: 1px solid {border_col};
                border-left: 3px solid {left_col};
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        avatar = QLabel(name[:1].upper())
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        palette = {
            "user": ("#0d0f14", C.WHITE, C.BORDER_B),
            "assistant": ("#12090a", C.RED, C.PRI),
            "system": ("#101525", "#7cb7ff", "#4b8cff"),
            "file": ("#0f1410", C.GREEN, "#2ec98a"),
            "error": ("#1a0f10", "#ffc38a", "#ff9a5c"),
        }
        bg, fg, border = palette.get(role, palette["system"])
        avatar.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 20px;"
        )

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")

        time_lbl = QLabel(stamp)
        time_lbl.setFont(QFont("Segoe UI", 7))
        time_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(time_lbl)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setFont(QFont("Segoe UI", 9))
        text_color = {
            "user": C.TEXT,
            "assistant": C.WHITE,
            "system": C.TEXT_MED,
            "file": C.GREEN,
            "error": C.RED,
        }.get(role, C.TEXT)
        text_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")

        body.addLayout(top)
        body.addWidget(text_lbl)
        lay.addWidget(avatar)
        lay.addLayout(body)


class TaskCard(QFrame):
    """Live view of the current request: plan, stage flow and tool activity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskCard")
        self._active = False
        self._workspace_locked = False
        self._activities: list[ToolActivityCard] = []
        self.setStyleSheet(
            f"""
            QFrame#TaskCard {{
                background: {EV['surface']};
                border: 1px solid {EV['border']};
                border-radius: 14px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel("TASK")
        self._title.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {EV['text_faint']}; letter-spacing: 1.4px;")
        self._pct = QLabel("0%")
        self._pct.setFont(QFont(_UI_FONT, 8, QFont.Weight.DemiBold))
        self._pct.setStyleSheet(f"color: {EV['text_dim']};")
        self._collapse_btn = QPushButton("Hide")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {EV['text_faint']}; font-size: 8pt; padding: 0; }}"
            f"QPushButton:hover {{ color: {EV['accent']}; }}"
        )
        self._collapse_btn.clicked.connect(self._toggle_collapsed)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._pct)
        header.addWidget(self._collapse_btn)
        lay.addLayout(header)

        self._command_lbl = QLabel("Waiting for a request")
        self._command_lbl.setWordWrap(True)
        self._command_lbl.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        self._command_lbl.setStyleSheet(f"color: {EV['text']};")
        lay.addWidget(self._command_lbl)

        self._stage_flow = StageFlow()
        lay.addWidget(self._stage_flow)

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(9)

        self._plan_lbl = QLabel("E.V. will outline the plan here.")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setFont(QFont(_UI_FONT, 8))
        self._plan_lbl.setStyleSheet(f"color: {EV['text_dim']}; line-height: 140%;")
        body.addWidget(self._plan_lbl)

        self._activity_box = QVBoxLayout()
        self._activity_box.setContentsMargins(0, 0, 0, 0)
        self._activity_box.setSpacing(7)
        body.addLayout(self._activity_box)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setFont(QFont(_UI_FONT, 8))
        self._status_lbl.setStyleSheet(f"color: {EV['text_med']};")
        self._status_lbl.setVisible(False)
        body.addWidget(self._status_lbl)

        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        self._result_lbl.setFont(QFont(_UI_FONT, 9))
        self._result_lbl.setStyleSheet(f"color: {EV['text']};")
        self._result_lbl.setVisible(False)
        body.addWidget(self._result_lbl)

        lay.addWidget(self._body)
        self._update_visibility()

    # -- collapsed state ----------------------------------------------------
    def _toggle_collapsed(self):
        collapsed = self._body.isVisible()
        self._body.setVisible(not collapsed)
        self._collapse_btn.setText("Show" if collapsed else "Hide")

    # -- public API (kept compatible with the runtime) ----------------------
    def set_task(self, title: str, desc: str, percent: int):
        if self._workspace_locked:
            return
        if self._active:
            self.update_workspace(title=title, status=desc, percent=percent)
            return
        self._title.setText("TASK")
        self._command_lbl.setText(title)
        self._status_lbl.setText(desc)
        self._status_lbl.setVisible(bool(desc))
        self._set_percent(percent)
        self._update_visibility()

    def _format_plan(self, plan: list[str] | str | None) -> str:
        if not plan:
            return "Understanding the request…"
        if isinstance(plan, str):
            items = [line.strip(" •-") for line in plan.splitlines() if line.strip(" •-")]
        else:
            items = [str(item).strip() for item in plan if str(item).strip()]
        if not items:
            return "Understanding the request…"
        return "\n".join(f"•  {item}" for item in items)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._clear_activities()
        self._active = True
        self._workspace_locked = False
        self._title.setText("TASK")
        self._command_lbl.setText(command or "Working")
        self._plan_lbl.setText(self._format_plan(plan))
        self._status_lbl.setText("Building the plan…")
        self._status_lbl.setVisible(True)
        self._result_lbl.setVisible(False)
        self._stage_flow.reset()
        self._stage_flow.set_stage(1)
        self._set_percent(6)
        self._source = source
        self._body.setVisible(True)
        self._collapse_btn.setText("Hide")
        self._update_visibility()

    def update_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                         status: str | None = None, output: str | None = None, percent: int | None = None,
                         footer: str | None = None):
        if title:
            self._title.setText(title.upper()[:28])
        if command:
            self._command_lbl.setText(command)
        if plan is not None:
            self._plan_lbl.setText(self._format_plan(plan))
        if status:
            self._status_lbl.setText(status)
            self._status_lbl.setVisible(True)
        if output:
            self._result_lbl.setText(output)
            self._result_lbl.setVisible(True)
        if percent is not None:
            self._set_percent(percent)
        if footer:
            self._status_lbl.setText(footer)
        # stage flow follows the reported progress
        if percent is not None:
            if percent >= 96:
                self._stage_flow.set_stage(4)
            elif percent >= 70:
                self._stage_flow.set_stage(3)
            elif percent >= 20:
                self._stage_flow.set_stage(2)
            else:
                self._stage_flow.set_stage(1)
        self._active = True
        self._workspace_locked = False
        self._update_visibility()

    def finish_workspace(self, result: str, status: str = "Completed", percent: int = 100, *, success: bool = True):
        self._active = False
        self._workspace_locked = True
        self._result_lbl.setText(result or "Done.")
        self._result_lbl.setVisible(True)
        self._status_lbl.setText(status)
        self._status_lbl.setVisible(True)
        self._set_percent(percent)
        self._stage_flow.set_stage(4 if success else 2, failed=not success)
        for card in self._activities:
            if card._status in ("running", "pending"):
                card.finish(success=success)
        self._update_visibility()
        QTimer.singleShot(7000, self._auto_collapse)

    def _auto_collapse(self):
        if self._active or not self._result_lbl.isVisible():
            return
        self._body.setVisible(False)
        self._collapse_btn.setText("Show")

    def clear_workspace(self):
        self._active = False
        self._workspace_locked = False
        self._clear_activities()
        self._title.setText("TASK")
        self._command_lbl.setText("Waiting for a request")
        self._plan_lbl.setText("E.V. will outline the plan here.")
        self._status_lbl.setText("")
        self._status_lbl.setVisible(False)
        self._result_lbl.setText("")
        self._result_lbl.setVisible(False)
        self._set_percent(0)
        self._stage_flow.reset()
        self._update_visibility()

    # -- tool activity ------------------------------------------------------
    def add_activity(self, tool: str, title: str, detail: str = "") -> ToolActivityCard:
        card = ToolActivityCard(tool, title, detail)
        self._activities.append(card)
        self._activity_box.addWidget(card)
        self._body.setVisible(True)
        self._collapse_btn.setText("Hide")
        self._update_visibility()
        return card

    def update_activity(self, detail: str = "", title: str = ""):
        card = self._last_activity()
        if card is not None:
            card.set_status("running", detail=detail or None, title=title or None)

    def finish_activity(self, *, success: bool = True, detail: str = "", title: str = ""):
        card = self._last_activity()
        if card is not None:
            card.finish(success=success, detail=detail or None, title=title or None)

    def _last_activity(self) -> ToolActivityCard | None:
        for card in reversed(self._activities):
            if card._status == "running":
                return card
        return self._activities[-1] if self._activities else None

    def _clear_activities(self):
        for card in self._activities:
            self._activity_box.removeWidget(card)
            card.deleteLater()
        self._activities = []

    # -- helpers ------------------------------------------------------------
    def _set_percent(self, percent: int):
        pct = max(0, min(100, int(percent or 0)))
        self._pct.setText(f"{pct}%")
        self._pct.setStyleSheet(
            f"color: {EV['success'] if pct >= 100 else EV['text_dim']};"
        )

    def _update_visibility(self):
        has_content = bool(self._activities) or self._active or self._workspace_locked or self._result_lbl.isVisible()
        self.setVisible(has_content)


def _fmt_time_stamp(value: int | float | None = None) -> str:
    try:
        from datetime import datetime
        if value is None:
            dt = datetime.now()
        else:
            stamp = float(value)
            if stamp > 10_000_000_000:
                stamp /= 1000.0
            dt = datetime.fromtimestamp(stamp)
        return dt.strftime("%H:%M")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Chat rendering: markdown, syntax highlighting and copy affordances
# ---------------------------------------------------------------------------
PY_KEYWORDS = (
    "def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|lambda|"
    "pass|raise|yield|await|async|global|nonlocal|assert|del|in|is|not|and|or|None|True|False|"
    "self|break|continue"
)
JS_KEYWORDS = (
    "function|const|let|var|return|if|else|for|while|class|extends|import|export|from|await|"
    "async|new|try|catch|finally|throw|typeof|instanceof|null|undefined|true|false|this|super"
)
SHELL_KEYWORDS = "if|then|else|fi|for|do|done|while|case|esac|function|echo|export|set|cd|source"

_HL_LANGUAGES = {
    "python": ("py", PY_KEYWORDS, "#"),
    "py": ("py", PY_KEYWORDS, "#"),
    "javascript": ("js", JS_KEYWORDS, "//"),
    "js": ("js", JS_KEYWORDS, "//"),
    "typescript": ("js", JS_KEYWORDS, "//"),
    "ts": ("js", JS_KEYWORDS, "//"),
    "tsx": ("js", JS_KEYWORDS, "//"),
    "jsx": ("js", JS_KEYWORDS, "//"),
    "json": ("json", "", ""),
    "bash": ("sh", SHELL_KEYWORDS, "#"),
    "sh": ("sh", SHELL_KEYWORDS, "#"),
    "shell": ("sh", SHELL_KEYWORDS, "#"),
    "powershell": ("ps", SHELL_KEYWORDS, "#"),
    "ps1": ("ps", SHELL_KEYWORDS, "#"),
    "html": ("html", "", ""),
    "css": ("css", "", ""),
}


def _highlight_code(code: str, language: str = "") -> str:
    """Small, dependency-free syntax highlighter for chat code blocks.

    Tokens are matched on the raw source and escaped individually, so no
    placeholder bookkeeping is needed and no token can be re-matched.
    """
    lang = (language or "").strip().lower()
    spec = _HL_LANGUAGES.get(lang)
    if not spec or not code:
        return html_lib.escape(code)

    family, keywords, comment_token = spec
    keyword_set = {word.strip() for word in keywords.split("|") if word.strip()} if keywords else set()
    if comment_token == "#":
        comment_pattern = r"#[^\n]*"
    elif comment_token == "//":
        comment_pattern = r"(?://|/\*)[^\n]*"
    else:
        comment_pattern = None

    alternatives = [
        r"""(?P<string>\"\"\".*?\"\"\"|'''.*?'''|"[^"\n]*"|'[^'\n]*'|`[^`]*`)""",
        r"(?P<number>\b\d+(?:\.\d+)?\b)",
        r"(?P<word>[A-Za-z_][A-Za-z0-9_]*)",
    ]
    if comment_pattern:
        alternatives.insert(0, f"(?P<comment>{comment_pattern})")

    token_re = re.compile("|".join(alternatives), re.DOTALL)
    out: list[str] = []
    cursor = 0
    for match in token_re.finditer(code):
        out.append(html_lib.escape(code[cursor:match.start()]))
        kind = match.lastgroup
        text = html_lib.escape(match.group(0))
        if kind == "comment":
            out.append(f'<span style="color:#5c6e80;">{text}</span>')
        elif kind == "string":
            out.append(f'<span style="color:#9fe0a8;">{text}</span>')
        elif kind == "number":
            out.append(f'<span style="color:#ffc07a;">{text}</span>')
        elif kind == "word" and match.group(0) in keyword_set:
            out.append(f'<span style="color:#8fb6ff;">{text}</span>')
        else:
            out.append(text)
        cursor = match.end()
    out.append(html_lib.escape(code[cursor:]))
    return "".join(out)


def _copy_href(text: str) -> str:
    payload = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
    return f"evcopy:{payload}"


def _decode_copy_href(href: str) -> str:
    try:
        return base64.b64decode(href.split(":", 1)[1].encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def _code_block_html(code: str, language: str = "") -> str:
    label = (language or "code").strip().lower() or "code"
    highlighted = _highlight_code(code, language)
    return (
        '<table width="100%" cellspacing="0" cellpadding="0" '
        'style="margin:12px 0 6px 0; background-color:#070b11; '
        'border:1px solid rgba(255,255,255,0.10);">'
        '<tr><td style="padding:7px 12px 9px 12px;">'
        f'<p style="margin:0 0 6px 0; color:{EV["text_faint"]}; font-size:8pt;">'
        f'{html_lib.escape(label)} &nbsp;&nbsp;'
        f'<a href="{_copy_href(code)}" style="color:{EV["text_dim"]}; text-decoration:none; '
        f'font-size:8pt;">Copy code</a></p>'
        f'<pre style="margin:0; white-space:pre-wrap; color:{EV["text"]}; font-size:9pt; '
        f'font-family:{_MONO_FONT},Consolas,monospace;">{highlighted}</pre>'
        '</td></tr>'
        '</table>'
    )


def _markdown_to_html(text: str, role: str = "assistant") -> str:
    """Render assistant/user markdown into the subset of HTML Qt supports."""
    source = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[str] = []
    cursor = 0

    # 1. fenced code blocks first so their content is never re-formatted
    for match in re.finditer(r"```([\w+-]*)\n?(.*?)```", source, flags=re.S):
        chunks.append(_inline_markdown(source[cursor:match.start()]))
        chunks.append(_code_block_html(match.group(2).rstrip("\n"), match.group(1)))
        cursor = match.end()
    chunks.append(_inline_markdown(source[cursor:]))
    body = "".join(chunks)

    colour = EV["text"] if role == "assistant" else EV["text"]
    return (
        f'<div style="color:{colour}; font-size:9.5pt; line-height:150%;">'
        f"{body}</div>"
    )


def _inline_markdown(text: str) -> str:
    safe = html_lib.escape(text or "")
    safe = re.sub(
        r"`([^`\n]+)`",
        lambda m: (
            f'<span style="background-color:#0d141d; color:{EV["accent"]}; '
            f'border:1px solid rgba(255,255,255,0.08); padding:0 4px;">{m.group(1)}</span>'
        ),
        safe,
    )
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", safe)
    safe = re.sub(r"(?m)^### (.+)$", r'<h3 style="font-size:11pt; margin:12px 0 4px 0;">\1</h3>', safe)
    safe = re.sub(r"(?m)^## (.+)$", r'<h2 style="font-size:12pt; margin:14px 0 5px 0;">\1</h2>', safe)
    safe = re.sub(r"(?m)^# (.+)$", r'<h1 style="font-size:14pt; margin:14px 0 6px 0;">\1</h1>', safe)
    safe = re.sub(r"(?m)^\s*[-*] (.+)$", r'<div style="margin:2px 0;">&nbsp;&nbsp;&#8226;&nbsp;&nbsp;\1</div>', safe)
    safe = re.sub(r"(?m)^\s*(\d+)\. (.+)$", lambda m: f'<div style="margin:2px 0;">&nbsp;&nbsp;{m.group(1)}.&nbsp;&nbsp;{m.group(2)}</div>', safe)
    safe = re.sub(r"(?m)^&gt; (.+)$", r'<div style="margin:4px 0; color:#9fb0c0;">\1</div>', safe)
    safe = re.sub(r"https?://[^\s<]+", lambda m: f'<a href="{m.group(0)}" style="color:{EV["accent"]};">{m.group(0)}</a>', safe)
    safe = re.sub(r"\n{2,}", "<br><br>", safe)
    safe = safe.replace("\n", "<br>")
    return safe


class CopyableTextBrowser(QTextBrowser):
    """Read-only markdown surface that handles the inline Copy affordances."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._on_anchor)

    def _on_anchor(self, url: QUrl):
        href = url.toString()
        if href.startswith("evcopy:"):
            text = _decode_copy_href(href)
            if text:
                QApplication.clipboard().setText(text)
                self._flash_copy_state()
            return
        if href.startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(href))

    def _flash_copy_state(self):
        window = self.window()
        if hasattr(window, "_flash_toast"):
            try:
                window._flash_toast("Copied to clipboard")
            except Exception:
                pass


class AttachmentCard(QFrame):
    """Compact chip shown under a user message for attached files."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentCard")
        self.setStyleSheet(
            f"""
            QFrame#AttachmentCard {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-radius: 10px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(9)
        icon = QLabel("FILE")
        icon.setFixedSize(34, 20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(_UI_FONT, 6, QFont.Weight.Bold))
        icon.setStyleSheet(
            f"color: {EV['accent']}; background: {EV['accent_soft']}; "
            f"border: 1px solid {EV['accent_line']}; border-radius: 5px;"
        )
        lay.addWidget(icon)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {EV['text']}; font: 600 9pt '{_UI_FONT}';")
        text.addWidget(title_lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"color: {EV['text_dim']}; font: 8pt '{_UI_FONT}';")
            text.addWidget(sub)
        lay.addLayout(text, 1)


class EVCard(QFrame):
    """Base glass surface used across the dashboard and sidebars."""

    def __init__(self, object_name: str = "EVCard", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)


class ToolActivityCard(QFrame):
    """One tool/agent action rendered as a compact live activity card."""

    STATUS_COLOURS = {
        "pending": EV["text_dim"],
        "running": EV["accent"],
        "completed": EV["success"],
        "failed": EV["danger"],
        "cancelled": EV["warning"],
    }

    def __init__(self, tool: str, title: str, detail: str = "", status: str = "running", parent=None):
        super().__init__(parent)
        self._tool = (tool or "E.V.").strip() or "E.V."
        self._title = title or "Working"
        self._detail = detail or ""
        self._status = status
        self._spinner = 0
        self.setObjectName("ToolActivityCard")
        self.setStyleSheet(
            f"""
            QFrame#ToolActivityCard {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(10)

        self._badge = QLabel(self._tool[:1].upper())
        self._badge.setFixedSize(26, 26)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFont(QFont(_UI_FONT, 9, QFont.Weight.Bold))
        lay.addWidget(self._badge)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._tool_lbl = QLabel(self._tool.upper())
        self._tool_lbl.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        self._tool_lbl.setStyleSheet(f"color: {EV['text_faint']}; letter-spacing: 1px;")
        self._status_lbl = QLabel()
        self._status_lbl.setFont(QFont(_UI_FONT, 8, QFont.Weight.Bold))
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._elapsed_lbl = QLabel("")
        self._elapsed_lbl.setFont(QFont(_UI_FONT, 7))
        self._elapsed_lbl.setStyleSheet(f"color: {EV['text_faint']};")
        head.addWidget(self._tool_lbl)
        head.addStretch(1)
        head.addWidget(self._elapsed_lbl)
        head.addWidget(self._status_lbl)
        self._title_lbl = QLabel(self._title)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        self._title_lbl.setStyleSheet(f"color: {EV['text']};")
        body.addLayout(head)
        body.addWidget(self._title_lbl)

        self._detail_lbl = QLabel(self._detail)
        self._detail_lbl.setWordWrap(True)
        self._detail_lbl.setFont(QFont(_UI_FONT, 8))
        self._detail_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        self._detail_lbl.setVisible(bool(self._detail))
        body.addWidget(self._detail_lbl)
        lay.addLayout(body, 1)

        self._started = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_status()

    # -- public API ---------------------------------------------------------
    def set_status(self, status: str, detail: str | None = None, title: str | None = None):
        self._status = status
        if detail is not None and detail != self._detail:
            self._detail = detail
            self._detail_lbl.setText(detail)
            self._detail_lbl.setVisible(bool(detail))
        if title:
            self._title = title
            self._title_lbl.setText(title)
        self._apply_status()

    def finish(self, *, success: bool = True, detail: str | None = None, title: str | None = None):
        self.set_status("completed" if success else "failed", detail=detail, title=title)
        self._timer.stop()

    # -- internals ----------------------------------------------------------
    def _tick(self):
        if self._status != "running":
            return
        elapsed = time.monotonic() - self._started
        self._spinner = (self._spinner + 1) % 4
        self._elapsed_lbl.setText(f"{elapsed:.0f}s" if elapsed >= 1 else "")
        dots = "." * (self._spinner + 1)
        self._status_lbl.setText(f"Running{dots}")
        colour = self._accent_colour()
        self._status_lbl.setStyleSheet(f"color: {colour};")

    def _accent_colour(self) -> str:
        return self.STATUS_COLOURS.get(self._status, EV["accent"])

    def _apply_status(self):
        colour = self._accent_colour()
        glyphs = {
            "pending": "…",
            "running": "▶",
            "completed": "✓",
            "failed": "!",
            "cancelled": "—",
        }
        self._badge.setText(glyphs.get(self._status, "•"))
        self._badge.setStyleSheet(
            f"color: {colour}; background: rgba(255,255,255,0.03); "
            f"border: 1px solid {colour}; border-radius: 13px;"
        )
        labels = {
            "pending": "Queued",
            "running": "Running…",
            "completed": "Done",
            "failed": "Failed",
            "cancelled": "Cancelled",
        }
        self._status_lbl.setText(labels.get(self._status, self._status))
        self._status_lbl.setStyleSheet(f"color: {colour};")
        if self._status == "running":
            self._timer.start(1000)
        else:
            self._timer.stop()
            self._elapsed_lbl.setText("")


class StageFlow(QWidget):
    """Request → Planning → Executing → Verifying → Completed pipeline."""

    STAGES = ("Request", "Planning", "Executing", "Verifying", "Completed")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._index = 0
        self._failed = False
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def set_stage(self, index: int, *, failed: bool = False):
        self._index = max(0, min(len(self.STAGES) - 1, int(index)))
        self._failed = failed
        self.update()

    def reset(self):
        self._index = 0
        self._failed = False
        self.update()

    def _tick(self):
        if not self.isVisible():
            return
        self._pulse = (self._pulse + 0.06) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setFont(QFont(_UI_FONT, 7, QFont.Weight.DemiBold))
        count = len(self.STAGES)
        seg = W / count
        for i, stage in enumerate(self.STAGES):
            x = i * seg
            done = i < self._index
            active = i == self._index and not self._failed and self._index < count - 1
            failed = self._failed and i == self._index
            if failed:
                colour = QColor(EV["danger"])
            elif done:
                colour = QColor(EV["success"])
            elif active:
                alpha = int(150 + 105 * abs(math.sin(self._pulse * math.pi)))
                colour = QColor(EV["accent"])
                colour.setAlpha(alpha)
            elif i == count - 1 and self._index >= count - 1:
                colour = QColor(EV["success"])
            else:
                colour = QColor(EV["text_faint"])
            # node
            cx = x + 7
            cy = H / 2
            p.setPen(QPen(colour, 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - 3.4, cy - 3.4, 6.8, 6.8))
            if done or (i == count - 1 and self._index >= count - 1):
                p.setBrush(QBrush(colour))
                p.drawEllipse(QRectF(cx - 1.6, cy - 1.6, 3.2, 3.2))
            # label
            p.setPen(QPen(colour))
            p.drawText(QRectF(cx + 9, 0, seg - 14, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, stage)
            # connector
            if i < count - 1:
                line_colour = QColor(EV["success"] if done else EV["border_strong"])
                line_colour.setAlpha(190 if done else 90)
                p.setPen(QPen(line_colour, 1.2))
                p.drawLine(QPointF(cx + 5, cy), QPointF(x + seg - 4, cy))


class ErrorCard(QFrame):
    """Human-readable failure with Retry / Details affordances."""

    retry_requested = pyqtSignal()
    details_requested = pyqtSignal()

    def __init__(self, message: str, *, details: str = "", on_retry=None, parent=None):
        super().__init__(parent)
        self._details = details or ""
        self._details_visible = False
        self.setObjectName("ErrorCard")
        self.setStyleSheet(
            f"""
            QFrame#ErrorCard {{
                background: {EV['danger_soft']};
                border: 1px solid rgba(255, 95, 109, 0.36);
                border-radius: 12px;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 5px 10px;
                color: {EV['text']};
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.08);
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(9)
        glyph = QLabel("!")
        glyph.setFixedSize(22, 22)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFont(QFont(_UI_FONT, 9, QFont.Weight.Bold))
        glyph.setStyleSheet(
            f"color: {EV['danger']}; background: rgba(255,95,109,0.14); "
            f"border: 1px solid rgba(255,95,109,0.42); border-radius: 11px;"
        )
        head.addWidget(glyph)
        self._message_lbl = QLabel(message)
        self._message_lbl.setWordWrap(True)
        self._message_lbl.setFont(QFont(_UI_FONT, 9))
        self._message_lbl.setStyleSheet(f"color: {EV['text']};")
        head.addWidget(self._message_lbl, 1)
        lay.addLayout(head)

        self._detail_lbl = QLabel(self._details)
        self._detail_lbl.setWordWrap(True)
        self._detail_lbl.setFont(QFont(_MONO_FONT, 8))
        self._detail_lbl.setStyleSheet(
            f"color: {EV['text_dim']}; background: rgba(0,0,0,0.25); "
            f"border: 1px solid {EV['border']}; border-radius: 8px; padding: 8px;"
        )
        self._detail_lbl.setVisible(False)
        lay.addWidget(self._detail_lbl)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._details_btn = QPushButton("Details")
        self._details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.clicked.connect(self._on_retry)
        self._details_btn.clicked.connect(self._toggle_details)
        buttons.addWidget(self._retry_btn)
        buttons.addWidget(self._details_btn)
        buttons.addStretch(1)
        lay.addLayout(buttons)
        self._on_retry_cb = on_retry
        if not self._details:
            self._details_btn.setEnabled(False)

    def _on_retry(self):
        self.retry_requested.emit()
        if callable(self._on_retry_cb):
            try:
                self._on_retry_cb()
            except Exception:
                pass

    def _toggle_details(self):
        self._details_visible = not self._details_visible
        self._detail_lbl.setVisible(self._details_visible)
        self._details_btn.setText("Hide details" if self._details_visible else "Details")
        self.details_requested.emit()


class EventCard(QFrame):
    """Neutral system/result row inside the conversation feed."""

    def __init__(self, title: str, detail: str, stamp: str, icon: str = "•", accent: str = EV["accent"], parent=None):
        super().__init__(parent)
        self.setObjectName("EventCard")
        self.setStyleSheet(
            f"""
            QFrame#EventCard {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-left: 2px solid {accent};
                border-radius: 10px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)

        glyph = QLabel(icon[:1])
        glyph.setFixedSize(24, 24)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFont(QFont(_UI_FONT, 9, QFont.Weight.Bold))
        glyph.setStyleSheet(f"color: {accent}; background: rgba(255,255,255,0.03); border-radius: 12px;")
        lay.addWidget(glyph)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(_UI_FONT, 8, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {EV['text_med']}; letter-spacing: 0.6px;")
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont(_UI_FONT, 7))
        stamp_lbl.setStyleSheet(f"color: {EV['text_faint']};")
        head.addWidget(title_lbl)
        head.addStretch(1)
        head.addWidget(stamp_lbl)
        detail_lbl = QLabel(detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setFont(QFont(_UI_FONT, 9))
        detail_lbl.setStyleSheet(f"color: {EV['text']};")
        body.addLayout(head)
        body.addWidget(detail_lbl)
        lay.addLayout(body, 1)


class ArtifactCard(QFrame):
    """A generated or attached file with working Open / Show in folder."""

    def __init__(self, title: str, file_type: str = "File", status: str = "Ready", path: str = "", parent=None):
        super().__init__(parent)
        self._path = (path or "").strip()
        self.setObjectName("ArtifactCard")
        self.setStyleSheet(
            f"""
            QFrame#ArtifactCard {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-radius: 12px;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.04);
                color: {EV['text']};
                border: 1px solid {EV['border_strong']};
                border-radius: 8px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {EV['accent_soft']};
                border: 1px solid {EV['accent_line']};
            }}
            QPushButton:disabled {{
                color: {EV['text_faint']};
                border: 1px solid {EV['border']};
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(11)
        badge = QLabel((file_type or "FILE")[:4].upper())
        badge.setFixedSize(42, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        badge.setStyleSheet(
            f"background: {EV['accent_soft']}; color: {EV['accent']}; "
            f"border: 1px solid {EV['accent_line']}; border-radius: 9px;"
        )
        head.addWidget(badge)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        name_lbl = QLabel(Path(title).name or title or "Generated file")
        name_lbl.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {EV['text']};")
        type_lbl = QLabel(f"{status} • {file_type or 'File'}")
        type_lbl.setFont(QFont(_UI_FONT, 8))
        type_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        meta.addWidget(name_lbl)
        meta.addWidget(type_lbl)
        head.addLayout(meta, 1)
        lay.addLayout(head)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._open_btn = QPushButton("Open")
        self._reveal_btn = QPushButton("Show in folder")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reveal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._open_file)
        self._reveal_btn.clicked.connect(self._reveal_file)
        if not self._path or not Path(self._path).exists():
            self._open_btn.setEnabled(False)
            self._reveal_btn.setEnabled(False)
        buttons.addWidget(self._open_btn)
        buttons.addWidget(self._reveal_btn)
        buttons.addStretch(1)
        lay.addLayout(buttons)

    def _open_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            if _OS == "Windows":
                os.startfile(self._path)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))
        except Exception:
            pass

    def _reveal_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            if _OS == "Windows":
                subprocess.Popen(["explorer", "/select,", self._path])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._path).parent)))
        except Exception:
            pass


class ChatBubble(QFrame):
    """A single conversation message: user bubble or E.V. answer."""

    def __init__(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None,
                 parent=None, animate: bool = False):
        super().__init__(parent)
        self._role = (role or "assistant").lower()
        self._full_text = text or ""
        self._typing_index = 0
        self._typing_timer: QTimer | None = None
        self._animate = bool(animate) and self._role == "assistant"
        self.setObjectName("ChatBubble")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("QFrame#ChatBubble { background: transparent; border: none; }")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)

        avatar = QLabel("EV" if self._role == "assistant" else "YOU")
        avatar.setFixedSize(26, 22)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont(_UI_FONT, 6, QFont.Weight.Bold))
        if self._role == "assistant":
            avatar.setStyleSheet(
                f"background: {EV['accent_soft']}; color: {EV['accent']}; "
                f"border: 1px solid {EV['accent_line']}; border-radius: 8px;"
            )
        else:
            avatar.setStyleSheet(
                f"background: rgba(255,255,255,0.05); color: {EV['text_med']}; "
                f"border: 1px solid {EV['border']}; border-radius: 8px;"
            )

        self._body = QFrame()
        self._body.setObjectName("ChatBubbleBody")
        if self._role == "assistant":
            self._body.setStyleSheet("QFrame#ChatBubbleBody { background: transparent; border: none; }")
        else:
            self._body.setStyleSheet(
                f"QFrame#ChatBubbleBody {{ background: {EV['surface_low']}; "
                f"border: 1px solid {EV['border']}; border-radius: 12px; }}"
            )
        body = QVBoxLayout(self._body)
        body.setContentsMargins(12 if self._role != "assistant" else 2, 9 if self._role != "assistant" else 2, 12, 9)
        body.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        name_lbl = QLabel("E.V." if self._role == "assistant" else (name or "You"))
        name_lbl.setFont(QFont(_UI_FONT, 8, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {EV['text_med'] if self._role != 'assistant' else EV['accent']};")
        self._stamp_lbl = QLabel(stamp)
        self._stamp_lbl.setFont(QFont(_UI_FONT, 7))
        self._stamp_lbl.setStyleSheet(f"color: {EV['text_faint']};")
        top.addWidget(name_lbl)
        top.addStretch(1)
        top.addWidget(self._stamp_lbl)

        self._browser = CopyableTextBrowser()
        self._browser.setFrameShape(QFrame.Shape.NoFrame)
        self._browser.setReadOnly(True)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._browser.setStyleSheet("QTextBrowser { background: transparent; border: none; padding: 0; }")
        self._browser.document().setDocumentMargin(0)

        body.addLayout(top)
        body.addWidget(self._browser, 1)

        if attachments:
            for attachment in attachments:
                title = str(attachment.get("name") or attachment.get("title") or attachment.get("path") or "Attachment")
                path = str(attachment.get("path") or attachment.get("file") or "")
                body.addWidget(ArtifactCard(title, file_type=(Path(title).suffix.lstrip(".").upper() or "File"),
                                            status="Attached", path=path or title))

        if self._render_actions():
            body.addLayout(self._build_actions())

        if self._animate:
            self._render_text("")
            self._start_typing_animation()
        else:
            self._render_text(self._full_text)

        if self._role == "user":
            row.addStretch(1)
            row.addWidget(self._body, 0)
            row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        else:
            row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(self._body, 1)
        outer.addLayout(row)
        QTimer.singleShot(0, self._fit_to_content)

    # -- rendering ----------------------------------------------------------
    def _render_text(self, text: str):
        self._browser.setHtml(_markdown_to_html(text or "", self._role))
        QTimer.singleShot(0, self._fit_to_content)

    def _start_typing_animation(self):
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(16)
        self._typing_timer.timeout.connect(self._tick_typing)
        self._typing_timer.start()

    def _tick_typing(self):
        total = len(self._full_text)
        remaining = total - self._typing_index
        step = max(2, remaining // 8)
        self._typing_index = min(total, self._typing_index + step)
        self._render_text(self._full_text[:self._typing_index])
        if self._typing_index >= total:
            try:
                self._typing_timer.stop()
            except Exception:
                pass
            self._render_text(self._full_text)

    def _fit_to_content(self):
        """Size the message so nothing is cut off, measuring at the final width."""
        try:
            viewport = self.parentWidget()
            while viewport is not None and not hasattr(viewport, "viewport"):
                viewport = viewport.parentWidget()
            viewport_width = viewport.viewport().width() if viewport and hasattr(viewport, "viewport") else self.width()
            ratio = 0.94 if self._role == "assistant" else 0.66
            width = max(240, min(int(viewport_width * ratio), max(260, viewport_width - 120)))
            if self._browser.width() != width:
                self._browser.setFixedWidth(width)
            doc = self._browser.document()
            doc.setTextWidth(width)
            height = max(22, int(doc.size().height()) + 8)
            self._browser.setMinimumHeight(height)
            self._browser.setMaximumHeight(height)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_to_content()

    # -- message actions ----------------------------------------------------
    def _render_actions(self) -> bool:
        return self._role == "assistant" and bool(self._full_text)

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(10)
        style = f"QPushButton {{ background: transparent; border: none; color: {EV['text_faint']}; font-size: 8pt; padding: 2px 0; }} QPushButton:hover {{ color: {EV['accent']}; }}"
        copy_btn = QPushButton("Copy reply")
        copy_btn.setStyleSheet(style)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_message)
        row.addWidget(copy_btn)
        row.addStretch(1)
        return row

    def _copy_message(self):
        QApplication.clipboard().setText(self._full_text)
        window = self.window()
        if hasattr(window, "_flash_toast"):
            try:
                window._flash_toast("Copied to clipboard")
            except Exception:
                pass


class TypingIndicator(QFrame):
    """Shown while E.V. is thinking or running tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots = 0
        self._label = "Thinking"
        self.setObjectName("TypingIndicator")
        self.setStyleSheet(f"QFrame#TypingIndicator {{ background: transparent; border: none; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(9)
        badge = QLabel("EV")
        badge.setFixedSize(26, 22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont(_UI_FONT, 6, QFont.Weight.Bold))
        badge.setStyleSheet(
            f"background: {EV['accent_soft']}; color: {EV['accent']}; "
            f"border: 1px solid {EV['accent_line']}; border-radius: 8px;"
        )
        lay.addWidget(badge)
        self._lbl = QLabel("Thinking")
        self._lbl.setFont(QFont(_UI_FONT, 9))
        self._lbl.setStyleSheet(f"color: {EV['text_dim']};")
        lay.addWidget(self._lbl)
        lay.addStretch(1)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(420)

    def set_label(self, text: str):
        self._label = text or "Thinking"
        self._lbl.setText(self._label + "." * (self._dots + 1))

    def _tick(self):
        self._dots = (self._dots + 1) % 3
        self._lbl.setText(self._label + "." * (self._dots + 1))


class HistoryConversationItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, conversation_id: str, title: str, stamp: str, pinned: bool = False, parent=None):
        super().__init__(parent)
        self._conversation_id = conversation_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("HistoryConversationItem")
        self.setStyleSheet(
            """
            QFrame#HistoryConversationItem {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(92, 211, 255,0.18);
                border-radius: 10px;
            }
            QFrame#HistoryConversationItem:hover {
                background: rgba(92, 211, 255,0.07);
                border: 1px solid rgba(92, 211, 255,0.32);
            }
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        icon = QLabel("B")
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: rgba(92, 211, 255,0.10); color: #7cdcff; border: 1px solid rgba(92, 211, 255,0.28); border-radius: 15px; font: 700 11pt 'Segoe UI';")
        lay.addWidget(icon)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        title_lbl = QLabel(title or "Conversation")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        row.addWidget(title_lbl)
        if pinned:
            pin = QLabel("PIN")
            pin.setStyleSheet("color: #3ddc97; background: transparent; font: 700 7pt 'Courier New';")
            row.addWidget(pin)
        row.addStretch()
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont("Segoe UI", 7))
        stamp_lbl.setStyleSheet("color: rgba(255,255,255,0.50); background: transparent;")
        row.addWidget(stamp_lbl)
        meta.addLayout(row)
        lay.addLayout(meta, 1)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._conversation_id)


class ConversationFeed(QScrollArea):
    """Scrollable conversation transcript with an inviting empty state."""

    suggestion_chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 4, 2)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)
        self._empty_widget: QWidget | None = None
        self._message_count = 0
        self._typing: TypingIndicator | None = None

    # -- empty state --------------------------------------------------------
    def _ensure_empty_widget(self) -> QWidget:
        if self._empty_widget is not None:
            return self._empty_widget
        frame = QFrame()
        frame.setObjectName("FeedEmptyState")
        frame.setStyleSheet(
            f"""
            QFrame#FeedEmptyState {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-radius: 14px;
            }}
            QPushButton {{
                background: rgba(255, 255, 255, 0.03);
                color: {EV['text_med']};
                border: 1px solid {EV['border']};
                border-radius: 9px;
                padding: 8px 11px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {EV['accent_soft']};
                border: 1px solid {EV['accent_line']};
                color: {EV['text']};
            }}
            """
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 13, 14, 13)
        lay.setSpacing(9)
        title = QLabel("How can I help?")
        title.setFont(QFont(_UI_FONT, 10, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {EV['text']};")
        subtitle = QLabel("Type or speak naturally — E.V. will plan the work and use the right tools.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {EV['text_dim']}; font-size: 8.5pt;")
        lay.addWidget(title)
        lay.addWidget(subtitle)
        grid = QGridLayout()
        grid.setSpacing(7)
        for index, suggestion in enumerate([
            "Summarise screen",
            "Create report",
            "Search the web",
            "Organise downloads",
        ]):
            btn = QPushButton(suggestion)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(0)
            btn.setToolTip(suggestion)
            btn.clicked.connect(lambda _=False, s=suggestion: self.suggestion_chosen.emit(s))
            grid.addWidget(btn, index // 2, index % 2)
        lay.addLayout(grid)
        self._empty_widget = frame
        return frame

    # -- transcript ---------------------------------------------------------
    def clear_messages(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._empty_widget:
                widget.deleteLater()
        self._typing = None
        if self._empty_widget is not None:
            self._empty_widget.hide()
        self._layout.addStretch(1)
        self._message_count = 0
        self._sync_empty_state()

    def add_message(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None,
                    animate: bool = False, event_type: str | None = None):
        self._remove_typing()
        self._remove_stretch()
        role = (role or "").strip().lower()
        if role == "system":
            widget = self._build_event_card(text, stamp, event_type=event_type)
        elif role == "error":
            widget = self._build_error_card(text)
        elif role == "file":
            widget = self._build_artifact_card(text, attachments=attachments, stamp=stamp)
        else:
            widget = ChatBubble(role, name, text, stamp, attachments=attachments, parent=self, animate=animate)
        self._layout.addWidget(widget)
        self._layout.addStretch(1)
        self._message_count += 1
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def add_error(self, message: str, details: str = "", retry=None):
        self._remove_typing()
        self._remove_stretch()
        card = ErrorCard(humanize_error(message), details=error_details(details or message), on_retry=retry)
        self._layout.addWidget(card)
        self._layout.addStretch(1)
        self._message_count += 1
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)
        return card

    def show_typing(self, label: str = "Thinking"):
        if self._typing is not None:
            self._typing.set_label(label)
            return
        self._remove_stretch()
        self._typing = TypingIndicator()
        self._typing.set_label(label)
        self._layout.addWidget(self._typing)
        self._layout.addStretch(1)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def hide_typing(self):
        self._remove_typing()

    def _remove_typing(self):
        if self._typing is None:
            return
        self._layout.removeWidget(self._typing)
        self._typing.deleteLater()
        self._typing = None

    def _remove_stretch(self):
        if self._layout.count() and self._layout.itemAt(self._layout.count() - 1).spacerItem() is not None:
            self._layout.takeAt(self._layout.count() - 1)

    def _build_event_card(self, text: str, stamp: str, event_type: str | None = None) -> QWidget:
        low = (event_type or text or "").lower()
        title, icon, accent = "UPDATE", "•", EV["accent"]
        if "discord" in low and "connect" in low:
            title, icon, accent = "DISCORD CONNECTED", "◉", "#5865F2"
        elif "presentation" in low:
            title, icon, accent = "PRESENTATION READY", "▣", EV["warning"]
        elif "website" in low:
            title, icon, accent = "WEBSITE READY", "⌂", EV["success"]
        elif "spreadsheet" in low:
            title, icon, accent = "SPREADSHEET READY", "▦", EV["accent"]
        elif "document" in low or "pdf" in low:
            title, icon, accent = "DOCUMENT READY", "▤", EV["accent"]
        elif "browser" in low:
            title, icon, accent = "BROWSER", "↗", EV["accent"]
        elif "organ" in low and "file" in low:
            title, icon, accent = "FILES", "🗂", EV["success"]
        elif "screen" in low:
            title, icon, accent = "SCREEN", "◫", EV["accent"]
        elif "memory" in low:
            title, icon, accent = "MEMORY", "◆", EV["violet"]
        elif "error" in low or "failed" in low:
            title, icon, accent = "PROBLEM", "!", EV["danger"]
        return EventCard(title, text, stamp, icon=icon, accent=accent, parent=self)

    def _build_error_card(self, text: str) -> QWidget:
        return ErrorCard(humanize_error(text), details=error_details(text))

    def _build_artifact_card(self, text: str, attachments: list[dict] | None = None, stamp: str = "") -> QWidget:
        attachment = (attachments or [{}])[0] if attachments else {}
        path = str(attachment.get("path") or attachment.get("file") or attachment.get("name") or "").strip()
        title = str(attachment.get("name") or attachment.get("title") or Path(path).name or text or "Generated file").strip()
        suffix = Path(path or title).suffix.lstrip(".").upper() or (str(attachment.get("type") or "FILE")).upper()
        return ArtifactCard(title, file_type=suffix, status="Created", path=path or title, parent=self)

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def load_messages(self, messages: list[dict[str, Any]]):
        self.clear_messages()
        for msg in messages:
            role = (msg.get("role") or "assistant").strip().lower()
            content = msg.get("content") or ""
            stamp = _fmt_time_stamp(msg.get("timestamp"))
            attachments = msg.get("attachments") or []
            name = {"user": "You", "assistant": "E.V.", "system": "E.V.", "file": "Files", "error": "E.V."}.get(role, "E.V.")
            self.add_message(role, name, content, stamp, attachments=attachments, animate=False)
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _sync_empty_state(self):
        widget = self._ensure_empty_widget()
        if self._message_count <= 0:
            if self._layout.indexOf(widget) == -1:
                self._layout.insertWidget(0, widget)
            widget.show()
        else:
            if self._layout.indexOf(widget) != -1:
                self._layout.removeWidget(widget)
            widget.hide()

    def has_messages(self) -> bool:
        return self._message_count > 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for i in range(self._layout.count()):
            widget = self._layout.itemAt(i).widget()
            if hasattr(widget, "_fit_to_content"):
                widget._fit_to_content()
        QTimer.singleShot(0, self.scroll_to_bottom)


class ActivityFeed(QScrollArea):
    """Running log of tool activity cards for the Activity tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 4, 2)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setWidget(self._content)
        self._cards: list[ToolActivityCard] = []
        self._empty = QLabel("No activity yet. E.V.'s tool runs will appear here.")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(f"color: {EV['text_dim']}; padding: 10px 2px;")
        self._layout.insertWidget(0, self._empty)

    def add_activity(self, tool: str, title: str, detail: str = "") -> ToolActivityCard:
        self._empty.setVisible(False)
        card = ToolActivityCard(tool, title, detail)
        self._cards.append(card)
        while len(self._cards) > 60:
            old = self._cards.pop(0)
            self._layout.removeWidget(old)
            old.deleteLater()
        self._layout.insertWidget(self._layout.count() - 1, card)
        QTimer.singleShot(0, self._scroll_bottom)
        return card

    def update_last(self, *, detail: str = "", title: str = ""):
        card = self._last_running()
        if card:
            card.set_status("running", detail=detail or None, title=title or None)

    def finish_last(self, *, success: bool = True, detail: str = "", title: str = ""):
        card = self._last_running()
        if card:
            card.finish(success=success, detail=detail or None, title=title or None)

    def _last_running(self) -> ToolActivityCard | None:
        for card in reversed(self._cards):
            if card._status in ("running", "pending"):
                return card
        return self._cards[-1] if self._cards else None

    def clear(self):
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards = []
        self._empty.setVisible(True)

    def _scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class TaskDock(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskDock")
        self._collapsed = False
        self._expanded_w = 392
        self._collapsed_w = 44
        self.setFixedWidth(self._expanded_w)
        self.setStyleSheet(
            f"""
            QFrame#TaskDock {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(7, 8, 12, 250),
                    stop:1 rgba(3, 4, 6, 245));
                border-left: 1px solid rgba(92, 211, 255, 0.55);
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel("TASK WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()

        self._toggle_btn = QPushButton(">")
        self._toggle_btn.setFixedSize(34, 34)
        self._toggle_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(12,14,18,245); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
        )
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._toggle_btn)
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.PRI_GHO}; margin: 2px 0;")
        root.addWidget(sep)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._mini_hint = QLabel("TASK")
        self._mini_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mini_hint.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._mini_hint.setStyleSheet(
            f"color: {C.PRI}; background: rgba(12,14,18,245); border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 10px 4px;"
        )
        self._mini_hint.setVisible(False)
        lay.addWidget(self._mini_hint)

        root.addWidget(self._content, stretch=1)
        self._apply_state()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        self._apply_state()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._content.setVisible(not self._collapsed)
        self._mini_hint.setVisible(self._collapsed)
        self._toggle_btn.setText(">" if self._collapsed else "<")
        self._toggle_btn.setToolTip("Open task workspace" if self._collapsed else "Collapse task workspace")
        self._title.setVisible(not self._collapsed)
        self.setFixedWidth(self._collapsed_w if self._collapsed else self._expanded_w)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._task_card.start_workspace(command, plan, source)
        if self._collapsed:
            return

    def update_workspace(self, **kwargs):
        self._task_card.update_workspace(**kwargs)

    def finish_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._task_card.finish_workspace(result, status, percent)

    def clear_workspace(self):
        self._task_card.clear_workspace()


class WorkspaceSidebar(QWidget):
    command_submitted = pyqtSignal(str)
    close_requested = pyqtSignal()
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._collapsed = True
        self._expanded_w = 468
        self._target_h = 860
        self._active_conversation_id: str | None = None
        self._store = workspace_store()
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._panel = QFrame(self)
        self._panel.setObjectName("WorkspaceSidebarPanel")
        self._panel.setStyleSheet(
            """
            QFrame#WorkspaceSidebarPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                stop:0.55 rgba(10, 12, 18, 210),
                stop:1 rgba(5, 7, 11, 200));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 22px;
            }
            """
        )
        try:
            shadow = QGraphicsDropShadowEffect(self._panel)
            shadow.setBlurRadius(35)
            shadow.setColor(QColor(0, 0, 0, 72))
            shadow.setOffset(0, 12)
            self._panel.setGraphicsEffect(shadow)
        except Exception:
            pass
        root = QHBoxLayout(self._panel)
        root.setContentsMargins(14, 14, 12, 14)
        root.setSpacing(10)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content = QVBoxLayout(self._content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._title = QLabel("CHAT + TASK WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()
        self._close_btn = QPushButton("E.V.")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedHeight(30)
        self._close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(15,15,20,220);
                color: #FFFFFF;
                border: 1px solid rgba(92, 211, 255,120);
                border-radius: 10px;
                padding: 0 12px;
            }
            QPushButton:hover {
                border: 1px solid rgba(92, 211, 255,200);
            }
            """
        )
        self._close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self._close_btn)
        content.addLayout(header)

        self._tab_row = QHBoxLayout()
        self._tab_row.setSpacing(8)
        self._chat_tab_btn = self._make_tab_button("CHAT", True)
        self._history_tab_btn = self._make_tab_button("HISTORY", False)
        self._chat_tab_btn.clicked.connect(lambda: self._set_tab(0))
        self._history_tab_btn.clicked.connect(lambda: self._set_tab(1))
        self._tab_row.addWidget(self._chat_tab_btn)
        self._tab_row.addWidget(self._history_tab_btn)
        self._tab_row.addStretch(1)
        content.addLayout(self._tab_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_history_tab())
        content.addWidget(self._stack, 1)

        root.addWidget(self._content, stretch=1)

        self._panel.hide()
        self.hide()
        self._set_tab(0)
        self._ensure_active_conversation()
        self._load_active_conversation()
        self._refresh_history()
        self._apply_state()

    def _make_tab_button(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setStyleSheet(self._tab_style(active))
        return btn

    def _tab_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: rgba(92, 211, 255,0.16);
                    color: #FFFFFF;
                    border: 1px solid rgba(92, 211, 255,180);
                    border-radius: 10px;
                    padding: 0 14px;
                }
            """
        return """
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.82);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(92, 211, 255,0.08);
                border: 1px solid rgba(92, 211, 255,120);
            }
        """

    def _set_tab(self, index: int):
        index = 0 if index == 0 else 1
        self._stack.setCurrentIndex(index)
        self._chat_tab_btn.setStyleSheet(self._tab_style(index == 0))
        self._history_tab_btn.setStyleSheet(self._tab_style(index == 1))
        self._chat_tab_btn.setChecked(index == 0)
        self._history_tab_btn.setChecked(index == 1)
        if index == 1:
            self._history_search.setFocus(Qt.FocusReason.TabFocusReason)

    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(92, 211, 255,0.05);
                border: 1px solid rgba(92, 211, 255,0.24);
                border-radius: 12px;
            }
            """
        )
        mem_lay = QVBoxLayout(self._memory_frame)
        mem_lay.setContentsMargins(12, 10, 12, 10)
        mem_lay.setSpacing(6)
        mem_title = QLabel("Using Memory:")
        mem_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        mem_title.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._memory_items = QLabel("")
        self._memory_items.setWordWrap(True)
        self._memory_items.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        mem_lay.addWidget(mem_title)
        mem_lay.addWidget(self._memory_items)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        lay.addWidget(self._feed, 1)

        # Keep an internal input stub for signal safety, but do not render a command bar here.
        self._input = QLineEdit(self)
        self._input.hide()

        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._history_search = QLineEdit()
        self._history_search.setPlaceholderText("Search conversations...")
        self._history_search.setFont(QFont("Segoe UI", 10))
        self._history_search.setFixedHeight(38)
        self._history_search.setStyleSheet(
            """
            QLineEdit {
                background: rgba(10,11,14,205);
                color: #FFFFFF;
                border: 1px solid rgba(92, 211, 255,100);
                border-radius: 12px;
                padding: 0 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(92, 211, 255,190);
            }
            """
        )
        self._history_search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._history_search)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(92, 211, 255,0.45);
                border-radius: 4px;
                min-height: 24px;
            }
            """
        )
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    def _ensure_active_conversation(self, first_message: str | None = None) -> str:
        convo_id = self._active_conversation_id
        if convo_id:
            convo = self._store.get_conversation(convo_id)
            if convo:
                return convo_id
        convo_id = self._store.ensure_active_conversation(first_message or "")
        self._active_conversation_id = convo_id
        return convo_id

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.58); background: transparent; letter-spacing: 1px;")
        return lbl

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._history_search.text().strip() if hasattr(self, "_history_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        current = self._active_conversation_id
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet("color: rgba(255,255,255,0.60); background: transparent;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                widget = HistoryConversationItem(
                    item["id"],
                    item["title"],
                    _fmt_time_stamp(item["updatedAt"]),
                    pinned=bool(item["pinned"]),
                )
                if item["id"] == current:
                    widget.setStyleSheet(
                        """
                        QFrame#HistoryConversationItem {
                            background: rgba(92, 211, 255,0.10);
                            border: 1px solid rgba(92, 211, 255,0.55);
                            border-radius: 10px;
                        }
                        QFrame#HistoryConversationItem:hover {
                            background: rgba(92, 211, 255,0.14);
                            border: 1px solid rgba(92, 211, 255,0.70);
                        }
                        """
                    )
                widget.clicked.connect(self._load_conversation)
                self._history_layout.addWidget(widget)
            self._history_layout.addSpacing(4)
        self._history_layout.addStretch(1)

    def _show_memory_banner(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_items.setText("")
            self._memory_frame.hide()
            return
        self._memory_items.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memory_banner(self):
        self._memory_items.setText("")
        self._memory_frame.hide()

    def _load_active_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])
            self._active_conversation_id = convo_id
            self._hide_memory_banner()

    def _load_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _new_conversation(self):
        self._active_conversation_id = self._store.create_conversation("New Conversation")
        self._feed.clear_messages()
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _clear_current_conversation(self):
        self._new_conversation()

    def _rename_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        current = (convo or {}).get("title") or "Conversation"
        title, ok = QInputDialog.getText(self, "Rename Conversation", "Conversation title:", text=current)
        if ok and title.strip():
            self._store.rename_conversation(convo_id, title.strip())
            self._refresh_history()

    def _export_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        title = (convo or {}).get("title") or "conversation"
        default = str(BASE_DIR / "downloads" / f"{title}.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export Conversation", default, "JSON Files (*.json)")
        if not path:
            return
        try:
            self._store.export_conversation(convo_id, path)
        except Exception:
            pass

    def _pin_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        pinned = not bool((convo or {}).get("pinned"))
        self._store.pin_conversation(convo_id, pinned)
        self._refresh_history()

    def _delete_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        self._store.delete_conversation(convo_id)
        self._active_conversation_id = None
        self._new_conversation()

    def show_at(self):
        self.show_workspace(animate=False)

    def reposition(self):
        if not self.isVisible():
            return
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self._expanded_w + 1
        y = screen.top() + 18
        h = max(640, screen.height() - 36)
        self.setGeometry(x, y, self._expanded_w, h)
        self._target_h = h
        self._panel.setGeometry(0, 0, self._expanded_w, h)

    def _dock_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() - w + 1
        return QRectF(x, y, w, h)

    def _collapsed_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() + 8
        return QRectF(x, y, w, h)

    def show_workspace(self, animate: bool = True):
        self._collapsed = False
        self._panel.show()
        self._content.show()
        dock = self._dock_rect()
        start = self._collapsed_rect() if animate else dock
        self.setGeometry(start.toRect())
        self.show()
        self.raise_()
        self.activateWindow()
        self._apply_state()
        if animate:
            self._anim.stop()
            self._anim.setStartValue(start.toRect())
            self._anim.setEndValue(dock.toRect())
            self._anim.start()
        else:
            self.setGeometry(dock.toRect())
        self._panel.setGeometry(0, 0, self.width(), self.height())

    def hide_workspace(self, animate: bool = True):
        self._collapsed = True
        if not self.isVisible():
            self._panel.hide()
            self.hide()
            return
        if animate:
            dock = self.geometry()
            end = self._collapsed_rect()
            self._anim.stop()
            self._anim.setStartValue(dock)
            self._anim.setEndValue(end.toRect())
            self._anim.finished.connect(self._hide_after_anim)
            self._anim.start()
        else:
            self._hide_after_anim()

    def _hide_after_anim(self):
        try:
            self._anim.finished.disconnect(self._hide_after_anim)
        except Exception:
            pass
        self._panel.hide()
        self.hide()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        if bool(collapsed):
            self.hide_workspace(animate=True)
        else:
            self.show_workspace(animate=True)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._panel.setVisible(not self._collapsed)
        self._content.setVisible(not self._collapsed)
        if self.isVisible() and not self._collapsed:
            self.reposition()

    def append_log(self, text: str):
        line = parse_log_line(text)
        if line["kind"] in ("empty", "you", "ev", "ev ai", "assistant"):
            return
        if line["kind"] in ("sys", "system", "warn", "module"):
            self.record_chat_event({"role": "system", "text": line["body"], "source": "local"})

    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text:
            return
        attachments = data.get("attachments") or []
        stamp = data.get("timestamp")
        convo_id = data.get("conversation_id") or self._active_conversation_id
        if role == "user":
            convo_id = self._store.record_chat("user", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("user", "You", text, _fmt_time_stamp(stamp), attachments=attachments)
            memories = self._store.search_memories(text)
            self._show_memory_banner(memories)
        elif role == "assistant":
            convo_id = self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("assistant", "E.V.", text, _fmt_time_stamp(stamp), attachments=attachments, animate=True)
            self._hide_memory_banner()
        elif role == "system":
            convo_id = self._store.record_chat("system", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("system", "System", text, _fmt_time_stamp(stamp), attachments=attachments, event_type=text)
        elif role == "file":
            convo_id = self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._active_conversation_id = convo_id
            self._feed.add_message("file", "Files", text, _fmt_time_stamp(stamp), attachments=attachments)
        self._refresh_history()

    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            command = data.get("command") or ""
            plan = data.get("plan") or []
            plan_text = plan if isinstance(plan, str) else "\n".join(f"• {item}" for item in plan) if plan else ""
            self._task_card.show()
            self._task_card.start_workspace(command, plan, data.get("source") or "local")
            # Intentionally do not post a 'Task started' system message to the activity feed
            # because the workspace UI already shows the task status.
        elif action == "update":
            self._task_card.show()
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            chunks = [data.get("status") or "", data.get("output") or "", data.get("footer") or ""]
            text = "\n".join(chunk for chunk in chunks if chunk)
            if text:
                self.record_chat_event({"role": "system", "text": text, "source": data.get("source") or "local"})
        elif action == "finish":
            self._task_card.show()
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or "Task completed.",
                int(data.get("percent") or 100),
            )
            self.record_chat_event({
                "role": "system",
                "text": data.get("result") or data.get("output") or "Done.",
                "source": data.get("source") or "local",
            })
        elif action == "clear":
            self._task_card.clear_workspace()

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._ensure_active_conversation(text)
        self.command_submitted.emit(text)


class InlineChatWorkspace(QFrame):
    """Right-hand E.V. panel: conversation, live activity and history."""

    command_submitted = pyqtSignal(str)
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InlineChatWorkspace")
        self._store = workspace_store()
        self._active_conversation_id: str | None = None
        self.setStyleSheet("QFrame#InlineChatWorkspace { background: transparent; border: none; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Conversation")
        title.setFont(QFont(_UI_FONT, 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {EV['text']};")
        self._context_lbl = QLabel("Ready when you are.")
        self._context_lbl.setFont(QFont(_UI_FONT, 8))
        self._context_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        header.addWidget(title)
        header.addWidget(self._context_lbl)
        root.addLayout(header)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self._chat_btn = self._mk_tab("Chat", 0)
        self._activity_btn = self._mk_tab("Activity", 1)
        self._history_btn = self._mk_tab("History", 2)
        tabs.addWidget(self._chat_btn)
        tabs.addWidget(self._activity_btn)
        tabs.addWidget(self._history_btn)
        tabs.addStretch(1)
        root.addLayout(tabs)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_activity_tab())
        self._stack.addWidget(self._build_history_tab())
        root.addWidget(self._stack, 1)

        composer = QHBoxLayout()
        composer.setSpacing(8)
        self._quick_attach_btn = QPushButton("Attach")
        self._quick_attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quick_attach_btn.setToolTip("Attach a file for E.V. to work with")
        self._quick_attach_btn.clicked.connect(self.attach_requested.emit)
        self._quick_mic_btn = QPushButton("Voice")
        self._quick_mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quick_mic_btn.setToolTip("Toggle the microphone")
        self._quick_mic_btn.clicked.connect(self.mic_requested.emit)
        composer_style = (
            f"QPushButton {{ background: rgba(255,255,255,0.04); border: 1px solid {EV['border']}; "
            f"border-radius: 9px; padding: 5px 12px; color: {EV['text_med']}; font-size: 8pt; }}"
            f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
        )
        self._quick_attach_btn.setStyleSheet(composer_style)
        self._quick_mic_btn.setStyleSheet(composer_style)
        composer.addWidget(self._quick_attach_btn)
        composer.addWidget(self._quick_mic_btn)
        composer.addStretch(1)
        root.addLayout(composer)

        self._set_tab(0)
        self._ensure_conversation()
        self._load_active_conversation()
        self._refresh_history()

    # -- tabs ---------------------------------------------------------------
    def _mk_tab(self, text: str, index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.setFont(QFont(_UI_FONT, 8, QFont.Weight.DemiBold))
        btn.clicked.connect(lambda: self._set_tab(index))
        return btn

    def _tab_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {EV['accent_soft']}; color: {EV['text']}; "
                f"border: 1px solid {EV['accent_line']}; border-radius: 9px; padding: 0 14px; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {EV['text_dim']}; "
            f"border: 1px solid {EV['border']}; border-radius: 9px; padding: 0 14px; }}"
            f"QPushButton:hover {{ color: {EV['text']}; border: 1px solid {EV['border_strong']}; }}"
        )

    def _set_tab(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate((self._chat_btn, self._activity_btn, self._history_btn)):
            btn.setChecked(i == index)
            btn.setStyleSheet(self._tab_style(i == index))
        if index == 2:
            self._refresh_history()

    # -- tabs: chat ---------------------------------------------------------
    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet(
            f"QFrame {{ background: {EV['surface_low']}; border: 1px solid {EV['border']}; border-radius: 12px; }}"
        )
        mlay = QVBoxLayout(self._memory_frame)
        mlay.setContentsMargins(12, 10, 12, 10)
        mlay.setSpacing(5)
        memory_title = QLabel("REMEMBERED")
        memory_title.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        memory_title.setStyleSheet(f"color: {EV['text_faint']}; letter-spacing: 1.2px;")
        self._memory_lbl = QLabel("")
        self._memory_lbl.setWordWrap(True)
        self._memory_lbl.setStyleSheet(f"color: {EV['text_med']}; font-size: 8.5pt;")
        mlay.addWidget(memory_title)
        mlay.addWidget(self._memory_lbl)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        self._feed.suggestion_chosen.connect(self.command_submitted.emit)
        lay.addWidget(self._feed, 1)
        return page

    # -- tabs: activity -----------------------------------------------------
    def _build_activity_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)
        self._activity_stage = StageFlow()
        lay.addWidget(self._activity_stage)
        self._activity_feed = ActivityFeed()
        lay.addWidget(self._activity_feed, 1)
        return page

    # -- tabs: history ------------------------------------------------------
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations…")
        self._search.setFont(QFont(_UI_FONT, 9))
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._search)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        new_btn = QPushButton("New")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._new_conversation)
        rename_btn = QPushButton("Rename")
        rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rename_btn.clicked.connect(self._rename_current_conversation)
        controls.addWidget(new_btn)
        controls.addWidget(rename_btn)
        controls.addStretch(1)
        lay.addLayout(controls)

        for btn in (new_btn, rename_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.03); border: 1px solid {EV['border']}; "
                f"border-radius: 8px; padding: 5px 10px; color: {EV['text_med']}; font-size: 8pt; }}"
                f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
            )

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 4, 0)
        self._history_layout.setSpacing(8)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    # -- conversation plumbing ---------------------------------------------
    def _ensure_conversation(self, first_message: str | None = None):
        if self._active_conversation_id:
            convo = self._store.get_conversation(self._active_conversation_id)
            if convo:
                return self._active_conversation_id
        self._active_conversation_id = self._store.ensure_active_conversation(first_message or "")
        return self._active_conversation_id

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._search.text().strip() if hasattr(self, "_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet(f"color: {EV['text_dim']}; padding: 8px 2px;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                card = HistoryConversationItem(
                    item["id"], item["title"], _fmt_time_stamp(item["updatedAt"]), pinned=bool(item["pinned"])
                )
                card.clicked.connect(self._open_conversation)
                self._history_layout.addWidget(card)
        self._history_layout.addStretch(1)

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(str(title).upper())
        lbl.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {EV['text_faint']}; letter-spacing: 1.2px; padding-top: 4px;")
        return lbl

    def _show_memories(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_lbl.setText("")
            self._memory_frame.hide()
            return
        self._memory_lbl.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memories(self):
        self._memory_lbl.setText("")
        self._memory_frame.hide()

    def _open_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memories()
        self._refresh_history()
        self._set_tab(0)

    def _load_active_conversation(self):
        convo_id = self._ensure_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])

    def _new_conversation(self):
        self._active_conversation_id = self._store.create_conversation("New conversation")
        self._store.set_active_conversation_id(self._active_conversation_id)
        self._feed.clear_messages()
        self._hide_memories()
        self._refresh_history()
        self._set_tab(0)

    def _rename_current_conversation(self):
        convo_id = self._ensure_conversation()
        convo = self._store.get_conversation(convo_id) or {}
        current = convo.get("title") or "Conversation"
        title, ok = QInputDialog.getText(self, "Rename conversation", "Title:", text=current)
        if ok and title.strip():
            self._store.rename_conversation(convo_id, title.strip())
            self._refresh_history()

    def set_context(self, text: str):
        self._context_lbl.setText(text or "Ready when you are.")

    def show_typing(self, label: str = "Thinking"):
        self._feed.show_typing(label)

    def hide_typing(self):
        self._feed.hide_typing()

    # -- incoming events ----------------------------------------------------
    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text or role == "thinking":
            if role == "thinking":
                self.show_typing(text or "Thinking")
            return
        convo_id = data.get("conversation_id") or self._ensure_conversation(text if role == "user" else None)
        attachments = data.get("attachments") or []
        stamp = _fmt_time_stamp(data.get("timestamp"))
        if role == "user":
            self.hide_typing()
            self._store.record_chat("user", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("user", "You", text, stamp, attachments=attachments)
            self._show_memories(self._store.search_memories(text))
        elif role == "assistant":
            self.hide_typing()
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("assistant", "E.V.", text, stamp, attachments=attachments, animate=True)
            self._hide_memories()
        elif role == "error":
            self.hide_typing()
            self._store.record_chat("system", text, conversation_id=convo_id)
            self._feed.add_message("error", "E.V.", text, stamp)
        elif role == "system":
            self._store.record_chat("system", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("system", "E.V.", text, stamp, attachments=attachments)
        elif role == "file":
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("file", "Files", text, stamp, attachments=attachments)
        self._refresh_history()

    def append_log(self, text: str):
        line = parse_log_line(text)
        if line["kind"] in ("sys", "system", "warn", "module"):
            self.record_chat_event({"role": "system", "text": line["body"]})

    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            self._activity_feed.clear()
            self._activity_stage.reset()
            self._activity_stage.set_stage(1)
            self._task_card.start_workspace(
                data.get("command") or "",
                data.get("plan") or [],
                data.get("source") or "local",
            )
            self._task_card.add_activity("E.V.", "Planning the request", "Choosing the right tools.")
        elif action == "update":
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            stage = data.get("stage")
            if stage is not None:
                self._activity_stage.set_stage(int(stage))
        elif action == "activity":
            phase = (data.get("phase") or "start").lower()
            tool = data.get("tool") or "E.V."
            title = data.get("title") or "Working"
            detail = data.get("detail") or ""
            if phase == "start":
                self._task_card.add_activity(tool, title, detail)
                self._activity_feed.add_activity(tool, title, detail)
                self._activity_stage.set_stage(2)
            elif phase == "update":
                self._task_card.update_activity(detail=detail, title=title)
                self._activity_feed.update_last(detail=detail, title=title)
            else:
                success = bool(data.get("success", True))
                self._task_card.finish_activity(success=success, detail=detail, title=title)
                self._activity_feed.finish_last(success=success, detail=detail, title=title)
        elif action == "finish":
            success = bool(data.get("success", True))
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or ("Completed" if success else "Failed"),
                int(data.get("percent") or 100),
                success=success,
            )
            self._activity_stage.set_stage(4 if success else 2, failed=not success)
            if not success:
                self._feed.add_error(data.get("result") or data.get("status") or "The task failed.")
        elif action == "clear":
            self._task_card.clear_workspace()
            self._activity_stage.reset()

    def _send(self):
        text = getattr(self, "_input", None).text().strip() if hasattr(self, "_input") else ""
        if not text:
            return
        self._input.clear()
        self._ensure_conversation(text)
        self.command_submitted.emit(text)


class LauncherControlPanel(QDialog):
    def __init__(self, *, startup_workspace: bool = False, on_open=None, on_close=None,
                 on_toggle_startup=None, on_hide_icon=None, on_restart=None, on_quit=None,
                 on_open_app=None,
                 on_show_icon=None,
                 on_open_dev=None,
                 parent=None):
        super().__init__(parent)
        self._on_open = on_open
        self._on_close = on_close
        self._on_toggle_startup = on_toggle_startup
        self._on_hide_icon = on_hide_icon
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._on_open_app = on_open_app
        self._on_show_icon = on_show_icon
        self._on_open_dev = on_open_dev

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(15,15,20,235);
                border: 1px solid rgba(0,191,255,60);
                border-radius: 18px;
            }
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("E.V. CONTROL")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        lay.addWidget(title)

        sub = QLabel("Desktop launcher controls")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        lay.addWidget(sub)

        def mk_btn(text: str, *, checkable: bool = False, checked: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(checkable)
            btn.setChecked(checked)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.05);
                    color: #FFFFFF;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 6px 12px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(0,191,255,0.10);
                    border: 1px solid rgba(0,191,255,0.45);
                }
                QPushButton:checked {
                    background: rgba(0,191,255,0.16);
                    border: 1px solid rgba(0,191,255,0.60);
                }
            """)
            return btn

        self._open_btn = mk_btn("Open Workspace")
        self._close_btn = mk_btn("Close Workspace")
        self._startup_btn = mk_btn("Show Workspace On Startup", checkable=True, checked=bool(startup_workspace))
        self._show_icon_btn = mk_btn("Show Floating Icon")
        self._hide_icon_btn = mk_btn("Hide Floating Icon")
        self._restart_btn = mk_btn("Restart E.V.")
        self._quit_btn = mk_btn("Quit E.V.")
        self._open_app_btn = mk_btn("Open App")
        self._open_dev_btn = mk_btn("Open Developer Mode")

        self._open_btn.clicked.connect(lambda: self._invoke(self._on_open))
        self._close_btn.clicked.connect(lambda: self._invoke(self._on_close))
        self._startup_btn.clicked.connect(lambda: self._invoke(self._on_toggle_startup, self._startup_btn.isChecked()))
        self._show_icon_btn.clicked.connect(lambda: self._invoke(self._on_show_icon))
        self._hide_icon_btn.clicked.connect(self._hide_icon_confirm)
        self._restart_btn.clicked.connect(lambda: self._invoke(self._on_restart))
        self._quit_btn.clicked.connect(lambda: self._invoke(self._on_quit))
        self._open_app_btn.clicked.connect(lambda: self._invoke(self._on_open_app))
        self._open_dev_btn.clicked.connect(lambda: self._invoke(self._on_open_dev))

        for btn in (
            self._open_app_btn, self._open_btn, self._close_btn, self._startup_btn,
            self._show_icon_btn, self._hide_icon_btn, self._open_dev_btn,
            self._restart_btn, self._quit_btn
        ):
            lay.addWidget(btn)

        self.adjustSize()

    def _invoke(self, fn, *args):
        if fn:
            try:
                fn(*args)
            except Exception:
                pass
        self.close()

    def _hide_icon_confirm(self):
        box = QDialog(self)
        box.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        box.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: rgba(15,15,20,240); border: 1px solid rgba(0,191,255,60); border-radius: 16px; }")
        lay.addWidget(frame)
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(18, 16, 18, 16)
        flay.setSpacing(10)
        lbl = QLabel("Hide E.V. icon?")
        lbl.setStyleSheet("color: #FFFFFF; background: transparent; font: 700 11pt 'Segoe UI';")
        sub = QLabel("You can restore it from the system tray.")
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        flay.addWidget(lbl)
        flay.addWidget(sub)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        hide = QPushButton("Hide")
        for btn in (cancel, hide):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; } QPushButton:hover { border: 1px solid #5cd3ff; }")
        cancel.clicked.connect(box.reject)
        hide.clicked.connect(box.accept)
        row.addWidget(cancel)
        row.addWidget(hide)
        flay.addLayout(row)
        box.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        box.move(screen.center().x() - box.width() // 2, screen.center().y() - box.height() // 2)
        if box.exec():
            self._invoke(self._on_hide_icon)

    def set_startup_workspace(self, enabled: bool):
        self._startup_btn.setChecked(bool(enabled))


class StatCard(QFrame):
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            f"""
            QFrame#StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 20, 26, 240),
                    stop:1 rgba(8, 10, 14, 220));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 16px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        lbl = QLabel(label.upper())
        lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._detail_lbl = QLabel("")
        self._detail_lbl.setFont(QFont("Segoe UI", 7))
        self._detail_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {C.WHITE};
                border-radius: 2px;
            }}
            """
        )
        lay.addWidget(lbl)
        lay.addWidget(val)
        lay.addWidget(self._detail_lbl)
        lay.addWidget(self._bar)
        self._value_lbl = val

    def set_value(self, value: str, level: int | None = None, detail: str | None = None):
        self._value_lbl.setText(value)
        if detail is not None:
            self._detail_lbl.setText(detail)
        if level is not None:
            self._bar.setValue(max(0, min(100, int(level))))


class LogWidget(QScrollArea):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 24px;
            }}
            """
        )
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)

        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        role, name, body = self._parse(text)
        stamp = time.strftime("%H:%M")

        card = MessageCard(role, name, body, stamp)
        self._layout.insertWidget(self._layout.count() - 1, card)
        QTimer.singleShot(0, self._scroll_bottom)

    def _scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _parse(self, text: str) -> tuple[str, str, str]:
        line = parse_log_line(text)
        return line["role"], line["name"], line["body"]

_FILE_ICONS = {
    "image":   ("IMG",  EV["accent"]),  "video":   ("VID",  "#ff9a5c"),
    "audio":   ("AUD",  EV["violet"]),  "pdf":     ("PDF",  EV["danger"]),
    "word":    ("DOC",  "#6aa8ff"),     "excel":   ("XLS",  EV["success"]),
    "code":    ("CODE", EV["warning"]), "archive": ("ZIP",  "#ff9a5c"),
    "pptx":    ("PPT",  "#ff9a5c"),     "text":    ("TXT",  EV["text_med"]),
    "data":    ("DATA", "#8fe0ff"),     "unknown": ("FILE", EV["text_dim"]),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for E.V.", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "â¬‡")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont(_UI_FONT, 11, QFont.Weight.Bold))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "âœ•")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None, defaults: dict | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: {EV['surface_solid']};
                border: 1px solid {EV['border_strong']};
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; }}
            QLineEdit {{
                background: rgba(255,255,255,0.03);
                color: {EV['text']};
                border: 1px solid {EV['border']};
                border-radius: 10px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {EV['accent_line']}; }}
        """)

        defaults = defaults or {}

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=EV["text"],
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont(_UI_FONT, font_size,
                            QFont.Weight.DemiBold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("SET UP E.V.", 16, True))
        layout.addWidget(_lbl("Add your API keys to finish setup.", 9, color=EV["text_dim"]))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {EV['border']};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=EV["text_faint"],
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont(_UI_FONT, 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {EV["text"]};
                border: 1px solid {EV["border"]}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {EV["accent"]}; }}
        """)
        layout.addWidget(self._key_input)
        self._key_input.setText((defaults.get("gemini_api_key") or "").strip())
        layout.addSpacing(8)

        layout.addWidget(_lbl("OPENROUTER API KEY", 8, color=EV["text_dim"],
                       align=Qt.AlignmentFlag.AlignLeft))
        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-…")
        self._or_input.setFont(QFont(_UI_FONT, 10))
        self._or_input.setFixedHeight(32)
        self._or_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {EV["text"]};
                border: 1px solid {EV["border"]}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {EV["text_med"]}; }}
        """)
        layout.addWidget(self._or_input)
        self._or_input.setText((defaults.get("openrouter_api_key") or "").strip())

        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {EV['border']};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=EV["text_dim"],
                               align=Qt.AlignmentFlag.AlignLeft))
        os_default = (defaults.get("os_system") or detected).strip().lower()
        if os_default not in {"windows", "mac", "linux"}:
            os_default = detected
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=EV["text_med"],
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(os_default)
        layout.addSpacing(12)

        self._status = QLabel("The Gemini key is required. OpenRouter stays optional and is used as a fallback.")
        self._status.setWordWrap(True)
        self._status.setFont(QFont(_UI_FONT, 8))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {EV['text_dim']}; background: transparent;")
        layout.addWidget(self._status)
        layout.addSpacing(8)

        init_btn = QPushButton("Initialise")
        init_btn.setFont(QFont(_UI_FONT, 10, QFont.Weight.DemiBold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {EV['accent_soft']}; color: {EV['text']};
                border: 1px solid {EV['accent_line']}; border-radius: 10px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255, 0.22);
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows": (EV["accent"], "#04202c"), "mac": (EV["violet"], "#141a2e"), "linux": (EV["success"], "#04241a")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: 1px solid {fg}; border-radius: 10px;
                        font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(255,255,255,0.03); color: {EV['text_dim']};
                        border: 1px solid {EV['border']}; border-radius: 10px;
                    }}
                    QPushButton:hover {{ color: {EV['text']}; border: 1px solid {EV['border_strong']}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        or_key = self._or_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {EV['danger']}; }}"
            )
            self._status.setText("Gemini key is required.")
            return
        if or_key and not or_key.startswith("sk-or-"):
            self._status.setText("OpenRouter key looks invalid. Continuing with Gemini only.")
            or_key = ""
        else:
            self._status.setText("Saving settings...")
        self.done.emit(key, or_key, self._sel_os)


class CommandBar(QWidget):
    submitted = pyqtSignal(str)
    attach_clicked = pyqtSignal()
    mic_clicked = pyqtSignal()
    developer_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("CommandBar")
        self.setFixedSize(410, 72)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("CommandBarFrame")
        frame.setStyleSheet(f"""
            QFrame#CommandBarFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(8, 8, 8, 248),
                    stop:0.5 rgba(15, 15, 15, 248),
                    stop:1 rgba(8, 8, 8, 248));
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        lay.addWidget(_framed_logo(36, 24, bg="rgba(255,255,255,0.04)", border=C.BORDER_B, radius=18, inset=5))

        self._input = QLineEdit()
        self._input.setPlaceholderText("Tell E.V. what to do...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setFixedHeight(40)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(16,16,16,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 14px;
                padding: 0 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.BORDER_B}; }}
        """)
        self._input.returnPressed.connect(self._submit)
        lay.addWidget(self._input, stretch=1)

        attach = QPushButton()
        attach.setFixedSize(40, 40)
        attach.setCursor(Qt.CursorShape.PointingHandCursor)
        attach.setToolTip("Attach file")
        attach.setIcon(QIcon(_icon_pixmap("attach", 18)))
        attach.setIconSize(QSize(18, 18))
        attach.setStyleSheet(f"""
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(28,28,28,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        attach.clicked.connect(self.attach_clicked.emit)
        lay.addWidget(attach)

        mic = QPushButton()
        mic.setFixedSize(40, 40)
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setToolTip("Microphone")
        mic.setIcon(QIcon(_icon_pixmap("mic", 18)))
        mic.setIconSize(QSize(18, 18))
        mic.setStyleSheet(f"""
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(28,28,28,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        mic.clicked.connect(self.mic_clicked.emit)
        lay.addWidget(mic)

        dev = QPushButton("DEV")
        dev.setFixedSize(60, 40)
        dev.setCursor(Qt.CursorShape.PointingHandCursor)
        dev.setToolTip("Developer mode")
        dev.setStyleSheet(f"""
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid rgba(92, 211, 255,140);
                border-radius: 12px;
                font: 700 9px 'Segoe UI';
            }}
            QPushButton:hover {{
                background: rgba(34,18,18,245);
                border: 1px solid {C.PRI};
            }}
        """)
        dev.clicked.connect(self.developer_clicked.emit)
        lay.addWidget(dev)

        send = QPushButton()
        send.setFixedSize(40, 40)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setToolTip("Send")
        send.setIcon(QIcon(_icon_pixmap("send", 18)))
        send.setIconSize(QSize(18, 18))
        send.setStyleSheet(f"""
            QPushButton {{
                background: rgba(24,24,24,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(34,34,34,245);
                border: 1px solid {C.WHITE};
            }}
        """)
        send.clicked.connect(self._submit)
        lay.addWidget(send)

        _attach_pulse_glow(frame, color=C.PRI, blur_min=16.0, blur_max=28.0, alpha=120, period_ms=2800)

        root.addWidget(frame)

    def show_near(self, anchor: QWidget):
        screen = QApplication.primaryScreen().availableGeometry()
        geo = anchor.geometry()
        x = geo.center().x() - (self.width() // 2)
        y = geo.bottom() + 14
        x = max(screen.left() + 12, min(x, screen.right() - self.width() - 12))
        y = max(screen.top() + 12, min(y, screen.bottom() - self.height() - 12))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()
        self._input.selectAll()

    def hideEvent(self, event):
        super().hideEvent(event)

    def _submit(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.submitted.emit(txt)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class DeveloperModeDialog(QDialog):
    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Developer Mode")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background: rgba(8,10,14,235); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; }}
            QLabel {{ color: {C.TEXT}; }}
            QLineEdit {{
                background: rgba(16,16,16,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
                padding: 8px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{ background: rgba(28,28,28,245); border: 1px solid {C.PRI}; }}
            QCheckBox {{ color: {C.TEXT}; }}
        """)

        self._settings = dict(settings or {})
        self._enabled = bool(self._settings.get("developer_mode_enabled", False))
        fallback_workspace = str(Path(__file__).resolve().parent)
        self._workspace = str(self._settings.get("developer_mode_workspace", "") or fallback_workspace)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Developer Co-pilot")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI};")
        root.addWidget(title)

        desc = QLabel("Pick a workspace folder E.V. should use when building websites or other workspace-based tasks.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C.TEXT_DIM};")
        root.addWidget(desc)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self._workspace_edit = QLineEdit(self._workspace)
        self._workspace_edit.setPlaceholderText("Select a folder...")
        self._workspace_edit.setReadOnly(True)
        folder_row.addWidget(self._workspace_edit, stretch=1)

        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse)
        root.addLayout(folder_row)

        self._enabled_box = QCheckBox("Turn developer mode on")
        self._enabled_box.setChecked(self._enabled)
        root.addWidget(self._enabled_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self._save_and_close)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select developer workspace", self._workspace or str(BASE_DIR))
        if path:
            self._workspace_edit.setText(path)

    def _save_and_close(self):
        self._settings["developer_mode_enabled"] = bool(self._enabled_box.isChecked())
        self._settings["developer_mode_workspace"] = self._workspace_edit.text().strip()
        self.accept()

    def get_settings(self) -> dict:
        return dict(self._settings)


class ScanningOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._phase = 0.0
        self._text = "SCANNING SCREEN"
        self._sub = "Analyzing display..."

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        # splash + boot UI state
        self._mode = "splash"  # splash -> boot
        self._steps: list[tuple[str, QLabel]] = []
        self._progress_val = 0
        self._progress_tip = ""

        self._center = QFrame(self)
        self._center.setStyleSheet("background: transparent; border: none;")
        self._center_lay = QVBoxLayout(self._center)
        self._center_lay.setContentsMargins(36, 36, 36, 36)
        self._center_lay.setSpacing(18)

        # Splash widgets
        self._splash_logo = QLabel()
        self._splash_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_logo.setPixmap(_logo_pixmap(160))
        self._splash_title = QLabel("E.V.")
        self._splash_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        self._splash_title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        self._splash_sub = QLabel("Your Intelligent Desktop Assistant")
        self._splash_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._splash_slogan = QLabel("Think. Command. Accomplish.")
        self._splash_slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_slogan.setStyleSheet(f"color: {C.PRI}; font-weight: 700;")
        self._splash_status = QLabel("Initializing E.V...")
        self._splash_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._splash_status.setStyleSheet(f"color: {C.TEXT_MED};")

        # Boot widgets
        self._boot_title = QLabel("E.V.")
        self._boot_title.setFont(QFont("Segoe UI", 20, QFont.Weight.Black))
        self._boot_title.setStyleSheet(f"color: {C.WHITE};")
        self._boot_sub = QLabel("System Boot Sequence")
        self._boot_sub.setStyleSheet(f"color: {C.TEXT_DIM};")

        self._checklist_frame = QFrame()
        self._checklist_frame.setStyleSheet("background: transparent; border: none;")
        self._checklist_lay = QVBoxLayout(self._checklist_frame)
        self._checklist_lay.setSpacing(8)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(14)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.04); border-radius: 8px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(92, 211, 255,220), stop:1 rgba(255,120,120,220)); border-radius: 8px; }"
        )

        self._progress_tip_lbl = QLabel("")
        self._progress_tip_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")

        # Layout initial splash
        self._center_lay.addWidget(self._splash_logo)
        self._center_lay.addWidget(self._splash_title)
        self._center_lay.addWidget(self._splash_sub)
        self._center_lay.addWidget(self._splash_slogan)
        self._center_lay.addWidget(self._splash_status)

        self._center.setFixedWidth(820)
        self._center.adjustSize()

        # auto transition from splash to boot
        QTimer.singleShot(1700, self._enter_boot_mode)

    def set_message(self, text: str, sub: str | None = None):
        self._text = (text or "SCANNING SCREEN").upper()
        if sub is not None:
            self._sub = sub
        self.update()

    def show_fullscreen(self, text: str = "SCANNING SCREEN", sub: str = "Analyzing display..."):
        self.set_message(text, sub)
        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1280, 720).toRect()
        self.setGeometry(geo)
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

    def _tick(self):
        self._phase = (self._phase + 0.012) % 1.0
        if self.isVisible():
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        p.fillRect(rect, QColor(0, 0, 0, 185))

        # subtle grid
        grid_pen = QPen(qcol(C.WHITE, 12), 1)
        p.setPen(grid_pen)
        step = 64
        for x in range(0, rect.width(), step):
            p.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), step):
            p.drawLine(0, y, rect.width(), y)

        # blue-white scan beam
        y = int(rect.height() * self._phase)
        beam = QLinearGradient(0, y - 140, 0, y + 140)
        beam.setColorAt(0.0, QColor(120, 210, 255, 0))
        beam.setColorAt(0.48, QColor(120, 210, 255, 90))
        beam.setColorAt(0.50, QColor(255, 255, 255, 180))
        beam.setColorAt(0.52, QColor(120, 210, 255, 90))
        beam.setColorAt(1.0, QColor(120, 210, 255, 0))
        p.fillRect(QRectF(0, y - 140, rect.width(), 280), beam)

        # corner brackets
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        br = 28
        for x, y0, dx, dy in [
            (20, 20, 1, 1),
            (rect.width() - 20, 20, -1, 1),
            (20, rect.height() - 20, 1, -1),
            (rect.width() - 20, rect.height() - 20, -1, -1),
        ]:
            p.drawLine(QPointF(x, y0), QPointF(x + dx * br, y0))
            p.drawLine(QPointF(x, y0), QPointF(x, y0 + dy * br))

        # center orb glow
        cx, cy = rect.width() / 2, rect.height() / 2
        for i in range(6):
            r = 110 + i * 22
            alpha = 28 - i * 3
            p.setPen(QPen(QColor(80, 170, 255, max(0, alpha)), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # text
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        sub_font = QFont("Segoe UI", 10)
        p.setPen(QColor(255, 255, 255, 235))
        p.setFont(title_font)
        p.drawText(QRectF(0, cy - 26, rect.width(), 40), Qt.AlignmentFlag.AlignCenter, self._text)
        p.setFont(sub_font)
        p.setPen(QColor(190, 220, 255, 210))
        p.drawText(QRectF(0, cy + 18, rect.width(), 28), Qt.AlignmentFlag.AlignCenter, self._sub)


class BootSequenceOverlay(QWidget):
    """Short, honest startup card: E.V.'s mark, one status line, real steps.

    The sequence is driven by whichever comes first — the real startup work
    reported through :meth:`add_step` / :meth:`set_progress`, or a short
    timeout. Nothing is padded with fake waiting; a click or key press skips it.
    """

    finished = pyqtSignal()

    MIN_VISIBLE_MS = 420
    MAX_VISIBLE_MS = 2400
    FADE_MS = 220

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(0.0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to skip")

        self._device_name = "DEVICE"
        self._greeting_name = ""
        self._status_text = "Starting up"
        self._running = False
        self._skip_requested = False
        self._started_at = 0.0
        self._steps: list[tuple[str, QLabel]] = []
        self._progress_val = 0
        self._fade_anim: QPropertyAnimation | None = None
        self._phase_timers: list[QTimer] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self._card = QFrame()
        self._card.setObjectName("BootCard")
        self._card.setFixedWidth(420)
        self._card.setStyleSheet(
            f"""
            QFrame#BootCard {{
                background: rgba(8, 11, 16, 0.96);
                border: 1px solid {EV['border_strong']};
                border-radius: 20px;
            }}
            QLabel {{ background: transparent; border: none; }}
            """
        )
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(34, 30, 34, 28)
        card_lay.setSpacing(10)

        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        logo_row.addWidget(_framed_logo(76, 58, bg="transparent", border="transparent", radius=0, inset=0))
        logo_row.addStretch(1)
        card_lay.addLayout(logo_row)

        title = QLabel("E.V.")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(_UI_FONT, 22, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {EV['text']}; letter-spacing: 3px;")
        card_lay.addWidget(title)

        sub = QLabel("Personal AI Assistant")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont(_UI_FONT, 9))
        sub.setStyleSheet(f"color: {EV['text_dim']};")
        card_lay.addWidget(sub)

        card_lay.addSpacing(6)

        self._status_lbl = QLabel(self._status_text)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setFont(QFont(_UI_FONT, 9))
        self._status_lbl.setStyleSheet(f"color: {EV['text_med']};")
        card_lay.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.06); border: none; border-radius: 2px; }"
            f"QProgressBar::chunk {{ background: {EV['accent']}; border-radius: 2px; }}"
        )
        card_lay.addWidget(self._progress)

        hint = QLabel("Click anywhere to skip")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(QFont(_UI_FONT, 8))
        hint.setStyleSheet(f"color: {EV['text_faint']};")
        card_lay.addWidget(hint)

        row.addWidget(self._card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        self._checklist_frame = QWidget()
        self._checklist_lay = QVBoxLayout(self._checklist_frame)
        self._checklist_lay.setContentsMargins(0, 0, 0, 0)
        self._checklist_lay.setSpacing(4)
        self._checklist_frame.hide()

    # -- public API ----------------------------------------------------------
    def add_step(self, text: str) -> QLabel | None:
        label = QLabel(f"• {text}")
        label.setFont(QFont(_UI_FONT, 8))
        label.setStyleSheet(f"color: {EV['text_dim']};")
        self._checklist_lay.addWidget(label)
        self._steps.append((text, label))
        self.set_message(text)
        return label

    def set_step_status(self, text: str, status: str):
        for step_text, label in self._steps:
            if step_text != text:
                continue
            if status == "done":
                label.setStyleSheet(f"color: {EV['success']};")
                label.setText(f"✓ {step_text}")
            elif status == "in_progress":
                label.setStyleSheet(f"color: {EV['accent']};")
                label.setText(f"→ {step_text}")
            elif status == "failed":
                label.setStyleSheet(f"color: {EV['danger']};")
                label.setText(f"✕ {step_text}")
            else:
                label.setStyleSheet(f"color: {EV['text_dim']};")
                label.setText(f"• {step_text}")
            break

    def set_message(self, text: str):
        self._status_text = (text or "").strip() or self._status_text
        self._status_lbl.setText(self._status_text)

    def set_progress(self, percent: int, tip: str | None = None):
        self._progress_val = max(0, min(100, int(percent)))
        self._progress.setValue(self._progress_val)
        if tip:
            self.set_message(tip)
        if self._progress_val >= 100:
            self._finish()

    def start(self, device_name: str, greeting_name: str = ""):
        self._device_name = (device_name or "DEVICE").strip().upper()
        self._greeting_name = (greeting_name or "").strip()
        self._running = True
        self._skip_requested = False
        self._started_at = time.monotonic()
        self._progress_val = 0
        self._progress.setValue(0)
        self._status_lbl.setText(self._status_text)

        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1280, 720).toRect()
        self.setGeometry(geo)
        self.showFullScreen()
        self.raise_()

        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(self.FADE_MS)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

        self._phase_timers.clear()
        self._schedule(self.MAX_VISIBLE_MS, self._finish)

    def _schedule(self, ms: int, fn):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(fn)
        timer.start(ms)
        self._phase_timers.append(timer)

    # -- sequence control ----------------------------------------------------
    def _finish(self):
        if not self._running or self._skip_requested:
            return
        elapsed_ms = (time.monotonic() - self._started_at) * 1000
        if elapsed_ms < self.MIN_VISIBLE_MS:
            self._schedule(int(self.MIN_VISIBLE_MS - elapsed_ms) + 20, self._finish)
            return
        self._running = False
        for timer in self._phase_timers:
            try:
                timer.stop()
            except Exception:
                pass
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(self.FADE_MS)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self._done)
        self._fade_anim.start()

    def _skip(self):
        if self._skip_requested:
            return
        self._skip_requested = True
        self._running = False
        for timer in self._phase_timers:
            try:
                timer.stop()
            except Exception:
                pass
        self.hide()
        self._done()

    def _done(self):
        self.hide()
        self.finished.emit()

    # -- interaction ---------------------------------------------------------
    def mousePressEvent(self, event):
        self._skip()
        event.accept()

    def keyPressEvent(self, event):
        self._skip()
        event.accept()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(4, 6, 10, 214))
        painter.end()


class IncomingAlertDialog(QDialog):
    decision = pyqtSignal(str)

    def __init__(self, event: dict, parent=None):
        super().__init__(parent)
        self._event = event or {}
        self._kind = (self._event.get("kind") or "message").strip().lower()
        self._app = (self._event.get("app") or "App").strip()
        self._title = (self._event.get("title") or "").strip()
        self._preview = (self._event.get("preview") or "").strip()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("IncomingAlertDialog")
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("IncomingAlertFrame")
        frame.setStyleSheet(f"""
            QFrame#IncomingAlertFrame {{
                background: rgba(8, 8, 8, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 16px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        heading = QLabel("Incoming Call" if self._kind == "call" else "Incoming Message")
        heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        heading.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(heading)

        app_lbl = QLabel(f"From {self._app}")
        app_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        app_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(app_lbl)

        body = self._preview or self._title or "A notification was detected."
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setFont(QFont("Segoe UI", 10))
        body_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(body_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        def _btn(text: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            fg = C.WHITE
            border = C.BORDER_B if primary else C.BORDER
            bg = "rgba(255,255,255,0.10)" if primary else "rgba(14,14,14,235)"
            if danger:
                border = C.RED
                bg = "rgba(60,10,10,235)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 11px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.14);
                    border: 1px solid {C.WHITE};
                }}
            """)
            return btn

        if self._kind == "call":
            self._accept_btn = _btn("Pick up", primary=True)
            self._ignore_btn = _btn("Ignore")
            self._cut_btn = _btn("Cut call", danger=True)
            self._x_btn = _btn("X")
            self._accept_btn.clicked.connect(lambda: self._choose("accept"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._cut_btn.clicked.connect(lambda: self._choose("cut"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            for btn in (self._accept_btn, self._ignore_btn, self._cut_btn, self._x_btn):
                btn_row.addWidget(btn)
        else:
            self._hear_btn = _btn("Hear it", primary=True)
            self._reply_btn = _btn("Reply")
            self._ignore_btn = _btn("Ignore")
            self._x_btn = _btn("X")
            self._hear_btn.clicked.connect(lambda: self._choose("hear"))
            self._reply_btn.clicked.connect(lambda: self._choose("reply"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            btn_row.addWidget(self._hear_btn)
            btn_row.addWidget(self._reply_btn)
            btn_row.addWidget(self._ignore_btn)
            btn_row.addWidget(self._x_btn)

        lay.addLayout(btn_row)

    def _choose(self, decision: str):
        self.decision.emit(decision)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._choose("ignore")
            return
        super().keyPressEvent(event)


class MeetingOverlay(QWidget):
    stop_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self._expanded_height = 142
        self._collapsed_height = 58
        self._collapsed = False
        self.setFixedHeight(self._expanded_height)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(5, 5, 5, 232);
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        self._badge = QLabel("MEETING MODE")
        self._badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._badge.setStyleSheet(
            f"color: {C.WHITE}; background: rgba(255,255,255,0.06); border: 1px solid {C.BORDER_B}; border-radius: 10px; padding: 4px 10px;"
        )
        top.addWidget(self._badge)

        self._title = QLabel("Watching the meeting")
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        top.addWidget(self._title)
        top.addStretch()

        self._min_btn = QPushButton("-")
        self._min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min_btn.setFixedSize(28, 28)
        self._min_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._min_btn.setToolTip("Minimize meeting bar")
        self._min_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._min_btn.clicked.connect(self._toggle_collapsed)
        top.addWidget(self._min_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        top.addWidget(self._stop_btn)

        self._close_btn = QPushButton("x")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._close_btn.setToolTip("Close meeting bar")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        top.addWidget(self._close_btn)
        lay.addLayout(top)

        self._summary = QLabel("Waiting for a meeting to start...")
        self._summary.setWordWrap(True)
        self._summary.setFont(QFont("Segoe UI", 10))
        self._summary.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._summary)

        self._speech = QLabel("They said: nothing yet.")
        self._speech.setWordWrap(True)
        self._speech.setFont(QFont("Segoe UI", 10))
        self._speech.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._speech)

        self._answer = QLabel("E.V. will show the live answer here.")
        self._answer.setWordWrap(True)
        self._answer.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._answer.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._answer)

        self._apply_collapsed_state(False)

    def set_content(self, title: str, summary: str, answer: str, active: bool = True, speech: str = ""):
        self._title.setText(title or "Watching the meeting")
        self._summary.setText(summary or "Watching the meeting screen.")
        self._speech.setText(f"They said: {speech or 'nothing yet.'}")
        self._answer.setText(answer or "No question detected yet.")
        self._badge.setText("MEETING LIVE" if active else "MEETING MODE")

    def _apply_collapsed_state(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        for widget in (self._summary, self._speech, self._answer):
            widget.setVisible(not self._collapsed)
        self._min_btn.setText("?" if self._collapsed else "-")
        self._min_btn.setToolTip("Restore meeting bar" if self._collapsed else "Minimize meeting bar")
        self.setFixedHeight(self._collapsed_height if self._collapsed else self._expanded_height)

    def set_collapsed(self, collapsed: bool):
        self._apply_collapsed_state(collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _toggle_collapsed(self):
        self.minimize_requested.emit()


class FloatingLauncher(QWidget):
    single_clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    action_requested = pyqtSignal(str)
    position_changed = pyqtSignal(int, int)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(74, 74)
        self._state = "idle"
        self._status_line = "Ready"
        self._hovered = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._ring = QFrame()
        self._ring.setStyleSheet("")
        lay = QVBoxLayout(self._ring)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(0)

        lay.addWidget(_framed_logo(54, 36, bg="rgba(255,255,255,0.04)", border=C.BORDER, radius=26, inset=6))
        root.addWidget(self._ring)
        _attach_pulse_glow(self._ring, color=C.WHITE, blur_min=18.0, blur_max=34.0, alpha=135, period_ms=2300)

        self._single_timer = QTimer(self)
        self._single_timer.setSingleShot(True)
        self._single_timer.timeout.connect(self.single_clicked.emit)
        self._dragging = False
        self._drag_button = None
        self._drag_offset = QPoint(0, 0)
        self._press_pos = QPoint(0, 0)
        self._apply_state_style()

    def show_at(self, x: int | None = None, y: int | None = None):
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 18
            y = screen.bottom() - self.height() - 90
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_state(self, state: str, detail: str | None = None):
        self._state = (state or "idle").strip().lower()
        self._status_line = (detail or self._default_status()).strip() or self._default_status()
        self._apply_state_style()

    def _default_status(self) -> str:
        return {
            "idle": "Ready",
            "listening": "Listening",
            "thinking": "Thinking...",
            "executing": "Executing task...",
            "error": "Error",
        }.get(self._state, "Ready")

    def _apply_state_style(self):
        state = self._state
        accent = {
            "idle": "#5cd3ff",
            "listening": "#4ef0ff",
            "thinking": "#bfe9ff",
            "executing": "#ffb648",
            "error": "#ff6b7a",
        }.get(state, "#5cd3ff")
        glow = {
            "idle": "rgba(0,191,255,0.18)",
            "listening": "rgba(78,240,255,0.26)",
            "thinking": "rgba(159,216,255,0.26)",
            "executing": "rgba(255,177,74,0.22)",
            "error": "rgba(255,107,107,0.24)",
        }.get(state, "rgba(0,191,255,0.18)")
        self._ring.setStyleSheet(f"""
            QFrame {{
                background: rgba(4, 4, 8, 234);
                border: 1px solid {accent};
                border-radius: 37px;
            }}
            QFrame:hover {{
                border: 1px solid {accent};
            }}
        """)
        self.setToolTip(f"E.V.\n{self._status_line}")

    def _show_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(8, 8, 8, 245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
        """)

        actions = [
            ("New Task", "new_task"),
            ("Voice Mode", "voice_mode"),
            ("Screen Analyzer", "screen_analyzer"),
            ("Browser Agent", "browser_agent"),
            ("Settings", "settings"),
            ("Open Workspace", "open_workspace"),
        ]
        for idx, (label, key) in enumerate(actions):
            action = QAction(label, self)
            action.triggered.connect(lambda _=False, k=key: self.action_requested.emit(k))
            menu.addAction(action)
            if idx != len(actions) - 1:
                menu.addSeparator()
        menu.exec(global_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self._single_timer.start(180)
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self.position_changed.emit(self.x(), self.y())
        if event.button() == Qt.MouseButton.RightButton:
            if not self._dragging:
                self._show_menu(event.globalPosition().toPoint())
            self._dragging = False
            self._drag_button = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._single_timer.stop()
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._single_timer.stop()
            self._drag_button = Qt.MouseButton.LeftButton
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._dragging = False
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._single_timer.stop()
            self._drag_button = Qt.MouseButton.RightButton
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
                self._dragging = True
            if self._dragging:
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos = pos - self._drag_offset
                new_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
                new_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
                self.move(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
            event.accept()
            return
        if event.buttons() & Qt.MouseButton.RightButton and self._drag_button == Qt.MouseButton.RightButton:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
                self._dragging = True
            if self._dragging:
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos = pos - self._drag_offset
                new_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
                new_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
                self.move(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_state_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_state_style()
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _scan_sig  = pyqtSignal(bool, str)
    _briefing_sig = pyqtSignal(object)
    _briefing_hide_sig = pyqtSignal()
    _attention_sig = pyqtSignal(object)
    _meeting_sig = pyqtSignal(object)
    _task_workspace_sig = pyqtSignal(object)
    discord_config_changed = pyqtSignal(object)
    discord_status_changed = pyqtSignal(str)
    minimized = pyqtSignal()

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.Tool, False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowIcon(self._make_window_icon())
        self.setWindowTitle("E.V.")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self.on_attention_action = None
        self.on_chat_event = None
        self.on_remote_clicked = None
        self._muted           = False
        self._wakeword_listening = False
        self._current_file: str | None = None
        self._state = "LISTENING"
        self._left_collapsed  = False
        self._right_collapsed = False
        self._left_auto = False
        self._right_auto = False
        self._current_page = "dashboard"
        self._settings_bridge = None
        self._api_ready = False
        self._app_settings_cache: dict | None = None
        self._overlay: QWidget | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._scan_overlay: ScanningOverlay | None = None
        self._incoming_alert: IncomingAlertDialog | None = None
        self._meeting_overlay: MeetingOverlay | None = None
        self._meeting_overlay_collapsed = False
        self._chat_source_queue: deque[str] = deque()
        self._store = workspace_store()
        self._task_history: list[dict] = []
        self._task_card = None
        self._task_card_owner = None

        central = BackgroundWidget(BACKGROUND_IMAGE_FILE if BACKGROUND_IMAGE_FILE.exists() else None)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel_modern()
        body.addWidget(self._left_panel, stretch=0)
        _attach_pulse_glow(self._left_panel, color=C.PRI, blur_min=8.0, blur_max=18.0, alpha=55, period_ms=3600)

        self._center_panel = self._build_center_panel_modern(face_path)
        body.addWidget(self._center_panel, stretch=1)
        _attach_pulse_glow(self._center_panel, color=C.PRI, blur_min=6.0, blur_max=14.0, alpha=36, period_ms=4200)

        self._right_panel = self._build_right_panel_modern()
        body.addWidget(self._right_panel, stretch=0)
        _attach_pulse_glow(self._right_panel, color=C.PRI, blur_min=8.0, blur_max=18.0, alpha=55, period_ms=3900)

        root.addLayout(body, stretch=1)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metric refresh timer
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._on_log_text)
        self._state_sig.connect(self._apply_state)
        self._briefing_sig.connect(self._apply_daily_briefing)
        self._briefing_hide_sig.connect(self._schedule_daily_briefing_hide)
        self._attention_sig.connect(self._show_attention_alert)
        self._meeting_sig.connect(self._apply_meeting_state)
        self._task_workspace_sig.connect(self._apply_task_workspace)
        self.discord_status_changed.connect(self._on_discord_status_update)

        self._ready = False
        self._activity_text = "Idle — no task running."
        self._activity_kind = ""
        self._card_hide_tmr = QTimer(self)
        self._card_hide_tmr.setSingleShot(True)
        self._card_hide_tmr.timeout.connect(self._hide_command_cards)
        self._briefing_hide_tmr = QTimer(self)
        self._briefing_hide_tmr.setSingleShot(True)
        self._briefing_hide_tmr.timeout.connect(self._hide_daily_briefing_card)

        self._ready = self._check_config()
        self._api_ready = self._ready
        if self._ready:
            self._apply_state("LISTENING")
        else:
            self._show_setup(self._load_api_defaults())
        self._scan_sig.connect(self._apply_scan_state)

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_left = QShortcut(QKeySequence("Ctrl+["), self)
        sc_left.activated.connect(self._toggle_left_sidebar)
        sc_right = QShortcut(QKeySequence("Ctrl+]"), self)
        sc_right.activated.connect(self._toggle_right_sidebar)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")
        self._app_settings_cache = dict(settings)

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log("ERR: startup animation setting failed: %s" % e)
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log("SYS: Startup animation %s." % state)

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif not channel_id:
            status = "Token saved - channel optional"
            color = C.TEXT_MED
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setText("Start Discord Bot")
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setText("Stop Discord Bot")
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _save_discord_token(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        settings = self._load_discord_settings()
        settings["bot_token"] = token
        settings["channel_id"] = channel_id
        settings["enabled"] = bool(token)
        self._discord_enabled = bool(token)
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        if token:
            self._log.append_log("SYS: Discord bot token saved and bot enabled.")
            self._refresh_discord_card("Token saved")
        else:
            self._log.append_log("SYS: Discord bot token cleared.")
            self._discord_enabled = False
            self._refresh_discord_card("Token required")

    def _start_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if not token:
            self._discord_enabled = False
            self._save_discord_token()
            return
        self._discord_enabled = True
        settings = {
            "bot_token": token,
            "enabled": True,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot started.")
        self._refresh_discord_card()

    def _stop_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        self._discord_enabled = False
        settings = {
            "bot_token": token,
            "enabled": False,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot stopped.")
        self._refresh_discord_card()

    def _load_api_defaults(self) -> dict:
        if not API_FILE.exists():
            return {
                "gemini_api_key": "",
                "openrouter_api_key": "",
                "anthropic_api_key": "",
                "os_system": platform.system(),
            }
        try:
            data = json.loads(API_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("anthropic_api_key", "")
                return data
        except Exception:
            pass
        return {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "anthropic_api_key": "",
            "os_system": platform.system(),
        }

    def _startup_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                _startup_registry_key(),
                0,
                winreg.KEY_READ | winreg.KEY_WRITE,
            ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "E.V.")
                    run_value = _startup_run_value()
                    if value != run_value:
                        winreg.SetValueEx(key, "E.V.", 0, winreg.REG_SZ, run_value)
                    return bool(value)
                except FileNotFoundError:
                    return False
        except Exception:
            return False

    def _set_startup_enabled(self, enabled: bool) -> bool:
        if platform.system() != "Windows":
            return False
        run_value = _startup_run_value()
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _startup_registry_key()) as key:
                if enabled:
                    winreg.SetValueEx(key, "E.V.", 0, winreg.REG_SZ, run_value)
                else:
                    try:
                        winreg.DeleteValue(key, "E.V.")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            self._log.append_log(f"ERR: startup setting failed: {e}")
            return False

    def _refresh_startup_button(self):
        if not hasattr(self, "_startup_btn"):
            return
        if platform.system() != "Windows":
            self._startup_btn.setText("Start on Startup (Windows only)")
            self._startup_btn.setEnabled(False)
            return
        if self._startup_enabled():
            self._startup_btn.setText("Start on Startup: ON")
        else:
            self._startup_btn.setText("Start on Startup: OFF")

    def _toggle_startup(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_enabled()
        if self._set_startup_enabled(enabled):
            self._refresh_startup_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Windows startup {state}.")

    def _apply_responsive_layout(self):
        """Collapse the side rails on smaller laptop screens and restore them when there is room."""
        width = self.width()
        if width <= 0:
            return
        need = 620
        changed = False
        left_w = 56 if self._left_collapsed else _LEFT_W
        if not self._right_collapsed and width - left_w - _RIGHT_W < need:
            self._right_collapsed = True
            self._right_auto = True
            changed = True
        right_w = 56 if self._right_collapsed else _RIGHT_W
        if not self._left_collapsed and width - right_w - _LEFT_W < need:
            self._left_collapsed = True
            self._left_auto = True
            changed = True
        if self._right_auto:
            if self._right_collapsed and width - left_w - _RIGHT_W >= need + 40:
                self._right_collapsed = False
                self._right_auto = False
                changed = True
            elif not self._right_collapsed:
                self._right_auto = False
        if self._left_auto:
            right_w = 56 if self._right_collapsed else _RIGHT_W
            if self._left_collapsed and width - right_w - _LEFT_W >= need + 40:
                self._left_collapsed = False
                self._left_auto = False
                changed = True
            elif not self._left_collapsed:
                self._left_auto = False
        if changed:
            self._apply_sidebar_state()

    def _toggle_left_sidebar(self):
        self._left_collapsed = not self._left_collapsed
        self._left_auto = False
        self._apply_sidebar_state()

    def _toggle_right_sidebar(self):
        self._right_collapsed = not self._right_collapsed
        self._right_auto = False
        self._apply_sidebar_state()

    def _apply_sidebar_state(self):
        if hasattr(self, "_left_content"):
            self._left_content.setVisible(not self._left_collapsed)
            if hasattr(self, "_left_panel"):
                self._left_panel.setFixedWidth(56 if self._left_collapsed else _LEFT_W)
            if hasattr(self, "_left_toggle_btn"):
                self._left_toggle_btn.setText(">" if self._left_collapsed else "<")
                self._left_toggle_btn.setToolTip("Expand left sidebar" if self._left_collapsed else "Collapse left sidebar")
        if hasattr(self, "_right_content"):
            self._right_content.setVisible(not self._right_collapsed)
        if hasattr(self, "_right_stack"):
            self._right_stack.setVisible(not self._right_collapsed)
            if hasattr(self, "_right_panel"):
                self._right_panel.setFixedWidth(56 if self._right_collapsed else _RIGHT_W)
            if hasattr(self, "_right_toggle_btn"):
                self._right_toggle_btn.setText("<" if self._right_collapsed else ">")
                self._right_toggle_btn.setToolTip("Expand right sidebar" if self._right_collapsed else "Collapse right sidebar")
        if hasattr(self, "_center_panel"):
            self._center_panel.update()

    def set_settings_bridge(self, bridge):
        self._settings_bridge = bridge
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "set_controller"):
            self._settings_page.set_controller(bridge)
        if hasattr(self, "_settings_sidebar") and hasattr(self._settings_sidebar, "set_controller"):
            self._settings_sidebar.set_controller(bridge)
        self._set_page(self._current_page)

    def _set_page(self, page: str):
        self._current_page = page
        for name, item in getattr(self, "_nav_items", {}).items():
            item.set_active(name == page)
        if hasattr(self, "_center_stack") and isinstance(self._center_stack, QStackedWidget):
            index = {"dashboard": 0, "home": 1, "settings": 2}.get(page, 0)
            self._center_stack.setCurrentIndex(index)
        if page == "home" and hasattr(self, "_home_page"):
            try:
                self._home_page.refresh()
            except Exception:
                pass
        if page == "dashboard" and hasattr(self, "_smart_devices_section"):
            try:
                self._smart_devices_section.refresh(force=True)
            except Exception:
                pass
        if hasattr(self, "_right_panel"):
            self._right_panel.setVisible(page == "dashboard")
        if hasattr(self, "_right_stack") and isinstance(self._right_stack, QStackedWidget):
            self._right_stack.setCurrentIndex({"dashboard": 0, "settings": 1, "home": 2}.get(page, 2))
            self._right_stack.setVisible(page == "dashboard")
        if self._settings_bridge and hasattr(self._settings_bridge, "set_dashboard_page"):
            try:
                self._settings_bridge.set_dashboard_page(page == "dashboard")
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_page"):
            try:
                self._settings_page.refresh()
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_sidebar"):
            try:
                self._settings_sidebar.refresh()
            except Exception:
                pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()
        if self._overlay and self._overlay.isVisible():
            size = self._overlay.sizeHint()
            ow = max(360, size.width() or self._overlay.width() or 460)
            oh = max(320, size.height() or self._overlay.height() or 390)
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _refresh_dashboard_lists(self):
        """Refresh the dashboard's task, conversation and service panels."""
        self._refresh_dashboard_tasks()
        self._refresh_dashboard_recent()
        self._refresh_dashboard_services()

    def _dash_clear(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _dash_row(self, title: str, detail: str = "", accent: str | None = None, on_click=None) -> QFrame:
        row = QFrame()
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.setFixedHeight(50 if detail else 36)
        row.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.02); border: 1px solid {EV['border']}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(row)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(f"color: {accent or EV['text']}; background: transparent; border: none;")
        title_lbl.setWordWrap(True)
        lay.addWidget(title_lbl)
        if detail:
            detail_lbl = QLabel(detail)
            detail_lbl.setFont(QFont(_UI_FONT, 8))
            detail_lbl.setStyleSheet(f"color: {EV['text_dim']}; background: transparent; border: none;")
            detail_lbl.setWordWrap(True)
            lay.addWidget(detail_lbl)
        if on_click is not None:
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.mousePressEvent = lambda event: on_click() if event.button() == Qt.MouseButton.LeftButton else None
        return row

    def _dash_empty(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(_UI_FONT, 8))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {EV['text_dim']}; padding: 6px 2px;")
        return lbl

    def _refresh_dashboard_tasks(self):
        box = getattr(self, "_dash_tasks_box", None)
        if box is None:
            return
        self._dash_clear(box)
        running = [task for task in self._task_history if not task.get("done")]
        recent = [task for task in self._task_history if task.get("done")][:3]
        if not running and not recent:
            box.addWidget(self._dash_empty("Nothing running. Ask E.V. and the plan will appear here."))
            return
        for task in running:
            percent = int(task.get("percent") or 0)
            box.addWidget(
                self._dash_row(
                    task.get("title") or "Working",
                    f"{task.get('status') or 'In progress'} · {percent}%",
                    accent=EV["accent"],
                )
            )
        for task in recent:
            state = "Completed" if task.get("success", True) else "Failed"
            accent = EV["success"] if task.get("success", True) else EV["danger"]
            box.addWidget(self._dash_row(task.get("title") or "Task", state, accent=accent))

    def _refresh_dashboard_recent(self):
        box = getattr(self, "_dash_recent_box", None)
        if box is None:
            return
        self._dash_clear(box)
        try:
            conversations = self._store.list_conversations()[:4]
        except Exception:
            conversations = []
        if not conversations:
            box.addWidget(self._dash_empty("No conversations yet."))
            return
        for item in conversations:
            title = item.get("title") or "Conversation"
            detail = _fmt_time_stamp(item.get("updatedAt"))
            box.addWidget(self._dash_row(title, detail, on_click=lambda cid=item.get("id"): self._open_conversation(cid)))

    def _refresh_dashboard_services(self):
        box = getattr(self, "_dash_services_box", None)
        if box is None:
            return
        self._dash_clear(box)
        services = self._collect_service_status()
        for name, state, ok in services:
            accent = EV["success"] if ok else EV["text_dim"]
            box.addWidget(self._dash_row(name, state, accent=accent))

    def _collect_service_status(self) -> list[tuple[str, str, bool]]:
        services: list[tuple[str, str, bool]] = []

        voice_ready = not bool(getattr(self.hud, "muted", False)) if hasattr(self, "hud") else False
        services.append(("Voice", "Microphone muted" if not voice_ready else "Listening for commands", voice_ready))

        try:
            memories = self._store.all_memories()
            count = len(memories)
        except Exception:
            count = 0
        services.append(("Memory", f"{count} entries stored" if count else "No memories stored yet", count > 0))

        try:
            settings = self._load_discord_settings()
            discord_ok = bool((settings.get("bot_token") or "").strip())
        except Exception:
            discord_ok = False
        services.append(("Discord", "Bot token configured" if discord_ok else "Not configured", discord_ok))

        api_ready = False
        try:
            api_ready = bool(self._check_config())
        except Exception:
            api_ready = False
        services.append(("AI provider", "API key present" if api_ready else "API key missing", api_ready))

        try:
            import importlib.util
            browser_ok = importlib.util.find_spec("playwright") is not None
        except Exception:
            browser_ok = False
        services.append(("Browser automation", "Playwright installed" if browser_ok else "Playwright not installed", browser_ok))
        return services

    def _open_conversation(self, conversation_id: str):
        if not conversation_id:
            return
        workspace = getattr(self, "_inline_workspace", None)
        if workspace is None:
            return
        self._right_collapsed = False
        self._apply_sidebar_state()
        workspace._open_conversation(conversation_id)

    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu = snap["cpu"]
        mem = snap["mem"]
        net = snap["net"]
        net_str = f"{net * 1024:.0f} KB/s" if net < 1.0 else f"{net:.1f} MB/s"

        if hasattr(self, "_cpu_lbl") and self._cpu_lbl is not None:
            self._cpu_lbl.setText(f"CPU {cpu:.0f}%")
        if hasattr(self, "_ram_lbl") and self._ram_lbl is not None:
            self._ram_lbl.setText(f"Memory {mem:.0f}%")
        if hasattr(self, "_net_lbl") and self._net_lbl is not None:
            self._net_lbl.setText(f"Network {net_str}")

        if not hasattr(self, "_bar_cpu"):
            return

        # CPU
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")
        if hasattr(self, "_stat_cpu"):
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 0
            cpu_threads = psutil.cpu_count(logical=True) or cpu_cores
            self._stat_cpu.set_value(
                f"{cpu:.0f}%",
                int(cpu),
                f"{cpu_threads} threads / {cpu_cores or cpu_threads} cores",
            )

        # MEM
        self._bar_mem.set_value(mem, f"{mem:.0f}%")
        if hasattr(self, "_stat_mem"):
            vm = psutil.virtual_memory()
            used_gb = vm.used / (1024**3)
            total_gb = vm.total / (1024**3)
            self._stat_mem.set_value(
                f"{mem:.0f}%",
                int(mem),
                f"{used_gb:.1f} GB / {total_gb:.1f} GB used",
            )

        # NET
        net_pct = min(100, net * 10)  # 10 MB/s = 100%
        self._bar_net.set_value(net_pct, net_str)
        if hasattr(self, "_stat_net"):
            self._stat_net.set_value(net_str if net >= 1 else "ONLINE", int(net_pct), _active_net_label())

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            self._bar_tmp.set_value(min(100, tmp), f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")
        if hasattr(self, "_stat_cam"):
            cam_on = _camera_available()
            self._stat_cam.set_value(
                "ON" if cam_on else "OFF",
                100 if cam_on else 0,
                "Webcam detected" if cam_on else "No camera found",
            )


    def _make_window_icon(self) -> QIcon:
        return _logo_icon()

    def _tick_clock(self):
        now = time.localtime()
        if hasattr(self, "_clock_lbl") and self._clock_lbl is not None:
            self._clock_lbl.setText(time.strftime("%H:%M"))
        if hasattr(self, "_date_lbl") and self._date_lbl is not None:
            self._date_lbl.setText(time.strftime("%A • %d %B"))
        if hasattr(self, "_core_lbl") and self._core_lbl is not None:
            hour = now.tm_hour
            if hour < 12:
                greeting = "Good morning."
            elif hour < 18:
                greeting = "Good afternoon."
            else:
                greeting = "Good evening."
            self._core_lbl.setText(greeting)
        if hasattr(self, "_core_sub_lbl") and self._core_sub_lbl is not None:
            self._core_sub_lbl.setText(self._ready_line())
        if hasattr(self, "_core_status_lbl") and self._core_status_lbl is not None:
            self._core_status_lbl.setText(self._environment_line())
        self._refresh_rail_provider()

    def _refresh_rail_provider(self):
        if hasattr(self, "_rail_provider_lbl"):
            self._rail_provider_lbl.setText(self._environment_line())

    def _ready_line(self) -> str:
        return {
            "THINKING": "Working on your request.",
            "SPEAKING": "Speaking now.",
            "EXECUTING": "Running a task.",
            "PROCESSING": "Processing audio.",
            "MUTED": "Microphone muted.",
            "OFFLINE": "Waiting for a connection.",
        }.get(getattr(self, "_state", "LISTENING"), "E.V. is ready.")

    def _environment_line(self) -> str:
        provider = "Gemini 2.5 Flash"
        try:
            data = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
            model = str(data.get("gemini_model") or data.get("model") or "").strip()
            if model:
                provider = model
        except Exception:
            pass
        fallback = "OpenRouter fallback" if _or_available() else "local tools"
        memory = "memory on"
        try:
            memory = f"{len(self._store.all_memories())} memories"
        except Exception:
            pass
        return f"{provider} · {fallback} · {memory}"

    def _on_file_selected(self, path: str):
        self._current_file = path
        p = Path(path)
        cat = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        if hasattr(self, "_file_chip") and self._file_chip:
            self._file_chip.setText(f"Attached: {icon} {p.name}  ·  {size}")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.') } | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _browse_attachment(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach a file to E.V.", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._on_file_selected(path)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._wakeword_listening = self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        muted = bool(muted)
        if muted == self._muted and not wakeword:
            return
        self._muted = muted
        self.hud.muted = self._muted
        self._wakeword_listening = bool(muted)
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if not hasattr(self, "_mute_btn") or self._mute_btn is None:
            return
        if self._muted:
            self._mute_btn.setText("Unmute")
            self._mute_btn.setToolTip("Turn the microphone back on (F4)")
            self._mute_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,182,72,0.12); color: {EV['warning']}; "
                f"border: 1px solid rgba(255,182,72,0.42); border-radius: 9px; padding: 6px 12px; font-size: 8pt; }}"
                f"QPushButton:hover {{ background: rgba(255,182,72,0.20); }}"
            )
        else:
            self._mute_btn.setText("Mute mic")
            self._mute_btn.setToolTip("Pause voice input (F4)")
            self._mute_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.04); color: {EV['text_med']}; "
                f"border: 1px solid {EV['border']}; border-radius: 9px; padding: 6px 12px; font-size: 8pt; }}"
                f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
            )

    def _send(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.submit_command(txt)

    def submit_command(self, txt: str, source: str = "local"):
        txt = (txt or "").strip()
        if not txt:
            return
        self._chat_source_queue.append(source or "local")
        self._set_activity_line(f"Request: {txt}")
        self._restart_card_hide_timer()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt, source or "local"), daemon=True).start()

    def _on_log_text(self, text: str):
        self._log.append_log(text)
        line = parse_log_line(text)
        kind = line["kind"]
        if kind == "empty":
            return
        if kind == "you":
            self._show_command_card(line["body"])
            self._relay_chat_event("user", line["body"], pop_queue=True)
        elif kind in ("ev", "ev ai", "assistant"):
            self._show_result_card(line["body"])
            self._relay_chat_event("assistant", line["body"], pop_queue=True)
        elif kind == "error":
            self._show_result_card(humanize_error(line["body"]), kind="error")
            self._relay_chat_event("error", line["body"], pop_queue=True)

    def _relay_chat_event(self, role: str, body: str, *, pop_queue: bool = False):
        """Forward a parsed log line into the conversation feed."""
        if self.on_chat_event and body:
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            try:
                self.on_chat_event({"role": role, "text": body, "source": source})
            except Exception:
                pass
        if pop_queue and self._chat_source_queue:
            self._chat_source_queue.popleft()

    def _set_activity_line(self, text: str):
        self._activity_text = text or ""
        if hasattr(self, "_activity_lbl"):
            preview = self._activity_text
            if len(preview) > 150:
                preview = preview[:150] + "…"
            self._activity_lbl.setText(preview or "Idle — no task running.")
            colour = EV["danger"] if getattr(self, "_activity_kind", "") == "error" else EV["text_dim"]
            self._activity_lbl.setStyleSheet(f"color: {colour};")

    def _show_command_card(self, body: str):
        if not body:
            return
        self._activity_kind = "info"
        self._set_activity_line(f"Request: {body}")
        self._restart_card_hide_timer()

    def _show_result_card(self, body: str, *, kind: str = "info"):
        if not body:
            return
        self._activity_kind = kind
        prefix = "Problem: " if kind == "error" else ""
        self._set_activity_line(f"{prefix}{body}")
        self._restart_card_hide_timer()

    def _restart_card_hide_timer(self):
        if hasattr(self, "_card_hide_tmr"):
            self._card_hide_tmr.start(5000)

    def _hide_command_cards(self):
        self._activity_kind = ""
        self._set_activity_line("Idle — no task running.")

    def _apply_daily_briefing(self, payload):
        action, text = payload if isinstance(payload, tuple) else ("hide", "")
        if action == "show" and hasattr(self, "_briefing_card"):
            clean_text = " ".join(str(text or "").split())
            self._briefing_text_lbl.setText(clean_text[:360] + ("..." if len(clean_text) > 360 else ""))
            self._briefing_card.show()
            self._briefing_card.raise_()
            if hasattr(self, "_smart_devices_section"):
                self._smart_devices_section.hide()
        elif hasattr(self, "_briefing_card"):
            self._briefing_card.hide()
            if hasattr(self, "_smart_devices_section"):
                self._smart_devices_section.show()
                try:
                    self._smart_devices_section.refresh(force=True)
                except Exception:
                    pass

    def _hide_daily_briefing_card(self):
        if hasattr(self, "_briefing_card"):
            self._briefing_card.hide()
        if hasattr(self, "_smart_devices_section"):
            self._smart_devices_section.show()
            try:
                self._smart_devices_section.refresh(force=True)
            except Exception:
                pass

    def _schedule_daily_briefing_hide(self):
        if hasattr(self, "_briefing_hide_tmr"):
            self._briefing_hide_tmr.start(10000)

    def show_daily_briefing(self, text: str):
        self._briefing_sig.emit(("show", text or ""))

    def hide_daily_briefing(self):
        self._briefing_sig.emit(("hide", ""))

    def schedule_daily_briefing_hide(self):
        self._briefing_hide_sig.emit()

    def show_app(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_remote_connect(self):
        if not self.on_remote_clicked:
            self._log_sig.emit("ERR: Mobile remote is not ready yet.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log_sig.emit("ERR: Mobile remote could not start. Install dashboard dependencies and try again.")
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else url
        manual = result[3] if len(result) >= 4 else url

        if self._remote_overlay is not None:
            try:
                self._remote_overlay.deleteLater()
            except Exception:
                pass
            self._remote_overlay = None

        overlay = RemoteKeyOverlay(url, key, auto, manual, parent=self)
        overlay.set_new_key_callback(self.on_remote_clicked)
        overlay.closed.connect(lambda: setattr(self, "_remote_overlay", None))
        self._remote_overlay = overlay
        self._position_remote_overlay()
        overlay.show()
        overlay.raise_()
        self._log_sig.emit(f"SYS: Mobile Connect ready at {manual}. Scan the QR code or enter key {key}.")

    def _position_remote_overlay(self):
        if not self._remote_overlay:
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._remote_overlay.width()) // 2)
        y = max(16, (geo.height() - self._remote_overlay.height()) // 2)
        self._remote_overlay.move(x, y)

    def notify_phone_connected(self):
        if self._remote_overlay is not None:
            self._remote_overlay.mark_connected()
        self._log_sig.emit("SYS: Phone connected to E.V. remote.")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.minimized.emit()

    def _apply_state(self, state: str):
        self._state = state
        self.hud.state = state
        self.hud.speaking = (state == "SPEAKING")

        chip_text = {
            "THINKING": "● Working",
            "SPEAKING": "● Speaking",
            "EXECUTING": "● Executing",
            "PROCESSING": "● Processing",
            "MUTED": "● Muted",
            "OFFLINE": "● Offline",
        }.get(state, "● Online")
        chip_color = {
            "THINKING": EV["violet"],
            "SPEAKING": EV["accent"],
            "EXECUTING": EV["accent"],
            "MUTED": EV["warning"],
            "OFFLINE": EV["danger"],
        }.get(state, EV["success"])
        if hasattr(self, "_status_chip"):
            self._status_chip.setText(chip_text)
            self._status_chip.setStyleSheet(f"color: {chip_color}; background: transparent;")
        if hasattr(self, "_ai_lbl"):
            self._ai_lbl.setText(chip_text.replace("● ", "AI ").lower().capitalize())
            self._ai_lbl.setStyleSheet(f"color: {chip_color}; background: transparent;")
        if hasattr(self, "_time_status_lbl"):
            self._time_status_lbl.setText(
                {"THINKING": "Working", "SPEAKING": "Speaking", "EXECUTING": "Executing", "MUTED": "Muted", "OFFLINE": "Offline"}.get(state, "Online")
            )
            self._time_status_lbl.setStyleSheet(f"color: {chip_color}; background: transparent;")
        if hasattr(self, "_voice_state_lbl"):
            self._voice_state_lbl.setText(
                {
                    "THINKING": "Thinking",
                    "SPEAKING": "Speaking",
                    "EXECUTING": "Working",
                    "PROCESSING": "Processing",
                    "MUTED": "Muted",
                    "OFFLINE": "Offline",
                }.get(state, "Listening")
            )
            self._voice_state_lbl.setStyleSheet(f"color: {chip_color}; background: transparent;")
        if hasattr(self, "_rail_status_lbl"):
            self._rail_status_lbl.setText(f"● {chip_text.replace('● ', '')}")
            self._rail_status_lbl.setStyleSheet(f"color: {chip_color};")
        if hasattr(self, "_core_sub_lbl"):
            self._core_sub_lbl.setText(self._ready_line())
        if hasattr(self, "_inline_workspace"):
            self._inline_workspace.set_context(self._ready_line())
        if state in ("THINKING", "PROCESSING"):
            self._set_page_state("working")
        elif state in ("LISTENING", "SPEAKING", "MUTED", "EXECUTING"):
            self._set_page_state("idle")

    def _set_page_state(self, mode: str):
        """Small hook kept for the boot overlay / status dots; no fake progress."""
        if hasattr(self, "_rail_status_lbl"):
            self._rail_dot_mode = mode


    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (bool(d.get("gemini_api_key")) and
                    bool(d.get("os_system")))
        except Exception:
            return False

    def _apply_scan_state(self, enabled: bool, text: str = ""):
        if enabled:
            if self._scan_overlay is None:
                self._scan_overlay = ScanningOverlay()
            self._scan_overlay.show_fullscreen(text or "SCANNING SCREEN", "Analyzing display...")
        else:
            if self._scan_overlay is not None:
                self._scan_overlay.hide_overlay()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._scan_sig.emit(bool(enabled), text or "")

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._meeting_sig.emit({
            "enabled": bool(enabled),
            "title": title or "",
            "summary": summary or "",
            "answer": answer or "",
            "speech": speech or "",
        })

    def _apply_meeting_state(self, event: object):
        data = event if isinstance(event, dict) else {}
        enabled = bool(data.get("enabled"))
        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        answer = (data.get("answer") or "").strip()
        speech = (data.get("speech") or "").strip()

        if enabled:
            if self._meeting_overlay is None:
                self._meeting_overlay = MeetingOverlay()
                self._meeting_overlay.stop_requested.connect(self._request_stop_meeting)
                self._meeting_overlay.minimize_requested.connect(self._toggle_meeting_overlay)
                self._meeting_overlay.close_requested.connect(self._request_stop_meeting)
            self._meeting_overlay.set_content(
                title or "Meeting mode",
                summary or "Watching the meeting screen.",
                answer or "No question detected yet.",
                True,
                speech,
            )
            self._position_meeting_overlay()
            self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
            self._meeting_overlay.show()

    def _apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        workspace = getattr(self, "_inline_workspace", None)
        if workspace is not None:
            workspace.apply_task_workspace(data)

        if action == "start":
            command = data.get("command") or "Task"
            if not any(task.get("title") == command and not task.get("done") for task in self._task_history):
                self._task_history.insert(
                    0, {"title": command, "status": "Planning", "percent": 4, "done": False, "success": True}
                )
            del self._task_history[8:]
            self._right_collapsed = False
            self._apply_sidebar_state()
        elif action == "update":
            if self._task_history and not self._task_history[0].get("done"):
                current = self._task_history[0]
                if data.get("title"):
                    current["title"] = data["title"]
                if data.get("percent") is not None:
                    try:
                        current["percent"] = int(data["percent"])
                    except Exception:
                        pass
                if data.get("status"):
                    current["status"] = data["status"]
        elif action == "finish":
            if self._task_history:
                current = self._task_history[0]
                current["done"] = True
                current["percent"] = int(data.get("percent") or 100)
                current["success"] = str(data.get("status") or "").lower() not in ("failed", "error")
                current["status"] = data.get("status") or "Completed"
        elif action == "clear":
            for task in self._task_history:
                task["done"] = True
        self._refresh_dashboard_tasks()

    def _on_discord_status_update(self, message: str):
        if not message:
            return
        if hasattr(self, "_discord_status_lbl"):
            note = message.strip()
            self._refresh_discord_card(note)
            if self._meeting_overlay is not None:
                try:
                    self._meeting_overlay.raise_()
                except Exception:
                    pass
        else:
            if self._meeting_overlay is not None:
                self._meeting_overlay.hide()
            self._meeting_overlay_collapsed = False

    def _request_stop_meeting(self):
        if self.on_attention_action:
            try:
                self.on_attention_action({"kind": "meeting", "app": "Meeting mode"}, "stop")
            except Exception:
                pass

    def _toggle_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        self._meeting_overlay_collapsed = not self._meeting_overlay_collapsed
        self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
        self._position_meeting_overlay()
        if not self._meeting_overlay.isVisible():
            self._meeting_overlay.show()
        self._meeting_overlay.raise_()

    def _position_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 12
        h = self._meeting_overlay.height()
        w = min(980, max(780, screen.width() - margin * 2))
        x = screen.left() + (screen.width() - w) // 2
        y = screen.top() + margin
        self._meeting_overlay.setGeometry(x, y, w, h)

    def _show_attention_alert(self, event: object):
        data = event if isinstance(event, dict) else {}
        if self._incoming_alert is not None:
            try:
                self._incoming_alert.close()
            except Exception:
                pass
            self._incoming_alert = None

        dlg = IncomingAlertDialog(data, None)
        dlg.decision.connect(lambda decision, ev=data: self._attention_choice(ev, decision))

        if (data.get("kind") or "").strip().lower() == "call":
            self.show_app()

        screen = QApplication.primaryScreen().availableGeometry()
        margin = 16
        dlg.adjustSize()
        x = screen.right() - dlg.width() - margin
        y = screen.top() + margin
        dlg.move(x, y)
        dlg.show()
        dlg.raise_()
        self._incoming_alert = dlg

    def _attention_choice(self, event: dict, decision: str):
        if self.on_attention_action:
            try:
                self.on_attention_action(event, decision)
            except Exception:
                pass
        self._incoming_alert = None

    def _show_setup(self, defaults: dict | None = None):
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        ov = SetupOverlay(self.centralWidget(), defaults=defaults or self._load_api_defaults())
        cw = self.centralWidget()
        ow, oh = 460, 430
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        ov.raise_()
        ov.activateWindow()
        self._overlay = ov

    # Change signature:
    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            existing = self._load_api_defaults()
            API_FILE.write_text(
                json.dumps({
                    "gemini_api_key":    key,
                    "openrouter_api_key": or_key,
                    "anthropic_api_key": existing.get("anthropic_api_key", ""),
                    "os_system":         os_name,
                }, indent=4),
                encoding="utf-8",
            )
            self._ready = True
            self._api_ready = True
            if self._overlay:
                self._overlay.hide()
                self._overlay.deleteLater()
                self._overlay = None
            self._apply_state("LISTENING")
            self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. E.V. online.")
        except Exception as e:
            self._log.append_log(f"ERR: setup failed: {e}")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Left rail: identity, navigation, quick actions, system status
    # ------------------------------------------------------------------
    def _build_left_panel_modern(self) -> QWidget:
        w = QFrame()
        w.setObjectName("LeftRail")
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(
            f"""
            QFrame#LeftRail {{
                background: {EV['surface']};
                border: 1px solid {EV['border']};
                border-radius: 18px;
            }}
            """
        )
        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(14, 14, 14, 14)
        root_lay.setSpacing(12)

        toggle_row = QHBoxLayout()
        self._left_toggle_btn = QPushButton("‹")
        self._left_toggle_btn.setFixedSize(30, 30)
        self._left_toggle_btn.setFont(QFont(_UI_FONT, 12, QFont.Weight.Bold))
        self._left_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._left_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.03); color: {EV['text_med']}; "
            f"border: 1px solid {EV['border']}; border-radius: 9px; }}"
            f"QPushButton:hover {{ color: {EV['accent']}; border: 1px solid {EV['accent_line']}; }}"
        )
        self._left_toggle_btn.clicked.connect(self._toggle_left_sidebar)
        toggle_row.addWidget(self._left_toggle_btn)
        toggle_row.addStretch()
        root_lay.addLayout(toggle_row)

        self._left_content = QWidget()
        self._left_content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self._left_content)
        lay.setContentsMargins(2, 4, 2, 2)
        lay.setSpacing(10)
        root_lay.addWidget(self._left_content, stretch=1)

        def section(title: str) -> QLabel:
            lbl = QLabel(title.upper())
            lbl.setObjectName("EVSectionLabel")
            return lbl

        class NavItem(QFrame):
            clicked = pyqtSignal()

            def __init__(self, text: str, active: bool = False, letter: str | None = None, compact: bool = False):
                super().__init__()
                self._compact = compact
                self._letter = (letter or text[:2]).upper()
                self._text = text
                self._active = bool(active)
                self.setObjectName("LeftNavItem")
                self.setFixedHeight(40 if compact else 42)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                r = QHBoxLayout(self)
                r.setContentsMargins(10, 0, 10, 0)
                r.setSpacing(10)
                self._icon = QLabel(self._letter)
                self._icon.setFixedSize(26, 22)
                self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._icon.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
                self._lbl = QLabel(text)
                self._lbl.setFont(QFont(_UI_FONT, 9 if compact else 10, QFont.Weight.DemiBold if active else QFont.Weight.Normal))
                r.addWidget(self._icon)
                r.addWidget(self._lbl)
                r.addStretch()
                self.set_active(active)

            def set_active(self, active: bool):
                self._active = bool(active)
                if self._active:
                    self.setStyleSheet(
                        f"QFrame#LeftNavItem {{ background: {EV['accent_soft']}; "
                        f"border: 1px solid {EV['accent_line']}; border-radius: 11px; }}"
                    )
                    self._icon.setStyleSheet(
                        f"background: rgba(92,211,255,0.16); color: {EV['accent']}; "
                        f"border: 1px solid {EV['accent_line']}; border-radius: 7px;"
                    )
                    self._lbl.setStyleSheet(f"color: {EV['text']}; background: transparent;")
                else:
                    self.setStyleSheet(
                        f"QFrame#LeftNavItem {{ background: transparent; border: 1px solid transparent; border-radius: 11px; }}"
                        f"QFrame#LeftNavItem:hover {{ background: rgba(255,255,255,0.04); border: 1px solid {EV['border']}; }}"
                    )
                    self._icon.setStyleSheet(
                        f"background: rgba(255,255,255,0.03); color: {EV['text_dim']}; "
                        f"border: 1px solid {EV['border']}; border-radius: 7px;"
                    )
                    self._lbl.setStyleSheet(f"color: {EV['text_med']}; background: transparent;")

            def mousePressEvent(self, event):
                super().mousePressEvent(event)
                if event.button() == Qt.MouseButton.LeftButton:
                    self.clicked.emit()

        self._nav_items: dict[str, NavItem] = {}

        def activate(page: str):
            if page == "chat" and hasattr(self, "_right_panel"):
                self._right_collapsed = False
                self._apply_sidebar_state()
                self._set_page("dashboard")
                self._nav_items["chat"].set_active(True)
                return
            self._set_page(page)

        brand = QWidget()
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(2, 2, 0, 2)
        brand_lay.setSpacing(12)
        brand_lay.addWidget(_framed_logo(48, 38, bg=EV["surface_solid"], border=EV["border"], radius=12, inset=6))
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        title = QLabel("E.V.")
        title.setFont(QFont(_UI_FONT, 17, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {EV['text']}; letter-spacing: 0.5px;")
        sub = QLabel("Personal assistant")
        sub.setFont(QFont(_UI_FONT, 8))
        sub.setStyleSheet(f"color: {EV['text_dim']};")
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand_lay.addLayout(brand_text)
        brand_lay.addStretch(1)
        lay.addWidget(brand)

        lay.addWidget(section("Workspace"))
        self._nav_items["dashboard"] = NavItem("Overview", active=True, letter="OV")
        self._nav_items["chat"] = NavItem("Conversation", active=False, letter="CH")
        self._nav_items["home"] = NavItem("Home Control", active=False, letter="HC")
        self._nav_items["settings"] = NavItem("Settings", active=False, letter="ST")
        self._nav_items["dashboard"].clicked.connect(lambda: activate("dashboard"))
        self._nav_items["chat"].clicked.connect(lambda: activate("chat"))
        self._nav_items["home"].clicked.connect(lambda: activate("home"))
        self._nav_items["settings"].clicked.connect(lambda: activate("settings"))
        for key in ("dashboard", "chat", "home", "settings"):
            lay.addWidget(self._nav_items[key])

        lay.addWidget(section("Quick actions"))
        quick_grid = QGridLayout()
        quick_grid.setSpacing(7)
        quick_actions = (
            ("Screen", "Summarise my screen", 0, 0),
            ("Report", "Create a project report", 0, 1),
            ("Search", "Search the web for today's news", 1, 0),
            ("Files", "Organise my downloads folder", 1, 1),
        )
        for label, prompt, row, col in quick_actions:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(prompt)
            btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.03); color: {EV['text_med']}; "
                f"border: 1px solid {EV['border']}; border-radius: 10px; padding: 8px 6px; font-size: 8pt; }}"
                f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
            )
            btn.clicked.connect(lambda _=False, p=prompt: self.submit_command(p))
            quick_grid.addWidget(btn, row, col)
        lay.addLayout(quick_grid)

        lay.addWidget(section("Hand tracking"))
        self._gesture_preview = GestureCameraPreview(compact=True)
        self._gesture_preview.setMinimumWidth(0)
        lay.addWidget(self._gesture_preview)

        lay.addStretch(1)

        status_card = QFrame()
        status_card.setObjectName("LeftStatusCard")
        status_card.setStyleSheet(
            f"""
            QFrame#LeftStatusCard {{
                background: {EV['surface_low']};
                border: 1px solid {EV['border']};
                border-radius: 14px;
            }}
            QLabel {{ background: transparent; border: none; }}
            """
        )
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(12, 10, 12, 10)
        status_lay.setSpacing(4)
        self._rail_status_lbl = QLabel("● System online")
        self._rail_status_lbl.setFont(QFont(_UI_FONT, 8, QFont.Weight.DemiBold))
        self._rail_status_lbl.setStyleSheet(f"color: {EV['success']};")
        name = QLabel("E.V. — Personal AI Assistant")
        name.setFont(QFont(_UI_FONT, 8))
        name.setStyleSheet(f"color: {EV['text_med']};")
        self._rail_provider_lbl = QLabel(self._environment_line())
        self._rail_provider_lbl.setFont(QFont(_UI_FONT, 7))
        self._rail_provider_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        self._rail_provider_lbl.setWordWrap(True)
        status_lay.addWidget(self._rail_status_lbl)
        status_lay.addWidget(name)
        status_lay.addWidget(self._rail_provider_lbl)
        lay.addWidget(status_card)

        self._apply_sidebar_state()
        return w

    # ------------------------------------------------------------------
    # Centre: the E.V. dashboard
    # ------------------------------------------------------------------
    def _ev_card(self, object_name: str = "EVCard") -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setStyleSheet(
            f"QFrame#{object_name} {{ background: {EV['surface']}; "
            f"border: 1px solid {EV['border']}; border-radius: 16px; }}"
        )
        return card

    def _ev_card_header(self, title: str, hint: str = "") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(title.upper())
        label.setObjectName("EVSectionLabel")
        row.addWidget(label)
        row.addStretch(1)
        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setFont(QFont(_UI_FONT, 7))
            hint_lbl.setStyleSheet(f"color: {EV['text_faint']};")
            row.addWidget(hint_lbl)
        return row

    def _build_center_panel_modern(self, face_path: str) -> QWidget:
        w = QWidget()
        w.setObjectName("CenterStage")
        w.setStyleSheet("QWidget#CenterStage { background: transparent; border: none; }")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(14)

        # --- greeting + clock -------------------------------------------
        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        self._core_lbl = QLabel("Good morning.")
        self._core_lbl.setFont(QFont(_UI_FONT, 21, QFont.Weight.DemiBold))
        self._core_lbl.setStyleSheet(f"color: {EV['text']}; letter-spacing: 0.2px;")
        self._core_sub_lbl = QLabel("E.V. is ready.")
        self._core_sub_lbl.setFont(QFont(_UI_FONT, 10))
        self._core_sub_lbl.setStyleSheet(f"color: {EV['accent']};")
        self._core_status_lbl = QLabel("")
        self._core_status_lbl.setWordWrap(True)
        self._core_status_lbl.setFont(QFont(_UI_FONT, 8))
        self._core_status_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        title_box.addWidget(self._core_lbl)
        title_box.addWidget(self._core_sub_lbl)
        title_box.addWidget(self._core_status_lbl)
        top_row.addLayout(title_box)
        top_row.addStretch()

        time_card = self._ev_card("EVTimeCard")
        time_card.setFixedWidth(176)
        time_lay = QVBoxLayout(time_card)
        time_lay.setContentsMargins(16, 12, 16, 12)
        time_lay.setSpacing(2)
        self._clock_lbl = QLabel("00:00")
        self._clock_lbl.setFont(QFont(_UI_FONT, 24, QFont.Weight.DemiBold))
        self._clock_lbl.setStyleSheet(f"color: {EV['text']};")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont(_UI_FONT, 8))
        self._date_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._time_status_lbl = QLabel("Online")
        self._time_status_lbl.setFont(QFont(_UI_FONT, 8, QFont.Weight.DemiBold))
        self._time_status_lbl.setStyleSheet(f"color: {EV['success']};")
        self._time_status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_lay.addWidget(self._clock_lbl)
        time_lay.addWidget(self._date_lbl)
        time_lay.addWidget(self._time_status_lbl)
        top_row.addWidget(time_card)
        lay.addLayout(top_row)

        # --- voice core + quick actions ----------------------------------
        middle = QHBoxLayout()
        middle.setSpacing(14)

        voice_card = self._ev_card("EVVoiceCard")
        voice_card.setFixedWidth(268)
        voice_lay = QVBoxLayout(voice_card)
        voice_lay.setContentsMargins(16, 14, 16, 14)
        voice_lay.setSpacing(8)
        voice_lay.addLayout(self._ev_card_header("Voice", "Mic + speech"))
        self.hud = HudCanvas(face_path)
        self.hud.setMinimumSize(172, 172)
        self.hud.setMaximumSize(196, 196)
        voice_lay.addWidget(self.hud, alignment=Qt.AlignmentFlag.AlignHCenter)
        voice_row = QHBoxLayout()
        voice_row.setSpacing(8)
        self._voice_state_lbl = QLabel("Listening")
        self._voice_state_lbl.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        self._voice_state_lbl.setStyleSheet(f"color: {EV['accent']};")
        self._mute_btn = QPushButton("Mute mic")
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.04); color: {EV['text_med']}; "
            f"border: 1px solid {EV['border']}; border-radius: 9px; padding: 6px 12px; font-size: 8pt; }}"
            f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
        )
        self._mute_btn.clicked.connect(self._toggle_mute)
        voice_row.addWidget(self._voice_state_lbl)
        voice_row.addStretch(1)
        voice_row.addWidget(self._mute_btn)
        voice_lay.addLayout(voice_row)
        middle.addWidget(voice_card)

        right_column = QVBoxLayout()
        right_column.setSpacing(14)
        right_column.setContentsMargins(0, 0, 0, 0)

        status_card = self._ev_card("EVStatusCard")
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(16, 14, 16, 14)
        status_lay.setSpacing(10)
        status_lay.addLayout(self._ev_card_header("System", "Live"))
        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(18)
        status_grid.setVerticalSpacing(8)
        self._status_chip = QLabel("● Online")
        self._status_chip.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
        self._status_chip.setStyleSheet(f"color: {EV['success']};")
        self._cpu_lbl = QLabel("CPU —")
        self._ram_lbl = QLabel("Memory —")
        self._net_lbl = QLabel("Network —")
        self._ai_lbl = QLabel("AI ready")
        for idx, widget in enumerate((self._status_chip, self._ai_lbl, self._cpu_lbl, self._ram_lbl, self._net_lbl)):
            widget.setFont(QFont(_UI_FONT, 8))
            widget.setStyleSheet(f"color: {EV['text_dim']};")
            status_grid.addWidget(widget, idx // 3, idx % 3)
        status_lay.addLayout(status_grid)
        self._activity_lbl = QLabel("Idle — no task running.")
        self._activity_lbl.setWordWrap(True)
        self._activity_lbl.setFont(QFont(_UI_FONT, 8))
        self._activity_lbl.setStyleSheet(f"color: {EV['text_dim']};")
        status_lay.addWidget(self._activity_lbl)

        right_column.addWidget(status_card)

        quick_card = self._ev_card("EVQuickCard")
        quick_lay = QVBoxLayout(quick_card)
        quick_lay.setContentsMargins(16, 14, 16, 14)
        quick_lay.setSpacing(9)
        quick_lay.addLayout(self._ev_card_header("Quick actions", "One click"))
        quick_buttons = QGridLayout()
        quick_buttons.setSpacing(8)
        entries = (
            ("Summarise screen", lambda: self.submit_command("What's on my screen?")),
            ("New report", lambda: self.submit_command("Create a project status report")),
            ("Web search", lambda: self.submit_command("Search the web for today's technology news")),
            ("Organise files", lambda: self.submit_command("Organise my downloads folder")),
            ("Daily briefing", lambda: self.submit_command("Give me my daily briefing")),
            ("Open settings", lambda: self._open_settings_page()),
        )
        for index, (label, handler) in enumerate(entries):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.03); color: {EV['text_med']}; "
                f"border: 1px solid {EV['border']}; border-radius: 10px; padding: 9px 10px; font-size: 8.5pt; text-align: left; }}"
                f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; color: {EV['text']}; }}"
            )
            btn.clicked.connect(handler)
            quick_buttons.addWidget(btn, index // 2, index % 2)
        quick_lay.addLayout(quick_buttons)
        right_column.addWidget(quick_card)
        middle.addLayout(right_column, 1)
        lay.addLayout(middle)

        # --- tasks / recent / services -----------------------------------
        bottom_cards = []

        tasks_card = self._ev_card("EVTasksCard")
        tasks_lay = QVBoxLayout(tasks_card)
        tasks_lay.setContentsMargins(16, 14, 16, 14)
        tasks_lay.setSpacing(9)
        tasks_lay.addLayout(self._ev_card_header("Active tasks", "Agent queue"))
        self._dash_tasks_box = QVBoxLayout()
        self._dash_tasks_box.setSpacing(6)
        tasks_lay.addLayout(self._dash_tasks_box)
        tasks_lay.addStretch(1)
        tasks_card.setMinimumWidth(205)
        bottom_cards.append(tasks_card)

        recent_card = self._ev_card("EVRecentCard")
        recent_lay = QVBoxLayout(recent_card)
        recent_lay.setContentsMargins(16, 14, 16, 14)
        recent_lay.setSpacing(9)
        recent_lay.addLayout(self._ev_card_header("Recent conversations", "Memory"))
        self._dash_recent_box = QVBoxLayout()
        self._dash_recent_box.setSpacing(6)
        recent_lay.addLayout(self._dash_recent_box)
        recent_lay.addStretch(1)
        recent_card.setMinimumWidth(205)
        bottom_cards.append(recent_card)

        services_card = self._ev_card("EVServicesCard")
        services_lay = QVBoxLayout(services_card)
        services_lay.setContentsMargins(16, 14, 16, 14)
        services_lay.setSpacing(9)
        services_lay.addLayout(self._ev_card_header("Connected services", "Integrations"))
        self._dash_services_box = QVBoxLayout()
        self._dash_services_box.setSpacing(6)
        services_lay.addLayout(self._dash_services_box)
        services_lay.addStretch(1)
        services_card.setMinimumWidth(205)
        bottom_cards.append(services_card)
        lay.addWidget(ResponsiveCardRow(bottom_cards))
        lay.addStretch(1)

        # --- contextual cards (kept wired to the runtime) ----------------
        self._smart_devices_section = SmartDevicesSection(self)
        self._smart_devices_section.setMinimumHeight(0)
        self._smart_devices_section.hide()
        lay.addWidget(self._smart_devices_section)

        self._briefing_card = self._ev_card("DailyBriefingCard")
        self._briefing_card.setStyleSheet(
            f"QFrame#DailyBriefingCard {{ background: {EV['surface_high']}; "
            f"border: 1px solid {EV['accent_line']}; border-radius: 14px; }}"
        )
        self._briefing_card.setFixedSize(560, 104)
        briefing_lay = QVBoxLayout(self._briefing_card)
        briefing_lay.setContentsMargins(16, 11, 16, 11)
        briefing_lay.setSpacing(4)
        briefing_title = QLabel("DAILY BRIEFING")
        briefing_title.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        briefing_title.setStyleSheet(f"color: {EV['accent']}; letter-spacing: 1.2px;")
        briefing_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._briefing_text_lbl = QLabel()
        self._briefing_text_lbl.setWordWrap(True)
        self._briefing_text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._briefing_text_lbl.setFont(QFont(_UI_FONT, 9))
        self._briefing_text_lbl.setStyleSheet(f"color: {EV['text']};")
        briefing_lay.addWidget(briefing_title)
        briefing_lay.addWidget(self._briefing_text_lbl, stretch=1)
        lay.addWidget(self._briefing_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._briefing_card.hide()

        self._developer_card = self._ev_card("DeveloperCard")
        self._developer_card.setStyleSheet(
            f"QFrame#DeveloperCard {{ background: {EV['surface_high']}; "
            f"border: 1px solid {EV['border_strong']}; border-radius: 14px; }}"
        )
        self._developer_card.setFixedSize(560, 74)
        dev_lay = QVBoxLayout(self._developer_card)
        dev_lay.setContentsMargins(16, 10, 16, 10)
        dev_lay.setSpacing(3)
        dev_title = QLabel("DEVELOPER MODE")
        dev_title.setFont(QFont(_UI_FONT, 7, QFont.Weight.Bold))
        dev_title.setStyleSheet(f"color: {EV['text_faint']}; letter-spacing: 1.2px;")
        dev_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._developer_status_lbl = QLabel("Developer mode is idle")
        self._developer_status_lbl.setWordWrap(True)
        self._developer_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._developer_status_lbl.setFont(QFont(_UI_FONT, 9))
        self._developer_status_lbl.setStyleSheet(f"color: {EV['text']};")
        dev_lay.addWidget(dev_title)
        dev_lay.addWidget(self._developer_status_lbl)
        lay.addWidget(self._developer_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._developer_card.hide()

        # --- command bar (pinned below the scrollable dashboard) ----------
        self._command_panel = QWidget()
        self._command_panel.setObjectName("EVCommandPanel")
        self._command_panel.setStyleSheet("QWidget#EVCommandPanel { background: transparent; border: none; }")
        cmd_lay = QVBoxLayout(self._command_panel)
        cmd_lay.setContentsMargins(24, 0, 24, 16)
        cmd_lay.setSpacing(8)
        cmd_lay.addLayout(self._build_command_row())

        self._home_page = EVHomePage()
        self._settings_page = SystemConnectivityPage()
        self._center_stack = QStackedWidget()
        self._center_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        dashboard_page = QWidget()
        dashboard_page.setObjectName("EVDashboardPage")
        dashboard_page.setStyleSheet("QWidget#EVDashboardPage { background: transparent; border: none; }")
        page_lay = QVBoxLayout(dashboard_page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(0)
        page_lay.addWidget(self._wrap_scrollable(w), stretch=1)
        page_lay.addWidget(self._command_panel)
        self._center_stack.addWidget(dashboard_page)
        self._center_stack.addWidget(self._home_page)
        self._center_stack.addWidget(self._settings_page)
        self._center_stack.setCurrentIndex(0)
        self._refresh_dashboard_lists()
        return self._center_stack

    def _wrap_scrollable(self, inner: QWidget) -> QScrollArea:
        """Keep the dashboard usable on smaller laptop screens."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 0 4px 0; }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.12);
                border-radius: 4px; min-height: 28px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(92, 211, 255, 0.45); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        inner.setMinimumWidth(0)
        scroll.setWidget(inner)
        return scroll

    def _open_settings_page(self):
        self._set_page("settings")

    # ------------------------------------------------------------------
    # Right side: conversation panel
    # ------------------------------------------------------------------
    def _build_right_panel_modern(self) -> QWidget:
        w = QFrame()
        w.setObjectName("RightPanel")
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(
            f"""
            QFrame#RightPanel {{
                background: {EV['surface']};
                border: 1px solid {EV['border']};
                border-radius: 18px;
            }}
            """
        )
        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(14, 12, 14, 14)
        root_lay.setSpacing(10)

        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        self._right_toggle_btn = QPushButton("›")
        self._right_toggle_btn.setFixedSize(30, 30)
        self._right_toggle_btn.setFont(QFont(_UI_FONT, 12, QFont.Weight.Bold))
        self._right_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._right_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.03); color: {EV['text_med']}; "
            f"border: 1px solid {EV['border']}; border-radius: 9px; }}"
            f"QPushButton:hover {{ color: {EV['accent']}; border: 1px solid {EV['accent_line']}; }}"
        )
        self._right_toggle_btn.clicked.connect(self._toggle_right_sidebar)
        toggle_row.addWidget(self._right_toggle_btn)
        root_lay.addLayout(toggle_row)

        self._right_stack = QStackedWidget()
        self._right_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

        self._right_content = QWidget()
        self._right_content.setStyleSheet("background: transparent;")
        chat_lay = QVBoxLayout(self._right_content)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(8)

        self._inline_workspace = InlineChatWorkspace()
        self._inline_workspace.attach_requested.connect(self._browse_attachment)
        self._inline_workspace.mic_requested.connect(self._toggle_mute)
        self._inline_workspace.command_submitted.connect(self._send)
        self._log = self._inline_workspace
        self._task_card = self._inline_workspace._task_card
        self._task_card_owner = self._inline_workspace
        chat_lay.addWidget(self._inline_workspace, stretch=1)

        self._settings_sidebar = SystemConnectivitySidebar()
        self._empty_right = QWidget()
        self._empty_right.setStyleSheet("background: transparent;")

        self._right_stack.addWidget(self._right_content)
        self._right_stack.addWidget(self._settings_sidebar)
        self._right_stack.addWidget(self._empty_right)
        root_lay.addWidget(self._right_stack, stretch=1)

        self._apply_sidebar_state()
        return w

    # ------------------------------------------------------------------
    # Command bar
    # ------------------------------------------------------------------
    def _build_command_row(self) -> QHBoxLayout:
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("EVCommandBar")
        bar.setFixedHeight(62)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.setStyleSheet(
            f"""
            QFrame#EVCommandBar {{
                background: {EV['surface_high']};
                border: 1px solid {EV['border_strong']};
                border-radius: 16px;
            }}
            """
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 11, 14, 11)
        row.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask E.V. anything — or press F4 to talk")
        self._input.setFont(QFont(_UI_FONT, 10))
        self._input.setFixedHeight(40)
        self._input.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,0.03); color: {EV['text']}; "
            f"border: 1px solid {EV['border']}; border-radius: 11px; padding: 0 13px; }}"
            f"QLineEdit:focus {{ border: 1px solid {EV['accent_line']}; }}"
        )
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)

        def _icon_button(tooltip: str, kind: str, handler, accent: bool = False) -> QPushButton:
            btn = QPushButton()
            btn.setFixedSize(38, 38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setIcon(QIcon(_icon_pixmap(kind, 18)))
            btn.setIconSize(QSize(18, 18))
            btn.clicked.connect(handler)
            if accent:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; border-radius: 11px; }}"
                    f"QPushButton:hover {{ background: rgba(92,211,255,0.24); }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.03); border: 1px solid {EV['border']}; border-radius: 11px; }}"
                    f"QPushButton:hover {{ background: {EV['accent_soft']}; border: 1px solid {EV['accent_line']}; }}"
                )
            return btn

        attach = _icon_button("Attach a file", "attach", self._browse_attachment)
        row.addWidget(attach)

        mic = _icon_button("Voice input (F4)", "mic", self._toggle_mute, accent=True)
        row.addWidget(mic)

        self._send_btn = _icon_button("Send", "send", self._send, accent=True)
        row.addWidget(self._send_btn)

        wrapper.addWidget(bar)
        return wrapper



class SystemConnectivitySidebar(QFrame):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivitySidebar")
        self.setStyleSheet(
            f"""
            QFrame#SystemConnectivitySidebar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(14, 16, 22, 235),
                    stop:1 rgba(7, 9, 13, 220));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 22px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                text-align: left;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.10);
                border: 1px solid {C.PRI};
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)

        title = QLabel("SYSTEM STATUS")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(title)

        self._status_card = QFrame()
        self._status_card.setStyleSheet("QFrame { background: rgba(14,16,20,0.88); border: 1px solid rgba(53,255,117,0.18); border-radius: 14px; }")
        s_lay = QVBoxLayout(self._status_card)
        s_lay.setContentsMargins(16, 14, 16, 14)
        s_lay.setSpacing(10)
        self._online_lbl = QLabel("● System Online")
        self._online_lbl.setStyleSheet("color: #3ddc97; font-weight: 700;")
        self._desc_lbl = QLabel("All systems are operational.")
        self._desc_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        s_lay.addWidget(self._online_lbl)
        s_lay.addWidget(self._desc_lbl)
        lay.addWidget(self._status_card)

        self._info_rows: dict[str, QLabel] = {}
        for label in ("Version", "Platform", "Current AI Provider", "Last Updated"):
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 4)
            row.setSpacing(10)
            icon = QLabel("◌")
            icon.setFixedWidth(18)
            icon.setStyleSheet(f"color: {C.WHITE};")
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(f"color: {C.WHITE};")
            val_lbl = QLabel("")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            row.addWidget(icon)
            row.addWidget(key_lbl)
            row.addStretch(1)
            row.addWidget(val_lbl)
            lay.addLayout(row)
            self._info_rows[label] = val_lbl

        quick_title = QLabel("QUICK ACTIONS")
        quick_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        quick_title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(quick_title)

        self._quick_actions = QVBoxLayout()
        self._quick_actions.setSpacing(10)
        lay.addLayout(self._quick_actions)
        self._mk_quick_action("↻ Restart E.V.", QStyle.StandardPixmap.SP_BrowserReload, self._restart)
        self._mk_quick_action("⟳ Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload)
        self._mk_quick_action("📁 Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder)
        self._mk_quick_action("📄 View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs)
        self._mk_quick_action("⬇ Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates)

        tip = QFrame()
        tip.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        tip_lay = QVBoxLayout(tip)
        tip_lay.setContentsMargins(16, 14, 16, 14)
        tip_lay.setSpacing(8)
        tip_title = QLabel("Security Tip")
        tip_title.setStyleSheet("color: #ffb648; font-weight: 700;")
        tip_body = QLabel('"Never share your API keys with anyone."')
        tip_body.setWordWrap(True)
        tip_body.setStyleSheet(f"color: {C.TEXT_MED};")
        tip_lay.addWidget(tip_title)
        tip_lay.addWidget(tip_body)
        lay.addStretch(1)
        lay.addWidget(tip)

        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _mk_quick_action(self, text: str, icon_kind, slot):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(self.style().standardIcon(icon_kind))
        btn.clicked.connect(slot)
        self._quick_actions.addWidget(btn)
        return btn

    def _bridge(self):
        return self._controller

    def _restart(self):
        if self._bridge() and hasattr(self._bridge(), "_restart_app"):
            self._bridge()._restart_app()

    def _reload(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            try:
                self._bridge()._win._load_api_defaults()
                self._bridge()._win._load_discord_settings()
                self._bridge()._log_sig.emit("SYS: Configuration reloaded.")
            except Exception:
                pass

    def _open_data_folder(self):
        try:
            os.startfile(str(CONFIG_DIR))
        except Exception:
            pass

    def _view_logs(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception:
            pass

    def _check_updates(self):
        if self._bridge() and hasattr(self._bridge(), "write_log"):
            self._bridge().write_log("SYS: Update check is not connected to a remote service yet.")

    def refresh(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            version = f"v{APP_VERSION}"
            platform_name = platform.system()
            provider = self._bridge()._win._load_app_settings().get("default_ai_provider", "Gemini")
            last_updated = time.strftime("%d %b %Y %H:%M")
            self._info_rows["Version"].setText(version)
            self._info_rows["Platform"].setText(platform_name)
            self._info_rows["Current AI Provider"].setText(provider)
            self._info_rows["Last Updated"].setText(last_updated)
        else:
            self._info_rows["Version"].setText(f"v{APP_VERSION}")
            self._info_rows["Platform"].setText(platform.system())
            self._info_rows["Current AI Provider"].setText("Gemini")
            self._info_rows["Last Updated"].setText(time.strftime("%d %b %Y %H:%M"))


class SystemConnectivityPage(QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivityPage")
        self.setStyleSheet(f"""
            QWidget#SystemConnectivityPage {{
                background: transparent;
            }}
            QFrame#SettingsCard {{
                background: rgba(10,11,15,235);
                border: 1px solid rgba(92, 211, 255,0.18);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.10);
                border: 1px solid {C.PRI};
            }}
            QLineEdit, QComboBox {{
                background: rgba(13,15,19,240);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        root.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(6)
        title = QLabel("SYSTEM & CONNECTIVITY")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Black))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        sub = QLabel("Manage your AI providers, connections and application preferences.")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        h_lay.addWidget(title)
        h_lay.addWidget(sub)
        lay.addWidget(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._build_left_column(), 7)
        top.addWidget(self._build_summary_card(), 3, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addStretch(1)

        self._select_category("general")
        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _ctrl(self):
        return self._controller

    def _card(self, title: str, subtitle: str = "") -> QFrame:
        frame = QFrame()
        frame.setObjectName("SettingsCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        if title:
            head = QLabel(title)
            head.setFont(QFont(_UI_FONT, 12, QFont.Weight.DemiBold))
            head.setStyleSheet(f"color: {EV['text']};")
            lay.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {C.TEXT_DIM};")
            lay.addWidget(sub)
        return frame

    def _mk_toggle(self, text: str, checked: bool, callback):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: callback(btn.isChecked()))
        btn.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px 14px;
            }}
            QPushButton:checked {{
                background: rgba(92, 211, 255,0.12);
                border: 1px solid {C.PRI};
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.08);
            }}
            """
        )
        return btn

    def _provider_key_preview(self, key: str) -> str:
        key = (key or "").strip()
        if not key:
            return "Not set"
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"

    def _provider_row(self, name: str, key: str, model: str, setting_key: str):
        row = QFrame()
        row.setStyleSheet("QFrame { background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; }")
        r = QHBoxLayout(row)
        r.setContentsMargins(14, 12, 14, 12)
        r.setSpacing(12)
        icon = QLabel(name[:1].upper())
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        icon.setStyleSheet(f"background: rgba(92, 211, 255,0.12); color: {C.WHITE}; border: 1px solid rgba(92, 211, 255,0.38); border-radius: 21px;")
        r.addWidget(icon)
        meta = QVBoxLayout()
        title = QLabel(name)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE};")
        status = QLabel("Connected" if key else "Not connected")
        status.setStyleSheet(f"color: {C.GREEN if key else C.PRI};")
        model_lbl = QLabel(f"Current model: {model}")
        model_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        api_lbl = QLabel(self._provider_key_preview(key))
        api_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        meta.addWidget(title)
        meta.addWidget(status)
        meta.addWidget(model_lbl)
        meta.addWidget(api_lbl)
        r.addLayout(meta, 1)
        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(8)
        edit = QPushButton("Edit API Key")
        edit.clicked.connect(lambda: self._open_api_keys())
        test = QPushButton("Test Connection")
        test.clicked.connect(lambda: self._test_provider(setting_key))
        btn_lay.addWidget(edit)
        btn_lay.addWidget(test)
        r.addLayout(btn_lay)
        return row, status, api_lbl

    def _select_category(self, key: str):
        if key not in self._settings_pages:
            return
        self._settings_stack.setCurrentIndex([c[0] for c in _SETTINGS_CATEGORIES].index(key))
        for name, btn in self._category_buttons.items():
            active = name == key
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {EV['accent_soft']}; color: {EV['text']}; "
                    f"border: 1px solid {EV['accent_line']}; border-radius: 10px; text-align: left; padding: 0 12px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {EV['text_dim']}; border: 1px solid transparent; "
                    f"border-radius: 10px; text-align: left; padding: 0 12px; }}"
                    f"QPushButton:hover {{ color: {EV['text']}; background: rgba(255,255,255,0.04); }}"
                )

    def _add_setting(self, category: str, widget: QWidget):
        layout = self._settings_pages.get(category)
        if layout is None:
            return
        layout.insertWidget(layout.count() - 1, widget)

    def _build_voice_card(self) -> QFrame:
        card = self._card("Voice", "Microphone, wake word and speech output.")
        lay = card.layout()
        self._voice_status_lbl = QLabel("Microphone: —")
        self._voice_state_lbl = QLabel("Voice engine: —")
        self._wakeword_lbl = QLabel("Wake word: —")
        for lbl in (self._voice_status_lbl, self._voice_state_lbl, self._wakeword_lbl):
            lbl.setStyleSheet(f"color: {EV['text_med']};")
            lay.addWidget(lbl)
        self._mute_toggle_btn = self._mk_toggle("Mute the microphone (F4)", False, self._toggle_mute_from_page)
        lay.addWidget(self._mute_toggle_btn)
        return card

    def _toggle_mute_from_page(self, checked: bool):
        ctrl = self._ctrl()
        if not ctrl or not hasattr(ctrl, "_win"):
            return
        win = ctrl._win
        if bool(getattr(win, "_muted", False)) != bool(checked):
            win._toggle_mute()

    def _refresh_voice_card(self):
        ctrl = self._ctrl()
        win = getattr(ctrl, "_win", None) if ctrl else None
        muted = bool(getattr(win, "_muted", False)) if win else False
        state = getattr(win, "_state", "LISTENING") if win else "LISTENING"
        if hasattr(self, "_voice_status_lbl"):
            self._voice_status_lbl.setText("Microphone: muted" if muted else "Microphone: listening")
        if hasattr(self, "_voice_state_lbl"):
            self._voice_state_lbl.setText(f"Voice engine: engine {state.lower()} · F4 toggles the mic")
        if hasattr(self, "_wakeword_lbl"):
            listening = bool(getattr(win, "_wakeword_listening", False)) if win else False
            self._wakeword_lbl.setText("Wake word: listening for the wake phrase" if listening else "Wake word: paused")
        if hasattr(self, "_mute_toggle_btn"):
            self._mute_toggle_btn.setChecked(muted)

    def _build_automation_card(self) -> QFrame:
        card = self._card("Automation", "Hand tracking, browser control and smart home.")
        lay = card.layout()
        self._automation_hand_lbl = QLabel("Hand tracking: —")
        self._automation_browser_lbl = QLabel("Browser automation: —")
        self._automation_home_lbl = QLabel("Smart home: —")
        for lbl in (self._automation_hand_lbl, self._automation_browser_lbl, self._automation_home_lbl):
            lbl.setStyleSheet(f"color: {EV['text_med']};")
            lay.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(10)
        hand_btn = QPushButton("Open hand tracking")
        hand_btn.clicked.connect(self._open_hand_tracking)
        home_btn = QPushButton("Open Home Control")
        home_btn.clicked.connect(self._open_home_control)
        row.addWidget(hand_btn)
        row.addWidget(home_btn)
        lay.addLayout(row)
        return card

    def _open_hand_tracking(self):
        ctrl = self._ctrl()
        win = getattr(ctrl, "_win", None) if ctrl else None
        preview = getattr(win, "_gesture_preview", None) if win else None
        if preview is None:
            return
        if getattr(preview, "_category", None) != "camera":
            preview._category = "camera"
        if hasattr(preview, "_expand_compact") and getattr(preview, "_compact", False):
            preview._expand_compact()
        if win is not None and hasattr(win, "_left_collapsed") and win._left_collapsed:
            win._toggle_left_sidebar()

    def _open_home_control(self):
        ctrl = self._ctrl()
        win = getattr(ctrl, "_win", None) if ctrl else None
        if win is not None:
            win._set_page("home")

    def _refresh_automation_card(self):
        ctrl = self._ctrl()
        win = getattr(ctrl, "_win", None) if ctrl else None
        preview = getattr(win, "_gesture_preview", None) if win else None
        if hasattr(self, "_automation_hand_lbl"):
            if preview is None:
                self._automation_hand_lbl.setText("Hand tracking: unavailable")
            elif getattr(preview, "_cap", None) is not None:
                self._automation_hand_lbl.setText("Hand tracking: camera active")
            else:
                self._automation_hand_lbl.setText("Hand tracking: camera off — click the strip to open it")
        if hasattr(self, "_automation_browser_lbl"):
            try:
                import importlib.util
                installed = importlib.util.find_spec("playwright") is not None
            except Exception:
                installed = False
            self._automation_browser_lbl.setText(
                "Browser automation: Playwright installed" if installed
                else "Browser automation: Playwright not installed (run setup.py)"
            )
        if hasattr(self, "_automation_home_lbl"):
            count = 0
            try:
                home = getattr(win, "_home_page", None)
                devices = getattr(getattr(home, "_service", None), "devices", None)
                if callable(devices):
                    count = len(devices())
                elif devices is not None:
                    count = len(devices)
            except Exception:
                count = 0
            self._automation_home_lbl.setText(
                f"Smart home: {count} device{'s' if count != 1 else ''} registered" if count else "Smart home: no devices added yet"
            )

    def _build_advanced_card(self) -> QFrame:
        card = self._card("Advanced", "Maintenance, diagnostics and power-user tools.")
        lay = card.layout()
        dev_btn = QPushButton("Developer mode…")
        dev_btn.clicked.connect(self._open_developer_mode)
        lay.addWidget(dev_btn)
        data_btn = QPushButton("Open data folder")
        data_btn.clicked.connect(self._open_data_folder)
        lay.addWidget(data_btn)
        logs_btn = QPushButton("View logs")
        logs_btn.clicked.connect(self._view_logs)
        lay.addWidget(logs_btn)
        reload_btn = QPushButton("Reload configuration")
        reload_btn.clicked.connect(self._reload_config)
        lay.addWidget(reload_btn)
        return card

    def _open_developer_mode(self):
        ctrl = self._ctrl()
        win = getattr(ctrl, "_win", None) if ctrl else None
        dialog = getattr(win, "_developer_dialog", None) if win else None
        opener = getattr(win, "_open_developer_mode_dialog", None) if win else None
        if callable(opener):
            opener()

    def _refresh_extra_cards(self):
        try:
            self._refresh_voice_card()
            self._refresh_automation_card()
        except Exception:
            pass

    def _build_left_column(self):
        col = QWidget()
        lay = QHBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        rail = QVBoxLayout()
        rail.setContentsMargins(0, 0, 0, 0)
        rail.setSpacing(6)
        self._category_buttons: dict[str, QPushButton] = {}
        self._settings_stack = QStackedWidget()
        self._settings_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        self._settings_pages: dict[str, QVBoxLayout] = {}

        for key, label in _SETTINGS_CATEGORIES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.setFont(QFont(_UI_FONT, 9, QFont.Weight.DemiBold))
            btn.clicked.connect(lambda _=False, k=key: self._select_category(k))
            self._category_buttons[key] = btn
            rail.addWidget(btn)

            page = QWidget()
            page.setStyleSheet("background: transparent;")
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(0, 0, 4, 0)
            page_lay.setSpacing(14)
            page_lay.addStretch(1)
            self._settings_pages[key] = page_lay
            self._settings_stack.addWidget(page)

        rail.addStretch(1)
        lay.addLayout(rail, 0)
        lay.addWidget(self._settings_stack, 1)

        # AI Providers
        card = self._card("AI Providers", "Only the supported providers are shown here.")
        lay1 = card.layout()
        self._api_defaults = self._load_api_defaults()
        self._gemini_row, self._gemini_status, self._gemini_key = self._provider_row(
            "Google Gemini",
            self._api_defaults.get("gemini_api_key", ""),
            "gemini-2.5-flash",
            "gemini",
        )
        self._or_row, self._or_status, self._or_key = self._provider_row(
            "OpenRouter",
            self._api_defaults.get("openrouter_api_key", ""),
            "auto",
            "openrouter",
        )
        lay1.addWidget(self._gemini_row)
        lay1.addWidget(self._or_row)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self._default_provider = QComboBox()
        self._default_provider.addItems(["Google Gemini", "OpenRouter"])
        self._default_provider.setCurrentText("Google Gemini" if self._load_app_settings().get("default_ai_provider", "Gemini") in {"Gemini", "Google Gemini"} else "OpenRouter")
        self._default_provider.currentTextChanged.connect(self._set_default_provider)
        controls.addWidget(QLabel("Default AI Provider"))
        controls.addWidget(self._default_provider, 1)
        lay1.addLayout(controls)
        self._auto_switch_btn = self._mk_toggle("Automatically switch if a provider fails", bool(self._load_app_settings().get("auto_provider_switch", True)), self._toggle_auto_provider_switch)
        lay1.addWidget(self._auto_switch_btn)
        self._add_setting("ai", card)

        # Mobile connect
        mobile = self._card("Mobile Connect", "Connect your phone and control E.V. remotely.")
        ml = mobile.layout()
        self._mobile_status = QLabel("Connection Status: Ready")
        self._mobile_phone = QLabel("Phone Name: Not connected")
        self._mobile_last = QLabel("Last Connected: Never")
        for lbl in (self._mobile_status, self._mobile_phone, self._mobile_last):
            lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            ml.addWidget(lbl)
        row = QHBoxLayout()
        self._mobile_connect_btn = QPushButton("Connect Device")
        self._mobile_connect_btn.clicked.connect(self._connect_mobile)
        self._mobile_disconnect_btn = QPushButton("Disconnect")
        self._mobile_disconnect_btn.clicked.connect(self._disconnect_mobile)
        self._mobile_qr_btn = QPushButton("Generate QR Code")
        self._mobile_qr_btn.clicked.connect(self._show_qr_code)
        row.addWidget(self._mobile_connect_btn)
        row.addWidget(self._mobile_disconnect_btn)
        row.addWidget(self._mobile_qr_btn)
        ml.addLayout(row)
        self._add_setting("integrations", mobile)

        # Attention prompts
        attention = self._card("Attention Prompts", "Control incoming message and call alerts.")
        al = attention.layout()
        self._attention_message_btn = self._mk_toggle(
            "Show incoming message prompts",
            bool(self._load_app_settings().get("attention_message_prompts", True)),
            self._toggle_attention_message_prompts,
        )
        self._attention_call_btn = self._mk_toggle(
            "Show incoming call prompts",
            bool(self._load_app_settings().get("attention_call_prompts", True)),
            self._toggle_attention_call_prompts,
        )
        al.addWidget(self._attention_message_btn)
        al.addWidget(self._attention_call_btn)
        self._add_setting("general", attention)

        # Startup
        startup = self._card("Startup", "Use E.V. with Windows startup preferences.")
        sl = startup.layout()
        self._startup_launch_btn = self._mk_toggle("Launch E.V. when Windows starts", bool(self._load_app_settings().get("show_workspace_on_startup", False)), self._toggle_startup_from_page)
        self._startup_minimized_btn = self._mk_toggle("Launch Minimized", bool(self._load_app_settings().get("launch_minimized", False)), self._toggle_launch_minimized)
        self._startup_updates_btn = self._mk_toggle("Check for updates on startup", bool(self._load_app_settings().get("check_updates_on_startup", True)), self._toggle_update_check)
        sl.addWidget(self._startup_launch_btn)
        sl.addWidget(self._startup_minimized_btn)
        sl.addWidget(self._startup_updates_btn)
        self._add_setting("general", startup)

        # Shortcuts & Pinning
        shortcuts = self._card("Shortcuts & Pinning", "Create shortcuts and pin E.V. to your Windows system.")
        shl = shortcuts.layout()
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        self._desktop_shortcut_btn = QPushButton("Create Desktop Shortcut")
        self._desktop_shortcut_btn.clicked.connect(self._handle_create_desktop_shortcut)
        self._taskbar_pin_btn = QPushButton("Pin to Taskbar")
        self._taskbar_pin_btn.clicked.connect(self._handle_pin_to_taskbar)
        
        btn_row.addWidget(self._desktop_shortcut_btn, 1)
        btn_row.addWidget(self._taskbar_pin_btn, 1)
        shl.addLayout(btn_row)
        self._add_setting("general", shortcuts)

        # Startup animation
        anim = self._card("Startup Animation", "Control how the boot sequence behaves.")
        al = anim.layout()
        self._startup_anim_enable_btn = self._mk_toggle("Enable Startup Animation", bool(self._startup_animation_enabled()), self._toggle_startup_animation_from_page)
        al.addWidget(self._startup_anim_enable_btn)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Animation Speed"))
        self._anim_speed = QComboBox()
        self._anim_speed.addItems(["Fast", "Normal", "Slow"])
        self._anim_speed.setCurrentText(self._load_app_settings().get("startup_anim_speed", "Normal"))
        speed_row.addWidget(self._anim_speed, 1)
        al.addLayout(speed_row)
        self._anim_preview_btn = QPushButton("Preview Animation")
        self._anim_preview_btn.clicked.connect(self._preview_animation)
        al.addWidget(self._anim_preview_btn)
        self._preview_progress = QProgressBar()
        self._preview_progress.setRange(0, 100)
        self._preview_progress.setValue(0)
        self._preview_progress.setTextVisible(False)
        self._preview_progress.setFixedHeight(8)
        self._preview_progress.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.05); border: none; border-radius: 4px; } QProgressBar::chunk { background: #5cd3ff; border-radius: 4px; }")
        al.addWidget(self._preview_progress)
        self._add_setting("general", anim)

        # Discord bot
        discord = self._card("Discord Bot", "Mirror E.V. between the app and your server.")
        dl = discord.layout()
        self._discord_defaults = self._load_discord_settings()
        self._discord_status = QLabel("Bot Status: Offline")
        dl.addWidget(self._discord_status)
        self._discord_token = QLineEdit()
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._discord_token.setPlaceholderText("Bot Token")
        self._discord_token.setText((self._discord_defaults.get("bot_token") or "").strip())
        self._discord_token.setCursorPosition(0)
        dl.addWidget(self._discord_token)
        self._discord_reveal = QPushButton("Reveal")
        self._discord_reveal.setCheckable(True)
        self._discord_reveal.clicked.connect(self._toggle_discord_reveal)
        dl.addWidget(self._discord_reveal)
        self._discord_channel = QLineEdit()
        self._discord_channel.setPlaceholderText("Optional Channel ID")
        self._discord_channel.setText((self._discord_defaults.get("channel_id") or "").strip())
        dl.addWidget(self._discord_channel)
        db = QHBoxLayout()
        self._discord_save = QPushButton("Save")
        self._discord_test = QPushButton("Test Connection")
        self._discord_restart = QPushButton("Restart Bot")
        self._discord_save.clicked.connect(self._save_discord_from_page)
        self._discord_test.clicked.connect(self._test_discord_from_page)
        self._discord_restart.clicked.connect(self._restart_discord_from_page)
        db.addWidget(self._discord_save)
        db.addWidget(self._discord_test)
        db.addWidget(self._discord_restart)
        dl.addLayout(db)
        self._discord_msg = QLabel("")
        self._discord_msg.setStyleSheet(f"color: {C.TEXT_DIM};")
        dl.addWidget(self._discord_msg)
        self._add_setting("integrations", discord)

        about = self._card("About E.V.", "E.V. information only.")
        ab = about.layout()
        about_grid = QGridLayout()
        about_grid.setHorizontalSpacing(22)
        about_grid.setVerticalSpacing(8)
        entries = [
            ("Version", f"v{APP_VERSION}"),
            ("Build Number", APP_BUILD),
            ("Release Date", APP_RELEASED),
        ]
        self._about_values: dict[str, QLabel] = {}
        for idx, (label, value) in enumerate(entries):
            key = QLabel(label)
            key.setStyleSheet(f"color: {C.TEXT_DIM};")
            val = QLabel(value)
            val.setStyleSheet(f"color: {C.WHITE}; font-weight: 700;")
            about_grid.addWidget(key, idx, 0)
            about_grid.addWidget(val, idx, 1)
            self._about_values[label] = val
        ab.addLayout(about_grid)
        self._add_setting("general", about)

        self._add_setting("voice", self._build_voice_card())
        self._add_setting("automation", self._build_automation_card())
        self._add_setting("advanced", self._build_advanced_card())

        return col

    def _build_summary_card(self):
        card = self._card("")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.layout().setContentsMargins(18, 18, 18, 18)
        card.layout().setSpacing(14)
        card.layout().addWidget(self._build_status_box())
        card.layout().addWidget(self._build_quick_actions_box())
        card.layout().addWidget(self._build_security_tip())
        return card

    def _build_status_box(self):
        box = self._card("System Status", "")
        lay = box.layout()
        self._sys_online = QLabel("🟢 System Online")
        self._sys_online.setStyleSheet("color: #3ddc97; font-weight: 700;")
        self._sys_note = QLabel("All systems are operational.")
        self._sys_note.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(self._sys_online)
        lay.addWidget(self._sys_note)
        self._sys_version = QLabel(f"v{APP_VERSION}")
        self._sys_platform = QLabel(platform.system())
        self._sys_provider = QLabel("Gemini")
        self._sys_updated = QLabel(time.strftime("%d %b %Y %H:%M"))
        for label, val in (("Version", self._sys_version), ("Platform", self._sys_platform), ("Current AI Provider", self._sys_provider), ("Last Updated", self._sys_updated)):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch(1)
            row.addWidget(val)
            lay.addLayout(row)
        return box

    def _build_quick_actions_box(self):
        box = self._card("Quick Actions", "")
        lay = box.layout()
        actions = [
            ("Restart E.V.", QStyle.StandardPixmap.SP_BrowserReload, self._restart_app),
            ("Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload_config),
            ("Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder),
            ("View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs),
            ("Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates),
        ]
        for text, icon_kind, slot in actions:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(self.style().standardIcon(icon_kind))
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        return box

    def _build_security_tip(self):
        box = QFrame()
        box.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        title = QLabel("Security Tip")
        title.setStyleSheet("color: #ffb648; font-weight: 700;")
        body = QLabel('"Never share your API keys with anyone."')
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)
        lay.addWidget(body)
        return box

    def _load_api_defaults(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_api_defaults()
        return {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "os_system": platform.system(),
        }

    def _load_app_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_app_settings()
        return _default_app_settings()

    def _load_discord_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_discord_settings()
        return _default_discord_settings()

    def _startup_animation_enabled(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._startup_animation_enabled()
        return True

    def _set_setting(self, key: str, value):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            settings = self._ctrl()._win._load_app_settings()
            settings[key] = value
            self._ctrl()._win._save_app_settings(settings)

    def _open_api_keys(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._show_setup(self._ctrl()._win._load_api_defaults())

    def _test_provider(self, setting_key: str):
        if setting_key == "gemini":
            msg = "Google Gemini key detected." if self._load_api_defaults().get("gemini_api_key") else "Google Gemini key missing."
        else:
            msg = "OpenRouter key detected." if self._load_api_defaults().get("openrouter_api_key") else "OpenRouter key missing."
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: {msg}")
        self.refresh()

    def _connect_mobile(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            self._mobile_connect_btn.setText("Connecting...")
            target._show_remote_connect()
            QTimer.singleShot(1100, lambda: self._mobile_connect_btn.setText("Connect Device"))

    def _disconnect_mobile(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Mobile Connect session closed.")
        self._mobile_status.setText("Connection Status: Disconnected")
        self._mobile_phone.setText("Phone Name: Not connected")
        self._mobile_last.setText("Last Connected: Never")

    def _show_qr_code(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            target._show_remote_connect()

    def _toggle_startup_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_button()

    def _toggle_launch_minimized(self, checked: bool):
        self._set_setting("launch_minimized", bool(checked))

    def _toggle_update_check(self, checked: bool):
        self._set_setting("check_updates_on_startup", bool(checked))

    def _toggle_startup_animation_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_animation_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_animation_button()

    def _set_default_provider(self, text: str):
        provider = "Gemini" if (text or "").strip().lower().startswith("google") else "OpenRouter"
        self._set_setting("default_ai_provider", provider)
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Default AI provider set to {provider}.")

    def _toggle_auto_provider_switch(self, checked: bool):
        self._set_setting("auto_provider_switch", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Auto provider switch {'enabled' if checked else 'disabled'}.")

    def _toggle_attention_message_prompts(self, checked: bool):
        self._set_setting("attention_message_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming message prompts {'enabled' if checked else 'disabled'}.")

    def _toggle_attention_call_prompts(self, checked: bool):
        self._set_setting("attention_call_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming call prompts {'enabled' if checked else 'disabled'}.")

    def _preview_animation(self):
        self._preview_progress.setValue(0)
        if hasattr(self, "_preview_timer") and self._preview_timer:
            try:
                self._preview_timer.stop()
            except Exception:
                pass
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._tick_preview)
        self._preview_timer.start(24)

    def _tick_preview(self):
        value = min(100, self._preview_progress.value() + 4)
        self._preview_progress.setValue(value)
        if value >= 100 and hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Startup animation preview finished.")

    def _toggle_discord_reveal(self, checked: bool):
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _save_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._discord_token_input = self._discord_token
            self._ctrl()._win._discord_channel_input = self._discord_channel
            self._ctrl()._win._save_discord_token()
            self._discord_status.setText("Bot Status: Saved")
            self.refresh()

    def _test_discord_from_page(self):
        self._save_discord_from_page()
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._start_discord_bot()
            self._ctrl()._win._stop_discord_bot()
            self._discord_status.setText("Bot Status: Test sent")
            self._discord_msg.setText("Connected as E.V.#9649" if self._discord_token.text().strip() else "Bot Offline")

    def _restart_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._stop_discord_bot()
            self._ctrl()._win._start_discord_bot()
            self._discord_status.setText("Bot Status: Restarted")

    def _restart_app(self):
        if self._ctrl() and hasattr(self._ctrl(), "_restart_app"):
            self._ctrl()._restart_app()

    def _reload_config(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._load_api_defaults()
            self._ctrl()._win._load_discord_settings()
            if hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Configuration reloaded.")
            self.refresh()

    def _open_data_folder(self):
        try:
            os.startfile(str(CONFIG_DIR))
        except Exception:
            pass

    def _view_logs(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception:
            pass

    def _check_updates(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Update check requested.")

    def refresh(self):
        api = self._load_api_defaults()
        app = self._load_app_settings()
        discord = self._load_discord_settings()
        for widget in (
            getattr(self, "_default_provider", None),
            getattr(self, "_auto_switch_btn", None),
            getattr(self, "_attention_message_btn", None),
            getattr(self, "_attention_call_btn", None),
            getattr(self, "_startup_launch_btn", None),
            getattr(self, "_startup_minimized_btn", None),
            getattr(self, "_startup_updates_btn", None),
            getattr(self, "_startup_anim_enable_btn", None),
            getattr(self, "_discord_token", None),
            getattr(self, "_discord_channel", None),
            getattr(self, "_discord_reveal", None),
        ):
            if widget is not None:
                widget.blockSignals(True)
        try:
            self._gemini_status.setText("Connected" if api.get("gemini_api_key") else "Not connected")
            self._or_status.setText("Connected" if api.get("openrouter_api_key") else "Not connected")
            self._gemini_key.setText(self._provider_key_preview(api.get("gemini_api_key", "")))
            self._or_key.setText(self._provider_key_preview(api.get("openrouter_api_key", "")))
            self._default_provider.setCurrentText("Google Gemini" if app.get("default_ai_provider", "Gemini") == "Gemini" else "OpenRouter")
            self._auto_switch_btn.setChecked(bool(app.get("auto_provider_switch", True)))
            self._attention_message_btn.setChecked(bool(app.get("attention_message_prompts", True)))
            self._attention_call_btn.setChecked(bool(app.get("attention_call_prompts", True)))
            self._startup_launch_btn.setChecked(bool(app.get("show_workspace_on_startup", False)))
            self._startup_minimized_btn.setChecked(bool(app.get("launch_minimized", False)))
            self._startup_updates_btn.setChecked(bool(app.get("check_updates_on_startup", True)))
            self._startup_anim_enable_btn.setChecked(bool(self._startup_animation_enabled()))
            self._discord_token.setText((discord.get("bot_token") or "").strip())
            self._discord_channel.setText((discord.get("channel_id") or "").strip())
        finally:
            for widget in (
                getattr(self, "_default_provider", None),
                getattr(self, "_auto_switch_btn", None),
                getattr(self, "_attention_message_btn", None),
                getattr(self, "_attention_call_btn", None),
                getattr(self, "_startup_launch_btn", None),
                getattr(self, "_startup_minimized_btn", None),
                getattr(self, "_startup_updates_btn", None),
                getattr(self, "_startup_anim_enable_btn", None),
                getattr(self, "_discord_token", None),
                getattr(self, "_discord_channel", None),
                getattr(self, "_discord_reveal", None),
            ):
                if widget is not None:
                    widget.blockSignals(False)
        enabled = bool(discord.get("enabled", False))
        token = (discord.get("bot_token") or "").strip()
        if enabled and token:
            self._discord_status.setText("Bot Status: Online")
            self._discord_msg.setText("Connected as E.V.#9649")
        elif token:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Bot Offline")
        else:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Token required")
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._sys_provider.setText("Gemini" if app.get("default_ai_provider", "Gemini") == "Gemini" else "OpenRouter")
        self._refresh_extra_cards()

    def _handle_create_desktop_shortcut(self):
        success, path_or_err = self._create_desktop_shortcut_logic()
        if success:
            QMessageBox.information(
                self, 
                "Success", 
                f"Desktop shortcut created successfully at:\n{path_or_err}"
            )
        else:
            QMessageBox.warning(
                self, 
                "Error", 
                f"Failed to create desktop shortcut:\n{path_or_err}"
            )

    def _handle_pin_to_taskbar(self):
        success, msg = self._pin_app_to_taskbar_logic()
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.warning(
                self, 
                "Taskbar Pinning", 
                msg
            )

    def _create_desktop_shortcut_logic(self):
        try:
            import os
            import sys
            import shutil
            import subprocess
            from pathlib import Path
            import winreg
            
            # Find the correct Desktop folder path using registry (OneDrive safe!)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                desktop_raw, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                desktop_dir = Path(os.path.expandvars(desktop_raw))
            except Exception:
                desktop_dir = Path(os.path.expanduser("~")) / "Desktop"
                
            desktop_dir.mkdir(parents=True, exist_ok=True)
            shortcut_path = desktop_dir / "E.V.lnk"
            
            # Base variables — resolved from the app location, not the CWD
            base_dir = Path(BASE_DIR)
            script_path = base_dir / "main.py"
            icon_path = base_dir / "assets" / "ev_logo.ico"
            
            python_exe = sys.executable
            if not python_exe:
                python_exe = shutil.which("pythonw") or shutil.which("python") or "pythonw"
                
            shortcut_target = python_exe
            shortcut_args = f'"{script_path}"'
            if getattr(sys, "frozen", False):
                shortcut_target = python_exe
                shortcut_args = ""
                
            powershell_exe = shutil.which("powershell.exe") or "powershell"
            
            def _ps_escape(value: str) -> str:
                return value.replace("'", "''")
                
            icon_value = str(icon_path) if icon_path.exists() else ""
            ps1_script = "\n".join([
                "$WshShell = New-Object -ComObject WScript.Shell",
                f"$Shortcut = $WshShell.CreateShortcut('{_ps_escape(str(shortcut_path))}')",
                f"$Shortcut.TargetPath = '{_ps_escape(shortcut_target)}'",
                f"$Shortcut.Arguments = '{_ps_escape(shortcut_args)}'",
                f"$Shortcut.WorkingDirectory = '{_ps_escape(str(base_dir))}'",
                "$Shortcut.WindowStyle = 7",
                "$Shortcut.Description = 'Launch E.V.'",
                f"if ('{_ps_escape(icon_value)}') {{ $Shortcut.IconLocation = '{_ps_escape(icon_value)},0' }}",
                "$Shortcut.Save()",
            ])
            
            # Written to a runtime file; config/create_desktop_shortcut.ps1 is the
            # portable sample that ships with the project.
            ps1_path = base_dir / "config" / ".runtime_shortcut.ps1"
            ps1_path.write_text(ps1_script, encoding="utf-8")
            
            subprocess.run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            
            # Write marker file
            marker_path = base_dir / "config" / ".desktop_shortcut_created"
            marker_path.write_text("created", encoding="utf-8")
            
            return True, str(shortcut_path)
        except Exception as e:
            return False, str(e)

    def _pin_app_to_taskbar_logic(self):
        try:
            import os
            import sys
            import shutil
            import subprocess
            from pathlib import Path
            
            # Ensure desktop shortcut exists first
            success, path_or_err = self._create_desktop_shortcut_logic()
            if not success:
                return False, f"Failed to create desktop shortcut first: {path_or_err}"
                
            shortcut_path = Path(path_or_err)
            if not shortcut_path.exists():
                return False, "Shortcut file does not exist."
                
            powershell_exe = shutil.which("powershell.exe") or "powershell"
            
            # COM pin script
            def _ps_escape(value: str) -> str:
                return value.replace("'", "''")
                
            pin_script = "\n".join([
                "$Shell = New-Object -ComObject Shell.Application",
                f"$Folder = $Shell.NameSpace('{_ps_escape(str(shortcut_path.parent))}')",
                f"$Item = $Folder.ParseName('{_ps_escape(shortcut_path.name)}')",
                "$Verb = $Item.Verbs() | Where-Object { $_.Name.Replace('&', '') -match 'Pin to taskbar' }",
                "if ($Verb) { $Verb.DoIt(); exit 0 } else { exit 1 }"
            ])
            
            res = subprocess.run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", pin_script],
                capture_output=True
            )
            
            if res.returncode == 0:
                return True, "E.V. has been pinned to your Taskbar!"
            else:
                return False, "Windows restricts programmatic taskbar pinning. Please right-click the 'E.V.lnk' shortcut on your Desktop and select 'Pin to taskbar', or drag it directly onto your taskbar."
        except Exception as e:
            return False, f"Error pinning to taskbar: {e}"

class SmartDevicesSection(QFrame):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._service = SmartHomeService()
        self._snapshot = ""
        self._device_tiles: list[_DeviceTile] = []
        self._card_anims: list[QPropertyAnimation] = []
        self._selected_device: dict[str, object] | None = None

        self.setObjectName("SmartDevicesSection")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f"""
            QFrame#SmartDevicesSection {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._title_lbl = QLabel("SMART DEVICES")
        self._title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        self._subtitle_lbl = QLabel("Quick access to your connected home devices.")
        self._subtitle_lbl.setFont(QFont("Segoe UI", 8))
        self._subtitle_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        title_box.addWidget(self._title_lbl)
        title_box.addWidget(self._subtitle_lbl)
        header.addLayout(title_box, 1)

        self._count_chip = QLabel("0 devices")
        self._count_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_chip.setStyleSheet(
            f"QLabel {{ background: rgba(255,255,255,0.03); color: {C.PRI}; border: 1px solid rgba(255,255,255,0.07); border-radius: 10px; padding: 4px 10px; }}"
        )
        header.addWidget(self._count_chip)

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(32, 32)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.08);
                border: 1px solid {C.PRI};
            }}
        """)
        self._refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        header.addWidget(self._refresh_btn)

        self._open_home_btn = QPushButton("Add Device")
        self._open_home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_home_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(92, 211, 255,0.10);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 9px;
                padding: 0 14px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.16);
            }}
        """)
        self._open_home_btn.clicked.connect(self._open_ev_home)
        header.addWidget(self._open_home_btn)
        root.addLayout(header)

        self._empty_card = QWidget()
        self._empty_card.setStyleSheet("background: transparent;")
        empty_lay = QVBoxLayout(self._empty_card)
        empty_lay.setContentsMargins(6, 4, 6, 4)
        empty_lay.setSpacing(6)
        empty_title = QLabel("No Smart Devices Connected")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        empty_title.setStyleSheet(f"color: {C.WHITE};")
        empty_desc = QLabel("Connect your first smart device to control it directly from your dashboard.")
        empty_desc.setWordWrap(True)
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_desc.setFont(QFont("Segoe UI", 8))
        empty_desc.setStyleSheet(f"color: {C.TEXT_DIM};")
        empty_btn = QPushButton("Open Home")
        empty_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        empty_btn.setFixedWidth(160)
        empty_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(92, 211, 255,0.12);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 10px;
                min-height: 34px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.18);
            }}
        """)
        empty_btn.clicked.connect(self._open_ev_home)
        empty_lay.addStretch(1)
        empty_lay.addWidget(empty_title)
        empty_lay.addWidget(empty_desc)
        empty_lay.addWidget(empty_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_lay.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._grid_page = QWidget()
        self._grid_page.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_page)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setHorizontalSpacing(12)
        self._grid_layout.setVerticalSpacing(12)

        self._row_page = QWidget()
        self._row_page.setStyleSheet("background: transparent;")
        self._row_layout = QHBoxLayout(self._row_page)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(12)

        self._cards_stack = QStackedWidget()
        self._cards_stack.setStyleSheet("background: transparent; border: none;")
        self._cards_stack.addWidget(self._grid_page)
        self._cards_stack.addWidget(self._row_page)
        self._scroll.setWidget(self._cards_stack)
        root.addWidget(self._empty_card)
        root.addWidget(self._scroll, 1)

        self._panel = QFrame(self)
        self._panel.setObjectName("SmartDevicePanel")
        self._panel.setStyleSheet(f"""
            QFrame#SmartDevicePanel {{
                background: rgba(8, 9, 13, 245);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: rgba(92, 211, 255,0.08);
                border: 1px solid {C.PRI};
            }}
        """)
        self._panel.setVisible(False)
        self._panel.setMinimumSize(280, 260)
        self._panel_effect = QGraphicsOpacityEffect(self._panel)
        self._panel_effect.setOpacity(0.0)
        self._panel.setGraphicsEffect(self._panel_effect)
        self._panel_lay = QVBoxLayout(self._panel)
        self._panel_lay.setContentsMargins(14, 12, 14, 12)
        self._panel_lay.setSpacing(8)

        panel_top = QHBoxLayout()
        panel_top.setSpacing(6)
        self._panel_name = QLabel("Device")
        self._panel_name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._panel_name.setStyleSheet(f"color: {C.WHITE};")
        panel_top.addWidget(self._panel_name, 1)
        self._panel_close = QPushButton("X")
        self._panel_close.setFixedSize(28, 28)
        self._panel_close.clicked.connect(self._close_panel)
        panel_top.addWidget(self._panel_close)
        self._panel_lay.addLayout(panel_top)

        self._panel_meta = QLabel("")
        self._panel_meta.setWordWrap(True)
        self._panel_meta.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._panel_lay.addWidget(self._panel_meta)

        self._panel_status = QLabel("")
        self._panel_status.setStyleSheet(f"color: {C.GREEN}; font-weight: 700;")
        self._panel_lay.addWidget(self._panel_status)

        self._panel_controls = QVBoxLayout()
        self._panel_controls.setSpacing(10)
        self._panel_lay.addLayout(self._panel_controls)
        self._panel_lay.addStretch(1)

        self._panel_actions = QHBoxLayout()
        self._panel_actions.setSpacing(8)
        self._panel_lay.addLayout(self._panel_actions)

        self._panel_hint = QLabel("")
        self._panel_hint.setWordWrap(True)
        self._panel_hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._panel_lay.addWidget(self._panel_hint)

        self._poll_tmr = QTimer(self)
        self._poll_tmr.timeout.connect(lambda: self.refresh(force=False))
        self._poll_tmr.start(2500)

        self.refresh(force=True)

    def _controller_bridge(self):
        return self._controller

    def _open_ev_home(self):
        bridge = self._controller_bridge()
        if bridge and hasattr(bridge, "_set_page"):
            bridge._set_page("home")

    def _snapshot_devices(self, devices: list[dict[str, object]]) -> str:
        payload = [
            (
                str(d.get("id", "")),
                int(d.get("updated_at") or 0),
                str(d.get("name", "")),
                bool(d.get("is_on")),
                str(d.get("room", "")),
                str(d.get("device_type", "")),
                str(d.get("manufacturer", "")),
            )
            for d in devices
        ]
        return json.dumps(payload, ensure_ascii=True, sort_keys=False)

    def refresh(self, force: bool = False):
        devices = self._service.list_devices()
        snapshot = self._snapshot_devices(devices)
        if not force and snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self._count_chip.setText(f"{len(devices)} device(s)")
        self._empty_card.setVisible(not devices)
        self._scroll.setVisible(bool(devices))
        self._rebuild_device_cards(devices)
        if self._panel.isVisible() and self._selected_device:
            device_id = str(self._selected_device.get("id", ""))
            device = self._find_device(device_id)
            if device:
                self._selected_device = device
                self._populate_panel(device)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild_device_cards(self, devices: list[dict[str, object]]):
        self._clear_layout(self._grid_layout)
        self._clear_layout(self._row_layout)
        self._device_tiles.clear()
        self._card_anims.clear()

        if not devices:
            self._cards_stack.setCurrentIndex(0)
            self._close_panel()
            return

        count = len(devices)
        if count <= 3:
            self._cards_stack.setCurrentIndex(1)
            self._clear_layout(self._row_layout)
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._row_layout.addWidget(tile)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            self._row_layout.addStretch(1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif count <= 6:
            self._cards_stack.setCurrentIndex(0)
            columns = 3 if count > 3 else count
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._grid_layout.addWidget(tile, idx // columns, idx % columns)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            last_row = (count - 1) // columns + 1
            self._grid_layout.setRowStretch(last_row, 1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self._cards_stack.setCurrentIndex(1)
            self._clear_layout(self._row_layout)
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._row_layout.addWidget(tile)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            self._row_layout.addStretch(1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _animate_card(self, widget: QWidget, index: int):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._card_anims.append(anim)
        QTimer.singleShot(index * 45, anim.start)

    def _device_id_from_input(self, device_or_id):
        if isinstance(device_or_id, dict):
            return str(device_or_id.get("id", ""))
        return str(device_or_id or "")

    def _find_device(self, device_id: str) -> dict[str, object] | None:
        for device in self._service.list_devices():
            if str(device.get("id", "")) == device_id:
                return device
        return None

    def _apply_tile_action(self, device_id: str, action: str, payload: dict):
        try:
            self._service.execute_device_action(device_id, action, payload)
        except Exception:
            return
        self.refresh(force=True)
        device = self._find_device(device_id)
        if device:
            self._selected_device = device
            self._open_device_panel(device)

    def _open_device_panel(self, device_or_id):
        try:
            device_id = self._device_id_from_input(device_or_id)
            device = self._find_device(device_id)
            if not device:
                return
            self._selected_device = device
            self._populate_panel(device)
            self._show_panel()
        except Exception:
            return

    def _show_panel(self):
        try:
            self._position_panel()
            self._panel.setVisible(True)
            self._panel.raise_()
            self._panel_effect.setOpacity(1.0)
        except Exception:
            self._panel.hide()
            self._panel_effect.setOpacity(0.0)

    def _close_panel(self):
        if not self._panel.isVisible():
            return
        self._panel.hide()
        self._panel_effect.setOpacity(0.0)

    def _clear_panel_controls(self):
        self._clear_layout(self._panel_controls)
        self._clear_layout(self._panel_actions)

    def _populate_panel(self, device: dict[str, object]):
        try:
            self._clear_panel_controls()
            self._clear_layout(self._panel_actions)
            name = str(device.get("name", "Device"))
            room = str(device.get("room", ""))
            device_type = str(device.get("device_type", "device")).lower()
            is_on = bool(device.get("is_on"))
            traits = device.get("traits") if isinstance(device.get("traits"), dict) else {}

            self._panel_name.setText(name)
            self._panel_meta.setText(
                f"Room: {room or 'Unassigned'}\nType: {device_type.title()}\nManufacturer: {device.get('manufacturer', '')}\nConnection: Connected"
            )
            self._panel_status.setText("ON" if is_on else "OFF")
            self._panel_hint.setText("Click outside the panel to close.")

            power_btn = QPushButton("Power")
            power_btn.clicked.connect(lambda: self._apply_tile_action(str(device.get("id", "")), "power", {"is_on": not is_on}))
            self._panel_actions.addWidget(power_btn)

            forget_btn = QPushButton("Forget")
            forget_btn.clicked.connect(lambda: self._forget_device(str(device.get("id", ""))))
            self._panel_actions.addWidget(forget_btn)

            rename_btn = QPushButton("Rename")
            rename_btn.clicked.connect(lambda: self._rename_device(str(device.get("id", "")), name))
            self._panel_actions.addWidget(rename_btn)

            if device_type == "fan":
                speed = int(traits.get("speed", 4) or 4)
                lbl = QLabel(f"Speed {speed}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(1, 6)
                slider.setValue(speed)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "speed", {"speed": value}))
                self._panel_controls.addWidget(slider)
            elif device_type == "light":
                brightness = int(traits.get("brightness", 75) or 75)
                lbl = QLabel(f"Brightness {brightness}%")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(1, 100)
                slider.setValue(brightness)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "brightness", {"brightness": value}))
                self._panel_controls.addWidget(slider)
                color_btn = QPushButton("Color")
                color_btn.clicked.connect(lambda: self._pick_color(device))
                self._panel_controls.addWidget(color_btn)
            elif device_type == "ac":
                temperature = int(traits.get("temperature", 24) or 24)
                lbl = QLabel(f"Temperature {temperature}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(16, 30)
                slider.setValue(temperature)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "temperature", {"temperature": value}))
                self._panel_controls.addWidget(slider)
            elif device_type in ("tv", "speaker"):
                volume = int(traits.get("volume", 18) or 18)
                lbl = QLabel(f"Volume {volume}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 100)
                slider.setValue(volume)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "volume", {"volume": value}))
                self._panel_controls.addWidget(slider)
            elif device_type == "plug":
                usage = traits.get("energy_usage", traits.get("power_usage", "N/A"))
                lbl = QLabel(f"Energy usage: {usage}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
            else:
                lbl = QLabel("Primary controls are available from the card below.")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
        except Exception:
            return

    def _pick_color(self, device: dict[str, object]):
        color = QColorDialog.getColor(QColor("#5cd3ff"), self, "Pick Light Color")
        if color.isValid():
            self._apply_tile_action(str(device.get("id", "")), "color", {"color": color.name()})

    def _rename_device(self, device_id: str, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Device", "New name:", text=current_name)
        if ok and new_name.strip():
            try:
                self._service.rename_device(device_id, new_name.strip())
            except Exception:
                return
            self.refresh(force=True)

    def _forget_device(self, device_id: str):
        try:
            self._service.forget_device(device_id)
        except Exception:
            return
        self._close_panel()
        self.refresh(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._panel.isVisible():
            self._position_panel()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh(force=True)

    def _position_panel(self):
        panel_w = min(330, max(270, int(self.width() * 0.28)))
        panel_h = min(340, max(240, int(self.height() * 0.45)))
        x = max(12, self.width() - panel_w - 12)
        y = 12
        self._panel.setGeometry(x, y, panel_w, panel_h)

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class EVUI:
    def __init__(self, face_path: str, size=None, *, show_immediately: bool = True):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationDisplayName("E.V.")
        self._app.setWindowIcon(self._make_app_icon())
        try:
            current_store = workspace_store()
            current_store.rollover_active_conversation_on_startup()
        except Exception:
            pass
        self._win = MainWindow(face_path)
        self._win.set_settings_bridge(self)
        self._discord_service = DiscordBotService(
            status_callback=self._win.discord_status_changed.emit,
            log_callback=self._win._log_sig.emit,
        )
        self._discord_service.bind_app_submitter(self._win.submit_command)
        self._win.discord_config_changed.connect(self._on_discord_config_changed)
        self._win.on_chat_event = self._on_chat_event
        self._app.aboutToQuit.connect(self._discord_service.stop)
        self._launcher = FloatingLauncher()
        self._command_bar = CommandBar()
        self._workspace_sidebar = WorkspaceSidebar()
        self._control_panel: LauncherControlPanel | None = None
        self._boot_overlay: BootSequenceOverlay | None = None
        self._app_settings_cache: dict | None = None
        self._launcher.single_clicked.connect(self._toggle_command_bar)
        self._launcher.double_clicked.connect(self._show_control_panel)
        self._launcher.action_requested.connect(self._handle_launcher_action)
        self._launcher.position_changed.connect(self._save_launcher_position)
        self._command_bar.submitted.connect(self._submit_command)
        self._command_bar.attach_clicked.connect(self._browse_attachment)
        self._command_bar.mic_clicked.connect(self._toggle_mute)
        self._command_bar.developer_clicked.connect(self._open_developer_mode_dialog)
        self._workspace_sidebar.command_submitted.connect(self._submit_command)
        self._workspace_sidebar.attach_requested.connect(self._browse_attachment)
        self._workspace_sidebar.mic_requested.connect(self._toggle_mute)
        self._workspace_sidebar.close_requested.connect(self._close_workspace_sidebar)
        self._win._inline_workspace.attach_requested.connect(self._browse_attachment)
        self._win._inline_workspace.mic_requested.connect(self._toggle_mute)
        self._win._inline_workspace.command_submitted.connect(self._submit_command)
        self._win.minimized.connect(self._on_minimized)
        self._win._state_sig.connect(self._sync_launcher_state)
        self._tray = QSystemTrayIcon(self._make_app_icon(), self._app)
        self._tray.setToolTip("E.V.")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.setContextMenu(self._build_tray_menu())
        self._tray.show()
        self._win._log_sig.connect(self._workspace_sidebar.append_log)
        self._win._log_sig.connect(self._win._inline_workspace.append_log)
        self._win._task_workspace_sig.connect(self._workspace_sidebar.apply_task_workspace)
        self._on_discord_config_changed(self._win._load_discord_settings())
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.show_at(int(launcher_pos[0]), int(launcher_pos[1]))
            except Exception:
                self._launcher.show_at()
        else:
            self._launcher.show_at()
        if bool(self._load_app_settings().get("show_workspace_on_startup", False)):
            self._workspace_sidebar.show_workspace(animate=False)
        else:
            self._workspace_sidebar.hide_workspace(animate=False)
        self.set_dashboard_page(getattr(self._win, "_current_page", "dashboard") == "dashboard")
        self._apply_developer_mode_ui()
        if show_immediately:
            self.show_main()
        self.root = _RootShim(self._app)

    def _make_app_icon(self) -> QIcon:
        return _logo_icon()

    def show_main(self):
        try:
            self._win.showNormal()
        except Exception:
            self._win.show()
        self._win.raise_()
        self._win.activateWindow()
        if self._launcher.isVisible():
            try:
                self._launcher.raise_()
                self._launcher.activateWindow()
            except Exception:
                pass

    def set_dashboard_page(self, enabled: bool):
        try:
            if enabled:
                if not self._launcher.isVisible():
                    self._show_floating_icon()
            else:
                self._command_bar.hide()
                self._workspace_sidebar.hide_workspace(animate=False)
                self._launcher.hide()
        except Exception:
            pass

    def hide_main(self):
        self._command_bar.hide()
        self._launcher.hide()
        self._win.hide()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")
        self._app_settings_cache = dict(settings)

    def _save_launcher_position(self, x: int, y: int):
        try:
            settings = self._load_app_settings()
            settings["launcher_pos"] = [int(x), int(y)]
            self._save_app_settings(settings)
        except Exception:
            pass

    def _open_developer_mode_dialog(self):
        try:
            dialog = DeveloperModeDialog(self._win, settings=self._load_app_settings())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                settings = dialog.get_settings()
                self._save_app_settings(settings)
                self._apply_developer_mode_ui()
        except Exception:
            pass

    def _apply_developer_mode_ui(self):
        try:
            settings = self._load_app_settings()
            enabled = bool(settings.get("developer_mode_enabled", False))
            workspace = str(settings.get("developer_mode_workspace", "")).strip()
            if hasattr(self._win, "_developer_card") and hasattr(self._win, "_developer_status_lbl"):
                if enabled:
                    workspace_text = workspace or "No folder selected"
                    self._win._developer_status_lbl.setText(
                        f"Developer mode is on • {workspace_text}"
                    )
                    self._win._developer_card.show()
                    self._win._developer_card.raise_()
                else:
                    self._win._developer_card.hide()
        except Exception:
            pass

    def _sync_launcher_state(self, state: str):
        state = (state or "idle").strip().lower()
        detail = {
            "listening": "Ready",
            "thinking": "Thinking...",
            "processing": "Executing task...",
            "speaking": "Speaking",
            "muted": "Muted",
        }.get(state, "Ready")
        try:
            self._launcher.set_state(state, detail)
        except Exception:
            pass

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setEnabled(True)
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setEnabled(True)
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log(f"ERR: startup animation setting failed: {e}")
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Startup animation {state}.")

    def _should_play_boot_sequence(self) -> bool:
        if platform.system() != "Windows":
            return False
        if not _launched_from_windows_startup():
            return False
        if not self._win._startup_enabled():
            return False
        if not self._startup_animation_enabled():
            return False
        settings = self._load_app_settings()
        boot_stamp = _current_boot_stamp()
        last_boot = int(settings.get("last_boot_stamp") or 0)
        played = bool(settings.get("boot_sequence_played"))
        if last_boot != boot_stamp:
            settings["last_boot_stamp"] = boot_stamp
            settings["boot_sequence_played"] = False
            self._save_app_settings(settings)
            played = False
        return not played

    def _mark_boot_sequence_played(self):
        try:
            settings = self._load_app_settings()
            settings["last_boot_stamp"] = _current_boot_stamp()
            settings["boot_sequence_played"] = True
            self._save_app_settings(settings)
        except Exception:
            pass

    def play_boot_sequence(self, finished_callback=None):
        if self._boot_overlay is not None:
            try:
                self._boot_overlay.deleteLater()
            except Exception:
                pass
            self._boot_overlay = None
        self.hide_main()
        overlay = BootSequenceOverlay()
        self._boot_overlay = overlay

        device_name = platform.node() or os.environ.get("COMPUTERNAME") or "DEVICE"

        def _done():
            self._mark_boot_sequence_played()
            try:
                self.show_main()
            finally:
                if self._boot_overlay is not None:
                    try:
                        self._boot_overlay.deleteLater()
                    except Exception:
                        pass
                    self._boot_overlay = None
                if finished_callback:
                    finished_callback()

        overlay.finished.connect(_done)
        overlay.start(device_name=device_name, greeting_name="Suryaansh")

    # Thread-safe helpers for driving the boot overlay from background threads
    def boot_add_step(self, text: str):
        try:
            if not self._boot_overlay:
                return None
            QTimer.singleShot(0, lambda: self._boot_overlay.add_step(text))
        except Exception:
            pass

    def boot_set_step_status(self, text: str, status: str):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_step_status(text, status))
        except Exception:
            pass

    def boot_set_progress(self, percent: int, tip: str | None = None):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_progress(percent, tip))
        except Exception:
            pass

    def _build_tray_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(8, 8, 8, 245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
        """)

        open_app_action = menu.addAction("Open App")
        open_action = menu.addAction("Open Workspace")
        close_action = menu.addAction("Close Workspace")
        startup_action = menu.addAction("Show Workspace On Startup")
        startup_action.setCheckable(True)
        startup_action.setChecked(bool(self._load_app_settings().get("show_workspace_on_startup", False)))
        show_icon_action = menu.addAction("Show Floating Icon")
        hide_icon_action = menu.addAction("Hide Floating Icon")
        menu.addSeparator()
        restart_action = menu.addAction("Restart")
        quit_action = menu.addAction("Quit")

        open_app_action.triggered.connect(self.show_main)
        open_action.triggered.connect(self._show_workspace_sidebar)
        close_action.triggered.connect(self._close_workspace_sidebar)
        startup_action.triggered.connect(lambda: self._toggle_workspace_on_startup(startup_action.isChecked()))
        show_icon_action.triggered.connect(self._show_floating_icon)
        hide_icon_action.triggered.connect(self._hide_launcher_with_protection)
        restart_action.triggered.connect(self._restart_app)
        quit_action.triggered.connect(self._app.quit)
        return menu

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_command_bar()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_control_panel()

    def _on_minimized(self):
        if self._launcher.isVisible():
            self._launcher.raise_()
        self._command_bar.hide()

    def _toggle_command_bar(self):
        if self._command_bar.isVisible():
            self._command_bar.hide()
        else:
            self._command_bar.show_near(self._launcher)

    def _toggle_workspace_sidebar(self):
        if self._workspace_sidebar.isVisible():
            self._close_workspace_sidebar()
        else:
            self._show_workspace_sidebar()

    def _show_workspace_sidebar(self):
        self._workspace_sidebar.show_workspace()
        self._launcher.hide()

    def _close_workspace_sidebar(self):
        self._workspace_sidebar.hide_workspace()
        self._show_floating_icon()

    def _show_floating_icon(self):
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.show_at(int(launcher_pos[0]), int(launcher_pos[1]))
                return
            except Exception:
                pass
        self._launcher.show_at()

    def _restart_app(self):
        try:
            args = _hidden_launch_args("--startup" if _launched_from_windows_startup() else "")
            args = [arg for arg in args if arg]
            kwargs = {"cwd": str(BASE_DIR)}
            if _OS == "Windows":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(args, **kwargs)
        except Exception as exc:
            self._win.write_log(f"ERR: Restart failed: {exc}")
        self._app.quit()

    def _toggle_workspace_on_startup(self, enabled: bool):
        try:
            settings = self._load_app_settings()
            settings["show_workspace_on_startup"] = bool(enabled)
            self._save_app_settings(settings)
        except Exception:
            pass

    def _hide_launcher_with_protection(self):
        self._show_hide_launcher_confirm()

    def _show_hide_launcher_confirm(self):
        panel = LauncherControlPanel(
            startup_workspace=bool(self._load_app_settings().get("show_workspace_on_startup", False)),
            on_open=self._show_workspace_sidebar,
            on_close=self._close_workspace_sidebar,
            on_toggle_startup=self._toggle_workspace_on_startup,
            on_hide_icon=self._launcher.hide,
            on_restart=self._restart_app,
            on_quit=self._app.quit,
            on_open_app=self.show_main,
            on_show_icon=self._show_floating_icon,
            on_open_dev=self._open_developer_mode_dialog,
        )
        self._control_panel = panel
        self._position_control_panel(panel)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def _position_control_panel(self, panel: LauncherControlPanel):
        try:
            geo = self._launcher.geometry()
            panel.adjustSize()
            panel.move(max(20, geo.left() - panel.width() - 16), max(20, geo.top() - 10))
        except Exception:
            screen = QApplication.primaryScreen().availableGeometry()
            panel.move(screen.center().x() - panel.width() // 2, screen.center().y() - panel.height() // 2)

    def _show_control_panel(self):
        self._show_hide_launcher_confirm()

    def _handle_launcher_action(self, action: str):
        action = (action or "").strip().lower()
        if action == "open_app":
            self.show_main()
        elif action == "open_workspace":
            self._show_workspace_sidebar()
        elif action == "close_workspace":
            self._close_workspace_sidebar()
        elif action == "show_icon":
            self._show_floating_icon()
        elif action == "hide_icon":
            self._hide_launcher_with_protection()
        elif action == "restart":
            self._restart_app()
        elif action == "quit":
            self._app.quit()
        elif action == "toggle_startup":
            current = bool(self._load_app_settings().get("show_workspace_on_startup", False))
            self._toggle_workspace_on_startup(not current)

    def _submit_command(self, text: str):
        self._win.submit_command(text)

    def _browse_attachment(self):
        self._win._browse_attachment()

    def _toggle_mute(self):
        self._win._toggle_mute()

    def _on_chat_event(self, event: dict):
        try:
            self._discord_service.mirror_chat_event(event or {})
        except Exception:
            pass
        try:
            self._workspace_sidebar.record_chat_event(event or {})
        except Exception:
            pass
        try:
            self._win._inline_workspace.record_chat_event(event or {})
        except Exception:
            pass

    def _on_discord_config_changed(self, settings: dict):
        settings = settings or {}
        enabled = bool(settings.get("enabled", False) or (settings.get("bot_token") or "").strip())
        token = (settings.get("bot_token") or "").strip()
        channel_id = (settings.get("channel_id") or "").strip()
        self._discord_service.set_target_channel_id(channel_id)
        if not enabled or not token:
            self._discord_service.stop()
            if not token:
                self._win.discord_status_changed.emit("Token required")
            else:
                self._win.discord_status_changed.emit("Discord bot disabled")
            return
        try:
            self._discord_service.start(token)
        except Exception as exc:
            msg = f"Discord error: {exc}"
            self._win.discord_status_changed.emit(msg)
            self._win._log_sig.emit(f"ERR: {msg}")

    def _open_app(self):
        self._command_bar.hide()
        self._launcher.show_at()
        self._win.show_app()

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    def set_muted(self, muted: bool):
        if bool(muted) != self._win._muted:
            self._win.set_muted_state(bool(muted))

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        self._win.set_muted_state(bool(muted), wakeword=wakeword)

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_attention_action(self):
        return self._win.on_attention_action

    @on_attention_action.setter
    def on_attention_action(self, cb):
        self._win.on_attention_action = cb

    @property
    def on_chat_event(self):
        return self._win.on_chat_event

    @on_chat_event.setter
    def on_chat_event(self, cb):
        self._win.on_chat_event = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def show_daily_briefing(self, text: str):
        self._win.show_daily_briefing(text)

    def hide_daily_briefing(self):
        self._win.hide_daily_briefing()

    def schedule_daily_briefing_hide(self):
        self._win.schedule_daily_briefing_hide()

    def submit_external_command(self, text: str, source: str = "discord"):
        self._win.submit_command(text, source=source)

    def notify_phone_connected(self):
        self._win.notify_phone_connected()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._win.set_scanning(enabled, text)

    def show_attention_alert(self, event: dict):
        self._win._attention_sig.emit(event or {})

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._win.set_meeting_mode(enabled, title, summary, answer, speech)

    def begin_task_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._win._task_workspace_sig.emit({
            "action": "start",
            "command": command or "",
            "plan": plan or [],
            "source": source or "local",
        })

    def update_task_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                              status: str | None = None, output: str | None = None, percent: int | None = None,
                              footer: str | None = None, source: str | None = None):
        payload = {"action": "update"}
        if title is not None:
            payload["title"] = title
        if command is not None:
            payload["command"] = command
        if plan is not None:
            payload["plan"] = plan
        if status is not None:
            payload["status"] = status
        if output is not None:
            payload["output"] = output
        if percent is not None:
            payload["percent"] = percent
        if footer is not None:
            payload["footer"] = footer
        if source is not None:
            payload["source"] = source or "local"
        self._win._task_workspace_sig.emit(payload)

    def finish_task_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._win._task_workspace_sig.emit({
            "action": "finish",
            "result": result or "Done.",
            "status": status or "Task completed.",
            "percent": percent,
        })

    def clear_task_workspace(self):
        self._win._task_workspace_sig.emit({"action": "clear"})

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")





