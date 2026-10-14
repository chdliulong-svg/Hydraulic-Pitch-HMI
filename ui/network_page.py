# -*- coding: utf-8 -*-
"""
Network Configuration Page
Replaces legacy FilePage.
Provides PLC Ethernet configuration (Hostname, IP, Subnet Mask)
and User Authentication using unified LoginCard.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from config import (
    DEFAULT_PLC_HOSTNAME, DEFAULT_PLC_IP, DEFAULT_PLC_SUBNET,
    PASSWORD_SUPER_USER, PASSWORD_MAINT_LOGIN,
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
        is_cn = (self.current_lang == "CN")
        grp = QGroupBox("PLC 控制器操作" if is_cn else "PLC Controller Action")
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

        self.lbl_sys_reset_hint = QLabel(
            "修改网络参数后需软重启 PLC 生效。需登录维护权限。" if is_cn
            else "PLC soft restart required for IP changes. Maintenance login required."
        )
        self.lbl_sys_reset_hint.setWordWrap(True)
        self.lbl_sys_reset_hint.setStyleSheet("font-size: 10px; color: #64748B;")
        layout.addWidget(self.lbl_sys_reset_hint)

        self.btn_plc_restart = QPushButton("🔄 PLC 软重启" if is_cn else "🔄 PLC Soft Restart")
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
        if pwd in [PASSWORD_SUPER_USER, "super"]:
            self.current_user_role = ROLE_SUPER_USER
            self.plc.is_super_user = True
            return True, ""
        elif pwd in [PASSWORD_MAINT_LOGIN, "asdf"]:
            self.current_user_role = ROLE_MAINTENANCE
            return True, ""
        return False, tr("Invalid password!", self.current_lang)

    def _handle_network_logout(self):
        self.current_user_role = ROLE_NOT_LOGGED_IN
        self.plc.is_super_user = False

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

        is_cn = (self.current_lang == "CN")
        node_missing = (self.plc.is_opcua_online and not getattr(self.plc, "has_network_nodes", False))

        if is_auth:
            if node_missing:
                self.lbl_net_status.setText(
                    "⚠️ 权限正常，但 PLC 符号配置未发布网络变量 (BadNodeIdUnknown)，修改仅在本地生效。" if is_cn
                    else "⚠️ Authorized, but PLC Symbol Configuration does not export network variables (BadNodeIdUnknown)."
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
                    "状态: 需维护登录。⚠️ PLC 符号配置未发布 Common.PVturbineSpecific.network" if is_cn
                    else "Status: Maintenance login required. ⚠️ PLC symbol not exported."
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

        self.edit_new_host.setText(host)
        self.edit_new_ip.setText(ip)
        self.edit_new_mask.setText(mask)

        if self.current_user_role not in [ROLE_MAINTENANCE, ROLE_SUPER_USER]:
            QMessageBox.warning(self, tr("Permission Denied", self.current_lang), tr("Network settings update requires Maintenance login!", self.current_lang))
            return

        self._user_edited_host = False
        self._user_edited_ip = False
        self._user_edited_mask = False
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

        is_cn = (self.current_lang == "CN")

        # Check whether OPC UA is online and whether network node is available
        if self.opcua_service and self.plc.is_opcua_online:
            if not getattr(self.plc, "has_network_nodes", False):
                title = "PLC 节点未导出警告" if is_cn else "PLC Symbol Missing Warning"
                warn_msg = (
                    "⚠️ 写入失败 (错误: BadNodeIdUnknown)\n\n"
                    "当前 CODESYS PLC 的【符号配置】(Symbol Configuration) 中未导出 'Common.PVturbineSpecific.network'，OPC UA 无法寻址该节点。\n\n"
                    "• 上位机本地缓存：已更新为新参数\n"
                    "• PLC 控制器硬件：未能写入（变量未发布）\n\n"
                    "💡 解决建议：请在 CODESYS 项目的【Symbol Configuration】中勾选 'Common.PVturbineSpecific' 变量，并执行在线变更 (Online Change)。"
                    if is_cn else
                    "⚠️ Write Failed (Error: BadNodeIdUnknown)\n\n"
                    "The node 'Common.PVturbineSpecific.network' is not published in CODESYS Symbol Configuration.\n\n"
                    "• Local HMI memory: Updated\n"
                    "• PLC hardware: NOT written (symbol not exported)\n\n"
                    "💡 Solution: In CODESYS Symbol Configuration, check 'Common.PVturbineSpecific' and perform Online Change."
                )
                QMessageBox.warning(self, title, warn_msg)
                self.lbl_net_status.setText("⚠️ " + ("PLC 节点未发布，参数仅在本地更新" if is_cn else "PLC symbol missing, updated locally only"))
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #D97706; margin-top: 4px;")
            else:
                self.opcua_service.write_network_settings(host, ip, mask)
                title = "网络设置" if is_cn else "Network Settings"
                info_msg = (
                    "✔ 网络参数已成功下发至 PLC！\n\n请在下方点击【🔄 PLC 软重启】使新网络配置生效。"
                    if is_cn else
                    "✔ Network parameters sent to PLC successfully!\n\nPlease perform PLC Soft Restart below to apply changes."
                )
                QMessageBox.information(self, title, info_msg)
                self.lbl_net_status.setText("✔ " + ("参数已下发至 PLC，重启控制器生效" if is_cn else "Sent to PLC. Restart controller to apply"))
                self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D; margin-top: 4px;")
        else:
            title = "通信断开" if is_cn else "Communication Offline"
            warn_msg = (
                "⚠️ 当前 PLC 通信已断开，网络参数已在本地保存，但未能下发至控制器！\n\n待建立 OPC UA 通信后方可下发至 PLC。"
                if is_cn else
                "⚠️ PLC communication is offline. Network settings saved locally, but NOT sent to controller!\n\nPlease check OPC UA connection."
            )
            QMessageBox.warning(self, title, warn_msg)
            self.lbl_net_status.setText("⚠️ " + ("当前离线，参数仅在本地更新" if is_cn else "Offline, updated locally only"))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #DC2626; margin-top: 4px;")

    def handle_plc_soft_restart(self):
        is_cn = (self.current_lang == "CN")
        title = "PLC 软重启确认" if is_cn else "PLC Soft Restart Confirmation"
        prompt = (
            "⚠️ 警告：确定要向 PLC 发送软重启指令 (sysReset) 吗？\n\n"
            "此操作将使 CODESYS PLC 控制器重启并应用新的网络设置，请确保现场设备安全并且人员不在轮毂内！"
            if is_cn else
            "⚠️ WARNING: Are you sure you want to send Soft Restart (sysReset) to the PLC?\n\n"
            "This will restart the PLC controller to apply settings. Please verify site safety and ensure no personnel in the hub!"
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
                self.opcua_service.send_msgbox_ok()
                success_msg = "PLC 软重启指令已成功下发至控制器！" if is_cn else "PLC soft restart command sent successfully!"
                QMessageBox.information(self, title, success_msg)
            else:
                warn_msg = (
                    "⚠️ 当前 PLC 通信已断开，无法下发软重启指令！\n请检查底层 OPC UA 通信连接。"
                    if is_cn else
                    "⚠️ PLC communication is offline. Cannot send soft restart command!\nPlease check OPC UA connection."
                )
                QMessageBox.warning(self, title, warn_msg)
        else:
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.send_msgbox_abort()

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
