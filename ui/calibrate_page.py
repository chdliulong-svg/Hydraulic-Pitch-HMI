# -*- coding: utf-8 -*-
"""
Calibrate Page - Hydraulic Pitch HMI
Implements Pitch Position Calibration, GRD Calibration, and User Authentication Login.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator, QDoubleValidator

from config import (
    ROLE_NOT_LOGGED_IN,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG
)
from ui.login_card import LoginCard
from ui.grd_calc_dialog import GrdCalcDialog
from utils.i18n import tr


class CalibratePage(QWidget):
    def __init__(self, plc_state, opcua_service=None, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"
        self._user_edited_offsets = [False, False, False]
        self._user_edited_grds = [False, False, False]

        self.init_ui()
        self.plc.state_changed.connect(self.update_ui_state)
        self.plc.auth_changed.connect(self._on_auth_changed)
        self.update_ui_state()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)

        # 1. Pitch Position Calibration Group (Left Column)
        self.grp_calib_pos = self._create_pos_calib_group()
        main_layout.addWidget(self.grp_calib_pos, 1)

        # 2. GRD Calibration Group (Middle Column)
        self.grp_calib_grd = self._create_grd_calib_group()
        main_layout.addWidget(self.grp_calib_grd, 1)

        # 3. User Login Group (Right Column)
        self.grp_login = self._create_login_group()
        main_layout.addWidget(self.grp_login, 0, Qt.AlignmentFlag.AlignTop)

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
        table_grid.setVerticalSpacing(8)

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

            val = QLabel("0.00 °")
            val.setFixedWidth(86)
            val.setFixedHeight(26)
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("background-color: #FFFFFF; border: 1px solid #B0B5B9; border-radius: 3px; font-size: 11px; font-weight: bold; color: #111111;")

            edit = QLineEdit(f"{self.plc.blades[row-1].calib_offset_deg:.2f}")
            edit.setFixedWidth(86)
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
        table_grid.setHorizontalSpacing(8)
        table_grid.setVerticalSpacing(8)

        self.lbl_hdr_grd_blade = QLabel("Blade")
        self.lbl_hdr_grd_blade.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_cur = QLabel("Current")
        self.lbl_hdr_grd_cur.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_grd_new = QLabel("New")
        self.lbl_hdr_grd_new.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_new.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hdr_grd_calc = QLabel("Calc")
        self.lbl_hdr_grd_calc.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
        self.lbl_hdr_grd_calc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_grid.addWidget(self.lbl_hdr_grd_blade, 0, 0)
        table_grid.addWidget(self.lbl_hdr_grd_cur, 0, 1)
        table_grid.addWidget(self.lbl_hdr_grd_new, 0, 2)
        table_grid.addWidget(self.lbl_hdr_grd_calc, 0, 3)

        self.grd_cur_labels = []
        self.grd_new_edits = []
        self.lbl_grd_blade_names = []
        self.btn_grd_calcs = []
        for row, name in enumerate(["Blade A", "Blade B", "Blade C"], start=1):
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
            self.lbl_grd_blade_names.append(lbl_name)

            cur = QLabel(str(self.plc.blades[row-1].grd_current))
            cur.setFixedWidth(78)
            cur.setFixedHeight(26)
            cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cur.setStyleSheet("background-color: #FFFFFF; border: 1px solid #B0B5B9; border-radius: 3px; font-size: 11px; font-weight: bold; color: #111111;")

            edit = QLineEdit(str(self.plc.blades[row-1].grd_current))
            edit.setFixedWidth(78)
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

            btn_calc = QPushButton("📐 " + tr("Calc", self.current_lang))
            btn_calc.setFixedWidth(68)
            btn_calc.setFixedHeight(26)
            btn_calc.setStyleSheet("""
                QPushButton {
                    background-color: #F8FAFC; color: #0284C7; font-weight: bold;
                    border: 1px solid #BAE6FD; border-radius: 3px; font-size: 11px;
                }
                QPushButton:hover { background-color: #E0F2FE; border-color: #0284C7; color: #0369A1; }
                QPushButton:disabled { background-color: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }
            """)
            btn_calc.setToolTip(
                "基于油缸全行程固定全长 (822.000 mm) 与实测无损全精度进行 GRD 反向精确推算"
                if self.current_lang == "CN"
                else "Reverse calculate GRD based on cylinder full stroke (822.000 mm) with lossless precision"
            )
            btn_calc.clicked.connect(lambda _, idx=row-1: self._open_grd_calc_dialog(idx))

            table_grid.addWidget(lbl_name, row, 0)
            table_grid.addWidget(cur, row, 1)
            table_grid.addWidget(edit, row, 2)
            table_grid.addWidget(btn_calc, row, 3)

            self.grd_cur_labels.append(cur)
            self.grd_new_edits.append(edit)
            self.btn_grd_calcs.append(btn_calc)

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

    def retranslate_ui(self, lang="EN"):
        self.current_lang = lang

        self.grp_calib_pos.setTitle(tr("Pitch Position Calibration [deg]", lang))
        self.grp_calib_grd.setTitle(tr("GRD Calibration [cm/s]", lang))
        self.login_card.retranslate_ui(lang)

        self.btn_apply_pos_calib.setText(tr("Apply Changes", lang))
        self.btn_apply_grd.setText(tr("Apply Changes", lang))

        self.lbl_hdr_pos_blade.setText(tr("Blade", lang))
        self.lbl_hdr_pos_cur.setText(tr("Current", lang))
        self.lbl_hdr_pos_off.setText(tr("Offset [°]", lang))

        self.lbl_hdr_grd_blade.setText(tr("Blade", lang))
        self.lbl_hdr_grd_cur.setText(tr("Current", lang))
        self.lbl_hdr_grd_new.setText(tr("New", lang))
        if hasattr(self, "lbl_hdr_grd_calc"):
            self.lbl_hdr_grd_calc.setText(tr("Calc", lang))

        for btn in getattr(self, "btn_grd_calcs", []):
            btn.setText("📐 " + tr("Calc", lang))
            btn.setToolTip(
                "基于油缸全行程固定全长 (822.000 mm) 与实测无损全精度进行 GRD 反向精确推算"
                if lang == "CN"
                else "Reverse calculate GRD based on cylinder full stroke (822.000 mm) with lossless precision"
            )

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

        self.update_ui_state()

    def update_ui_state(self):
        # 1. Check user login role
        user_role = self.plc.current_role
        is_authenticated = (user_role != ROLE_NOT_LOGGED_IN)

        # 2. Update Calibration Group Lock & State
        for edit in self.edit_offsets:
            edit.setEnabled(is_authenticated)
        self.btn_apply_pos_calib.setEnabled(is_authenticated)

        for edit in self.grd_new_edits:
            edit.setEnabled(is_authenticated)
        self.btn_apply_grd.setEnabled(is_authenticated)
        for btn in getattr(self, "btn_grd_calcs", []):
            btn.setEnabled(is_authenticated)

        if is_authenticated:
            self.badge_pos_auth.setText(tr("🔓 Authorized", self.current_lang))
            self.badge_pos_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #059669;
                background-color: #D1FAE5; border: 1px solid #A7F3D0;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.badge_grd_auth.setText(tr("🔓 Authorized", self.current_lang))
            self.badge_grd_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #059669;
                background-color: #D1FAE5; border: 1px solid #A7F3D0;
                border-radius: 3px; padding: 2px 8px;
            """)
        else:
            self.badge_pos_auth.setText(tr("🔒 Require Login", self.current_lang))
            self.badge_pos_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #D97706;
                background-color: #FEF3C7; border: 1px solid #FDE68A;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.badge_grd_auth.setText(tr("🔒 Require Login", self.current_lang))
            self.badge_grd_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #D97706;
                background-color: #FEF3C7; border: 1px solid #FDE68A;
                border-radius: 3px; padding: 2px 8px;
            """)

        # 3. Synchronize Current Values and Inputs from PLC
        for i, b in enumerate(self.plc.blades):
            if i < len(self.lbl_pos_cur_vals):
                self.lbl_pos_cur_vals[i].setText(f"{b.angle_deg:.2f} °")
            if i < len(self.grd_cur_labels):
                self.grd_cur_labels[i].setText(str(b.grd_current))

            if i < len(self.edit_offsets):
                edit = self.edit_offsets[i]
                if not self._user_edited_offsets[i] and not edit.hasFocus():
                    edit.setText(f"{b.calib_offset_deg:.2f}")

            if i < len(self.grd_new_edits):
                edit = self.grd_new_edits[i]
                if not self._user_edited_grds[i] and not edit.hasFocus():
                    edit.setText(str(b.grd_current))

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

    def _open_grd_calc_dialog(self, blade_idx: int):
        bld = self.plc.blades[blade_idx]
        blade_display_name = f"{tr('Blade', self.current_lang)} {chr(65 + blade_idx)}"

        cur_grd = bld.grd_current
        # Read live cylinder position
        cur_pos_mm = getattr(bld, "cyl_pos_mm", 0.0)

        dlg = GrdCalcDialog(
            blade_name=blade_display_name,
            cur_grd=cur_grd,
            cur_pos_mm=cur_pos_mm,
            full_stroke_mm=822.0,
            lang=self.current_lang,
            parent=self
        )
        if dlg.exec():
            calc_grd = dlg.get_calculated_grd()
            if calc_grd is not None and (GRD_MIN_VALUE <= calc_grd <= GRD_MAX_VALUE):
                edit = self.grd_new_edits[blade_idx]
                edit.setText(str(calc_grd))
                self._user_edited_grds[blade_idx] = True
                if calc_grd == bld.grd_current:
                    edit.setStyleSheet("")
                    self._user_edited_grds[blade_idx] = False
                else:
                    edit.setStyleSheet("background-color: #FFFDE7; border: 2px solid #FBC02D; color: #E65100; font-weight: bold;")

    def apply_pos_calib(self):
        invalid_blades = []
        parsed_vals = []
        for i, edit in enumerate(self.edit_offsets):
            txt = edit.text().strip()
            try:
                v = float(txt)
                if not (OFFSET_MIN_DEG <= v <= OFFSET_MAX_DEG):
                    invalid_blades.append((chr(65 + i), txt))
                else:
                    parsed_vals.append(v)
            except ValueError:
                invalid_blades.append((chr(65 + i), txt))

        if invalid_blades:
            title = tr("Calibration Value Error", self.current_lang)
            err_details = "\n".join([f"• {tr('Blade', self.current_lang)} {b}: '{val}'" for b, val in invalid_blades])
            msg = (
                f"{tr('The following pitch calibration offsets are outside valid range', self.current_lang)}:\n\n"
                f"{err_details}\n\n"
                f"{tr('Allowed Range', self.current_lang)}: [{OFFSET_MIN_DEG:.1f}° ~ {OFFSET_MAX_DEG:.1f}°]"
            )
            QMessageBox.critical(self, title, msg)
            return

        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot apply pitch position calibration to controller!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        for idx, val in enumerate(parsed_vals):
            self.opcua_service.write_hmi_blade_offset(idx, val)
        if hasattr(self.opcua_service, "apply_pitch_position_calib"):
            self.opcua_service.apply_pitch_position_calib()
        elif hasattr(self.opcua_service, "apply_pos_calibration"):
            self.opcua_service.apply_pos_calibration()

        for idx, edit in enumerate(self.edit_offsets):
            self._user_edited_offsets[idx] = False
            edit.setStyleSheet("")

        title = tr("Calibration Success", self.current_lang)
        msg = tr("Pitch Position Calibration applied successfully to PLC!", self.current_lang)
        QMessageBox.information(self, title, msg)
        self.update_ui_state()

    def apply_grd_calib(self):
        invalid_blades = []
        parsed_vals = []
        for i, edit in enumerate(self.grd_new_edits):
            txt = edit.text().strip()
            try:
                v = int(txt)
                if not (GRD_MIN_VALUE <= v <= GRD_MAX_VALUE):
                    invalid_blades.append((chr(65 + i), txt))
                else:
                    parsed_vals.append(v)
            except ValueError:
                invalid_blades.append((chr(65 + i), txt))

        if invalid_blades:
            title = tr("Calibration Value Error", self.current_lang)
            err_details = "\n".join([f"• {tr('Blade', self.current_lang)} {b}: '{val}'" for b, val in invalid_blades])
            msg = (
                f"{tr('The following GRD values are outside valid range', self.current_lang)}:\n\n"
                f"{err_details}\n\n"
                f"{tr('Allowed Range', self.current_lang)}: [{GRD_MIN_VALUE} ~ {GRD_MAX_VALUE}] pulse/(cm/s)"
            )
            QMessageBox.critical(self, title, msg)
            return

        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot apply GRD calibration to controller!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        for idx, val in enumerate(parsed_vals):
            self.opcua_service.write_hmi_blade_grd(idx, val)
        if hasattr(self.opcua_service, "apply_grd_calib"):
            self.opcua_service.apply_grd_calib()
        elif hasattr(self.opcua_service, "apply_grd_calibration"):
            self.opcua_service.apply_grd_calibration()

        for idx, edit in enumerate(self.grd_new_edits):
            self._user_edited_grds[idx] = False
            edit.setStyleSheet("")

        title = tr("Calibration Success", self.current_lang)
        msg = tr("GRD Calibration applied successfully to PLC!", self.current_lang)
        QMessageBox.information(self, title, msg)
        self.update_ui_state()
