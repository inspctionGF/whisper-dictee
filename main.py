"""Dictée locale.

    python main.py           pilule, micro et collage (Ctrl+Alt+Espace)
    python main.py --test    enregistre 5 secondes et affiche le texte
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from audio import AudioRecorder, mic_name, record_seconds
from controller import Controller, autostart_enabled, load_settings, save_settings, set_autostart
from overlay.window import OverlayWindow
from transcriber import Transcriber, gpu_name, load_model, log, resolve_backend, transcribe_array


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def print_banner(settings: dict) -> None:
    whisper = settings.get("whisper", {})
    backend = resolve_backend(str(whisper.get("modele", "auto")))
    where = gpu_name() if backend.device == "cuda" else "processeur"
    log("Dictée locale")
    log(f"Machine : {where}")
    log(
        f"Moteur : faster-whisper {backend.model_name}, "
        f"{backend.device}, {backend.compute_type}, {whisper.get('langue', 'fr')}"
    )
    log(f"Micro : {mic_name()}")
    log("Raccourci : maintenir Ctrl+Alt+Espace, relâcher pour coller")
    log("Échap annule la prise en cours.")
    log("Une fenêtre lancée en administrateur n'accepte le collage que si cette application l'est aussi.")


def tray_icon() -> QIcon:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QPen

    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(243, 232, 214, 46), 1.2))
    painter.setBrush(QColor("#16130F"))
    painter.drawRoundedRect(QRectF(3, 3, 58, 58), 16, 16)
    painter.setPen(Qt.PenStyle.NoPen)
    filaments = ((16, 12, "#E4DCD0"), (24, 22, "#E2A15A"), (32, 15, "#FF6A3D"))
    for x, height, color in filaments:
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(x, 32 - height / 2, 4, height), 2, 2)
    painter.setBrush(QColor(0, 0, 0, 90))
    painter.drawEllipse(QPointF(48, 32), 8, 8)
    painter.setBrush(QColor("#FF5E3A"))
    painter.drawEllipse(QPointF(48, 32), 3.4, 3.4)
    painter.end()
    return QIcon(pixmap)


def run_test(settings: dict) -> None:
    print_banner(settings)
    whisper = settings.get("whisper", {})
    engine = load_model(str(whisper.get("modele", "large-v3")), str(whisper.get("langue", "fr")))
    log("Parlez maintenant. Enregistrement de 5 secondes…")
    audio = record_seconds(5)
    import numpy as np

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    log(f"Niveau du micro : {peak:.3f}")
    import time

    started = time.perf_counter()
    text = transcribe_array(
        engine.model,
        audio,
        str(whisper.get("langue", "fr")),
        str(whisper.get("initial_prompt", "")),
    )
    log(f"Latence : {time.perf_counter() - started:.2f} s")
    log(text or "(aucun texte)")


def run_app(settings: dict) -> None:
    print_banner(settings)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Dictée locale")
    families = set(QFontDatabase.families())
    if "Bahnschrift" in families:
        font = QFont("Bahnschrift")
    elif "Segoe UI Variable" in families:
        font = QFont("Segoe UI Variable")
    else:
        font = QFont("Segoe UI")
    app.setFont(font)
    app.setStyle("Fusion")

    whisper = settings.get("whisper", {})
    overlay = OverlayWindow(settings)
    recorder = AudioRecorder(settings.get("audio", {}).get("micro"))
    transcriber = Transcriber(
        str(whisper.get("modele", "large-v3")),
        str(whisper.get("langue", "fr")),
        str(whisper.get("initial_prompt", "")),
    )
    controller = Controller(overlay, recorder, transcriber, settings)

    tray = QSystemTrayIcon(tray_icon())
    tray.setToolTip("Dictée locale — Ctrl+Alt+Espace")
    menu = QMenu()
    status = QAction("Chargement du modèle…", menu)
    status.setEnabled(False)
    dark_mode = QAction("Mode sombre", menu)
    dark_mode.setCheckable(True)
    dark_mode.setChecked(overlay.is_dark())
    autostart = QAction("Démarrer avec Windows", menu)
    autostart.setCheckable(True)
    autostart.setChecked(autostart_enabled())
    quit_action = QAction("Quitter", menu)
    menu.addAction(status)
    menu.addSeparator()
    menu.addAction(dark_mode)
    menu.addAction(autostart)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)

    def mark_ready(model_name: str) -> None:
        status.setText(f"Prêt — {model_name}")

    def toggle_theme(checked: bool) -> None:
        overlay.set_theme("sombre" if checked else "clair")
        save_settings(settings)

    def toggle_autostart(checked: bool) -> None:
        set_autostart(checked)

    def quit_app() -> None:
        controller.shutdown()
        tray.hide()
        app.quit()

    transcriber.ready.connect(mark_ready)
    dark_mode.toggled.connect(toggle_theme)
    autostart.toggled.connect(toggle_autostart)
    quit_action.triggered.connect(quit_app)
    tray.show()
    controller.start()
    raise SystemExit(app.exec())


def main() -> None:
    configure_stdio()
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Dictée locale avec Whisper.")
    parser.add_argument("--test", action="store_true", help="Enregistre 5 secondes et affiche le texte.")
    args = parser.parse_args()
    if args.test:
        run_test(settings)
    else:
        run_app(settings)


if __name__ == "__main__":
    main()
