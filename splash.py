"""The window shown while the main window is being built."""

from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QFrame,
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar
)

from i18n import tr


class SplashScreen(QWidget):
    """A frameless, always-on-top card with the title and a busy bar.

    The window itself is transparent and the card inside it has the rounded
    background, so the corners outside the rounding stay see-through (with a
    compositor). The card's style names it (`QFrame#splash`): a style
    without a selector would also give every label and the bar a border.
    """

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(420, 220)

        self.card = QFrame(self)
        self.card.setObjectName("splash")

        self.card.setStyleSheet("""
            QFrame#splash {
                background-color: #070707;
                border: 1px solid #2d2b24;
                border-radius: 18px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)

        layout.setContentsMargins(
            30,
            30,
            30,
            30
        )

        title = QLabel(
            "Squad Ballistics"
        )

        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #f2f2ee;
        """)

        layout.addWidget(title)

        self.status = QLabel(
            tr("splash_loading")
        )

        self.status.setStyleSheet("""
            color: #c8b98f;
            font-size: 14px;
        """)

        layout.addWidget(self.status)

        # Busy indicator while the main window is built
        self.progress = QProgressBar()

        self.progress.setRange(0, 0)

        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #151512;
                border: 1px solid #2d2b24;
                border-radius: 10px;
                height: 20px;
                color: #f2f2ee;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #c8b98f;
                border-radius: 10px;
            }
        """)

        layout.addWidget(self.progress)
