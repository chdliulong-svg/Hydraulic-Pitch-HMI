# -*- coding: utf-8 -*-
"""
LoginCard - Unified Authentication Widget
Used across ManualPage, MaintenancePage, and NetworkPage.
Ensures 100% consistent sizing, styling, status indicators,
and authentication interaction.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.i18n import tr


class LoginCard(QGroupBox):
    """
    Unified Login / Authentication Card Component
    Emits login_changed(bool) when user logs in or out.
    """
    login_changed = pyqtSignal(bool)

    def __init__(self, on_login=None, on_logout=None, parent=None):
        super().__init__("Login", parent)
        self.on_login_cb = on_login
        self.on_logout_cb = on_logout
        self.is_logged_in = False
        self.current_role = None
        self.current_lang = "EN"

        # Fixed dimensions for absolute pixel-level uniformity across all pages
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
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        # 1. Top status badge row (Right-aligned pill badge)
        status_row = QHBoxLayout()
        self.badge_status = QLabel("○ Logged Out")
        self.badge_status.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #64748B;
            background-color: #F1F5F9; border: 1px solid #E2E8F0;
            border-radius: 3px; padding: 2px 8px;
        """)
        status_row.addStretch()
        status_row.addWidget(self.badge_status)
        layout.addLayout(status_row)
        self.badge_login_status = self.badge_status  # alias
        self.badge_login = self.badge_status         # alias

        # 2. Password prompt label
        self.lbl_pwd = QLabel("Password:")
        self.lbl_pwd.setStyleSheet("font-size: 11px; color: #475569; font-weight: bold;")
        layout.addWidget(self.lbl_pwd)

        # 3. Password input box
        self.edit_password = QLineEdit()
        self.edit_pw = self.edit_password             # alias
        self.edit_password.setFixedHeight(28)
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_password.setPlaceholderText("Enter password...")
        self.edit_password.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #0284C7;
            }
        """)
        self.edit_password.returnPressed.connect(self.handle_login_logout)
        layout.addWidget(self.edit_password)

        layout.addStretch()

        # 4. Action Button (Login / Logout)
        self.btn_login = QPushButton("Login")
        self.btn_login.setFixedHeight(32)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0F172A; color: white; font-weight: bold;
                border-radius: 4px; font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_login.clicked.connect(self.handle_login_logout)
        layout.addWidget(self.btn_login)

    def set_state(self, is_logged: bool, role_name: str = None):
        """Update visual state based on current authorization status"""
        self.is_logged_in = is_logged
        self.current_role = role_name

        if is_logged:
            badge_text = f"● {role_name}" if role_name else tr("● Logged In", self.current_lang)
            self.badge_status.setText(badge_text)
            self.badge_status.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #059669;
                background-color: #D1FAE5; border: 1px solid #A7F3D0;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.btn_login.setText(tr("Logout", self.current_lang))
            self.btn_login.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444; color: white; font-weight: bold;
                    border-radius: 4px; font-size: 11px;
                }
                QPushButton:hover { background-color: #DC2626; }
            """)
        else:
            self.badge_status.setText(tr("○ Logged Out", self.current_lang))
            self.badge_status.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #64748B;
                background-color: #F1F5F9; border: 1px solid #E2E8F0;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.btn_login.setText(tr("Login", self.current_lang))
            self.btn_login.setStyleSheet("""
                QPushButton {
                    background-color: #0F172A; color: white; font-weight: bold;
                    border-radius: 4px; font-size: 11px;
                }
                QPushButton:hover { background-color: #334155; }
            """)

    def handle_login_logout(self):
        if self.is_logged_in:
            if callable(self.on_logout_cb):
                self.on_logout_cb()
            self.is_logged_in = False
            self.edit_password.clear()
            self.set_state(False)
            self.login_changed.emit(False)
        else:
            pwd = self.edit_password.text().strip()
            if callable(self.on_login_cb):
                ok, msg = self.on_login_cb(pwd)
                if ok:
                    self.is_logged_in = True
                    self.edit_password.clear()
                    self.set_state(True, self.current_role)
                    self.login_changed.emit(True)
                else:
                    QMessageBox.warning(
                        self,
                        tr("Password Error", self.current_lang),
                        msg if msg else tr("Incorrect password!", self.current_lang)
                    )
            else:
                self.login_changed.emit(True)

    def retranslate_ui(self, lang: str = "EN"):
        self.current_lang = lang
        self.setTitle(tr("Login", lang))
        self.lbl_pwd.setText(tr("Password:", lang))
        self.edit_password.setPlaceholderText(tr("Enter password...", lang))
        self.set_state(self.is_logged_in, self.current_role)
