"""Filaments qui restent ivoire au repos et chauffent vers le cuivre avec la voix."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

BARS = 32
BAR_WIDTH = 3.5
BAR_GAP = 3.0
PAD_X = 2.0
MIN_HEIGHT = 6.0
MAX_HEIGHT = 34.0


class WaveformWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(int(MAX_HEIGHT + 12))
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mode = "live"
        self.reduced_motion = False
        self.quiet = QColor("#FFFFFF")
        self.brass = QColor("#FFFFFF")
        self.hot = QColor("#FFFFFF")
        self.track = QColor(0, 0, 0, 0)
        self.paper = QColor("#FFFFFF")
        self.history = [0.0] * BARS
        self.heights = [0.08] * BARS
        self.latest = 0.0
        self.t = 0.0
        center = (BARS - 1) / 2
        self.envelope = [
            0.35 + 0.65 * math.exp(-((index - center) / 9.0) ** 2) for index in range(BARS)
        ]
        rng = np.random.default_rng()
        self.variation = rng.uniform(0.92, 1.08, size=BARS)

    def set_colors(self, quiet: QColor, brass: QColor, hot: QColor, track: QColor, paper: QColor) -> None:
        self.quiet = quiet
        self.brass = brass
        self.hot = hot
        self.track = track
        self.paper = paper

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_reduced_motion(self, reduced: bool) -> None:
        self.reduced_motion = reduced

    def push_level(self, level: float) -> None:
        self.latest = level
        self.history.insert(0, level)
        del self.history[BARS:]

    def tick(self) -> None:
        self.t += 0.016
        for index in range(BARS):
            target = self._target(index)
            if self.reduced_motion:
                self.heights[index] = target
                continue
            rate = 0.55 if target > self.heights[index] else 0.12
            if self.mode in {"flat", "shimmer", "loading"}:
                rate = 0.35
            self.heights[index] += (target - self.heights[index]) * rate
        self.update()

    def _target(self, index: int) -> float:
        if self.mode == "flat":
            return 0.0
        if self.mode == "loading":
            lit = self.t * 8 % BARS
            return 0.55 if index < lit else 0.06
        if self.mode == "shimmer":
            phase = (self.t % 1.4) / 1.4
            shine = math.exp(-((index / (BARS - 1) - phase) * 4.2) ** 2)
            return 0.08 + 0.5 * shine
        if self.latest < 0.04:
            if self.reduced_motion:
                return 0.07
            return 0.075 + 0.02 * math.sin(self.t * 1.4 + index * 0.38)
        age = min(BARS - 1, int(abs(index - 15.5)))
        return self.history[age] * self.envelope[index] * float(self.variation[index])

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        usable = max(1.0, self.width() - PAD_X * 2)
        bar_width = BAR_WIDTH
        gap = (usable - BARS * bar_width) / (BARS - 1)
        if gap < 2:
            gap = 2
            bar_width = max(2.0, (usable - (BARS - 1) * gap) / BARS)
        origin = PAD_X
        mid = self.height() / 2
        for index, level in enumerate(self.heights):
            amount = max(0.0, min(1.0, level))
            if amount < 0.04:
                continue
            bar_height = MIN_HEIGHT + (MAX_HEIGHT - MIN_HEIGHT) * amount
            x = origin + index * (bar_width + gap)
            rect = QRectF(x, mid - bar_height / 2, bar_width, bar_height)
            color = QColor(self.quiet)
            color.setAlphaF(0.34 + 0.66 * amount)
            painter.setBrush(color)
            path = QPainterPath()
            radius = BAR_WIDTH / 2
            path.addRoundedRect(rect, min(radius, bar_width / 2), min(radius, bar_width / 2))
            painter.drawPath(path)
        painter.end()
