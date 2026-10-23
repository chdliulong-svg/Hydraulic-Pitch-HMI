# -*- coding: utf-8 -*-
"""
Manual Mode Page - Hydraulic Pitch HMI
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
    MODE_MANUAL, MODE_PRODUCTION, STATE_STOPPED,
    ROLE_NOT_LOGGED_IN,
    MANUAL_FAST_SPEED_DEFAULT, MANUAL_SLOW_SPEED_DEFAULT,
    MANUAL_SPEED_MIN, MANUAL_SPEED_MAX,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG
)
from utils.widgets import StatusLed, WarningModal, ValueDisplay
from ui.login_card import LoginCard
from ui.mode_card import ModeCard
from utils.i18n import tr


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

        self.grp_calib_pos.setTitle(tr("Pitch Position Calibration [deg]", lang))
        self.grp_calib_grd.setTitle(tr("GRD Calibration [cm/s]", lang))
        self.grp_lub.setTitle(tr("Blade Lubrication", lang))
        self.grp_blade_ctrl.setTitle(tr("HMI Blade Control", lang))
        self.login_card.retranslate_ui(lang)
        self.grp_mode.retranslate_ui(lang)

        self.btn_apply_pos_calib.setText(tr("Apply Changes", lang))
        self.btn_apply_grd.setText(tr("Apply Changes", lang))

        self.lbl_hdr_pos_blade.setText(tr("Blade", lang))
        self.lbl_hdr_pos_cur.setText(tr("Current", lang))
        self.lbl_hdr_pos_off.setText(tr("Offset [°]", lang))

        self.lbl_hdr_grd_blade.setText(tr("Blade", lang))
        self.lbl_hdr_grd_cur.setText(tr("Current", lang))
        self.lbl_hdr_grd_new.setText(tr("New", lang))

        for i, name in enumerate(["A", "B", "C"]):
            prefix = tr("Blade", lang) + " "
            self.lbl_pos_blade_names[i].setText(f"{prefix}{name}")
            self.lbl_grd_blade_names[i].setText(f"{prefix}{name}")

        for edit in getattr(self, "edit_offsets", []):
            edit.setToolTip(
                f"{tr('Offset Valid Range', lang)}: {OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°"
            )

        for edit in getattr(self, "grd_new_edits", []):
            edit.setToolTip(
                f"{tr('GRD Valid Range', lang)}: {GRD_MIN_VALUE} ~ {GRD_MAX_VALUE} pulse/(cm/s)"
            )

        self.lbl_blade_sel_title.setText(tr("Blade selected", lang))
        self.lbl_blade_safe_title.setText(tr("Blade safe", lang))
        self.lbl_remote_box_speed_title.setText(tr("Remote box speed", lang))
        self.lbl_fast_spd_title.setText(tr("Fast speed", lang))
        self.lbl_slow_spd_title.setText(tr("Slow speed", lang))
        self.lbl_pos_mon_title.setText(tr("Current Pos.", lang))
        self.lbl_pitch_lock_title.setText(tr("Pitch Lock Control", lang))
        self.lbl_speed_mode_title.setText(tr("Fast/Slow Speed", lang))
        self.lbl_move_blade_title.setText(tr("Move Blade", lang))

        self.lbl_p1_title.setText(tr("Pump 1:", lang))
        self.lbl_p2_title.setText(tr("Pump 2:", lang))
        self.btn_move_feather.setText(tr("Feather", lang))
        self.btn_move_fine.setText(tr("Fine", lang))

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
                tr("Offset Valid Range: {min_deg:.1f}° ~ {max_deg:.1f}°", self.current_lang).format(
                    min_deg=OFFSET_MIN_DEG, max_deg=OFFSET_MAX_DEG
                )
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
                tr("GRD Valid Range: {min_val} ~ {max_val} pulse/(cm/s)", self.current_lang).format(
                    min_val=GRD_MIN_VALUE, max_val=GRD_MAX_VALUE
                )
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
        self.plc.auth_changed.connect(self._on_auth_changed)
        self.btn_login = self.login_card.btn_login
        self.edit_password = self.login_card.edit_password
        self.badge_login_status = self.login_card.badge_status
        return self.login_card

    def _handle_manual_login(self, pwd):
        ok, msg, role = self.plc.authenticate(pwd)
        if ok:
            return True, ""
        return False, tr("Incorrect password!", self.current_lang)

    def _handle_manual_logout(self):
        self.plc.logout()

    def _on_auth_changed(self, role):
        is_logged = (role != ROLE_NOT_LOGGED_IN)
        self.login_card.set_state(is_logged, role if is_logged else None)
        self.update_ui_state()

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
        self.led_pump1 = StatusLed(color="grey", shape="circle", size=14)
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
        self.led_pump2 = StatusLed(color="grey", shape="circle", size=14)
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
            led = StatusLed(color="grey", shape="circle", size=14)
            led.set_state(False)
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
        Unified tactile industrial toggle button style matching standard industrial HMI.
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

        # 1. Update Calibration Authorization Badges & Controls
        unlocked = logged_in or is_super
        if unlocked:
            self.badge_pos_auth.setText(tr("🔓 Unlocked", self.current_lang))
            self.badge_pos_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
            self.badge_grd_auth.setText(tr("🔓 Unlocked", self.current_lang))
            self.badge_grd_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
        else:
            self.badge_pos_auth.setText(tr("🔒 Require Login", self.current_lang))
            self.badge_pos_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #D97706; background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 3px; padding: 2px 8px;")
            self.badge_grd_auth.setText(tr("🔒 Require Login", self.current_lang))
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
        is_online = getattr(self.plc, "is_opcua_online", False)
        controls_allowed = (in_manual or is_super) and is_online
        if not is_online:
            self.badge_lub_auth.setText(tr("🔒 Offline", self.current_lang))
            self.badge_lub_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #DC2626; background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 3px; padding: 2px 8px;")
            self.badge_ctrl_auth.setText(tr("🔒 Offline", self.current_lang))
            self.badge_ctrl_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #DC2626; background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 3px; padding: 2px 8px;")
        elif controls_allowed:
            self.badge_lub_auth.setText(tr("✔ Super Access" if is_super else "✔ Ready", self.current_lang))
            self.badge_lub_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
            self.badge_ctrl_auth.setText(tr("✔ Super Access" if is_super else "✔ Ready", self.current_lang))
            self.badge_ctrl_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0; border-radius: 3px; padding: 2px 8px;")
        else:
            self.badge_lub_auth.setText(tr("🔒 Require Manual Mode", self.current_lang))
            self.badge_lub_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 3px; padding: 2px 8px;")
            self.badge_ctrl_auth.setText(tr("🔒 Require Manual Mode", self.current_lang))
            self.badge_ctrl_auth.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 3px; padding: 2px 8px;")

        self.btn_pump1.setEnabled(controls_allowed)
        self.btn_pump2.setEnabled(controls_allowed)
        self.btn_pump1.setText(tr("Deactivate Pump 1" if self.plc.pump1_active else "Activate Pump 1", self.current_lang))
        self.btn_pump2.setText(tr("Deactivate Pump 2" if self.plc.pump2_active else "Activate Pump 2", self.current_lang))
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
        role_name = tr("Super User", self.current_lang) if is_super else tr("Logged In", self.current_lang)
        self.login_card.set_state(unlocked, role_name=role_name if unlocked else None)

        # 4. Mode Request prompt and button
        if not is_online:
            self.grp_mode.set_state(
                is_active=in_manual,
                can_enter=False,
                prompt_text=tr("PLC communication offline. Mode switch disabled.", self.current_lang),
                badge_text=tr("🔒 Offline", self.current_lang),
                badge_type="locked",
                can_exit=False
            )
        elif in_manual:
            prompt = tr("Manual mode active. Ready to exit manual mode.", self.current_lang)
            self.grp_mode.set_state(
                is_active=True,
                can_enter=False,
                prompt_text=prompt,
                badge_text=tr("✔ Active", self.current_lang),
                badge_type="ready",
                can_exit=True
            )
        else:
            can_enter = (self.plc.blade_state == STATE_STOPPED) or is_super
            if can_enter:
                prompt = tr("Super User active. Ready to enter manual mode." if is_super else "Pitch System is ready to enter manual mode.", self.current_lang)
                badge_text = tr("✔ Super Access" if is_super else "✔ Ready to Enter", self.current_lang)
                badge_type = "ready"
            else:
                prompt = tr("PAC must be STOPPED to enter manual mode.", self.current_lang)
                badge_text = tr("🔒 Need Stopped", self.current_lang)
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

        # Update Pitch Lock Toggle Button (HMI control command, NOT hardware status feedback)
        is_disengaged = self.plc.manual_pitch_lock_disengaged
        is_lock_pressed = is_disengaged  # Released is the pressed/active state
        self.btn_pitch_lock.blockSignals(True)
        self.btn_pitch_lock.setChecked(is_lock_pressed)
        self.btn_pitch_lock.blockSignals(False)

        lock_text_en = "Released" if is_disengaged else "Engaged"
        self.btn_pitch_lock.setText(tr(lock_text_en, self.current_lang))
        self.btn_pitch_lock.setStyleSheet(self._style_industrial_toggle_btn(is_lock_pressed))

        # Update Fast/Slow Speed Toggle Button
        is_fast = (self.plc.manual_speed_mode == "FAST")
        is_speed_pressed = is_fast  # Fast Speed is the pressed/active state
        self.btn_speed_mode.blockSignals(True)
        self.btn_speed_mode.setChecked(is_speed_pressed)
        self.btn_speed_mode.blockSignals(False)

        spd_mode_en = "Fast Speed\nSelected" if is_fast else "Slow Speed\nSelected"
        self.btn_speed_mode.setText(tr(spd_mode_en, self.current_lang))
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

    def handle_request_mode(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot switch operation mode!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        if self.plc.blade_mode == MODE_PRODUCTION:
            title = tr("Warning - Manual Mode", self.current_lang)
            msg = tr("WARNING: Entering the hub is NOT safe under any circumstances in Manual Mode!\n\nDo you want to proceed?", self.current_lang)
            dlg = WarningModal(title, msg, self, opcua_service=None)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.opcua_service.request_manual_mode()
        else:
            self.opcua_service.request_producing_mode()
        self.update_ui_state()

    def on_blade_selected(self, btn):
        idx = self.btn_group_blade.id(btn)
        if idx == self.plc.selected_blade_idx:
            return  # Already on this blade
        ok, msg = self.plc.select_blade(idx)
        if not ok:
            title = tr("Blade Selection", self.current_lang)
            QMessageBox.warning(self, title, msg)
            if 0 <= self.plc.selected_blade_idx < len(self.radio_blades):
                self.radio_blades[self.plc.selected_blade_idx].setChecked(True)
        else:
            if self.opcua_service and self.plc.is_opcua_online:
                self.opcua_service.select_blade(idx)
            self.update_ui_state()

    def toggle_pitch_lock(self):
        new_state = self.plc.toggle_pitch_lock()
        if self.opcua_service and getattr(self.plc, "is_opcua_online", False):
            self.opcua_service.set_pitch_lock(new_state)
        self.update_ui_state()

    def toggle_speed_mode(self):
        if self.plc.manual_speed_mode == "FAST":
            self.plc.manual_speed_mode = "SLOW"
        else:
            self.plc.manual_speed_mode = "FAST"
        if self.opcua_service and self.plc.is_opcua_online:
            self.opcua_service.set_speed_mode(self.plc.manual_speed_mode)
        self.update_ui_state()

    def toggle_pump(self, pump_no):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot toggle lubrication pump!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        if pump_no == 1:
            target = not self.plc.pump1_active
            self.opcua_service.set_lubrication_pump(1, target)
        else:
            target = not self.plc.pump2_active
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

    def _safety_stop_motion(self):
        """Safety release on focus loss or tab hide to avoid runaway blade pitching"""
        if getattr(self.plc, "manual_moving_dir", 0) != 0:
            self.plc.set_move_dir(0)
            if self.opcua_service and getattr(self.plc, "is_opcua_online", False):
                self.opcua_service.set_move_feather(False)
                self.opcua_service.set_move_fine(False)

    def hideEvent(self, event):
        self._safety_stop_motion()
        super().hideEvent(event)

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
            title = tr("Input Range Error", self.current_lang)
            items = "\n".join(invalid_blades)
            msg = tr("Offset values must be within valid range [{min_deg:.1f}°, {max_deg:.1f}°]!\nOut of range:\n{items}", self.current_lang).format(
                min_deg=OFFSET_MIN_DEG, max_deg=OFFSET_MAX_DEG, items=items
            )
            QMessageBox.warning(self, title, msg)
            return

        # Check online communication status FIRST!
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot apply pitch position calibration to controller!\n\nPlease check OPC UA connection.", self.current_lang)
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

    def apply_grd_calib(self):
        # 1. Pre-validate all 3 blades
        invalid_blades = []
        parsed_vals = []
        for i, edit in enumerate(self.grd_new_edits):
            txt = edit.text().strip()
            blade_letter = chr(65 + i)
            blade_name = f"{tr('Blade', self.current_lang)} {blade_letter}"
            try:
                val = int(txt)
                if not (GRD_MIN_VALUE <= val <= GRD_MAX_VALUE):
                    invalid_blades.append(f"{blade_name}: {val}")
                parsed_vals.append(val)
            except ValueError:
                invalid_blades.append(f"{blade_name}: '{txt}'")
                parsed_vals.append(None)

        if invalid_blades:
            title = tr("Input Range Error", self.current_lang)
            msg = (
                f"{tr('GRD Valid Range', self.current_lang)}: [{GRD_MIN_VALUE}, {GRD_MAX_VALUE}]!\n"
                f"Out of range:\n" + "\n".join(invalid_blades)
            )
            QMessageBox.warning(self, title, msg)
            return

        # Check online communication status FIRST!
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot apply GRD calibration to controller!\n\nPlease check OPC UA connection.", self.current_lang)
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
