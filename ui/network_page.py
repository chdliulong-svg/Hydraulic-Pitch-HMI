# -*- coding: utf-8 -*-
"""
Network Configuration Page
Replaces legacy FilePage.
Provides PLC Ethernet configuration (Hostname, IP, Subnet Mask)
and User Authentication using unified LoginCard.
"""

import ipaddress
import re

HOSTNAME_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from config import (
    DEFAULT_PLC_HOSTNAME, DEFAULT_PLC_IP, DEFAULT_PLC_SUBNET,
    ROLE_NOT_LOGGED_IN, ROLE_MAINTENANCE, ROLE_SUPER_USER
)
from utils.i18n import tr
from ui.login_card import LoginCard


class NetworkPage(QWidget):
    def __init__(self, plc_state, opcua_service=None, parent=None, **kwargs):
        # Backward compatibility if legacy file_manager was passed as first arg
        if hasattr(plc_state, "blades"):
            self.plc = plc_state
            self.opcua_service = opcua_service
        elif opcua_service is not None and hasattr(opcua_service, "blades"):
            self.plc = opcua_service
            self.opcua_service = parent
            parent = kwargs.get("parent")
        else:
            self.plc = plc_state
            self.opcua_service = opcua_service

        super().__init__(parent)
        self.current_user_role = ROLE_NOT_LOGGED_IN
        self.current_lang = "EN"
        self._user_edited_host = False
        self._user_edited_ip = False
        self._user_edited_mask = False

        self.init_ui()
        self.update_ui_state()
        self.auto_sync_from_plc()

        # Real-time automatic synchronization from PLC state
        self.plc.state_changed.connect(self.auto_sync_from_plc)
        self.plc.auth_changed.connect(self._on_auth_changed)
        if getattr(self.plc, "current_role", ROLE_NOT_LOGGED_IN) != ROLE_NOT_LOGGED_IN:
            self._on_auth_changed(self.plc.current_role)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)

        # 2-Column Layout matching Manual & Maintenance proportions: [ Left: 77% | Right: 23% ]
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        card_groupbox_style = """
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
        """

        # =========================================================================
        # 1. Left Column: PLC Ethernet Parameters Card
        # =========================================================================
        col_left = QVBoxLayout()
        self.grp_net_params = QGroupBox("PLC Ethernet Configuration")
        self.grp_net_params.setStyleSheet(card_groupbox_style)
        net_layout = QGridLayout(self.grp_net_params)
        net_layout.setContentsMargins(16, 14, 16, 14)
        net_layout.setHorizontalSpacing(14)
        net_layout.setVerticalSpacing(10)
        net_layout.setColumnStretch(0, 2)
        net_layout.setColumnStretch(1, 3)
        net_layout.setColumnStretch(2, 3)

        # Column Headers
        self.lbl_hdr_param = QLabel("Parameter")
        self.lbl_hdr_param.setStyleSheet("font-weight: bold; font-size: 10px; color: #64748B;")
        self.lbl_cur_hdr = QLabel("Current Value")
        self.lbl_cur_hdr.setStyleSheet("font-weight: bold; font-size: 10px; color: #64748B;")
        self.lbl_new_hdr = QLabel("New Value (Editable)")
        self.lbl_new_hdr.setStyleSheet("font-weight: bold; font-size: 10px; color: #0284C7;")

        net_layout.addWidget(self.lbl_hdr_param, 0, 0)
        net_layout.addWidget(self.lbl_cur_hdr, 0, 1)
        net_layout.addWidget(self.lbl_new_hdr, 0, 2)

        cur_style = """
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 3px;
            padding: 4px 8px;
            font-family: 'Consolas', 'Segoe UI', monospace;
            font-size: 11px;
            font-weight: bold;
            color: #0F172A;
        """
        edit_style = """
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                border-radius: 3px;
                padding: 4px 8px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #0284C7;
                background-color: #FFFFFF;
            }
            QLineEdit:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
                border-color: #CBD5E1;
            }
        """

        self._edit_style = edit_style

        cur_host = getattr(self.plc, "net_hostname", DEFAULT_PLC_HOSTNAME) or DEFAULT_PLC_HOSTNAME
        cur_ip = getattr(self.plc, "net_ip", DEFAULT_PLC_IP) or DEFAULT_PLC_IP
        cur_mask = getattr(self.plc, "net_subnet", DEFAULT_PLC_SUBNET) or DEFAULT_PLC_SUBNET

        # Row 1: Hostname
        self.lbl_lbl_host = QLabel("Hostname")
        self.lbl_lbl_host.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.lbl_cur_host = QLabel(cur_host)
        self.lbl_cur_host.setFixedHeight(28)
        self.lbl_cur_host.setStyleSheet(cur_style)
        self.edit_new_host = QLineEdit(cur_host)
        self.edit_new_host.setFixedHeight(28)
        self.edit_new_host.setStyleSheet(edit_style)
        self.edit_new_host.textChanged.connect(lambda: self._on_net_text_changed(self.edit_new_host, self.lbl_cur_host.text()))
        self.edit_new_host.textEdited.connect(lambda: setattr(self, "_user_edited_host", True))
        self.edit_new_host.editingFinished.connect(lambda: self._on_net_edit_finished(self.edit_new_host, self.lbl_cur_host.text()))
        net_layout.addWidget(self.lbl_lbl_host, 1, 0)
        net_layout.addWidget(self.lbl_cur_host, 1, 1)
        net_layout.addWidget(self.edit_new_host, 1, 2)

        # Row 2: IP Address
        self.lbl_lbl_ip = QLabel("IP address")
        self.lbl_lbl_ip.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.lbl_cur_ip = QLabel(cur_ip)
        self.lbl_cur_ip.setFixedHeight(28)
        self.lbl_cur_ip.setStyleSheet(cur_style)
        self.edit_new_ip = QLineEdit(cur_ip)
        self.edit_new_ip.setFixedHeight(28)
        self.edit_new_ip.setStyleSheet(edit_style)
        self.edit_new_ip.textChanged.connect(lambda: self._on_net_text_changed(self.edit_new_ip, self.lbl_cur_ip.text()))
        self.edit_new_ip.textEdited.connect(lambda: setattr(self, "_user_edited_ip", True))
        self.edit_new_ip.editingFinished.connect(lambda: self._on_net_edit_finished(self.edit_new_ip, self.lbl_cur_ip.text()))
        net_layout.addWidget(self.lbl_lbl_ip, 2, 0)
        net_layout.addWidget(self.lbl_cur_ip, 2, 1)
        net_layout.addWidget(self.edit_new_ip, 2, 2)

        # Row 3: Subnet Mask
        self.lbl_lbl_mask = QLabel("Subnet mask")
        self.lbl_lbl_mask.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.lbl_cur_mask = QLabel(cur_mask)
        self.lbl_cur_mask.setFixedHeight(28)
        self.lbl_cur_mask.setStyleSheet(cur_style)
        self.edit_new_mask = QLineEdit(cur_mask)
        self.edit_new_mask.setFixedHeight(28)
        self.edit_new_mask.setStyleSheet(edit_style)
        self.edit_new_mask.textChanged.connect(lambda: self._on_net_text_changed(self.edit_new_mask, self.lbl_cur_mask.text()))
        self.edit_new_mask.textEdited.connect(lambda: setattr(self, "_user_edited_mask", True))
        self.edit_new_mask.editingFinished.connect(lambda: self._on_net_edit_finished(self.edit_new_mask, self.lbl_cur_mask.text()))
        net_layout.addWidget(self.lbl_lbl_mask, 3, 0)
        net_layout.addWidget(self.lbl_cur_mask, 3, 1)
        net_layout.addWidget(self.edit_new_mask, 3, 2)

        # Footer Bar: Left Status text, Right Update button
        footer_bar = QHBoxLayout()
        footer_bar.setContentsMargins(0, 8, 0, 0)
        footer_bar.setSpacing(10)

        self.lbl_net_status = QLabel("Status: Super User login required to update settings.")
        self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")

        self.btn_update_net = QPushButton("💾 Update Network Settings")
        self.btn_update_net.setFixedHeight(28)
        self.btn_update_net.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_net.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border: 1px solid #0369A1;
                border-radius: 4px;
                padding: 4px 18px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QPushButton:disabled {
                background-color: #CBD5E1;
                border-color: #94A3B8;
                color: #64748B;
            }
        """)
        self.btn_update_net.clicked.connect(self.handle_update_network)

        footer_bar.addWidget(self.lbl_net_status)
        footer_bar.addStretch()
        footer_bar.addWidget(self.btn_update_net)

        net_layout.addLayout(footer_bar, 4, 0, 1, 3)

        col_left.addWidget(self.grp_net_params)

        # PLC Soft Restart Group (under left column card)
        self.grp_sys_reset = self._create_sys_reset_group()
        col_left.addWidget(self.grp_sys_reset, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        col_left.addStretch()
        content_layout.addLayout(col_left, 77)

        # =========================================================================
        # 2. Right Column: Unified Login Card (Identical Size & Position)
        # =========================================================================
        col_right = QVBoxLayout()
        self.login_card = LoginCard(
            on_login=self._handle_network_login,
            on_logout=self._handle_network_logout,
            parent=self
        )
        self.login_card.login_changed.connect(lambda _: self.update_ui_state())

        # Aliases for backward compatibility
        self.grp_login = self.login_card
        self.btn_login = self.login_card.btn_login
        self.edit_password = self.login_card.edit_password
        self.edit_pw = self.login_card.edit_password
        self.badge_login_status = self.login_card.badge_status
        self.badge_role = self.login_card.badge_status

        col_right.addWidget(self.login_card, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        col_right.addStretch()
        content_layout.addLayout(col_right, 23)

        main_layout.addLayout(content_layout)

    def _create_sys_reset_group(self):
        grp = QGroupBox("PLC Controller Action")
        grp.setFixedWidth(260)
        grp.setStyleSheet("""
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
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        self.lbl_sys_reset_hint = QLabel("PLC soft restart required for IP changes. Maintenance login required.")
        self.lbl_sys_reset_hint.setWordWrap(True)
        self.lbl_sys_reset_hint.setStyleSheet("font-size: 10px; color: #64748B;")
        layout.addWidget(self.lbl_sys_reset_hint)

        self.btn_plc_restart = QPushButton("🔄 PLC Soft Restart")
        self.btn_plc_restart.setFixedHeight(32)
        self.btn_plc_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plc_restart.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                border: 1.5px solid #DC2626;
                color: #B91C1C;
                font-weight: bold;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #B91C1C;
            }
            QPushButton:disabled {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                color: #94A3B8;
            }
        """)
        self.btn_plc_restart.clicked.connect(self.handle_plc_soft_restart)
        layout.addWidget(self.btn_plc_restart)

        return grp

    def _handle_network_login(self, pwd):
        ok, msg, role = self.plc.authenticate(pwd)
        if ok:
            return True, ""
        return False, tr("Incorrect password!", self.current_lang)

    def _handle_network_logout(self):
        self.plc.logout()

    def _on_auth_changed(self, role):
        self.current_user_role = role
        is_logged = (role != ROLE_NOT_LOGGED_IN)
        self.login_card.set_state(is_logged, role if is_logged else None)
        self.update_ui_state()

    def handle_login_logout(self):
        self.login_card.handle_login_logout()

    def update_ui_state(self):
        role = self.current_user_role
        is_logged = (role != ROLE_NOT_LOGGED_IN)
        is_super = (role == ROLE_SUPER_USER)
        is_auth = (role in [ROLE_MAINTENANCE, ROLE_SUPER_USER])

        # Enable/Disable network update button
        self.btn_update_net.setEnabled(is_auth)
        self.edit_new_host.setEnabled(is_auth)
        self.edit_new_ip.setEnabled(is_auth)
        self.edit_new_mask.setEnabled(is_auth)
        if hasattr(self, 'btn_plc_restart'):
            self.btn_plc_restart.setEnabled(is_auth)

        # Update role badge on unified LoginCard
        role_display = tr(role, self.current_lang) if is_logged else None
        self.login_card.set_state(is_logged, role_name=role_display)

        node_missing = (self.plc.is_opcua_online and not getattr(self.plc, "has_network_nodes", False))

        if is_auth:
            if node_missing:
                self.lbl_net_status.setText(
                    tr("⚠️ Authorized, but PLC Symbol Configuration does not export network variables (BadNodeIdUnknown).", self.current_lang)
                )
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #D97706; margin-top: 4px;")
            elif is_super:
                self.lbl_net_status.setText(tr("Status: Super User logged in. All restrictions lifted.", self.current_lang))
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D; margin-top: 4px;")
            else:
                self.lbl_net_status.setText(tr("Status: Authorized. Ready to apply network settings.", self.current_lang))
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D; margin-top: 4px;")
        else:
            if node_missing:
                self.lbl_net_status.setText(
                    tr("Status: Maintenance login required. ⚠️ PLC symbol not exported.", self.current_lang)
                )
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #DC2626; margin-top: 4px;")
            else:
                self.lbl_net_status.setText(tr("Status: Maintenance login required to update settings.", self.current_lang))
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B; margin-top: 4px;")

    def _on_net_text_changed(self, edit, cur_val):
        txt = edit.text().strip()
        if txt and txt != cur_val:
            edit.setStyleSheet("""
                QLineEdit {
                    background-color: #FFFDE7;
                    border: 2px solid #FBC02D;
                    color: #E65100;
                    font-weight: bold;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 11px;
                }
            """)
        else:
            edit.setStyleSheet(self._edit_style)

    def _on_net_edit_finished(self, edit, cur_val):
        txt = edit.text().strip()
        if not txt or txt == cur_val:
            edit.setText(cur_val)
            edit.setStyleSheet(self._edit_style)
            if edit == self.edit_new_host: self._user_edited_host = False
            elif edit == self.edit_new_ip: self._user_edited_ip = False
            elif edit == self.edit_new_mask: self._user_edited_mask = False

    def auto_sync_from_plc(self):
        """Automatically synchronize live network parameters from PLC state"""
        cur_host = getattr(self.plc, "net_hostname", DEFAULT_PLC_HOSTNAME) or DEFAULT_PLC_HOSTNAME
        cur_ip = getattr(self.plc, "net_ip", DEFAULT_PLC_IP) or DEFAULT_PLC_IP
        cur_mask = getattr(self.plc, "net_subnet", DEFAULT_PLC_SUBNET) or DEFAULT_PLC_SUBNET

        self.lbl_cur_host.setText(cur_host)
        self.lbl_cur_ip.setText(cur_ip)
        self.lbl_cur_mask.setText(cur_mask)

        # Pre-fill or sync edit inputs if user hasn't explicitly typed custom input
        if not self._user_edited_host and not self.edit_new_host.hasFocus():
            self.edit_new_host.setText(cur_host)
            self.edit_new_host.setStyleSheet(self._edit_style)

        if not self._user_edited_ip and not self.edit_new_ip.hasFocus():
            self.edit_new_ip.setText(cur_ip)
            self.edit_new_ip.setStyleSheet(self._edit_style)

        if not self._user_edited_mask and not self.edit_new_mask.hasFocus():
            self.edit_new_mask.setText(cur_mask)
            self.edit_new_mask.setStyleSheet(self._edit_style)

        self.update_ui_state()

    def handle_sync_from_plc(self):
        self.auto_sync_from_plc()

    def showEvent(self, event):
        super().showEvent(event)
        self.auto_sync_from_plc()

    def handle_update_network(self):
        cur_host = getattr(self.plc, "net_hostname", DEFAULT_PLC_HOSTNAME) or DEFAULT_PLC_HOSTNAME
        cur_ip = getattr(self.plc, "net_ip", DEFAULT_PLC_IP) or DEFAULT_PLC_IP
        cur_mask = getattr(self.plc, "net_subnet", DEFAULT_PLC_SUBNET) or DEFAULT_PLC_SUBNET

        host = self.edit_new_host.text().strip() or cur_host
        ip = self.edit_new_ip.text().strip() or cur_ip
        mask = self.edit_new_mask.text().strip() or cur_mask

        # Validate Hostname
        if not HOSTNAME_REGEX.match(host):
            title = tr("Format Error", self.current_lang)
            msg = tr("Invalid Hostname: '{host}'!\nOnly alphanumeric characters, underscores, and hyphens allowed (1-32 chars).", self.current_lang).format(host=host)
            QMessageBox.warning(self, title, msg)
            return

        # Validate IP address
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            title = tr("Format Error", self.current_lang)
            msg = tr("Invalid IPv4 address: '{ip}'!", self.current_lang).format(ip=ip)
            QMessageBox.warning(self, title, msg)
            return

        # Validate Subnet Mask
        try:
            ipaddress.IPv4Network(f"0.0.0.0/{mask}")
        except ValueError:
            title = tr("Format Error", self.current_lang)
            msg = tr("Invalid subnet mask: '{mask}'!", self.current_lang).format(mask=mask)
            QMessageBox.warning(self, title, msg)
            return

        self.edit_new_host.setText(host)
        self.edit_new_ip.setText(ip)
        self.edit_new_mask.setText(mask)

        if self.current_user_role not in [ROLE_MAINTENANCE, ROLE_SUPER_USER]:
            QMessageBox.warning(self, tr("Permission Denied", self.current_lang), tr("Network settings update requires Maintenance login!", self.current_lang))
            return

        # 1. Require PLC to be online
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            warn_msg = tr("⚠️ PLC communication is offline. Cannot send network settings to controller!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, warn_msg)
            return

        self._user_edited_host = False
        self._user_edited_ip = False
        self._user_edited_mask = False

        # 2. Check whether CODESYS exports the symbol
        if not getattr(self.plc, "has_network_nodes", False):
            title = tr("PLC Symbol Missing Warning", self.current_lang)
            warn_msg = tr(
                "⚠️ Write Failed (Error: BadNodeIdUnknown)\n\n"
                "The node 'Common.PVturbineSpecific.network' is not published in CODESYS Symbol Configuration.\n\n"
                "• PLC hardware: NOT written (symbol not exported)\n\n"
                "💡 Solution: In CODESYS Symbol Configuration, check 'Common.PVturbineSpecific' and perform Online Change.",
                self.current_lang
            )
            QMessageBox.warning(self, title, warn_msg)
            self.lbl_net_status.setText("⚠️ " + tr("PLC symbol missing, cannot apply", self.current_lang))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #D97706; margin-top: 4px;")
            return

        # 3. Transmit to PLC
        self.opcua_service.write_network_settings(host, ip, mask)
        if hasattr(self.plc, "net_hostname"):
            self.plc.net_hostname = host
            self.plc.net_ip = ip
            self.plc.net_subnet = mask

        self.lbl_cur_host.setText(host)
        self.lbl_cur_ip.setText(ip)
        self.lbl_cur_mask.setText(mask)
        self.edit_new_host.setText(host)
        self.edit_new_ip.setText(ip)
        self.edit_new_mask.setText(mask)
        self.edit_new_host.setStyleSheet(self._edit_style)
        self.edit_new_ip.setStyleSheet(self._edit_style)
        self.edit_new_mask.setStyleSheet(self._edit_style)

        title = tr("Network Settings", self.current_lang)
        info_msg = tr(
            "✔ Network parameters sent to PLC successfully!\n\nPlease perform PLC Soft Restart below to apply changes.",
            self.current_lang
        )
        QMessageBox.information(self, title, info_msg)
        self.lbl_net_status.setText("✔ " + tr("Sent to PLC. Restart controller to apply", self.current_lang))
        self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D; margin-top: 4px;")

    def handle_plc_soft_restart(self):
        title = tr("PLC Soft Restart Confirmation", self.current_lang)
        prompt = tr(
            "⚠️ WARNING: Are you sure you want to send Soft Restart (sysReset) to the PLC?\n\n"
            "This will restart the PLC controller to apply settings. Please verify site safety and ensure no personnel in the hub!",
            self.current_lang
        )
        reply = QMessageBox.question(
            self,
            title,
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.send_plc_sys_reset()
                success_msg = tr("PLC soft restart command sent successfully!", self.current_lang)
                QMessageBox.information(self, title, success_msg)
            else:
                warn_msg = tr("⚠️ PLC communication is offline. Cannot send soft restart command!\nPlease check OPC UA connection.", self.current_lang)
                QMessageBox.warning(self, title, warn_msg)

    def retranslate_ui(self, lang="EN"):
        self.current_lang = lang
        self.grp_net_params.setTitle(tr("PLC Ethernet Configuration", lang))
        self.lbl_hdr_param.setText(tr("Parameter", lang))
        self.lbl_cur_hdr.setText(tr("Current Value", lang))
        self.lbl_new_hdr.setText(tr("New Value (Editable)", lang))
        self.lbl_lbl_host.setText(tr("Hostname", lang))
        self.lbl_lbl_ip.setText(tr("IP address", lang))
        self.lbl_lbl_mask.setText(tr("Subnet mask", lang))
        self.btn_update_net.setText(tr("💾 Update Network Settings", lang))

        if hasattr(self, 'grp_sys_reset'):
            self.grp_sys_reset.setTitle(tr("PLC Controller Action", lang))
            self.lbl_sys_reset_hint.setText(tr("PLC soft restart required for IP changes. Maintenance login required.", lang))
            self.btn_plc_restart.setText(tr("🔄 PLC Soft Restart", lang))

        self.login_card.retranslate_ui(lang)
        self.update_ui_state()
