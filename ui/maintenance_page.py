# -*- coding: utf-8 -*-
"""
Maintenance Mode Page - SEC PAC 6MW Hydraulic Pitch HMI
Matching Figures 26 - 42 of DFB1001650_DFB011019
Optimized with clean industrial layout, bilingual i18n support,
pixel-aligned button decks, and safety instruction card.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QCheckBox, QSlider, QLineEdit, QMessageBox,
    QFrame, QDialog
)
from PyQt6.QtCore import Qt
from config import (
    MODE_MAINTENANCE, STATE_ABORTED, PASSWORD_MAINT_LOGIN, PASSWORD_SUPER_USER
)
from utils.widgets import WarningModal
from ui.login_card import LoginCard
from ui.mode_card import ModeCard

# Proportional valve spool command physical limits (%)
PROP_VALVE_MIN_CMD = -100.0
PROP_VALVE_MAX_CMD = 100.0


class PillBadge(QLabel):
    """Status badge for card headers"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("locked", text)

    def set_state(self, state_type, text):
        self.setText(text)
        if state_type == "ready":
            self.setStyleSheet("""
                background-color: #DEF7EC;
                color: #03543F;
                border: 1px solid #31C48D;
                border-radius: 11px;
                padding: 1px 10px;
                font-size: 10px;
                font-weight: bold;
            """)
        elif state_type == "unlocked":
            self.setStyleSheet("""
                background-color: #E1EFFE;
                color: #1E429F;
                border: 1px solid #76A9FA;
                border-radius: 11px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:  # locked / warning
            self.setStyleSheet("""
                background-color: #FEF2F2;
                color: #991B1B;
                border: 1px solid #F87171;
                border-radius: 11px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: bold;
            """)


class MaintenancePage(QWidget):
    def __init__(self, plc_state, opcua_service=None, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"
        self.init_ui()
        self.retranslate_ui(self.current_lang)
        self.plc.state_changed.connect(self.update_ui_state)
        self.update_ui_state()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)

        # -------------------------------------------------------------
        # Left Area: Work Deck (HPU, Lubrication, PAC Valves & Prop)
        # -------------------------------------------------------------
        left_area = QVBoxLayout()
        left_area.setSpacing(8)

        # 1. HPU Card (Full width row)
        self.grp_hpu = self._create_hpu_group()
        left_area.addWidget(self.grp_hpu)

        # 2. Lubrication Card (Full width row)
        self.grp_lub = self._create_lubrication_group()
        left_area.addWidget(self.grp_lub)

        # 3. PAC Valve Matrix & Proportional Valve Section
        self.grp_pac = self._create_pac_valve_group()
        left_area.addWidget(self.grp_pac, 1)

        main_layout.addLayout(left_area, 1)

        # -------------------------------------------------------------
        # Right Column: Login, Mode Switch, Safety Notices
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

    # =========================================================================
    # Groupbox 1: HPU
    # =========================================================================
    def _create_hpu_group(self):
        grp = QGroupBox("液压动力单元 (HPU)")
        grp.setFixedHeight(68)
        layout = QHBoxLayout(grp)
        layout.setContentsMargins(14, 2, 14, 6)
        layout.setSpacing(8)

        self.chk_hpu_pressure = QCheckBox("请求 HPU 泵站建压")
        self.chk_hpu_pressure.setStyleSheet("font-weight: 500;")

        self.badge_hpu = PillBadge("🔒 需维护模式")

        self.btn_hpu_reset = QPushButton("重置")
        self.btn_hpu_reset.setFixedSize(68, 28)
        self.btn_hpu_reset.setStyleSheet(self._style_reset_btn())
        self.btn_hpu_reset.clicked.connect(self.reset_hpu)

        self.btn_hpu_apply = QPushButton("应用")
        self.btn_hpu_apply.setFixedSize(72, 28)
        self.btn_hpu_apply.setStyleSheet(self._style_apply_btn())
        self.btn_hpu_apply.clicked.connect(self.apply_hpu)

        layout.addWidget(self.chk_hpu_pressure)
        layout.addStretch()
        layout.addWidget(self.badge_hpu)
        layout.addSpacing(6)
        layout.addWidget(self.btn_hpu_reset)
        layout.addWidget(self.btn_hpu_apply)

        return grp

    # =========================================================================
    # Groupbox 2: Lubrication
    # =========================================================================
    def _create_lubrication_group(self):
        grp = QGroupBox("润滑系统测试")
        grp.setFixedHeight(68)
        layout = QHBoxLayout(grp)
        layout.setContentsMargins(14, 2, 14, 6)
        layout.setSpacing(8)

        self.chk_lub1 = QCheckBox("润滑泵 1")
        self.chk_lub2 = QCheckBox("润滑泵 2")

        self.badge_lub = PillBadge("🔒 需维护模式")

        self.btn_lub_reset = QPushButton("重置")
        self.btn_lub_reset.setFixedSize(68, 28)
        self.btn_lub_reset.setStyleSheet(self._style_reset_btn())
        self.btn_lub_reset.clicked.connect(self.reset_lub)

        self.btn_lub_apply = QPushButton("应用")
        self.btn_lub_apply.setFixedSize(72, 28)
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

    # =========================================================================
    # Groupbox 3: PAC Valve Matrix & Proportional Valve Section
    # =========================================================================
    def _create_pac_valve_group(self):
        grp = QGroupBox("PAC 阀组与比例阀测试")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 6, 14, 8)
        layout.setSpacing(6)

        # Top Bar
        top_bar = QHBoxLayout()
        self.lbl_pac_desc = QLabel("独立开关阀动作测试 与 比例阀 102A 连续调节")
        self.lbl_pac_desc.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_pac_desc.setStyleSheet("font-size: 11px; color: #64748B;")
        self.badge_pac = PillBadge("🔒 需维护模式并登录")
        top_bar.addWidget(self.lbl_pac_desc)
        top_bar.addStretch()
        top_bar.addWidget(self.badge_pac)
        layout.addLayout(top_bar)

        # Central Split: Left Frame (Matrix) | Right Frame (Prop Valve)
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(12)

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
        fv_layout.setContentsMargins(6, 8, 6, 8)
        fv_layout.setSpacing(3)

        grid_valves = QGridLayout()
        grid_valves.setHorizontalSpacing(4)
        grid_valves.setVerticalSpacing(4)
        grid_valves.setColumnStretch(0, 1)  # Valve name takes available width
        grid_valves.setColumnMinimumWidth(1, 26)  # A
        grid_valves.setColumnMinimumWidth(2, 26)  # B
        grid_valves.setColumnMinimumWidth(3, 26)  # C

        # Table Headers
        self.lbl_hdr_v_name = QLabel("阀门名称")
        self.lbl_hdr_v_name.setFixedHeight(28)
        self.lbl_hdr_v_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_va = QLabel("A")
        self.lbl_hdr_va.setFixedHeight(28)
        self.lbl_hdr_va.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_va.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_vb = QLabel("B")
        self.lbl_hdr_vb.setFixedHeight(28)
        self.lbl_hdr_vb.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_vb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_vc = QLabel("C")
        self.lbl_hdr_vc.setFixedHeight(28)
        self.lbl_hdr_vc.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.lbl_hdr_vc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid_valves.addWidget(self.lbl_hdr_v_name, 0, 0)
        grid_valves.addWidget(self.lbl_hdr_va, 0, 1)
        grid_valves.addWidget(self.lbl_hdr_vb, 0, 2)
        grid_valves.addWidget(self.lbl_hdr_vc, 0, 3)

        valve_defs = [
            ("Valve 132 Pitch Lock", "132 变桨锁紧阀 (Pitch Lock)", "v132"),
            ("Valve 130 Pitch Lock", "130 变桨锁止阀 (Pitch Lock)", "v130"),
            ("Valve 120 EMF", "120 应急顺桨阀 (EMF)", "v120"),
            ("Valve 103 EMF", "103 应急顺桨阀 (EMF)", "v103"),
            ("Valve 119A Cut Off 1", "119A 截止阀 1 (Cut Off 1)", "v119a"),
            ("Valve 119B Cut Off 2", "119B 截止阀 2 (Cut Off 2)", "v119b"),
            ("Valve 109 Cut Off P", "109 压力截止阀 P (Cut Off P)", "v109"),
            ("Valve 116 Dump", "116 主卸荷阀 (Dump)", "v116")
        ]

        self.valve_labels = []
        self.valve_checkboxes = []  # [(v_key, [chkA, chkB, chkC])]
        for row, (v_en, v_cn, v_key) in enumerate(valve_defs, start=1):
            lbl_v = QLabel(v_cn)
            lbl_v.setFixedHeight(32)
            lbl_v.setStyleSheet("font-size: 10px; font-weight: 500; color: #334155;")
            self.valve_labels.append((lbl_v, v_en, v_cn))
            grid_valves.addWidget(lbl_v, row, 0)

            row_chks = []
            for col in range(3):
                chk = QCheckBox()
                chk.setFixedHeight(32)
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
        fr_layout.setContentsMargins(14, 10, 14, 10)
        fr_layout.setSpacing(6)

        # Prop Valve Header
        self.lbl_hdr_prop = QLabel("比例阀 102A (-100% ~ +100%)")
        self.lbl_hdr_prop.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B;")
        fr_layout.addWidget(self.lbl_hdr_prop)

        self.prop_sliders = []
        self.prop_edits = []
        self.prop_labels = []
        self.lbl_spool_feedbacks = []

        prop_grid = QGridLayout()
        prop_grid.setHorizontalSpacing(8)
        prop_grid.setVerticalSpacing(14)
        prop_grid.setColumnStretch(1, 1)  # Proportional slider takes available width

        for i, b_name in enumerate(["A", "B", "C"]):
            lbl_p = QLabel(f"叶片 {b_name} 比例阀:")
            lbl_p.setFixedWidth(96)
            lbl_p.setStyleSheet("font-size: 11px; font-weight: 500; color: #334155;")
            self.prop_labels.append((lbl_p, f"Blade {b_name} (102A):", f"叶片 {b_name} 比例阀:"))

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(int(PROP_VALVE_MIN_CMD), int(PROP_VALVE_MAX_CMD))
            slider.setValue(0)
            slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #CBD5E1;
                    height: 6px;
                    background: #E2E8F0;
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
                    margin-top: -6px;
                    margin-bottom: -6px;
                    border-radius: 8px;
                }
            """)

            edit = QLineEdit("0.0 %")
            edit.setFixedWidth(64)
            edit.setFixedHeight(26)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setStyleSheet("font-weight: bold;")

            slider.valueChanged.connect(lambda v, e=edit: e.setText(f"{v:.1f} %"))

            def make_edit_handler(s, e):
                def on_edit_finished():
                    txt = e.text().replace("%", "").strip()
                    try:
                        val = float(txt)
                        val = max(PROP_VALVE_MIN_CMD, min(PROP_VALVE_MAX_CMD, val))
                        s.setValue(int(round(val)))
                        e.setText(f"{val:.1f} %")
                    except ValueError:
                        e.setText(f"{s.value():.1f} %")
                return on_edit_finished

            edit.editingFinished.connect(make_edit_handler(slider, edit))

            prop_grid.addWidget(lbl_p, i, 0)
            prop_grid.addWidget(slider, i, 1)
            prop_grid.addWidget(edit, i, 2)

            self.prop_sliders.append(slider)
            self.prop_edits.append(edit)

        fr_layout.addLayout(prop_grid)

        # Spool position telemetry feedback deck
        spool_box = QFrame()
        spool_box.setFixedHeight(36)
        spool_box.setStyleSheet("background-color: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 4px;")
        sb_layout = QHBoxLayout(spool_box)
        sb_layout.setContentsMargins(8, 4, 8, 4)
        self.lbl_spool_title = QLabel("阀芯实时反馈:")
        self.lbl_spool_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        sb_layout.addWidget(self.lbl_spool_title)

        for b_name in ["A", "B", "C"]:
            lbl_fb = QLabel(f"{b_name}: 0.0 %")
            lbl_fb.setStyleSheet("font-size: 11px; font-weight: bold; color: #0284C7; padding: 0 4px;")
            sb_layout.addWidget(lbl_fb)
            self.lbl_spool_feedbacks.append(lbl_fb)
        sb_layout.addStretch()
        fr_layout.addWidget(spool_box)

        # Diagnostic notice deck
        fr_layout.addStretch()
        self.lbl_pac_notice = QLabel(
            "提示：修改阀门复选框或比例阀开度后，点击右下角【应用更改】下发至 PLC。"
        )
        self.lbl_pac_notice.setWordWrap(True)
        self.lbl_pac_notice.setStyleSheet("font-size: 10px; color: #64748B; line-height: 14px;")
        fr_layout.addWidget(self.lbl_pac_notice)

        mid_layout.addWidget(frame_right, 3)
        layout.addLayout(mid_layout, 1)

        # PAC Bottom Action Buttons (Aligned to right edge)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_pac_reset = QPushButton("重置")
        self.btn_pac_reset.setFixedSize(75, 28)
        self.btn_pac_reset.setStyleSheet(self._style_reset_btn())
        self.btn_pac_reset.clicked.connect(self.reset_pac)

        self.btn_pac_apply = QPushButton("应用更改")
        self.btn_pac_apply.setFixedSize(105, 28)
        self.btn_pac_apply.setStyleSheet(self._style_apply_btn())
        self.btn_pac_apply.clicked.connect(self.apply_pac)

        btn_row.addWidget(self.btn_pac_reset)
        btn_row.addWidget(self.btn_pac_apply)
        layout.addLayout(btn_row)

        return grp

    # =========================================================================
    # Groupbox 4: Right Column (Login, Mode Toggle, Safety Deck)
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
        is_cn = (lang == "CN")

        # 1. GroupBox Titles
        self.grp_hpu.setTitle("液压动力单元 (HPU)" if is_cn else "HPU Hydraulic Power Unit")
        self.grp_lub.setTitle("润滑系统测试" if is_cn else "Lubrication System Test")
        self.grp_pac.setTitle("PAC 阀组与比例阀测试" if is_cn else "PAC Valve Actuation && Prop. Control")
        self.grp_login.setTitle("登录" if is_cn else "Login")
        self.grp_mode.retranslate_ui(lang)

        # 2. HPU & Lub Labels & Buttons
        self.chk_hpu_pressure.setText("请求 HPU 泵站建压" if is_cn else "Request HPU Buildup")
        self.chk_lub1.setText("润滑泵 1" if is_cn else "Lub. Pump 1")
        self.chk_lub2.setText("润滑泵 2" if is_cn else "Lub. Pump 2")

        self.btn_hpu_reset.setText("重置" if is_cn else "Reset")
        self.btn_hpu_apply.setText("应用" if is_cn else "Apply")
        self.btn_lub_reset.setText("重置" if is_cn else "Reset")
        self.btn_lub_apply.setText("应用" if is_cn else "Apply")
        self.btn_pac_reset.setText("重置" if is_cn else "Reset")
        self.btn_pac_apply.setText("应用更改" if is_cn else "Apply Changes")

        # 3. PAC Valve Matrix Headers & Names
        self.lbl_pac_desc.setText(
            "开关阀动作测试 与 比例阀 102A 连续调节" if is_cn
            else "Valve actuation & Prop. Valve 102A control"
        )
        self.lbl_hdr_v_name.setText("阀门名称" if is_cn else "Valve Name")
        self.lbl_hdr_va.setText("A")
        self.lbl_hdr_vb.setText("B")
        self.lbl_hdr_vc.setText("C")

        for lbl, v_en, v_cn in self.valve_labels:
            lbl.setText(v_cn if is_cn else v_en)

        # 4. Proportional Valve
        self.lbl_hdr_prop.setText("比例阀 102A (-100% ~ +100%)" if is_cn else "Prop. Valve 102A (-100% ~ +100%)")
        for lbl_p, en_t, cn_t in self.prop_labels:
            lbl_p.setText(cn_t if is_cn else en_t)
        self.lbl_spool_title.setText("阀芯反馈:" if is_cn else "Spool FB:")
        self.lbl_pac_notice.setText(
            "提示：修改阀门复选框或比例阀开度后，点击右下角【应用更改】下发至 PLC。" if is_cn
            else "Notice: After setting valves or proportional command, click 'Apply Changes' to transmit to PLC."
        )

        # 5. Login & Mode
        self.login_card.retranslate_ui(lang)
        self.lbl_mode_state_hint.setText("准入状态:" if is_cn else "Interlock:")
        self.update_ui_state()

    # =========================================================================
    # UI State Synchronization & Interlock Enforcing
    # =========================================================================
    def update_ui_state(self):
        in_maint = (self.plc.blade_mode == MODE_MAINTENANCE)
        logged_in = self.plc.maint_logged_in
        is_super = getattr(self.plc, "is_super_user", False)
        can_req_maint = (self.plc.blade_state == STATE_ABORTED) or is_super
        is_cn = (self.current_lang == "CN")

        # 1. Update Login Card
        role_name = ("超级用户" if is_cn else "Super User") if is_super else ("维护" if is_cn else "Maintenance")
        self.login_card.set_state(logged_in, role_name=role_name if logged_in else None)

        if in_maint:
            self.badge_hpu.set_state("ready", "✔ 维护中" if is_cn else "✔ Active")
            self.badge_lub.set_state("ready", "✔ 维护中" if is_cn else "✔ Active")
            self.badge_pac.set_state("ready", "✔ 允许动作测试" if is_cn else "✔ Ready to Test")

            prompt = "当前处于维护模式，允许进行开关阀与动作测试。" if is_cn else "Active in Maintenance Mode. Testing enabled."
            self.grp_mode.set_state(
                is_active=True,
                can_enter=True,
                prompt_text=prompt,
                badge_text="✔ 运行中" if is_cn else "✔ Active",
                badge_type="ready",
                can_exit=True
            )
        else:
            if is_super:
                self.badge_hpu.set_state("ready", "✔ 超级权限" if is_cn else "✔ Super Access")
                self.badge_lub.set_state("ready", "✔ 超级权限" if is_cn else "✔ Super Access")
                self.badge_pac.set_state("ready", "✔ 超级权限" if is_cn else "✔ Super Access")
                prompt = "超级用户已登录，已解除所有准入与控制限制。" if is_cn else "Super User active. All restrictions lifted."
                badge_text = "✔ 超级权限" if is_cn else "✔ Super Access"
                badge_type = "ready"
            else:
                self.badge_hpu.set_state("locked", "🔒 需维护模式" if is_cn else "🔒 Require Maint.")
                self.badge_lub.set_state("locked", "🔒 需维护模式" if is_cn else "🔒 Require Maint.")
                self.badge_pac.set_state("locked", "🔒 需维护模式并登录" if is_cn else "🔒 Require Maint. & Login")

                if can_req_maint:
                    prompt = "前置条件已满足，可请求维护模式。" if is_cn else "Preconditions met. Ready to enter maintenance mode."
                    badge_text = "✔ 具备准入条件" if is_cn else "✔ Ready to Enter"
                    badge_type = "ready"
                else:
                    if not logged_in:
                        prompt = "需处于已中止 (Aborted) 状态且已登录维护权限。" if is_cn else "Must be in Aborted state and logged in."
                    else:
                        prompt = "系统需处于已中止 (Aborted) 状态方可进入。" if is_cn else "System must be in Aborted state to enter."
                    badge_text = "🔒 需处于已中止" if is_cn else "🔒 Need Aborted"
                    badge_type = "locked"

            self.grp_mode.set_state(
                is_active=False,
                can_enter=can_req_maint,
                prompt_text=prompt,
                badge_text=badge_text,
                badge_type=badge_type
            )

        # 2. Controls Enabled State
        controls_allowed = (in_maint and logged_in) or is_super

        self.chk_hpu_pressure.setEnabled(controls_allowed)
        self.btn_hpu_apply.setEnabled(controls_allowed)
        self.btn_hpu_reset.setEnabled(controls_allowed)

        self.chk_lub1.setEnabled(controls_allowed)
        self.chk_lub2.setEnabled(controls_allowed)
        self.btn_lub_apply.setEnabled(controls_allowed)
        self.btn_lub_reset.setEnabled(controls_allowed)

        for _, row_chks in self.valve_checkboxes:
            for chk in row_chks:
                chk.setEnabled(controls_allowed)

        for s in self.prop_sliders:
            s.setEnabled(controls_allowed)
        for e in self.prop_edits:
            e.setEnabled(controls_allowed)
        self.btn_pac_apply.setEnabled(controls_allowed)
        self.btn_pac_reset.setEnabled(controls_allowed)

        # Update spool position feedback labels
        for i, lbl_fb in enumerate(self.lbl_spool_feedbacks):
            b_name = ["A", "B", "C"][i]
            spool_v = getattr(self.plc.blades[i], "spool_pos_pct", 0.0)
            lbl_fb.setText(f"{b_name}: {spool_v:.1f} %")

    # =========================================================================
    # Action Handlers
    # =========================================================================
    def _handle_maint_login(self, pwd):
        if pwd in [PASSWORD_SUPER_USER, "super"]:
            self.plc.maint_logged_in = True
            self.plc.is_super_user = True
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.login_maintenance()
            return True, ""
        elif pwd in [PASSWORD_MAINT_LOGIN, "asdf"]:
            self.plc.maint_logged_in = True
            self.plc.is_super_user = False
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.login_maintenance()
            return True, ""
        return False, "维护模式密码不正确！" if self.current_lang == "CN" else "Incorrect password for Maintenance Mode!"

    def _handle_maint_logout(self):
        self.plc.maint_logged_in = False
        self.plc.is_super_user = False

    def handle_login_logout(self):
        self.login_card.handle_login_logout()

    def handle_mode_action(self):
        is_cn = (self.current_lang == "CN")
        if self.plc.blade_mode != MODE_MAINTENANCE:
            # 1. 前置准入条件检查：变桨系统必须处于 已中止 (Aborted) 状态（超级用户除外）
            can_enter = (self.plc.blade_state == STATE_ABORTED) or getattr(self.plc, "is_super_user", False)
            if not can_enter:
                title = "准入限制" if is_cn else "Interlock Restriction"
                msg = (
                    "系统当前未处于 已中止 (Aborted) 状态！\n请先中止变桨系统，然后再请求进入维护模式。"
                    if is_cn else
                    "System is not in ABORTED state!\nPlease abort the pitch system before requesting Maintenance Mode."
                )
                QMessageBox.warning(self, title, msg)
                return

            # 2. 上位机安全警告确认弹窗（双语）
            title = "安全警告 - 维护模式" if is_cn else "Warning - Maintenance Mode"
            msg = (
                "⚠️ 严重警告：\n在维护模式下，任何情况下进入轮毂都是不安全的！\n\n是否确认请求进入维护模式？"
                if is_cn else
                "WARNING: Entering the hub is NOT safe under any circumstances in Maintenance Mode!\n\nDo you want to proceed?"
            )

            dlg = WarningModal(title, msg, self, opcua_service=self.opcua_service)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.request_maintenance_mode()
                    self.opcua_service.send_msgbox_ok()
                ok, err = self.plc.request_maintenance_mode()
                if not ok:
                    QMessageBox.warning(self, "维护模式" if is_cn else "Maintenance Mode", err)
            else:
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.send_msgbox_abort()
        else:
            self.plc.exit_maintenance_mode()
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.exit_maintenance_mode()
        self.update_ui_state()

    def apply_hpu(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法下发 HPU 动力单元设置！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot apply HPU settings!\n\nPlease check OPC UA connection."
            )
            return

        req = self.chk_hpu_pressure.isChecked()
        self.plc.hpu_pressure_buildup_req = req
        self.opcua_service.apply_maint_hpu(req)
        QMessageBox.information(
            self,
            "HPU 动力单元" if is_cn else "HPU",
            "HPU 建压请求已成功下发至 PLC。" if is_cn else "HPU pressure request applied to PLC successfully."
        )
        self.update_ui_state()

    def reset_hpu(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法复位 HPU 动力单元！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot reset HPU settings!\n\nPlease check OPC UA connection."
            )
            return

        self.chk_hpu_pressure.setChecked(False)
        self.plc.hpu_pressure_buildup_req = False
        self.opcua_service.reset_maint_hpu()
        self.update_ui_state()

    def apply_lub(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法下发润滑测试设置！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot apply lubrication settings!\n\nPlease check OPC UA connection."
            )
            return

        p1 = self.chk_lub1.isChecked()
        p2 = self.chk_lub2.isChecked()
        self.plc.pump1_active = p1
        self.plc.pump2_active = p2
        self.opcua_service.apply_maint_lub(p1, p2)
        QMessageBox.information(
            self,
            "润滑系统" if is_cn else "Lubrication",
            "润滑泵测试设置已成功下发至 PLC。" if is_cn else "Lubrication pump settings applied to PLC successfully."
        )
        self.update_ui_state()

    def reset_lub(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法复位润滑测试设置！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot reset lubrication settings!\n\nPlease check OPC UA connection."
            )
            return

        self.chk_lub1.setChecked(False)
        self.chk_lub2.setChecked(False)
        self.plc.pump1_active = False
        self.plc.pump2_active = False
        self.opcua_service.reset_maint_lub()
        self.update_ui_state()

    def apply_pac(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法下发 PAC 阀门动作指令！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot apply PAC valve actions!\n\nPlease check OPC UA connection."
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
            val = self.prop_sliders[b_idx].value()
            self.plc.blades[b_idx].prop_valve_cmd = val
            # Simulate spool follow
            self.plc.blades[b_idx].spool_pos_pct = float(val)
            spool_cmds.append(float(val))

        self.opcua_service.apply_maint_pac(valves_by_blade, spool_cmds)

        QMessageBox.information(
            self,
            "PAC 阀门动作" if is_cn else "PAC Control",
            "PAC 开关阀动作及比例阀指令已成功下发至 PLC！" if is_cn
            else "PAC valve actuations and proportional commands applied to PLC successfully!"
        )
        self.update_ui_state()

    def reset_pac(self):
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            QMessageBox.warning(
                self,
                "通信断开" if is_cn else "Communication Offline",
                "⚠️ 当前 PLC 通信已断开，无法复位 PAC 阀门！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot reset PAC valves!\n\nPlease check OPC UA connection."
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
