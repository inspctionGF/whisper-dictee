"""Lampe encastrée : le même logement change de température selon l'état."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mode = "loading"
        self.reduced_motion = False
        self.t = 0.0
        self.check = 0.0
        self.listen = QColor("#FF5E3A")
        self.work = QColor("#E3944F")
        self.success = QColor("#9DDCB0")
        self.error = QColor("#F07167")
        self.warn = QColor("#E7B15A")
        self.muted = QColor("#A3988C")
        self.well = QColor(0, 0, 0, 88)
        self.paper = QColor("#FFF6EA")

    def set_colors(self, listen, work, success, error, warn, muted, well=None, paper=None) -> None:
        self.listen = listen
        self.work = work
        self.success = success
        self.error = error
        self.warn = warn
        self.muted = muted
        if well is not None:
            self.well = well
        if paper is not None:
            self.paper = paper

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "success":
            self.check = 0.0

    def set_reduced_motion(self, reduced: bool) -> None:
        self.reduced_motion = reduced

    def tick(self) -> None:
        self.t += 0.016
        if self.mode == "success" and self.check < 1.0:
            self.check = min(1.0, self.check + 0.016 / 0.200)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        if self.mode == "listen":
            self._paint_led(painter, center, self.listen, 3.5)
        elif self.mode == "transcribe":
            self._paint_arc(painter, center)
        elif self.mode == "success":
            self._paint_check(painter, center)
        elif self.mode == "error":
            self._paint_cross(painter, center)
        elif self.mode == "warn":
            self._paint_led(painter, center, self.warn, 3.5)
        else:
            self._paint_loading(painter, center)
        painter.end()

    def _paint_rings(self, painter: QPainter, center: QPointF) -> None:
        if self.reduced_motion:
            return
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for offset in (0.0, 0.52):
            phase = ((self.t / 1.9) + offset) % 1.0
            radius = 13.5 + 6.0 * phase
            halo = QColor(self.listen)
            halo.setAlphaF(0.34 * (1.0 - phase) ** 1.5)
            painter.setPen(QPen(halo, 1.35))
            painter.drawEllipse(center, radius, radius)

    def _paint_well(self, painter: QPainter, center: QPointF) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.well)
        painter.drawEllipse(center, 14.5, 14.5)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 70), 1))
        painter.drawEllipse(center, 13.6, 13.6)
        painter.setPen(QPen(QColor(self.paper.red(), self.paper.green(), self.paper.blue(), 36), 1))
        arc = QRectF(center.x() - 12.2, center.y() - 12.2, 24.4, 24.4)
        painter.drawArc(arc, 45 * 16, 110 * 16)

    def _paint_led(self, painter: QPainter, center: QPointF, color: QColor, radius: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, radius, radius)

    def _paint_loading(self, painter: QPainter, center: QPointF) -> None:
        phase = 0.55 if self.reduced_motion else 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self.t * 1.5))
        color = QColor(self.muted)
        color.setAlphaF(phase)
        self._paint_led(painter, center, color, 3.6)

    def _paint_arc(self, painter: QPainter, center: QPointF) -> None:
        rect = QRectF(center.x() - 6, center.y() - 6, 12, 12)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        track = QColor(self.muted)
        track.setAlpha(70)
        painter.setPen(QPen(track, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(rect)
        painter.setPen(QPen(self.work, 2.05, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start = 90 * 16 if self.reduced_motion else int((-self.t * 360) * 16)
        painter.drawArc(rect, start % (360 * 16), 250 * 16)

    def _paint_check(self, painter: QPainter, center: QPointF) -> None:
        pen = QPen(self.success, 2.15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        progress = 1.0 if self.reduced_motion else self.check
        points = (
            QPointF(center.x() - 4.2, center.y() + 0.2),
            QPointF(center.x() - 1.1, center.y() + 3.4),
            QPointF(center.x() + 4.6, center.y() - 3.6),
        )
        if progress < 0.55:
            painter.drawLine(points[0], self._lerp(points[0], points[1], progress / 0.55))
            return
        painter.drawLine(points[0], points[1])
        painter.drawLine(points[1], self._lerp(points[1], points[2], (progress - 0.55) / 0.45))

    def _paint_cross(self, painter: QPainter, center: QPointF) -> None:
        pen = QPen(self.error, 2.05, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        span = 3.6
        painter.drawLine(QPointF(center.x() - span, center.y() - span), QPointF(center.x() + span, center.y() + span))
        painter.drawLine(QPointF(center.x() + span, center.y() - span), QPointF(center.x() - span, center.y() + span))

    @staticmethod
    def _lerp(start: QPointF, end: QPointF, amount: float) -> QPointF:
        amount = max(0.0, min(1.0, amount))
        return QPointF(
            start.x() + (end.x() - start.x()) * amount,
            start.y() + (end.y() - start.y()) * amount,
        )
