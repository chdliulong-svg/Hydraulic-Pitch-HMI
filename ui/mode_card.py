# -*- coding: utf-8 -*-
"""
ModeCard - Unified Mode Permission / Acquisition Widget
Used across ManualPage and MaintenancePage.
Ensures 100% consistent sizing, styling, status indicators,
interlock prompt message, and mode toggle action button.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.i18n import tr


class PillBadge(QLabel):
    """Status badge for card headers"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("locked", text)

    def set_state(self, state_type, text):
        self.setText(text)
        if state_type in ("ready", "unlocked"):
            self.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #03543F;
                background-color: #DEF7EC; border: 1px solid #31C48D;
                border-radius: 11px; padding: 1px 8px;
            """)
        else:  # locked / warning
            self.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #991B1B;
                background-color: #FEF2F2; border: 1px solid #F87171;
                border-radius: 11px; padding: 1px 8px;
            """)


class ModeCard(QGroupBox):
    """
    Unified Mode Permission / Acquisition Card Component.
    Used for Manual Mode and Maintenance Mode.
    Emits action_clicked() when the action button is clicked.
    """
    action_clicked = pyqtSignal()

    def __init__(self, mode_type="manual", on_action=None, parent=None):
        """
        mode_type: "manual" or "maintenance"
        """
        title = "Manual Mode" if mode_type.lower() == "manual" else "Maintenance Mode"
        super().__init__(title, parent)
        self.mode_type = mode_type.lower()
        self.on_action_cb = on_action
        self.current_lang = "EN"
        self.is_active = False
        self.can_enter = False
        self.can_exit = True
        self.current_prompt = ""
        self.current_badge_text = ""
        self.current_badge_type = "locked"

        # Fixed dimensions for 100% pixel-level parity with LoginCard
        self.setFixedWidth(210)
        self.setFixedHeight(175)

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QGroupBox {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 11px;
                font-weight: bold;
                color: #1E293B;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                left: 10px;
                background-color: #FFFFFF;
                color: #0F172A;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(6)

        # 1. Top status row: [ "准入状态:" | Badge ]
        status_row = QHBoxLayout()
        self.lbl_status_hint = QLabel("Access Status:")
        self.lbl_status_hint.setStyleSheet("font-size: 10px; color: #64748B; font-weight: bold;")
        self.lbl_mode_state_hint = self.lbl_status_hint  # alias

        self.badge_status = PillBadge("🔒 Locked")
        self.badge_mode = self.badge_status              # alias

        status_row.addWidget(self.lbl_status_hint)
        status_row.addStretch()
        status_row.addWidget(self.badge_status)
        layout.addLayout(status_row)

        # 2. Prompt / Interlock note card
        self.card_prompt = QFrame()
        self.card_prompt.setFixedHeight(50)
        self.card_prompt.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
            }
        """)
        p_layout = QVBoxLayout(self.card_prompt)
        p_layout.setContentsMargins(4, 3, 4, 3)
        p_layout.setSpacing(0)

        self.lbl_prompt = QLabel("")
        self.lbl_prompt.setWordWrap(True)
        self.lbl_prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_prompt.setStyleSheet("font-size: 10px; color: #334155; font-weight: 500;")
        p_layout.addWidget(self.lbl_prompt)
        layout.addWidget(self.card_prompt)

        layout.addStretch()

        # 3. Action Button
        self.btn_action = QPushButton("Request Mode ⚙")
        self.btn_action.setFixedHeight(36)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.clicked.connect(self._handle_action_clicked)
        layout.addWidget(self.btn_action)

        # Aliases for compatibility
        self.btn_req_mode = self.btn_action
        self.btn_mode_action = self.btn_action

    def _handle_action_clicked(self):
        if callable(self.on_action_cb):
            self.on_action_cb()
        self.action_clicked.emit()

    def set_state(
        self,
        is_active: bool,
        can_enter: bool,
        prompt_text: str = "",
        badge_text: str = "",
        badge_type: str = "locked",
        can_exit: bool = True
    ):
        """Update visual state based on current mode and admission status"""
        self.is_active = is_active
        self.can_enter = can_enter
        self.can_exit = can_exit
        self.current_prompt = prompt_text
        self.current_badge_text = badge_text
        self.current_badge_type = badge_type

        # 1. Update Title
        if self.mode_type == "manual":
            self.setTitle(tr("Manual Mode Control", self.current_lang))
        else:
            self.setTitle(tr("Maintenance Mode Control", self.current_lang))

        # 2. Update Status Hint
        self.lbl_status_hint.setText(tr("Access Status:", self.current_lang))

        # 3. Update Badge
        if badge_text:
            self.badge_status.set_state(badge_type, badge_text)
        else:
            if is_active:
                self.badge_status.set_state("ready", tr("✔ Active", self.current_lang))
            elif can_enter:
                self.badge_status.set_state("unlocked", tr("✔ Ready to Enter", self.current_lang))
            else:
                if self.mode_type == "manual":
                    self.badge_status.set_state("locked", tr("🔒 Require Stopped", self.current_lang))
                else:
                    self.badge_status.set_state("locked", tr("🔒 Need Aborted", self.current_lang))

        # 4. Update Prompt Text
        self.lbl_prompt.setText(prompt_text)

        # 5. Update Action Button
        if is_active:
            # Mode active -> Exit button
            if self.mode_type == "manual":
                self.btn_action.setText(tr("Exit Manual Mode ✖", self.current_lang))
            else:
                self.btn_action.setText(tr("Exit Maint. Mode ✖", self.current_lang))

            self.btn_action.setEnabled(can_exit)
            if can_exit:
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #DC2626; color: white; font-weight: bold;
                        border-radius: 4px; font-size: 11px; border: 1px solid #B91C1C;
                    }
                    QPushButton:hover { background-color: #B91C1C; }
                """)
            else:
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #E2E8F0; color: #94A3B8; font-weight: bold;
                        border-radius: 4px; font-size: 11px; border: 1px solid #CBD5E1;
                    }
                """)
        else:
            # Mode inactive -> Request button
            if self.mode_type == "manual":
                self.btn_action.setText(tr("Request Manual Mode ⚙", self.current_lang))
            else:
                self.btn_action.setText(tr("Request Maint. Mode ⚙", self.current_lang))

            self.btn_action.setEnabled(can_enter)
            if can_enter:
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #2563EB; color: white; font-weight: bold;
                        border-radius: 4px; font-size: 11px; border: 1px solid #1D4ED8;
                    }
                    QPushButton:hover { background-color: #1D4ED8; }
                """)
            else:
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background-color: #E2E8F0; color: #94A3B8; font-weight: bold;
                        border-radius: 4px; font-size: 11px; border: 1px solid #CBD5E1;
                    }
                """)

    def retranslate_ui(self, lang: str = "EN"):
        self.current_lang = lang
        self.set_state(
            self.is_active,
            self.can_enter,
            self.current_prompt,
            self.current_badge_text,
            self.current_badge_type,
            self.can_exit
        )
