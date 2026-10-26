"""Pilule opaque, minimale, claire ou sombre selon Windows."""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QParallelAnimationGroup, Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from overlay.status_dot import StatusDot
from overlay.waveform import WaveformWidget

PILL_WIDTH = 520
PILL_HEIGHT = 72
PILL_RADIUS = 36

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_size_t
_user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
_user32.SetWindowLongPtrW.restype = ctypes.c_size_t
_user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.SetWindowPos.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]
_user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
_user32.SetWindowRgn.restype = ctypes.c_int
_gdi32.CreateRoundRectRgn.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
_gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p


def _family(*candidates: str) -> str:
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            return name
    return "Segoe UI"


def _font(size: int, weight: QFont.Weight, family: str, tracking: float = 0) -> QFont:
    font = QFont(family)
    font.setPixelSize(size)
    font.setWeight(weight)
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    try:
        font.setFeature(QFont.Tag("tnum"), 1)
    except Exception:
        pass
    return font


class Palette:
    def __init__(self, dark: bool, _opacity: float = 1.0) -> None:
        self.dark = dark
        if dark:
            self.fill = QColor("#141416")
            self.border = QColor(255, 255, 255, 28)
            self.text = QColor("#F4F4F5")
            self.muted = QColor("#A1A1AA")
            self.quiet = QColor("#F4F4F5")
            self.listen = QColor("#FF453A")
            self.success = QColor("#3DDC84")
            self.error = QColor("#FF6B6B")
            self.warn = QColor("#F5C16C")
        else:
            self.fill = QColor("#FFFFFF")
            self.border = QColor(0, 0, 0, 22)
            self.text = QColor("#111113")
            self.muted = QColor("#6B6B70")
            self.quiet = QColor("#111113")
            self.listen = QColor("#E5484D")
            self.success = QColor("#1F8A4C")
            self.error = QColor("#D92D20")
            self.warn = QColor("#B7791F")
        self.brass = self.quiet
        self.hot = self.quiet
        self.track = QColor(0, 0, 0, 0)
        self.well = QColor(0, 0, 0, 0)
        self.paper = self.text
        self.work = self.muted


class OverlayWindow(QWidget):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.reduced_motion = False
        self._state = "loading"
        self._elapsed = 0
        self._group: QParallelAnimationGroup | None = None
        popup = settings.get("popup", {})
        self._opacity = float(popup.get("opacite_fond", 0.92))
        self._position = str(popup.get("position", "bas-centre"))
        self._show_help = bool(popup.get("afficher_aide", True))
        self.display = _family("Bahnschrift", "Segoe UI Variable", "Segoe UI")
        self.mono = _family("Cascadia Mono", "Consolas", "Segoe UI")
        self.palette_colors = Palette(True, self._opacity)

        self.setFixedSize(PILL_WIDTH, PILL_HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Dictée locale")

        self.dot = StatusDot(self)
        self.wave = WaveformWidget(self)
        self.chrono = QLabel("00:00", self)
        self.kicker = QLabel("FR", self)
        self.separator = QLabel("·", self)
        self.help = QLabel("", self)
        self.message = QLabel("Chargement du modèle…", self)

        self.chrono.setFont(_font(14, QFont.Weight.Medium, self.mono))
        self.kicker.setFont(_font(11, QFont.Weight.Medium, self.display, 0.8))
        self.separator.setFont(_font(11, QFont.Weight.Normal, self.display))
        self.help.setFont(_font(12, QFont.Weight.Normal, self.display))
        self.message.setFont(_font(13, QFont.Weight.Medium, self.display))
        for label in (self.chrono, self.kicker, self.separator, self.help, self.message):
            label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.chrono.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.kicker.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.help.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.message.setWordWrap(False)
        self.chrono.setFixedWidth(58)
        self.message.setMinimumWidth(120)

        body = QWidget(self)
        body.setGeometry(0, 0, PILL_WIDTH, PILL_HEIGHT)
        body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        body.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        body.setAutoFillBackground(False)
        body.setStyleSheet("background: transparent;")
        self.dot.setStyleSheet("background: transparent;")
        self.wave.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(16, 0, 18, 0)
        layout.setSpacing(12)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.wave, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.message, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.help, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.kicker, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.separator, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.chrono, 0, Qt.AlignmentFlag.AlignVCenter)

        self._apply_palette()
        self.set_state("loading")
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda _scheme: self._apply_palette())

    def is_dark(self) -> bool:
        return self.palette_colors.dark

    def set_theme(self, theme: str) -> None:
        self.settings.setdefault("popup", {})["theme"] = theme
        self._apply_palette()

    def set_reduced_motion(self, reduced: bool) -> None:
        self.reduced_motion = reduced
        self.wave.set_reduced_motion(reduced)
        self.dot.set_reduced_motion(reduced)

    def set_language(self, code: str) -> None:
        self.kicker.setText(code.upper())

    def set_state(self, state: str, message: str = "") -> None:
        self._state = state
        modes = {
            "listening": "listen",
            "transcribing": "transcribe",
            "success": "success",
            "short": "warn",
            "silent": "warn",
            "error": "error",
            "cancelled": "warn",
            "loading": "loading",
        }
        self.dot.set_mode(modes.get(state, "loading"))
        wave_modes = {
            "listening": "live",
            "transcribing": "shimmer",
            "loading": "loading",
        }
        self.wave.set_mode(wave_modes.get(state, "flat"))
        labels = {
            "transcribing": "Transcription…",
            "success": "Collé",
            "short": "Trop court",
            "silent": "Aucun son détecté",
            "error": "Une erreur est survenue",
            "cancelled": "Annulé",
            "loading": "Chargement du modèle…",
        }
        self.message.setText(message or labels.get(state, ""))
        names = {
            "listening": "Enregistrement",
            "transcribing": "Transcription",
            "success": "Collé",
            "short": "Trop court",
            "silent": "Aucun son détecté",
            "error": "Erreur",
            "cancelled": "Annulé",
            "loading": "Chargement du modèle",
        }
        self.setAccessibleDescription(names.get(state, ""))
        self._sync_caption()
        self.update()

    def set_elapsed(self, seconds: int) -> None:
        self._elapsed = max(0, seconds)
        if seconds >= 60:
            text = f"{seconds // 60}:{seconds % 60:02d}"
            color = self.palette_colors.warn
        else:
            text = f"00:{seconds:02d}"
            color = self.palette_colors.text
        self.chrono.setText(text)
        self._tint(self.chrono, color)

    def show_help(self, visible: bool) -> None:
        if not self._show_help:
            self.help.setText("")
        else:
            self.help.setText("Relâchez pour coller" if visible else "")
        self._sync_caption()

    def present(self) -> None:
        self._stop_motion()
        self.place()
        self.wave.t = 0.0
        self.dot.t = 0.0
        if self.isVisible() and self.windowOpacity() > 0.9:
            self._apply_native()
            return
        end = self.pos()
        if self.reduced_motion:
            self.setWindowOpacity(0.0)
            self.show()
            self._apply_native()
            self._fade_to(1.0, 100, QEasingCurve.Type.Linear, end)
        else:
            self.move(end + QPoint(0, 8))
            self.setWindowOpacity(0.0)
            self.show()
            self._apply_native()
            self._fade_to(1.0, 200, QEasingCurve.Type.OutCubic, end)

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self._stop_motion()
        end = self.pos() + (QPoint(0, 0) if self.reduced_motion else QPoint(0, -6))
        duration = 100 if self.reduced_motion else 150
        curve = QEasingCurve.Type.Linear if self.reduced_motion else QEasingCurve.Type.InCubic
        self._fade_to(0.0, duration, curve, end, hide=True)

    def place(self) -> None:
        screen = QGuiApplication.screenAt(self._cursor_pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        if self._position == "haut-centre":
            x = area.x() + (area.width() - self.width()) // 2
            y = area.top() + 28
        elif self._position == "bas-droite":
            x = area.right() - 24 - self.width()
            y = area.bottom() + 1 - 36 - PILL_HEIGHT
        else:
            x = area.x() + (area.width() - self.width()) // 2
            y = area.bottom() + 1 - 36 - PILL_HEIGHT
        self.move(x, y)

    def tick(self) -> None:
        self.wave.tick()
        self.dot.tick()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        colors = self.palette_colors
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(colors.border, 1))
        painter.setBrush(colors.fill)
        painter.drawRoundedRect(rect, PILL_RADIUS, PILL_RADIUS)
        painter.end()

    def _sync_caption(self) -> None:
        listening = self._state == "listening"
        show_help = listening and bool(self.help.text())
        self.chrono.setVisible(listening)
        self.kicker.setVisible(listening and not show_help)
        self.separator.setVisible(False)
        self.help.setVisible(show_help)
        self.message.setVisible(not listening)

    def _apply_palette(self) -> None:
        theme = str(self.settings.get("popup", {}).get("theme", "auto"))
        if theme == "sombre":
            dark = True
        elif theme == "clair":
            dark = False
        else:
            scheme = QGuiApplication.styleHints().colorScheme()
            dark = scheme != Qt.ColorScheme.Light
        self.palette_colors = Palette(dark, self._opacity)
        colors = self.palette_colors
        self.wave.set_colors(colors.quiet, colors.brass, colors.hot, colors.track, colors.paper)
        self.dot.set_colors(
            colors.listen,
            colors.work,
            colors.success,
            colors.error,
            colors.warn,
            colors.muted,
            colors.well,
            colors.paper,
        )
        self._tint(self.chrono, colors.warn if self._elapsed >= 60 else colors.text)
        self._tint(self.kicker, colors.muted)
        self._tint(self.separator, colors.muted)
        self._tint(self.help, colors.muted)
        self._tint(self.message, colors.text)
        self.update()

    @staticmethod
    def _tint(label: QLabel, color: QColor) -> None:
        label.setStyleSheet(
            f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            "background: transparent; border: none;"
        )

    def _fade_to(self, opacity: float, duration: int, curve, end: QPoint, hide: bool = False) -> None:
        self._group = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(duration)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(opacity)
        fade.setEasingCurve(curve)
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(duration)
        slide.setStartValue(self.pos())
        slide.setEndValue(end)
        slide.setEasingCurve(curve)
        self._group.addAnimation(fade)
        self._group.addAnimation(slide)
        if hide:
            self._group.finished.connect(self._after_hide)
        self._group.start()

    def _after_hide(self) -> None:
        self.hide()
        self.setWindowOpacity(1.0)

    def _stop_motion(self) -> None:
        if self._group is not None:
            self._group.stop()
            self._group = None

    def _apply_native(self) -> None:
        hwnd = int(self.winId())
        if not hwnd:
            return
        style = _user32.GetWindowLongPtrW(hwnd, -20)
        noactivate = 0x08000000
        tool = 0x00000080
        transparent = 0x00000020
        _user32.SetWindowLongPtrW(hwnd, -20, style | noactivate | tool | transparent)
        _user32.ShowWindow(hwnd, 4)
        _user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            ctypes.c_void_p(-1),
            0,
            0,
            0,
            0,
            0x0002 | 0x0001 | 0x0010 | 0x0040,
        )
        ratio = max(1.0, float(self.devicePixelRatio()))
        width = max(1, int(round(self.width() * ratio)))
        height = max(1, int(round(self.height() * ratio)))
        region = _gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, height, height)
        _user32.SetWindowRgn(ctypes.c_void_p(hwnd), ctypes.c_void_p(region), True)

    @staticmethod
    def _cursor_pos():
        from PySide6.QtGui import QCursor

        return QCursor.pos()
