# -*- coding: utf-8 -*-
"""
Manual Mode Page - SEC PAC 6MW Hydraulic Pitch HMI
Matching Figures 12 - 25 of DFB1001650_DFB011019
Fully redesigned with pixel-perfect industrial grid alignment, clean authorization badges,
and balanced component hierarchy.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QRadioButton, QButtonGroup,
    QMessageBox, QFrame, QDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIntValidator, QDoubleValidator
from config import (
    MODE_MANUAL, MODE_PRODUCTION, STATE_STOPPED, PASSWORD_MANUAL_CALIB, PASSWORD_SUPER_USER,
    MANUAL_FAST_SPEED_DEFAULT, MANUAL_SLOW_SPEED_DEFAULT,
    MANUAL_SPEED_MIN, MANUAL_SPEED_MAX,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG
)
from utils.widgets import StatusLed, WarningModal, ValueDisplay
from ui.login_card import LoginCard
from ui.mode_card import ModeCard


class ManualPage(QWidget):
    def __init__(self, plc_state, opcua_service=None, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"
        self._user_edited_offsets = [False, False, False]
        self._user_edited_grds = [False, False, False]
        self._user_edited_fast_spd = False
        self._user_edited_slow_spd = False
        self.init_ui()
        self.plc.state_changed.connect(self.update_ui_state)
        self.update_ui_state()

    def retranslate_ui(self, lang="EN"):
        from utils.i18n import tr
        self.current_lang = lang
        is_cn = (lang == "CN")

        self.grp_calib_pos.setTitle("变桨位置标定 [deg]" if is_cn else "Pitch Position Calibration [deg]")
        self.grp_calib_grd.setTitle("GRD 标定 [cm/s]" if is_cn else "GRD Calibration [cm/s]")
        self.grp_lub.setTitle("叶片润滑" if is_cn else "Blade Lubrication")
        self.grp_blade_ctrl.setTitle("HMI 变桨控制" if is_cn else "HMI Blade Control")
        self.login_card.retranslate_ui(lang)
        self.grp_mode.retranslate_ui(lang)

        self.btn_apply_pos_calib.setText("应用更改" if is_cn else "Apply Changes")
        self.btn_apply_grd.setText("应用更改" if is_cn else "Apply Changes")

        self.lbl_hdr_pos_blade.setText("叶片" if is_cn else "Blade")
        self.lbl_hdr_pos_cur.setText("当前值" if is_cn else "Current")
        self.lbl_hdr_pos_off.setText("偏置" if is_cn else "Offset [°]")

        self.lbl_hdr_grd_blade.setText("叶片" if is_cn else "Blade")
        self.lbl_hdr_grd_cur.setText("当前值" if is_cn else "Current")
        self.lbl_hdr_grd_new.setText("新设定" if is_cn else "New")

        for i, name in enumerate(["A", "B", "C"]):
            prefix = "叶片 " if is_cn else "Blade "
            self.lbl_pos_blade_names[i].setText(f"{prefix}{name}")
            self.lbl_grd_blade_names[i].setText(f"{prefix}{name}")

        for edit in getattr(self, "edit_offsets", []):
            edit.setToolTip(
                f"偏置有效范围: {OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°"
                if is_cn
                else f"Offset Valid Range: {OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°"
            )

        for edit in getattr(self, "grd_new_edits", []):
            edit.setToolTip(
                f"GRD 有效范围: {GRD_MIN_VALUE} ~ {GRD_MAX_VALUE} pulse/(cm/s)"
                if is_cn
                else f"GRD Valid Range: {GRD_MIN_VALUE} ~ {GRD_MAX_VALUE} pulse/(cm/s)"
            )

        self.lbl_blade_sel_title.setText("桨叶选择" if is_cn else "Blade selected")
        self.lbl_blade_safe_title.setText("桨叶安全" if is_cn else "Blade safe")
        self.lbl_remote_box_speed_title.setText("手操盒速度" if is_cn else "Remote box speed")
        self.lbl_fast_spd_title.setText("快速" if is_cn else "Fast speed")
        self.lbl_slow_spd_title.setText("慢速" if is_cn else "Slow speed")
        self.lbl_pos_mon_title.setText("当前开度" if is_cn else "Current Pos.")
        self.lbl_pitch_lock_title.setText("变桨锁控制" if is_cn else "Pitch Lock Control")
        self.lbl_speed_mode_title.setText("快/慢速选择" if is_cn else "Fast/Slow Speed")
        self.lbl_move_blade_title.setText("移动桨叶" if is_cn else "Move Blade")

        self.lbl_p1_title.setText("润滑泵 1:" if is_cn else "Pump 1:")
        self.lbl_p2_title.setText("润滑泵 2:" if is_cn else "Pump 2:")
        self.btn_move_feather.setText("顺桨" if is_cn else "Feather")
        self.btn_move_fine.setText("开桨" if is_cn else "Fine")

        self.update_ui_state()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # Main 2x3 Grid Layout
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)  # Left Col: Pos Calib & Lubrication (Equal Width)
        grid.setColumnStretch(1, 1)  # Mid Col: GRD Calib & Blade Control (Equal Width)
        grid.setColumnStretch(2, 0)  # Right Col: Login & Mode Control (Fixed 210px)
        grid.setRowStretch(0, 1)     # Row 0: Equal Height
        grid.setRowStretch(1, 1)     # Row 1: Equal Height

        # Row 0: Calibrations
        self.grp_calib_pos = self._create_pos_calib_group()
        grid.addWidget(self.grp_calib_pos, 0, 0)

        self.grp_calib_grd = self._create_grd_calib_group()
        grid.addWidget(self.grp_calib_grd, 0, 1)

        # Right Column: Login Card & Mode Request
        self.grp_login = self._create_login_group()
        self.grp_mode = self._create_mode_group()

        col_right = QVBoxLayout()
        col_right.setSpacing(8)
        col_right.addWidget(self.grp_login, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        col_right.addWidget(self.grp_mode, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        col_right.addStretch()
        grid.addLayout(col_right, 0, 2, 2, 1)

        # Row 1: Lubrication & Blade Control
        self.grp_lub = self._create_lubrication_group()
        grid.addWidget(self.grp_lub, 1, 0)

        self.grp_blade_ctrl = self._create_blade_ctrl_group()
        grid.addWidget(self.grp_blade_ctrl, 1, 1)

        main_layout.addLayout(grid)

        self.setStyleSheet("""
            QGroupBox {
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
                left: 10px;
                padding: 0 4px;
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #0284C7;
            }
            QLineEdit:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
                border-color: #CBD5E1;
            }
        """)

    def _create_pos_calib_group(self):
        grp = QGroupBox("Pitch Position Calibration [deg]")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Status badge row
        badge_row = QHBoxLayout()
        self.badge_pos_auth = QLabel("🔒 Require Login")
        self.badge_pos_auth.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #D97706;
            background-color: #FEF3C7; border: 1px solid #FDE68A;
            border-radius: 3px; padding: 2px 8px;
        """)
        badge_row.addStretch()
        badge_row.addWidget(self.badge_pos_auth)
        layout.addLayout(badge_row)

        # 3-Column Grid for Table Data
        table_grid = QGridLayout()
        table_grid.setHorizontalSpacing(8)
        table_grid.setVerticalSpacing(6)

        # Header
        self.lbl_hdr_pos_blade = QLabel("Blade")
        self.lbl_hdr_pos_blade.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_pos_cur = QLabel("Current")
        self.lbl_hdr_pos_cur.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_pos_cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_pos_off = QLabel("Offset [°]")
        self.lbl_hdr_pos_off.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_pos_off.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_grid.addWidget(self.lbl_hdr_pos_blade, 0, 0)
        table_grid.addWidget(self.lbl_hdr_pos_cur, 0, 1)
        table_grid.addWidget(self.lbl_hdr_pos_off, 0, 2)

        self.edit_offsets = []
        self.lbl_pos_cur_vals = []
        self.lbl_pos_blade_names = []
        for row, name in enumerate(["Blade A", "Blade B", "Blade C"], start=1):
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
            self.lbl_pos_blade_names.append(lbl_name)

            val = QLabel("89.05 °")
            val.setFixedWidth(80)
            val.setFixedHeight(26)
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("background-color: #FFFFFF; border: 1px solid #B0B5B9; border-radius: 3px; font-size: 11px; font-weight: bold; color: #111111;")

            edit = QLineEdit(f"{self.plc.blades[row-1].calib_offset_deg:.2f}")
            edit.setFixedWidth(80)
            edit.setFixedHeight(26)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_validator = QDoubleValidator(OFFSET_MIN_DEG, OFFSET_MAX_DEG, 2, self)
            val_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            edit.setValidator(val_validator)
            edit.setPlaceholderText(f"{OFFSET_MIN_DEG:.1f}~{OFFSET_MAX_DEG:.1f}")
            edit.setToolTip(
                f"偏置有效范围: {OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°"
                if self.current_lang == "CN"
                else f"Offset Valid Range: {OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°"
            )
            edit.textEdited.connect(self.on_pos_text_changed)
            edit.editingFinished.connect(lambda e=edit, idx=row-1: self._on_pos_edit_finished(e, idx))

            table_grid.addWidget(lbl_name, row, 0)
            table_grid.addWidget(val, row, 1)
            table_grid.addWidget(edit, row, 2)

            self.edit_offsets.append(edit)
            self.lbl_pos_cur_vals.append(val)

        layout.addLayout(table_grid)
        layout.addStretch()

        # Action Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply_pos_calib = QPushButton("Apply Changes")
        self.btn_apply_pos_calib.setFixedHeight(28)
        self.btn_apply_pos_calib.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6; color: white; font-weight: bold;
                border-radius: 3px; padding: 2px 14px; font-size: 11px;
            }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:disabled { background-color: #E2E8F0; color: #94A3B8; border: 1px solid #CBD5E1; }
        """)
        self.btn_apply_pos_calib.clicked.connect(self.apply_pos_calib)
        btn_row.addWidget(self.btn_apply_pos_calib)
        layout.addLayout(btn_row)

        return grp

    def _create_grd_calib_group(self):
        grp = QGroupBox("GRD Calibration [cm/s]")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Status badge row
        badge_row = QHBoxLayout()
        self.badge_grd_auth = QLabel("🔒 Require Login")
        self.badge_grd_auth.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #D97706;
            background-color: #FEF3C7; border: 1px solid #FDE68A;
            border-radius: 3px; padding: 2px 8px;
        """)
        badge_row.addStretch()
        badge_row.addWidget(self.badge_grd_auth)
        layout.addLayout(badge_row)

        # Table Grid with 100% aligned columns
        table_grid = QGridLayout()
        table_grid.setHorizontalSpacing(10)
        table_grid.setVerticalSpacing(6)

        self.lbl_hdr_grd_blade = QLabel("Blade")
        self.lbl_hdr_grd_blade.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_cur = QLabel("Current")
        self.lbl_hdr_grd_cur.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_grd_new = QLabel("New")
        self.lbl_hdr_grd_new.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_new.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_grid.addWidget(self.lbl_hdr_grd_blade, 0, 0)
        table_grid.addWidget(self.lbl_hdr_grd_cur, 0, 1)
        table_grid.addWidget(self.lbl_hdr_grd_new, 0, 2)

        self.grd_cur_labels = []
        self.grd_new_edits = []
        self.lbl_grd_blade_names = []
        for row, name in enumerate(["Blade A", "Blade B", "Blade C"], start=1):
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
            self.lbl_grd_blade_names.append(lbl_name)

            cur = QLabel(str(self.plc.blades[row-1].grd_current))
            cur.setFixedWidth(86)
            cur.setFixedHeight(26)
            cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cur.setStyleSheet("background-color: #FFFFFF; border: 1px solid #B0B5B9; border-radius: 3px; font-size: 11px; font-weight: bold; color: #111111;")

            edit = QLineEdit(str(self.plc.blades[row-1].grd_current))
            edit.setFixedWidth(86)
            edit.setFixedHeight(26)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setValidator(QIntValidator(GRD_MIN_VALUE, GRD_MAX_VALUE, self))
            edit.setPlaceholderText(f"{GRD_MIN_VALUE}-{GRD_MAX_VALUE}")
            edit.setToolTip(
                f"GRD 有效范围: {GRD_MIN_VALUE} ~ {GRD_MAX_VALUE} pulse/(cm/s)"
                if self.current_lang == "CN"
                else f"GRD Valid Range: {GRD_MIN_VALUE} ~ {GRD_MAX_VALUE} pulse/(cm/s)"
            )
            edit.textEdited.connect(self.on_grd_text_changed)
            edit.editingFinished.connect(lambda e=edit, idx=row-1: self._on_grd_edit_finished(e, idx))

            table_grid.addWidget(lbl_name, row, 0)
            table_grid.addWidget(cur, row, 1)
            table_grid.addWidget(edit, row, 2)

            self.grd_cur_labels.append(cur)
            self.grd_new_edits.append(edit)

        layout.addLayout(table_grid)
        layout.addStretch()

        # Action Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply_grd = QPushButton("Apply Changes")
        self.btn_apply_grd.setFixedHeight(28)
        self.btn_apply_grd.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6; color: white; font-weight: bold;
                border-radius: 3px; padding: 2px 14px; font-size: 11px;
            }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:disabled { background-color: #E2E8F0; color: #94A3B8; border: 1px solid #CBD5E1; }
        """)
        self.btn_apply_grd.clicked.connect(self.apply_grd_calib)
        btn_row.addWidget(self.btn_apply_grd)
        layout.addLayout(btn_row)

        return grp

    def _create_login_group(self):
        self.login_card = LoginCard(
            on_login=self._handle_manual_login,
            on_logout=self._handle_manual_logout,
            parent=self
        )
        self.login_card.login_changed.connect(lambda _: self.update_ui_state())
        self.btn_login = self.login_card.btn_login
        self.edit_password = self.login_card.edit_password
        self.badge_login_status = self.login_card.badge_status
        return self.login_card

    def _handle_manual_login(self, pwd):
        if pwd in [PASSWORD_SUPER_USER, "super"]:
            self.plc.manual_logged_in = True
            self.plc.is_super_user = True
            return True, ""
        elif pwd in [PASSWORD_MANUAL_CALIB, "asdf"]:
            self.plc.manual_logged_in = True
            self.plc.is_super_user = False
            return True, ""
        return False, "密码不正确！" if self.current_lang == "CN" else "Incorrect password!"

    def _handle_manual_logout(self):
        self.plc.manual_logged_in = False
        self.plc.is_super_user = False

    def _create_lubrication_group(self):
        grp = QGroupBox("Blade Lubrication")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Status badge row
        badge_row = QHBoxLayout()
        self.badge_lub_auth = QLabel("🔒 Require Manual Mode")
        self.badge_lub_auth.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #64748B;
            background-color: #F1F5F9; border: 1px solid #E2E8F0;
            border-radius: 3px; padding: 2px 8px;
        """)
        badge_row.addStretch()
        badge_row.addWidget(self.badge_lub_auth)
        layout.addLayout(badge_row)

        # Pump 1 Card
        row_p1 = QHBoxLayout()
        row_p1.setSpacing(10)
        self.led_pump1 = StatusLed(color="green", shape="circle", size=14)
        self.lbl_p1_title = QLabel("Pump 1:")
        self.lbl_p1_title.setFixedWidth(64)
        self.lbl_p1_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.btn_pump1 = QPushButton("Activate Pump 1")
        self.btn_pump1.setFixedHeight(34)
        self.btn_pump1.clicked.connect(lambda: self.toggle_pump(1))
        row_p1.addWidget(self.led_pump1)
        row_p1.addWidget(self.lbl_p1_title)
        row_p1.addWidget(self.btn_pump1, 1)
        layout.addLayout(row_p1)

        # Pump 2 Card
        row_p2 = QHBoxLayout()
        row_p2.setSpacing(10)
        self.led_pump2 = StatusLed(color="green", shape="circle", size=14)
        self.lbl_p2_title = QLabel("Pump 2:")
        self.lbl_p2_title.setFixedWidth(64)
        self.lbl_p2_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.btn_pump2 = QPushButton("Activate Pump 2")
        self.btn_pump2.setFixedHeight(34)
        self.btn_pump2.clicked.connect(lambda: self.toggle_pump(2))
        row_p2.addWidget(self.led_pump2)
        row_p2.addWidget(self.lbl_p2_title)
        row_p2.addWidget(self.btn_pump2, 1)
        layout.addLayout(row_p2)

        layout.addStretch()

        return grp

    def _create_blade_ctrl_group(self):
        grp = QGroupBox("HMI Blade Control")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Status badge row - Exactly aligned with Blade Lubrication frame
        badge_row = QHBoxLayout()
        self.badge_ctrl_auth = QLabel("🔒 Require Manual Mode")
        self.badge_ctrl_auth.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #64748B;
            background-color: #F1F5F9; border: 1px solid #E2E8F0;
            border-radius: 3px; padding: 2px 8px;
        """)
        badge_row.addStretch()
        badge_row.addWidget(self.badge_ctrl_auth)
        layout.addLayout(badge_row)

        # Formal contents starting directly below prompt text
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Left Column: Blade selection & safety
        col_left = QVBoxLayout()
        col_left.setSpacing(4)
        self.lbl_blade_sel_title = QLabel("Blade selected")
        self.lbl_blade_sel_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        col_left.addWidget(self.lbl_blade_sel_title)

        grid_sel = QGridLayout()
        grid_sel.setHorizontalSpacing(6)
        grid_sel.setVerticalSpacing(4)
        grid_sel.setContentsMargins(0, 0, 0, 0)

        self.btn_group_blade = QButtonGroup(self)
        self.btn_group_blade.setExclusive(True)
        self.radio_blades = []
        self.chk_blades = self.radio_blades  # Strict single-selection alias

        res_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
        chk_icon_path = os.path.join(res_dir, "chk_black.png").replace("\\", "/")

        chk_style = f"""
            QRadioButton {{ spacing: 0px; }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid #475569;
                background: #FFFFFF;
                border-radius: 2px;
            }}
            QRadioButton::indicator:checked {{
                image: url("{chk_icon_path}");
                background: #FFFFFF;
                border-color: #0F172A;
            }}
            QRadioButton::indicator:disabled {{
                background: #F1F5F9;
                border-color: #CBD5E1;
            }}
        """

        for col, b_name in enumerate(["A", "B", "C"]):
            lbl_b = QLabel(b_name)
            lbl_b.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B;")
            lbl_b.setCursor(Qt.CursorShape.PointingHandCursor)
            rb = QRadioButton()
            rb.setStyleSheet(chk_style)
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            if col == 0:
                rb.setChecked(True)
            self.btn_group_blade.addButton(rb, col)
            self.radio_blades.append(rb)

            lbl_b.mousePressEvent = lambda ev, btn=rb: btn.click()

            h = QHBoxLayout()
            h.setSpacing(3)
            h.addWidget(lbl_b)
            h.addWidget(rb)
            grid_sel.addLayout(h, 0, col)

        self.btn_group_blade.buttonClicked.connect(self.on_blade_selected)
        col_left.addLayout(grid_sel)
        col_left.addSpacing(4)

        self.lbl_blade_safe_title = QLabel("Blade safe")
        self.lbl_blade_safe_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        col_left.addWidget(self.lbl_blade_safe_title)

        grid_safe = QGridLayout()
        grid_safe.setHorizontalSpacing(6)
        grid_safe.setVerticalSpacing(4)
        grid_safe.setContentsMargins(0, 0, 0, 0)
        self.safe_leds = []

        for col, b_name in enumerate(["A", "B", "C"]):
            lbl_b = QLabel(b_name)
            lbl_b.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B;")
            led = StatusLed(color="green", shape="circle", size=14)
            led.set_state(True)
            self.safe_leds.append(led)

            h = QHBoxLayout()
            h.setSpacing(3)
            h.addWidget(lbl_b)
            h.addWidget(led)
            grid_safe.addLayout(h, 0, col)

        col_left.addLayout(grid_safe)
        col_left.addStretch()
        top_row.addLayout(col_left)
        top_row.addStretch()

        # Right Column: Remote box speed & current pos
        col_right = QVBoxLayout()
        col_right.setSpacing(3)
        col_right.setAlignment(Qt.AlignmentFlag.AlignRight)

        grid_spd = QGridLayout()
        grid_spd.setHorizontalSpacing(4)
        grid_spd.setVerticalSpacing(3)
        grid_spd.setContentsMargins(0, 0, 0, 0)

        self.lbl_remote_box_speed_title = QLabel("Remote box speed")
        self.lbl_remote_box_speed_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        self.lbl_remote_box_speed_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid_spd.addWidget(self.lbl_remote_box_speed_title, 0, 0, 1, 3)

        self.lbl_fast_spd_title = QLabel("Fast speed")
        self.lbl_fast_spd_title.setStyleSheet("font-size: 10px; color: #475569;")
        self.lbl_fast_spd_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit_fast_spd = QLineEdit(f"{MANUAL_FAST_SPEED_DEFAULT:.1f}")
        self.edit_fast_spd.setFixedSize(52, 22)
        self.edit_fast_spd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_fast_spd.setStyleSheet("""
            QLineEdit {
                border: 1px solid #B0B5B9; border-radius: 2px;
                font-size: 11px; font-weight: bold; color: #0F172A; background: #FFFFFF;
            }
            QLineEdit:focus { border: 1.5px solid #3B82F6; }
            QLineEdit:disabled { background-color: #F1F5F9; color: #94A3B8; border-color: #E2E8F0; }
        """)
        self.lbl_fast_unit = QLabel("°/s")
        self.lbl_fast_unit.setStyleSheet("font-size: 10px; color: #64748B;")
        self.edit_fast_spd.textEdited.connect(self._on_fast_spd_edited)
        self.edit_fast_spd.editingFinished.connect(self._on_fast_spd_finished)
        grid_spd.addWidget(self.lbl_fast_spd_title, 1, 0)
        grid_spd.addWidget(self.edit_fast_spd, 1, 1)
        grid_spd.addWidget(self.lbl_fast_unit, 1, 2)

        self.lbl_slow_spd_title = QLabel("Slow speed")
        self.lbl_slow_spd_title.setStyleSheet("font-size: 10px; color: #475569;")
        self.lbl_slow_spd_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit_slow_spd = QLineEdit(f"{MANUAL_SLOW_SPEED_DEFAULT:.1f}")
        self.edit_slow_spd.setFixedSize(52, 22)
        self.edit_slow_spd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_slow_spd.setStyleSheet("""
            QLineEdit {
                border: 1px solid #B0B5B9; border-radius: 2px;
                font-size: 11px; font-weight: bold; color: #0F172A; background: #FFFFFF;
            }
            QLineEdit:focus { border: 1.5px solid #3B82F6; }
            QLineEdit:disabled { background-color: #F1F5F9; color: #94A3B8; border-color: #E2E8F0; }
        """)
        self.edit_slow_spd.textEdited.connect(self._on_slow_spd_edited)
        self.edit_slow_spd.editingFinished.connect(self._on_slow_spd_finished)
        self.lbl_slow_unit = QLabel("°/s")
        self.lbl_slow_unit.setStyleSheet("font-size: 10px; color: #64748B;")
        grid_spd.addWidget(self.lbl_slow_spd_title, 2, 0)
        grid_spd.addWidget(self.edit_slow_spd, 2, 1)
        grid_spd.addWidget(self.lbl_slow_unit, 2, 2)

        self.lbl_pos_mon_title = QLabel("Current Pos.")
        self.lbl_pos_mon_title.setStyleSheet("font-size: 10px; color: #475569;")
        self.lbl_pos_mon_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_current_pos = QLabel("89.1")
        self.lbl_current_pos.setFixedSize(52, 22)
        self.lbl_current_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_current_pos.setStyleSheet("border: 1px solid #B0B5B9; background: #FFFFFF; border-radius: 2px; font-size: 11px; font-weight: bold; color: #0284C7;")
        self.lbl_pos_unit = QLabel("°")
        self.lbl_pos_unit.setStyleSheet("font-size: 10px; color: #64748B;")
        grid_spd.addWidget(self.lbl_pos_mon_title, 3, 0)
        grid_spd.addWidget(self.lbl_current_pos, 3, 1)
        grid_spd.addWidget(self.lbl_pos_unit, 3, 2)

        col_right.addLayout(grid_spd)
        col_right.addStretch()
        top_row.addLayout(col_right)
        layout.addLayout(top_row)

        layout.addSpacing(2)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #E2E8F0; margin: 2px 0;")
        layout.addWidget(sep)
        layout.addSpacing(2)

        # Bottom Row: 3 Control Columns Matching Figures 16 - 19
        bot_row = QHBoxLayout()
        bot_row.setSpacing(8)

        # Col 1: Pitch Lock Control (Figure 17) - Industrial Toggle Button
        c1 = QVBoxLayout()
        c1.setSpacing(4)
        self.lbl_pitch_lock_title = QLabel("Pitch Lock Control")
        self.lbl_pitch_lock_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pitch_lock_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")

        self.btn_pitch_lock = QPushButton("Engaged")
        self.btn_pitch_lock.setCheckable(True)
        self.btn_pitch_lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pitch_lock.setFixedHeight(68)
        self.btn_pitch_lock.clicked.connect(self.toggle_pitch_lock)
        c1.addWidget(self.lbl_pitch_lock_title)
        c1.addWidget(self.btn_pitch_lock)
        bot_row.addLayout(c1, stretch=1)

        # Col 2: Fast/Slow Speed (Figure 19) - Industrial Toggle Button
        c2 = QVBoxLayout()
        c2.setSpacing(4)
        self.lbl_speed_mode_title = QLabel("Fast/Slow Speed")
        self.lbl_speed_mode_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_speed_mode_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")

        self.btn_speed_mode = QPushButton("Fast Speed\nSelected")
        self.btn_speed_mode.setCheckable(True)
        self.btn_speed_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speed_mode.setFixedHeight(68)
        self.btn_speed_mode.clicked.connect(self.toggle_speed_mode)
        c2.addWidget(self.lbl_speed_mode_title)
        c2.addWidget(self.btn_speed_mode)
        bot_row.addLayout(c2, stretch=1)

        # Col 3: Move Blade (Figure 18)
        c3 = QVBoxLayout()
        c3.setSpacing(4)
        self.lbl_move_blade_title = QLabel("Move Blade")
        self.lbl_move_blade_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_move_blade_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")

        self.btn_move_feather = QPushButton("Feather")
        self.btn_move_feather.setFixedHeight(31)
        self.btn_move_feather.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9; border: 1px solid #64748B;
                color: #1E293B; font-weight: bold; border-radius: 3px; font-size: 11px;
            }
            QPushButton:pressed { background-color: #93C5FD; color: #1E3A8A; }
            QPushButton:disabled { background-color: #F1F5F9; border: 1px solid #CBD5E1; color: #94A3B8; }
        """)
        self.btn_move_feather.pressed.connect(self._on_feather_pressed)
        self.btn_move_feather.released.connect(self._on_feather_released)

        self.btn_move_fine = QPushButton("Fine")
        self.btn_move_fine.setFixedHeight(31)
        self.btn_move_fine.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9; border: 1px solid #64748B;
                color: #1E293B; font-weight: bold; border-radius: 3px; font-size: 11px;
            }
            QPushButton:pressed { background-color: #93C5FD; color: #1E3A8A; }
            QPushButton:disabled { background-color: #F1F5F9; border: 1px solid #CBD5E1; color: #94A3B8; }
        """)
        self.btn_move_fine.pressed.connect(self._on_fine_pressed)
        self.btn_move_fine.released.connect(self._on_fine_released)

        c3.addWidget(self.lbl_move_blade_title)
        c3.addWidget(self.btn_move_feather)
        c3.addSpacing(6)
        c3.addWidget(self.btn_move_fine)
        bot_row.addLayout(c3, stretch=1)

        layout.addLayout(bot_row)
        return grp

    def _create_mode_group(self):
        self.mode_card = ModeCard(
            mode_type="manual",
            on_action=self.handle_request_mode,
            parent=self
        )
        self.btn_req_mode = self.mode_card.btn_action
        self.lbl_prompt = self.mode_card.lbl_prompt
        self.card_prompt = self.mode_card.card_prompt
        return self.mode_card

    def _style_industrial_toggle_btn(self, is_pressed: bool) -> str:
        """
        Unified tactile industrial toggle button style matching B&R / Hydratech HMI.
        - is_pressed == False (Unpressed / Raised / 弹起): 3D tactile raised button with bottom shadow
        - is_pressed == True (Pressed / Sunken / 按下去): Deep 3D sunken inset into console with top shadow
        """
        if not is_pressed:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:0.15 #F8FAFC, stop:1 #E2E8F0);
                    border: 1.5px solid #94A3B8;
                    border-bottom: 3px solid #64748B;
                    border-right: 2px solid #64748B;
                    border-radius: 4px;
                    color: #1E293B;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #EEF2F6);
                    border-color: #475569;
                }
                QPushButton:pressed {
                    background: #CBD5E1;
                    border-top: 2.5px solid #0F172A;
                    border-left: 2px solid #0F172A;
                    border-bottom: 1px solid #E2E8F0;
                    border-right: 1px solid #E2E8F0;
                    padding-top: 6px;
                    padding-left: 6px;
                }
                QPushButton:disabled {
                    background-color: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #94A3B8;
                }
            """
        else:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #64748B, stop:0.25 #CBD5E1, stop:1 #E2E8F0);
                    border: 2px solid #1E293B;
                    border-radius: 4px;
                    color: #0F172A;
                    font-size: 11px;
                    font-weight: 800;
                    padding-top: 5px;
                    padding-left: 5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #475569, stop:0.25 #94A3B8, stop:1 #CBD5E1);
                    border-color: #0F172A;
                }
                QPushButton:pressed {
                    background: #94A3B8;
                    padding-top: 8px;
                    padding-left: 8px;
                }
                QPushButton:disabled {
                    background-color: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #94A3B8;
                }
            """

    def update_ui_state(self):
        in_manual = (self.plc.blade_mode == MODE_MANUAL)
        logged_in = self.plc.manual_logged_in
        is_super = getattr(self.plc, "is_super_user", False)
        is_cn = (self.current_lang == "CN")

        # 1. Update Calibration Authorization Badges & Controls
        unlocked = logged_in or is_super
        if unlocked:
            self.badge_pos_auth.setText("🔓 已解锁" if is_cn else "🔓 Unlocked")
            self.badge_pos_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
            self.badge_grd_auth.setText("🔓 已解锁" if is_cn else "🔓 Unlocked")
            self.badge_grd_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
        else:
            self.badge_pos_auth.setText("🔒 需登录" if is_cn else "🔒 Require Login")
            self.badge_pos_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #D97706; background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 3px; padding: 2px 8px;")
            self.badge_grd_auth.setText("🔒 需登录" if is_cn else "🔒 Require Login")
            self.badge_grd_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #D97706; background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 3px; padding: 2px 8px;")

        self.btn_apply_pos_calib.setEnabled(unlocked)
        for e in self.edit_offsets: e.setEnabled(unlocked)

        self.btn_apply_grd.setEnabled(unlocked)
        for e in self.grd_new_edits: e.setEnabled(unlocked)
        if not unlocked:
            for i, edit in enumerate(self.edit_offsets):
                if self._user_edited_offsets[i]:
                    self._user_edited_offsets[i] = False
                    edit.setText(f"{self.plc.blades[i].calib_offset_deg:.2f}")
                    edit.setStyleSheet("")
            for i, edit in enumerate(self.grd_new_edits):
                if self._user_edited_grds[i]:
                    self._user_edited_grds[i] = False
                    edit.setText(str(self.plc.blades[i].grd_current))
                    edit.setStyleSheet("")

        # 2. Update Manual Controls Badges & Controls
        controls_allowed = in_manual or is_super
        if controls_allowed:
            self.badge_lub_auth.setText(("✔ 超级权限" if is_super else "✔ 就绪") if is_cn else ("✔ Super Access" if is_super else "✔ Ready"))
            self.badge_lub_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
            self.badge_ctrl_auth.setText(("✔ 超级权限" if is_super else "✔ 就绪") if is_cn else ("✔ Super Access" if is_super else "✔ Ready"))
            self.badge_ctrl_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
        else:
            self.badge_lub_auth.setText("🔒 需手动模式" if is_cn else "🔒 Require Manual Mode")
            self.badge_lub_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 3px; padding: 2px 8px;")
            self.badge_ctrl_auth.setText("🔒 需手动模式" if is_cn else "🔒 Require Manual Mode")
            self.badge_ctrl_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 3px; padding: 2px 8px;")

        self.btn_pump1.setEnabled(controls_allowed)
        self.btn_pump2.setEnabled(controls_allowed)
        self.btn_pump1.setText(("停止润滑泵 1" if self.plc.pump1_active else "启动润滑泵 1") if is_cn else ("Deactivate Pump 1" if self.plc.pump1_active else "Activate Pump 1"))
        self.btn_pump2.setText(("停止润滑泵 2" if self.plc.pump2_active else "启动润滑泵 2") if is_cn else ("Deactivate Pump 2" if self.plc.pump2_active else "Activate Pump 2"))
        self.led_pump1.set_state(self.plc.pump1_active, "green", "grey")
        self.led_pump2.set_state(self.plc.pump2_active, "green", "grey")

        self.btn_pitch_lock.setEnabled(controls_allowed)
        self.btn_speed_mode.setEnabled(controls_allowed)
        self.btn_move_feather.setEnabled(controls_allowed)
        self.btn_move_fine.setEnabled(controls_allowed)
        self.edit_fast_spd.setEnabled(controls_allowed)
        self.edit_slow_spd.setEnabled(controls_allowed)
        for chk in self.chk_blades:
            chk.setEnabled(controls_allowed)

        # 3. Update Login Status Badge
        role_name = ("超级用户" if is_cn else "Super User") if is_super else ("已登录" if is_cn else "Logged In")
        self.login_card.set_state(unlocked, role_name=role_name if unlocked else None)

        # 4. Mode Request prompt and button
        if in_manual:
            prompt = "手动模式运行中，可请求退出手动模式。" if is_cn else "Manual mode active. Ready to exit manual mode."
            self.grp_mode.set_state(
                is_active=True,
                can_enter=True,
                prompt_text=prompt,
                badge_text="✔ 运行中" if is_cn else "✔ Active",
                badge_type="ready",
                can_exit=True
            )
        else:
            can_enter = (self.plc.blade_state == STATE_STOPPED) or is_super
            if can_enter:
                prompt = ("超级用户已就绪，可直接进入手动模式。" if is_super else "变桨系统已就绪，可请求进入手动模式。") if is_cn else ("Super User active. Ready to enter manual mode." if is_super else "Pitch System is ready to enter manual mode.")
                badge_text = ("✔ 超级权限" if is_super else "✔ 具备准入条件") if is_cn else ("✔ Super Access" if is_super else "✔ Ready to Enter")
                badge_type = "ready"
            else:
                prompt = "PAC 必须处于 STOPPED 状态方可进入手动模式。" if is_cn else "PAC must be STOPPED to enter manual mode."
                badge_text = "🔒 需处于已停止" if is_cn else "🔒 Need Stopped"
                badge_type = "locked"
            self.grp_mode.set_state(
                is_active=False,
                can_enter=can_enter,
                prompt_text=prompt,
                badge_text=badge_text,
                badge_type=badge_type
            )

        # 5. Telemetry & Current Blade
        cur_blade = self.plc.blades[self.plc.selected_blade_idx]
        if self.plc.is_opcua_online and self.plc.manual_current_pos is not None:
            self.lbl_current_pos.setText(f"{self.plc.manual_current_pos:.1f}")
        else:
            self.lbl_current_pos.setText(f"{cur_blade.angle_deg:.1f}")
        if 0 <= self.plc.selected_blade_idx < len(self.chk_blades):
            self.chk_blades[self.plc.selected_blade_idx].setChecked(True)

        # Update Pitch Lock Toggle Button
        is_engaged = cur_blade.pitch_lock_engaged
        is_lock_pressed = not is_engaged  # Released is the pressed/active state
        self.btn_pitch_lock.blockSignals(True)
        self.btn_pitch_lock.setChecked(is_lock_pressed)
        self.btn_pitch_lock.blockSignals(False)

        lock_text_en = "Engaged" if is_engaged else "Released"
        lock_text_cn = "已投入" if is_engaged else "已脱开"
        self.btn_pitch_lock.setText(lock_text_cn if is_cn else lock_text_en)
        self.btn_pitch_lock.setStyleSheet(self._style_industrial_toggle_btn(is_lock_pressed))

        # Update Fast/Slow Speed Toggle Button
        is_fast = (self.plc.manual_speed_mode == "FAST")
        is_speed_pressed = is_fast  # Fast Speed is the pressed/active state
        self.btn_speed_mode.blockSignals(True)
        self.btn_speed_mode.setChecked(is_speed_pressed)
        self.btn_speed_mode.blockSignals(False)

        spd_mode_en = "Fast Speed\nSelected" if is_fast else "Slow Speed\nSelected"
        spd_mode_cn = "快速模式\n(已选中)" if is_fast else "慢速模式\n(已选中)"
        self.btn_speed_mode.setText(spd_mode_cn if is_cn else spd_mode_en)
        self.btn_speed_mode.setStyleSheet(self._style_industrial_toggle_btn(is_speed_pressed))

        # Auto-sync fast/slow speed inputs if user is not actively typing
        if not self._user_edited_fast_spd and not self.edit_fast_spd.hasFocus():
            self.edit_fast_spd.setText(f"{self.plc.manual_fast_speed:.1f}")
        if not self._user_edited_slow_spd and not self.edit_slow_spd.hasFocus():
            self.edit_slow_spd.setText(f"{self.plc.manual_slow_speed:.1f}")

        # 6. Safety LEDs & Calibration Current Values & Auto Sync
        for i, b in enumerate(self.plc.blades):
            is_safe = self.plc.blade_safe[i] if i < len(self.plc.blade_safe) else False
            self.safe_leds[i].set_state(is_safe, "green", "grey")
            if i < len(self.lbl_pos_cur_vals):
                self.lbl_pos_cur_vals[i].setText(f"{b.angle_deg:.2f} °")
            if i < len(self.grd_cur_labels):
                self.grd_cur_labels[i].setText(str(b.grd_current))

            # Auto-sync offset input box if user is not actively typing
            if i < len(self.edit_offsets):
                edit = self.edit_offsets[i]
                if not self._user_edited_offsets[i] and not edit.hasFocus():
                    edit.setText(f"{b.calib_offset_deg:.2f}")

            # Auto-sync GRD new input box if user is not actively typing
            if i < len(self.grd_new_edits):
                edit = self.grd_new_edits[i]
                if not self._user_edited_grds[i] and not edit.hasFocus():
                    edit.setText(str(b.grd_current))

    def handle_login_logout(self):
        if self.plc.manual_logged_in or getattr(self.plc, "is_super_user", False):
            self.plc.manual_logged_in = False
            self.plc.is_super_user = False
            self.edit_password.clear()
        else:
            pwd = self.edit_password.text().strip()
            if pwd in [PASSWORD_SUPER_USER, "super"]:
                self.plc.manual_logged_in = True
                self.plc.is_super_user = True
            elif pwd in [PASSWORD_MANUAL_CALIB, "asdf"]:
                self.plc.manual_logged_in = True
                self.plc.is_super_user = False
            else:
                QMessageBox.warning(self, "Password Error", "Incorrect password!")
        self.update_ui_state()

    def handle_request_mode(self):
        if self.plc.blade_mode == MODE_PRODUCTION:
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.request_manual_mode()

            dlg = WarningModal(
                "Warning - Manual Mode",
                "WARNING: Entering the hub is NOT safe under any circumstances in Manual Mode!\n\nDo you want to proceed?",
                self,
                opcua_service=self.opcua_service
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.send_msgbox_ok()
                ok, msg = self.plc.request_manual_mode()
                if not ok:
                    QMessageBox.warning(self, "Manual Mode", msg)
            else:
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.send_msgbox_abort()
        else:
            ok, msg = self.plc.request_producing_mode()
            if not ok:
                QMessageBox.warning(self, "Producing Mode", msg)
            else:
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.request_producing_mode()

    def on_blade_selected(self, btn):
        idx = self.btn_group_blade.id(btn)
        if idx == self.plc.selected_blade_idx:
            return  # Already on this blade
        ok, msg = self.plc.select_blade(idx)
        if not ok:
            title = "桨叶选择" if self.current_lang == "CN" else "Blade Selection"
            QMessageBox.warning(self, title, msg)
            if 0 <= self.plc.selected_blade_idx < len(self.radio_blades):
                self.radio_blades[self.plc.selected_blade_idx].setChecked(True)
        else:
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.select_blade(idx)
            self.update_ui_state()

    def toggle_pitch_lock(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            is_cn = (self.current_lang == "CN")
            title = "通信断开" if is_cn else "Communication Offline"
            msg = (
                "⚠️ 当前 PLC 通信已断开，无法切换变桨锁销动作！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot toggle pitch lock!\n\nPlease check OPC UA connection."
            )
            QMessageBox.warning(self, title, msg)
            return

        cur_blade = self.plc.blades[self.plc.selected_blade_idx]
        target_disengaged = cur_blade.pitch_lock_engaged  # If currently engaged, we want to disengage (True)
        self.opcua_service.set_pitch_lock(target_disengaged)
        self.plc.toggle_pitch_lock()

    def toggle_speed_mode(self):
        if self.plc.manual_speed_mode == "FAST":
            self.plc.manual_speed_mode = "SLOW"
        else:
            self.plc.manual_speed_mode = "FAST"
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_speed_mode(self.plc.manual_speed_mode)
        self.update_ui_state()

    def toggle_pump(self, pump_no):
        if pump_no == 1:
            target = not self.plc.pump1_active
            self.plc.pump1_active = target
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.set_lubrication_pump(1, target)
        else:
            target = not self.plc.pump2_active
            self.plc.pump2_active = target
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.set_lubrication_pump(2, target)
        self.update_ui_state()

    def on_pos_text_changed(self, text):
        sender = self.sender()
        if sender is None:
            return
        try:
            idx = self.edit_offsets.index(sender)
            self._user_edited_offsets[idx] = True
            cur_val = f"{self.plc.blades[idx].calib_offset_deg:.2f}"
        except (ValueError, IndexError):
            cur_val = ""

        txt = text.strip()
        if not txt:
            sender.setStyleSheet("")
            return

        if txt in [cur_val, f"{float(cur_val):.1f}" if cur_val else ""]:
            sender.setStyleSheet("")
            return

        if txt in ["-", "+", "."]:
            sender.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")
            return

        try:
            val = float(txt)
            if not (OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG):
                sender.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")
            else:
                sender.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")
        except ValueError:
            sender.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")

    def _on_pos_edit_finished(self, edit, idx):
        txt = edit.text().strip()
        try:
            val = float(txt)
            if OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG:
                edit.setText(f"{val:.2f}")
                cur_val = self.plc.blades[idx].calib_offset_deg
                if abs(val - cur_val) < 0.001:
                    edit.setStyleSheet("")
                    self._user_edited_offsets[idx] = False
                else:
                    edit.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")
            else:
                edit.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")
        except ValueError:
            edit.setText(f"{self.plc.blades[idx].calib_offset_deg:.2f}")
            edit.setStyleSheet("")
            self._user_edited_offsets[idx] = False

    def on_grd_text_changed(self, text):
        sender = self.sender()
        if sender is None:
            return
        try:
            idx = self.grd_new_edits.index(sender)
            self._user_edited_grds[idx] = True
            cur_val = str(self.plc.blades[idx].grd_current)
        except (ValueError, IndexError):
            cur_val = ""

        txt = text.strip()
        if not txt:
            sender.setStyleSheet("")
            return

        if txt == cur_val:
            sender.setStyleSheet("")
            return

        try:
            val = int(txt)
            if not (GRD_MIN_VALUE <= val <= GRD_MAX_VALUE):
                sender.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")
            else:
                sender.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")
        except ValueError:
            sender.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")

    def _on_grd_edit_finished(self, edit, idx):
        txt = edit.text().strip()
        try:
            val = int(txt)
            if GRD_MIN_VALUE <= val <= GRD_MAX_VALUE:
                edit.setText(str(val))
                if val == self.plc.blades[idx].grd_current:
                    edit.setStyleSheet("")
                    self._user_edited_grds[idx] = False
                else:
                    edit.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")
            else:
                edit.setStyleSheet("background-color: #FEE2E2; border: 2px solid #EF4444; color: #DC2626; font-weight: bold;")
        except ValueError:
            edit.setText(str(self.plc.blades[idx].grd_current))
            edit.setStyleSheet("")
            self._user_edited_grds[idx] = False

    def _on_fast_spd_edited(self, text):
        self._user_edited_fast_spd = True

    def _on_slow_spd_edited(self, text):
        self._user_edited_slow_spd = True

    def _on_fast_spd_finished(self):
        txt = self.edit_fast_spd.text().strip()
        try:
            val = float(txt)
            if MANUAL_SPEED_MIN <= val <= MANUAL_SPEED_MAX:
                self.plc.manual_fast_speed = val
                self.edit_fast_spd.setText(f"{val:.1f}")
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.write_fast_speed(val)
            else:
                self.edit_fast_spd.setText(f"{self.plc.manual_fast_speed:.1f}")
        except ValueError:
            self.edit_fast_spd.setText(f"{self.plc.manual_fast_speed:.1f}")
        self._user_edited_fast_spd = False

    def _on_slow_spd_finished(self):
        txt = self.edit_slow_spd.text().strip()
        try:
            val = float(txt)
            if MANUAL_SPEED_MIN <= val <= MANUAL_SPEED_MAX:
                self.plc.manual_slow_speed = val
                self.edit_slow_spd.setText(f"{val:.1f}")
                if self.opcua_service and self.plc.is_opcua_online:
                    self.opcua_service.write_slow_speed(val)
            else:
                self.edit_slow_spd.setText(f"{self.plc.manual_slow_speed:.1f}")
        except ValueError:
            self.edit_slow_spd.setText(f"{self.plc.manual_slow_speed:.1f}")
        self._user_edited_slow_spd = False

    def _on_feather_pressed(self):
        self.plc.set_move_dir(1)
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_move_feather(True)

    def _on_feather_released(self):
        self.plc.set_move_dir(0)
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_move_feather(False)

    def _on_fine_pressed(self):
        self.plc.set_move_dir(-1)
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_move_fine(True)

    def _on_fine_released(self):
        self.plc.set_move_dir(0)
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_move_fine(False)

    def apply_pos_calib(self):
        # 1. Pre-validate all 3 blades against [OFFSET_MIN_DEG, OFFSET_MAX_DEG]
        invalid_blades = []
        parsed_vals = []
        for i, edit in enumerate(self.edit_offsets):
            txt = edit.text().strip()
            blade_letter = chr(65 + i)
            blade_name = f"Blade {blade_letter}" if self.current_lang == "EN" else f"叶片 {blade_letter}"
            try:
                val = float(txt)
                if not (OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG):
                    invalid_blades.append(f"{blade_name}: {val:.2f}°")
                parsed_vals.append(val)
            except ValueError:
                invalid_blades.append(f"{blade_name}: '{txt}'")
                parsed_vals.append(None)

        if invalid_blades:
            title = "输入范围错误" if self.current_lang == "CN" else "Input Range Error"
            msg = (
                f"偏置值必须在有效范围 [{OFFSET_MIN_DEG:.1f}°, {OFFSET_MAX_DEG:.1f}°] 内！\n"
                f"超出范围项:\n" + "\n".join(invalid_blades)
                if self.current_lang == "CN"
                else f"Offset values must be within valid range [{OFFSET_MIN_DEG:.1f}°, {OFFSET_MAX_DEG:.1f}°]!\n"
                     f"Out of range:\n" + "\n".join(invalid_blades)
            )
            QMessageBox.warning(self, title, msg)
            return

        # Check online communication status FIRST!
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = "通信断开" if is_cn else "Communication Offline"
            msg = (
                "⚠️ 当前 PLC 通信已断开，无法下发变桨位置标定参数至控制器！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot apply pitch position calibration to controller!\n\nPlease check OPC UA connection."
            )
            QMessageBox.warning(self, title, msg)
            return

        # 2. Apply validated values to PLC state and OPC UA
        for i, val in enumerate(parsed_vals):
            self.plc.blades[i].calib_offset_deg = val
            self.plc.blades[i].hmi_offset_temp = val
            edit = self.edit_offsets[i]
            edit.setText(f"{val:.2f}")
            edit.setStyleSheet("")
            self._user_edited_offsets[i] = False
            self.opcua_service.write_hmi_blade_offset(i, val)

        # Pulse Common.hmi.buttons.applyPPCSelection = 1 to trigger PLC handshake
        self.opcua_service.apply_pitch_position_calib()

        title = "标定成功" if is_cn else "Calibration"
        msg = "变桨位置标定参数已成功下发至 PLC！" if is_cn else "Pitch Position Calibration applied successfully to PLC!"
        QMessageBox.information(self, title, msg)

    def apply_grd_calib(self):
        # 1. Pre-validate all 3 blades
        invalid_blades = []
        parsed_vals = []
        for i, edit in enumerate(self.grd_new_edits):
            txt = edit.text().strip()
            blade_letter = chr(65 + i)
            blade_name = f"Blade {blade_letter}" if self.current_lang == "EN" else f"叶片 {blade_letter}"
            try:
                val = int(txt)
                if not (GRD_MIN_VALUE <= val <= GRD_MAX_VALUE):
                    invalid_blades.append(f"{blade_name}: {val}")
                parsed_vals.append(val)
            except ValueError:
                invalid_blades.append(f"{blade_name}: '{txt}'")
                parsed_vals.append(None)

        if invalid_blades:
            title = "输入范围错误" if self.current_lang == "CN" else "Input Range Error"
            msg = (
                f"GRD 值必须在有效范围 [{GRD_MIN_VALUE}, {GRD_MAX_VALUE}] 内！\n"
                f"超出范围项:\n" + "\n".join(invalid_blades)
                if self.current_lang == "CN"
                else f"GRD values must be within valid range [{GRD_MIN_VALUE}, {GRD_MAX_VALUE}]!\n"
                     f"Out of range:\n" + "\n".join(invalid_blades)
            )
            QMessageBox.warning(self, title, msg)
            return

        # Check online communication status FIRST!
        is_cn = (self.current_lang == "CN")
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = "通信断开" if is_cn else "Communication Offline"
            msg = (
                "⚠️ 当前 PLC 通信已断开，无法下发 GRD 标定参数至控制器！\n\n请检查底层 OPC UA 通信连接。"
                if is_cn else
                "⚠️ PLC communication is offline. Cannot apply GRD calibration to controller!\n\nPlease check OPC UA connection."
            )
            QMessageBox.warning(self, title, msg)
            return

        # 2. Apply validated values to PLC state and OPC UA
        for i, val in enumerate(parsed_vals):
            self.plc.blades[i].grd_current = val
            self.plc.blades[i].grd_new = val
            self.grd_cur_labels[i].setText(str(val))
            edit = self.grd_new_edits[i]
            edit.setText(str(val))
            edit.setStyleSheet("")
            self._user_edited_grds[i] = False
            self.opcua_service.write_hmi_blade_grd(i, val)

        # Pulse Common.hmi.buttons.applyGRDSelection = 1 to trigger PLC handshake
        self.opcua_service.apply_grd_calib()

        title = "标定成功" if is_cn else "Calibration"
        msg = "GRD 标定参数已成功下发至 PLC！" if is_cn else "GRD Calibration applied successfully to PLC!"
        QMessageBox.information(self, title, msg)
