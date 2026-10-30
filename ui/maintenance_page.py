# -*- coding: utf-8 -*-
"""
Maintenance Mode Page - Hydraulic Pitch HMI
Consolidates Work Deck with 3 Sub-Tabs:
1. Output:
   - HPU Hydraulic Power Unit
   - Lubrication System Test
   - PAC Valve Actuation & Proportional Valve Control
2. Network:
   - PLC Ethernet Configuration (Hostname, IP, Subnet Mask)
3. Restart:
   - PLC Controller Action (Soft Restart / sysReset)

Right Column:
- Persistent Login Card & Maintenance Mode Card across all tabs.
"""

import ipaddress
import os
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QCheckBox, QSlider, QLineEdit, QMessageBox,
    QFrame, QDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from config import (
    MODE_MAINTENANCE, STATE_ABORTED,
    ROLE_NOT_LOGGED_IN, ROLE_MAINTENANCE, ROLE_SUPER_USER,
    DEFAULT_PLC_HOSTNAME, DEFAULT_PLC_IP, DEFAULT_PLC_SUBNET
)
from utils.widgets import WarningModal
from utils.i18n import tr
from ui.login_card import LoginCard
from ui.mode_card import ModeCard, PillBadge

HOSTNAME_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

# Proportional valve spool command physical limits (%)
PROP_VALVE_MIN_CMD = -100.0
PROP_VALVE_MAX_CMD = 100.0


class MaintenancePage(QWidget):
    tab_changed = pyqtSignal(int)

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
        self.current_lang = "EN"
        self._user_edited_host = False
        self._user_edited_ip = False
        self._user_edited_mask = False

        self.init_ui()
        self.retranslate_ui(self.current_lang)

        # Signal connections
        self.plc.state_changed.connect(self.update_ui_state)
        self.plc.auth_changed.connect(self._on_auth_changed)
        self.auto_sync_from_plc()
        self.update_ui_state()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Left Area: Work Deck with 3 Sub-Tabs (Output / Network / Restart)
        # -------------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 13px;
                font-weight: bold;
                background-color: #E4E7EB;
                border: 1px solid #B0B5B9;
                border-bottom: none;
                min-width: 90px;
                height: 28px;
                padding: 4px 20px;
                margin-right: 4px;
                color: #222222;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border-bottom: 2px solid #FFFFFF;
                color: #111111;
            }
            QTabWidget::pane {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                background-color: #ECEEF2;
            }
        """)

        # 1. Output Tab
        self.tab_output = self._create_output_tab()
        self.tabs.addTab(self.tab_output, "Output")

        # 2. Network Tab
        self.tab_network = self._create_network_tab()
        self.tabs.addTab(self.tab_network, "Network")

        # 3. Restart Tab
        self.tab_restart = self._create_restart_tab()
        self.tabs.addTab(self.tab_restart, "Restart")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs, 1)

        # -------------------------------------------------------------
        # Right Column: Login Card & Mode Switch Card (Persistent across tabs)
        # -------------------------------------------------------------
        col_right = self._create_right_column()
        main_layout.addLayout(col_right, 0)

        # Locate checkmark icon
        res_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
        chk_icon_path = os.path.join(res_dir, "chk_white.png").replace("\\", "/")

        self.setStyleSheet(f"""
            QGroupBox {{
                font-size: 11px;
                font-weight: bold;
                color: #1E293B;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 6px;
                background-color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background-color: #FFFFFF;
                color: #0F172A;
            }}
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
                color: #0F172A;
            }}
            QLineEdit:focus {{
                border: 1.5px solid #0284C7;
            }}
            QLineEdit:disabled {{
                background-color: #F1F5F9;
                color: #94A3B8;
                border-color: #CBD5E1;
            }}
            QCheckBox {{
                font-size: 11px;
                color: #334155;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1.5px solid #94A3B8;
                border-radius: 3px;
                background-color: #FFFFFF;
            }}
            QCheckBox::indicator:checked {{
                background-color: #059669;
                border-color: #047857;
                image: url("{chk_icon_path}");
            }}
            QCheckBox::indicator:disabled {{
                background-color: #F1F5F9;
                border-color: #CBD5E1;
            }}
        """)

    def _on_tab_changed(self, idx):
        self.tab_changed.emit(idx)
        if idx == 1:
            self.auto_sync_from_plc()
        self.update_ui_state()

    # =========================================================================
    # Tab 0: Output (HPU, Lubrication, PAC Valve Matrix & Proportional Valve)
    # =========================================================================
    def _create_output_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # 1. HPU Card
        self.grp_hpu = self._create_hpu_group()
        layout.addWidget(self.grp_hpu)

        # 2. Lubrication Card
        self.grp_lub = self._create_lubrication_group()
        layout.addWidget(self.grp_lub)

        # 3. PAC Valve Matrix & Proportional Valve Section
        self.grp_pac = self._create_pac_valve_group()
        layout.addWidget(self.grp_pac, 1)

        return tab

    def _create_hpu_group(self):
        grp = QGroupBox("HPU Hydraulic Power Unit")
        grp.setFixedHeight(58)
        layout = QHBoxLayout(grp)
        layout.setContentsMargins(14, 2, 14, 6)
        layout.setSpacing(8)

        self.chk_hpu_pressure = QCheckBox("Request HPU Buildup")
        self.chk_hpu_pressure.setStyleSheet("font-weight: 500;")

        self.badge_hpu = PillBadge("🔒 Require Maint.")

        self.btn_hpu_reset = QPushButton("Reset")
        self.btn_hpu_reset.setFixedSize(68, 26)
        self.btn_hpu_reset.setStyleSheet(self._style_reset_btn())
        self.btn_hpu_reset.clicked.connect(self.reset_hpu)

        self.btn_hpu_apply = QPushButton("Apply")
        self.btn_hpu_apply.setFixedSize(72, 26)
        self.btn_hpu_apply.setStyleSheet(self._style_apply_btn())
        self.btn_hpu_apply.clicked.connect(self.apply_hpu)

        layout.addWidget(self.chk_hpu_pressure)
        layout.addStretch()
        layout.addWidget(self.badge_hpu)
        layout.addSpacing(6)
        layout.addWidget(self.btn_hpu_reset)
        layout.addWidget(self.btn_hpu_apply)

        return grp

    def _create_lubrication_group(self):
        grp = QGroupBox("Lubrication System Test")
        grp.setFixedHeight(58)
        layout = QHBoxLayout(grp)
        layout.setContentsMargins(14, 2, 14, 6)
        layout.setSpacing(8)

        self.chk_lub1 = QCheckBox("Lub. Pump 1")
        self.chk_lub2 = QCheckBox("Lub. Pump 2")

        self.badge_lub = PillBadge("🔒 Require Maint.")

        self.btn_lub_reset = QPushButton("Reset")
        self.btn_lub_reset.setFixedSize(68, 26)
        self.btn_lub_reset.setStyleSheet(self._style_reset_btn())
        self.btn_lub_reset.clicked.connect(self.reset_lub)

        self.btn_lub_apply = QPushButton("Apply")
        self.btn_lub_apply.setFixedSize(72, 26)
        self.btn_lub_apply.setStyleSheet(self._style_apply_btn())
        self.btn_lub_apply.clicked.connect(self.apply_lub)

        layout.addWidget(self.chk_lub1)
        layout.addSpacing(10)
        layout.addWidget(self.chk_lub2)
        layout.addStretch()
        layout.addWidget(self.badge_lub)
        layout.addSpacing(6)
        layout.addWidget(self.btn_lub_reset)
        layout.addWidget(self.btn_lub_apply)

        return grp

    def _create_pac_valve_group(self):
        grp = QGroupBox("PAC Valve Actuation Prop. Control")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(12, 4, 12, 6)
        layout.setSpacing(4)

        # Top Bar
        top_bar = QHBoxLayout()
        self.lbl_pac_desc = QLabel("Valve actuation & Prop. Valve 102A control")
        self.lbl_pac_desc.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_pac_desc.setStyleSheet("font-size: 11px; color: #64748B;")
        self.badge_pac = PillBadge("🔒 Require Maint. & Login")
        top_bar.addWidget(self.lbl_pac_desc)
        top_bar.addStretch()
        top_bar.addWidget(self.badge_pac)
        layout.addLayout(top_bar)

        # Central Split: Left Frame (Matrix) | Right Frame (Prop Valve)
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(10)

        # ----------------- Left Frame: Valve Matrix -----------------
        frame_valves = QFrame()
        frame_valves.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
            }
        """)
        fv_layout = QVBoxLayout(frame_valves)
        fv_layout.setContentsMargins(6, 6, 6, 6)
        fv_layout.setSpacing(2)

        grid_valves = QGridLayout()
        grid_valves.setHorizontalSpacing(4)
        grid_valves.setVerticalSpacing(2)
        grid_valves.setColumnStretch(0, 1)  # Valve name takes available width
        grid_valves.setColumnMinimumWidth(1, 26)  # A
        grid_valves.setColumnMinimumWidth(2, 26)  # B
        grid_valves.setColumnMinimumWidth(3, 26)  # C

        # Table Headers
        self.lbl_hdr_v_name = QLabel("Valve Name")
        self.lbl_hdr_v_name.setFixedHeight(26)
        self.lbl_hdr_v_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_va = QLabel("A")
        self.lbl_hdr_va.setFixedHeight(26)
        self.lbl_hdr_va.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_va.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_vb = QLabel("B")
        self.lbl_hdr_vb.setFixedHeight(26)
        self.lbl_hdr_vb.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_vb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_vc = QLabel("C")
        self.lbl_hdr_vc.setFixedHeight(26)
        self.lbl_hdr_vc.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_vc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid_valves.addWidget(self.lbl_hdr_v_name, 0, 0)
        grid_valves.addWidget(self.lbl_hdr_va, 0, 1)
        grid_valves.addWidget(self.lbl_hdr_vb, 0, 2)
        grid_valves.addWidget(self.lbl_hdr_vc, 0, 3)

        valve_defs = [
            ("Valve 132 Pitch Lock", "v132"),
            ("Valve 130 Pitch Lock", "v130"),
            ("Valve 120 EMF", "v120"),
            ("Valve 103 EMF", "v103"),
            ("Valve 119A Cut Off 1", "v119a"),
            ("Valve 119B Cut Off 2", "v119b"),
            ("Valve 109 Cut Off P", "v109"),
            ("Valve 116 Dump", "v116")
        ]

        self.valve_labels = []
        self.valve_checkboxes = []  # [(v_key, [chkA, chkB, chkC])]
        for row, (v_en, v_key) in enumerate(valve_defs, start=1):
            lbl_v = QLabel(v_en)
            lbl_v.setFixedHeight(28)
            lbl_v.setStyleSheet("font-size: 10px; font-weight: 500; color: #334155;")
            self.valve_labels.append((lbl_v, v_en))
            grid_valves.addWidget(lbl_v, row, 0)

            row_chks = []
            for col in range(3):
                chk = QCheckBox()
                chk.setFixedHeight(28)
                grid_valves.addWidget(chk, row, col + 1, Qt.AlignmentFlag.AlignCenter)
                row_chks.append(chk)
            self.valve_checkboxes.append((v_key, row_chks))

        fv_layout.addLayout(grid_valves)
        fv_layout.addStretch()
        mid_layout.addWidget(frame_valves, 2)

        # ----------------- Right Frame: Prop Valve -----------------
        frame_right = QFrame()
        frame_right.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
            }
        """)
        fr_layout = QVBoxLayout(frame_right)
        fr_layout.setContentsMargins(10, 8, 10, 8)
        fr_layout.setSpacing(6)

        self.lbl_hdr_prop = QLabel("Prop. Valve 102A (-100% ~ +100%)")
        self.lbl_hdr_prop.setStyleSheet("font-size: 11px; font-weight: bold; color: #0F172A;")
        fr_layout.addWidget(self.lbl_hdr_prop)

        prop_slider_style = """
            QSlider::groove:horizontal {
                height: 6px;
                background: #CBD5E1;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #3B82F6;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #2563EB;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #EFF6FF;
                border-color: #1D4ED8;
            }
            QSlider::disabled {
                background: transparent;
            }
            QSlider::sub-page:horizontal:disabled {
                background: #94A3B8;
            }
            QSlider::handle:horizontal:disabled {
                background: #E2E8F0;
                border-color: #94A3B8;
            }
        """

        self.prop_sliders = []
        self.prop_edits = []
        self.prop_labels = []

        blade_names = ["Blade A (102A):", "Blade B (102A):", "Blade C (102A):"]
        for b_name in blade_names:
            row_l = QHBoxLayout()
            row_l.setSpacing(8)

            lbl_b = QLabel(b_name)
            lbl_b.setFixedWidth(82)
            lbl_b.setStyleSheet("font-size: 10px; font-weight: 500; color: #334155;")
            self.prop_labels.append((lbl_b, b_name))

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-1000, 1000)
            slider.setValue(0)
            slider.setStyleSheet(prop_slider_style)

            edit = QLineEdit("0.0 %")
            edit.setFixedSize(58, 24)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setStyleSheet("""
                QLineEdit {
                    background-color: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    color: #0F172A;
                }
            """)

            def make_slider_handler(s, e):
                return lambda val: e.setText(f"{val / 10.0:.1f} %")

            slider.valueChanged.connect(make_slider_handler(slider, edit))

            def make_edit_handler(s, e):
                def on_edit_finished():
                    txt = e.text().replace("%", "").strip()
                    try:
                        v = float(txt)
                        v_clamped = max(PROP_VALVE_MIN_CMD, min(PROP_VALVE_MAX_CMD, v))
                        s.setValue(int(v_clamped * 10))
                        e.setText(f"{v_clamped:.1f} %")
                    except ValueError:
                        e.setText(f"{s.value() / 10.0:.1f} %")
                return on_edit_finished

            edit.editingFinished.connect(make_edit_handler(slider, edit))

            row_l.addWidget(lbl_b)
            row_l.addWidget(slider, 1)
            row_l.addWidget(edit)
            fr_layout.addLayout(row_l)

            self.prop_sliders.append(slider)
            self.prop_edits.append(edit)

        fr_layout.addSpacing(4)

        # Spool Feedback Frame
        spool_fb_frame = QFrame()
        spool_fb_frame.setStyleSheet("""
            QFrame {
                background-color: #F1F5F9;
                border: 1px dashed #CBD5E1;
                border-radius: 4px;
            }
        """)
        fb_layout = QHBoxLayout(spool_fb_frame)
        fb_layout.setContentsMargins(8, 4, 8, 4)
        fb_layout.setSpacing(10)

        self.lbl_spool_title = QLabel("Spool FB:")
        self.lbl_spool_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        fb_layout.addWidget(self.lbl_spool_title)

        self.lbl_spool_feedbacks = []
        for b_str in ["A: 0.0 %", "B: 0.0 %", "C: 0.0 %"]:
            lbl_fb = QLabel(b_str)
            lbl_fb.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold; color: #0284C7;")
            fb_layout.addWidget(lbl_fb)
            self.lbl_spool_feedbacks.append(lbl_fb)
        fb_layout.addStretch()
        fr_layout.addWidget(spool_fb_frame)

        fr_layout.addStretch()

        # Notice label at bottom of right frame
        self.lbl_pac_notice = QLabel("Notice: After setting valves or proportional command, click 'Apply Changes' to transmit to PLC.")
        self.lbl_pac_notice.setWordWrap(True)
        self.lbl_pac_notice.setStyleSheet("font-size: 10px; color: #64748B; line-height: 1.3;")
        fr_layout.addWidget(self.lbl_pac_notice)

        mid_layout.addWidget(frame_right, 3)
        layout.addLayout(mid_layout, 1)

        # Bottom Button Deck
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_pac_reset = QPushButton("Reset")
        self.btn_pac_reset.setFixedSize(76, 28)
        self.btn_pac_reset.setStyleSheet(self._style_reset_btn())
        self.btn_pac_reset.clicked.connect(self.reset_pac)

        self.btn_pac_apply = QPushButton("Apply Changes")
        self.btn_pac_apply.setFixedSize(110, 28)
        self.btn_pac_apply.setStyleSheet(self._style_apply_btn())
        self.btn_pac_apply.clicked.connect(self.apply_pac)

        btn_row.addWidget(self.btn_pac_reset)
        btn_row.addSpacing(6)
        btn_row.addWidget(self.btn_pac_apply)
        layout.addLayout(btn_row)

        return grp

    # =========================================================================
    # Tab 1: Network (PLC Ethernet Configuration)
    # =========================================================================
    def _create_network_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

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

        self.lbl_net_status = QLabel("Status: Maintenance login required to update settings.")
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
        layout.addWidget(self.grp_net_params)
        layout.addStretch(1)

        return tab

    def _on_net_text_changed(self, edit, cur_val):
        if edit.text().strip() != cur_val:
            edit.setStyleSheet("""
                QLineEdit {
                    background-color: #FEF3C7;
                    border: 1.5px solid #F59E0B;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-family: 'Consolas', 'Segoe UI', monospace;
                    font-size: 11px;
                    font-weight: bold;
                    color: #92400E;
                }
            """)
        else:
            edit.setStyleSheet(self._edit_style)

    def _on_net_edit_finished(self, edit, cur_val):
        if edit.text().strip() == cur_val:
            edit.setStyleSheet(self._edit_style)
            if edit == self.edit_new_host: self._user_edited_host = False
            elif edit == self.edit_new_ip: self._user_edited_ip = False
            elif edit == self.edit_new_mask: self._user_edited_mask = False

    def auto_sync_from_plc(self):
        """Automatically synchronize live network parameters from PLC state"""
        cur_host = getattr(self.plc, "net_hostname", DEFAULT_PLC_HOSTNAME) or DEFAULT_PLC_HOSTNAME
        cur_ip = getattr(self.plc, "net_ip", DEFAULT_PLC_IP) or DEFAULT_PLC_IP
        cur_mask = getattr(self.plc, "net_subnet", DEFAULT_PLC_SUBNET) or DEFAULT_PLC_SUBNET

        if hasattr(self, "lbl_cur_host"):
            self.lbl_cur_host.setText(cur_host)
            self.lbl_cur_ip.setText(cur_ip)
            self.lbl_cur_mask.setText(cur_mask)

            if not self._user_edited_host and not self.edit_new_host.hasFocus():
                self.edit_new_host.setText(cur_host)
                self.edit_new_host.setStyleSheet(self._edit_style)

            if not self._user_edited_ip and not self.edit_new_ip.hasFocus():
                self.edit_new_ip.setText(cur_ip)
                self.edit_new_ip.setStyleSheet(self._edit_style)

            if not self._user_edited_mask and not self.edit_new_mask.hasFocus():
                self.edit_new_mask.setText(cur_mask)
                self.edit_new_mask.setStyleSheet(self._edit_style)

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

        role = getattr(self.plc, "current_role", ROLE_NOT_LOGGED_IN)
        if role not in [ROLE_MAINTENANCE, ROLE_SUPER_USER]:
            QMessageBox.warning(self, tr("Permission Denied", self.current_lang), tr("Network settings update requires Maintenance login!", self.current_lang))
            return

        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            warn_msg = tr("⚠️ PLC communication is offline. Cannot send network settings to controller!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, warn_msg)
            return

        self._user_edited_host = False
        self._user_edited_ip = False
        self._user_edited_mask = False

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

        self.lbl_net_status.setText("✔ " + tr("Sent to PLC. Restart controller to apply", self.current_lang))
        self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D; margin-top: 4px;")

    # =========================================================================
    # Tab 2: Restart (PLC Controller Action / Soft Restart)
    # =========================================================================
    def _create_restart_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.grp_sys_reset = QGroupBox("PLC Controller Action")
        self.grp_sys_reset.setStyleSheet("""
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
        rst_layout = QVBoxLayout(self.grp_sys_reset)
        rst_layout.setContentsMargins(16, 14, 16, 16)
        rst_layout.setSpacing(12)

        self.lbl_sys_reset_hint = QLabel(
            "PLC soft restart (sysReset) is required to apply IP changes, or to perform a cold controller reset.\n\n"
            "⚠️ Safety Notice: Before triggering soft restart, please verify site safety and confirm no personnel are inside the hub!"
        )
        self.lbl_sys_reset_hint.setWordWrap(True)
        self.lbl_sys_reset_hint.setStyleSheet("font-size: 11px; color: #475569; line-height: 1.4;")
        rst_layout.addWidget(self.lbl_sys_reset_hint)

        btn_row = QHBoxLayout()
        self.btn_plc_restart = QPushButton("🔄 PLC Soft Restart")
        self.btn_plc_restart.setFixedHeight(36)
        self.btn_plc_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plc_restart.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                border: 1.5px solid #DC2626;
                color: #B91C1C;
                font-weight: bold;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 24px;
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
        btn_row.addWidget(self.btn_plc_restart, 0, Qt.AlignmentFlag.AlignLeft)
        btn_row.addStretch()
        rst_layout.addLayout(btn_row)

        self.lbl_restart_status = QLabel("Status: Maintenance login required to trigger controller restart.")
        self.lbl_restart_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")
        rst_layout.addWidget(self.lbl_restart_status)

        layout.addWidget(self.grp_sys_reset)
        layout.addStretch(1)

        return tab

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
            if self.opcua_service and getattr(self.plc, "is_opcua_online", False):
                self.opcua_service.send_plc_sys_reset()
                self.lbl_restart_status.setText("✔ " + tr("PLC soft restart command sent successfully!", self.current_lang))
                self.lbl_restart_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D;")
            else:
                warn_msg = tr("⚠️ PLC communication is offline. Cannot send soft restart command!\nPlease check OPC UA connection.", self.current_lang)
                QMessageBox.warning(self, title, warn_msg)

    # =========================================================================
    # Right Column (Login Card, Mode Switch Card) - Persistent across tabs
    # =========================================================================
    def _create_right_column(self):
        col = QVBoxLayout()
        col.setSpacing(8)

        # 1. Login Card (Unified Component)
        self.login_card = LoginCard(
            on_login=self._handle_maint_login,
            on_logout=self._handle_maint_logout,
            parent=self
        )
        self.login_card.login_changed.connect(lambda _: self.update_ui_state())
        self.grp_login = self.login_card
        self.btn_login = self.login_card.btn_login
        self.edit_password = self.login_card.edit_password
        self.badge_login_status = self.login_card.badge_status
        self.badge_login = self.login_card.badge_status

        col.addWidget(self.login_card, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # 2. Mode Switch Card
        self.grp_mode = ModeCard(
            mode_type="maintenance",
            on_action=self.handle_mode_action,
            parent=self
        )
        self.btn_mode_action = self.grp_mode.btn_action
        self.badge_mode = self.grp_mode.badge_status
        self.lbl_mode_state_hint = self.grp_mode.lbl_status_hint
        col.addWidget(self.grp_mode, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        col.addStretch(1)
        return col

    # =========================================================================
    # Button Styles
    # =========================================================================
    def _style_reset_btn(self):
        return """
            QPushButton {
                background-color: #F1F5F9; border: 1px solid #CBD5E1;
                border-radius: 3px; font-size: 11px; font-weight: bold; color: #475569;
            }
            QPushButton:hover { background-color: #E2E8F0; }
            QPushButton:disabled { background-color: #F8FAFC; color: #CBD5E1; border-color: #E2E8F0; }
        """

    def _style_apply_btn(self):
        return """
            QPushButton {
                background-color: #10B981; border: 1px solid #059669;
                border-radius: 3px; font-size: 11px; font-weight: bold; color: white;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #E2E8F0; color: #94A3B8; border-color: #CBD5E1; }
        """

    # =========================================================================
    # Internationalization (i18n) Retranslation
    # =========================================================================
    def retranslate_ui(self, lang="EN"):
        self.current_lang = lang

        # Tabs
        self.tabs.setTabText(0, tr("Output", lang))
        self.tabs.setTabText(1, tr("Network", lang))
        self.tabs.setTabText(2, tr("Restart", lang))

        # Output Tab Items
        self.grp_hpu.setTitle(tr("HPU Hydraulic Power Unit", lang))
        self.grp_lub.setTitle(tr("Lubrication System Test", lang))
        self.grp_pac.setTitle(tr("PAC Valve Actuation & Prop. Control", lang))

        self.chk_hpu_pressure.setText(tr("Request HPU Buildup", lang))
        self.chk_lub1.setText(tr("Lub. Pump 1", lang))
        self.chk_lub2.setText(tr("Lub. Pump 2", lang))

        self.btn_hpu_reset.setText(tr("Reset", lang))
        self.btn_hpu_apply.setText(tr("Apply", lang))
        self.btn_lub_reset.setText(tr("Reset", lang))
        self.btn_lub_apply.setText(tr("Apply", lang))
        self.btn_pac_reset.setText(tr("Reset", lang))
        self.btn_pac_apply.setText(tr("Apply Changes", lang))

        self.lbl_pac_desc.setText(tr("Valve actuation & Prop. Valve 102A control", lang))
        self.lbl_hdr_v_name.setText(tr("Valve Name", lang))
        self.lbl_hdr_va.setText("A")
        self.lbl_hdr_vb.setText("B")
        self.lbl_hdr_vc.setText("C")

        for lbl, v_en in self.valve_labels:
            lbl.setText(tr(v_en, lang))

        self.lbl_hdr_prop.setText(tr("Prop. Valve 102A (-100% ~ +100%)", lang))
        for lbl_p, en_t in self.prop_labels:
            lbl_p.setText(tr(en_t, lang))
        self.lbl_spool_title.setText(tr("Spool FB:", lang))
        self.lbl_pac_notice.setText(tr("Notice: After setting valves or proportional command, click 'Apply Changes' to transmit to PLC.", lang))

        # Network Tab Items
        self.grp_net_params.setTitle(tr("PLC Ethernet Configuration", lang))
        self.lbl_hdr_param.setText(tr("Parameter", lang))
        self.lbl_cur_hdr.setText(tr("Current Value", lang))
        self.lbl_new_hdr.setText(tr("New Value (Editable)", lang))
        self.lbl_lbl_host.setText(tr("Hostname", lang))
        self.lbl_lbl_ip.setText(tr("IP address", lang))
        self.lbl_lbl_mask.setText(tr("Subnet mask", lang))
        self.btn_update_net.setText(tr("💾 Update Network Settings", lang))

        # Restart Tab Items
        self.grp_sys_reset.setTitle(tr("PLC Controller Action", lang))
        self.lbl_sys_reset_hint.setText(tr(
            "PLC soft restart (sysReset) is required to apply IP changes, or to perform a cold controller reset.\n\n"
            "⚠️ Safety Notice: Before triggering soft restart, please verify site safety and confirm no personnel are inside the hub!",
            lang
        ))
        self.btn_plc_restart.setText(tr("🔄 PLC Soft Restart", lang))

        # Right Column Cards
        self.grp_login.setTitle(tr("Login", lang))
        self.login_card.retranslate_ui(lang)
        self.grp_mode.retranslate_ui(lang)
        self.lbl_mode_state_hint.setText(tr("Interlock:", lang))

        self.update_ui_state()

    # =========================================================================
    # UI State Synchronization & Interlock Enforcing
    # =========================================================================
    def update_ui_state(self):
        in_maint = (self.plc.blade_mode == MODE_MAINTENANCE)
        logged_in = getattr(self.plc, "maint_logged_in", False)
        is_super = getattr(self.plc, "is_super_user", False)
        role = getattr(self.plc, "current_role", ROLE_NOT_LOGGED_IN)
        is_auth = (role in [ROLE_MAINTENANCE, ROLE_SUPER_USER]) or logged_in or is_super
        is_online = getattr(self.plc, "is_opcua_online", False)

        # 1. Update Login Card
        role_name = tr("Super User", self.current_lang) if is_super else tr("Maintenance", self.current_lang)
        self.login_card.set_state(is_auth, role_name=role_name if is_auth else None)

        # 2. Update Output Tab State
        can_req_maint = (self.plc.blade_state == STATE_ABORTED) or is_super
        if not is_online:
            self.badge_hpu.set_state("locked", tr("🔒 Offline", self.current_lang))
            self.badge_lub.set_state("locked", tr("🔒 Offline", self.current_lang))
            self.badge_pac.set_state("locked", tr("🔒 Offline", self.current_lang))
            self.grp_mode.set_state(
                is_active=in_maint,
                can_enter=False,
                prompt_text=tr("PLC communication offline. Mode switch disabled.", self.current_lang),
                badge_text=tr("🔒 Offline", self.current_lang),
                badge_type="locked",
                can_exit=False
            )
        elif in_maint:
            self.badge_hpu.set_state("ready", tr("✔ In Maintenance", self.current_lang))
            self.badge_lub.set_state("ready", tr("✔ In Maintenance", self.current_lang))
            self.badge_pac.set_state("ready", tr("✔ Ready to Test", self.current_lang))

            prompt = tr("Active in Maintenance Mode. Testing enabled.", self.current_lang)
            self.grp_mode.set_state(
                is_active=True,
                can_enter=False,
                prompt_text=prompt,
                badge_text=tr("✔ Active", self.current_lang),
                badge_type="ready",
                can_exit=True
            )
        else:
            if is_super:
                self.badge_hpu.set_state("ready", tr("✔ Super Access", self.current_lang))
                self.badge_lub.set_state("ready", tr("✔ Super Access", self.current_lang))
                self.badge_pac.set_state("ready", tr("✔ Super Access", self.current_lang))
                prompt = tr("Super User active. All restrictions lifted.", self.current_lang)
                badge_text = tr("✔ Super Access", self.current_lang)
                badge_type = "ready"
            else:
                self.badge_hpu.set_state("locked", tr("🔒 Require Maint.", self.current_lang))
                self.badge_lub.set_state("locked", tr("🔒 Require Maint.", self.current_lang))
                self.badge_pac.set_state("locked", tr("🔒 Require Maint. & Login", self.current_lang))

                if can_req_maint:
                    prompt = tr("Preconditions met. Ready to enter maintenance mode.", self.current_lang)
                    badge_text = tr("✔ Ready to Enter", self.current_lang)
                    badge_type = "ready"
                else:
                    if not is_auth:
                        prompt = tr("Must be in Aborted state and logged in.", self.current_lang)
                    else:
                        prompt = tr("System must be in Aborted state to enter.", self.current_lang)
                    badge_text = tr("🔒 Need Aborted", self.current_lang)
                    badge_type = "locked"

            self.grp_mode.set_state(
                is_active=False,
                can_enter=can_req_maint,
                prompt_text=prompt,
                badge_text=badge_text,
                badge_type=badge_type
            )

        output_allowed = ((in_maint and is_auth) or is_super) and is_online

        self.chk_hpu_pressure.setEnabled(output_allowed)
        self.btn_hpu_apply.setEnabled(output_allowed)
        self.btn_hpu_reset.setEnabled(output_allowed)

        self.chk_lub1.setEnabled(output_allowed)
        self.chk_lub2.setEnabled(output_allowed)
        self.btn_lub_apply.setEnabled(output_allowed)
        self.btn_lub_reset.setEnabled(output_allowed)

        for _, row_chks in self.valve_checkboxes:
            for chk in row_chks:
                chk.setEnabled(output_allowed)

        for s in self.prop_sliders:
            s.setEnabled(output_allowed)
        for e in self.prop_edits:
            e.setEnabled(output_allowed)
        self.btn_pac_apply.setEnabled(output_allowed)
        self.btn_pac_reset.setEnabled(output_allowed)

        # Update spool position feedback labels
        for i, lbl_fb in enumerate(self.lbl_spool_feedbacks):
            b_name = ["A", "B", "C"][i]
            spool_v = getattr(self.plc.blades[i], "spool_pos_pct", 0.0)
            lbl_fb.setText(f"{b_name}: {spool_v:.1f} %")

        # 3. Update Network Tab State
        net_allowed = is_auth and is_online
        self.edit_new_host.setEnabled(net_allowed)
        self.edit_new_ip.setEnabled(net_allowed)
        self.edit_new_mask.setEnabled(net_allowed)
        self.btn_update_net.setEnabled(net_allowed)

        if not is_online:
            self.lbl_net_status.setText("⚠️ " + tr("PLC communication offline.", self.current_lang))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #DC2626;")
        elif not is_auth:
            self.lbl_net_status.setText(tr("Status: Maintenance login required to update settings.", self.current_lang))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")
        elif not getattr(self.plc, "has_network_nodes", False):
            self.lbl_net_status.setText("⚠️ " + tr("PLC symbol missing, cannot apply", self.current_lang))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #D97706;")
        else:
            self.lbl_net_status.setText(tr("Status: Authorized. Ready to apply network settings.", self.current_lang))
            self.lbl_net_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #059669;")

        # 4. Update Restart Tab State
        restart_allowed = is_auth and is_online
        self.btn_plc_restart.setEnabled(restart_allowed)
        if not is_online:
            self.lbl_restart_status.setText("⚠️ " + tr("PLC communication offline.", self.current_lang))
            self.lbl_restart_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #DC2626;")
        elif not is_auth:
            self.lbl_restart_status.setText(tr("Status: Maintenance login required to trigger controller restart.", self.current_lang))
            self.lbl_restart_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")
        else:
            self.lbl_restart_status.setText("✔ " + tr("Status: Authorized. Ready to trigger restart.", self.current_lang))
            self.lbl_restart_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #059669;")

    # =========================================================================
    # Action Handlers: Output (HPU, Lub, PAC Valves)
    # =========================================================================
    def apply_hpu(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot apply HPU settings!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        req = self.chk_hpu_pressure.isChecked()
        self.plc.hpu_pressure_buildup_req = req
        self.opcua_service.apply_maint_hpu(req)
        self.update_ui_state()

    def reset_hpu(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot reset HPU settings!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        self.chk_hpu_pressure.setChecked(False)
        self.plc.hpu_pressure_buildup_req = False
        self.opcua_service.reset_maint_hpu()
        self.update_ui_state()

    def apply_lub(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot apply lubrication settings!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        p1 = self.chk_lub1.isChecked()
        p2 = self.chk_lub2.isChecked()
        self.plc.pump1_active = p1
        self.plc.pump2_active = p2
        self.opcua_service.apply_maint_lub(p1, p2)
        self.update_ui_state()

    def reset_lub(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot reset lubrication settings!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        self.chk_lub1.setChecked(False)
        self.chk_lub2.setChecked(False)
        self.plc.pump1_active = False
        self.plc.pump2_active = False
        self.opcua_service.reset_maint_lub()
        self.update_ui_state()

    def apply_pac(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot apply PAC valve actions!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        for e in self.prop_edits:
            e.clearFocus()
        valves_by_blade = {0: {}, 1: {}, 2: {}}
        for v_key, row_chks in self.valve_checkboxes:
            for b_idx in range(3):
                is_chk = row_chks[b_idx].isChecked()
                self.plc.blades[b_idx].valves[v_key] = is_chk
                valves_by_blade[b_idx][v_key] = is_chk
        spool_cmds = []
        for b_idx in range(3):
            val = self.prop_sliders[b_idx].value() / 10.0
            self.plc.blades[b_idx].prop_valve_cmd = val
            spool_cmds.append(float(val))

        self.opcua_service.apply_maint_pac(valves_by_blade, spool_cmds)
        self.update_ui_state()

    def reset_pac(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                tr("Communication Offline", self.current_lang),
                tr("⚠️ PLC communication is offline. Cannot reset PAC valves!\n\nPlease check OPC UA connection.", self.current_lang)
            )
            return

        for _, row_chks in self.valve_checkboxes:
            for chk in row_chks:
                chk.setChecked(False)
        for s in self.prop_sliders:
            s.setValue(0)
        for b_idx in range(3):
            for v_key in self.plc.blades[b_idx].valves:
                self.plc.blades[b_idx].valves[v_key] = False
            self.plc.blades[b_idx].prop_valve_cmd = 0
            self.plc.blades[b_idx].spool_pos_pct = 0.0
        self.opcua_service.reset_maint_pac()
        self.update_ui_state()

    # =========================================================================
    # Action Handlers: Login & Mode Switch
    # =========================================================================
    def _handle_maint_login(self, pwd):
        ok, msg, role = self.plc.authenticate(pwd)
        if ok:
            if self.opcua_service and getattr(self.plc, "is_opcua_online", False):
                self.opcua_service.login_maintenance()
            return True, ""
        return False, tr("Incorrect password for Maintenance Mode!", self.current_lang)

    def _handle_maint_logout(self):
        self.plc.logout()

    def _on_auth_changed(self, role):
        is_logged = (role != ROLE_NOT_LOGGED_IN)
        self.login_card.set_state(is_logged, role if is_logged else None)
        self.update_ui_state()

    def handle_login_logout(self):
        self.login_card.handle_login_logout()

    def handle_mode_action(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot switch operation mode!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        if self.plc.blade_mode != MODE_MAINTENANCE:
            can_enter = (self.plc.blade_state == STATE_ABORTED) or getattr(self.plc, "is_super_user", False)
            if not can_enter:
                title = tr("Interlock Restriction", self.current_lang)
                msg = tr("System is not in ABORTED state!\nPlease abort the pitch system before requesting Maintenance Mode.", self.current_lang)
                QMessageBox.warning(self, title, msg)
                return

            title = tr("Warning - Maintenance Mode", self.current_lang)
            msg = tr("WARNING: Entering the hub is NOT safe under any circumstances in Maintenance Mode!\n\nDo you want to proceed?", self.current_lang)

            dlg = WarningModal(title, msg, self, opcua_service=None)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.opcua_service.request_maintenance_mode()
        else:
            self.opcua_service.exit_maintenance_mode()
        self.update_ui_state()
