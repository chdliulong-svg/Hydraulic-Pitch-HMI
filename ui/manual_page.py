# -*- coding: utf-8 -*-
"""
Manual Mode Page - Hydraulic Pitch HMI
Contains:
1. ManualControlView:
   - 3 Blade Telemetry Cards (identical to Overview)
   - Blade Lubrication Deck
   - HMI Blade Control Deck
   - Mode Permission Card
2. CalibratePage (from ui.calibrate_page):
   - Pitch Position Calibration
   - GRD Calibration
   - User Login Card
3. ManualPage:
   - Container hosting 'Manual' and 'Calibrate' tabs
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QRadioButton, QButtonGroup,
    QMessageBox, QFrame, QDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config import (
    MODE_MANUAL, MODE_PRODUCTION, STATE_STOPPED,
    ROLE_NOT_LOGGED_IN,
    MANUAL_FAST_SPEED_DEFAULT, MANUAL_SLOW_SPEED_DEFAULT,
    MANUAL_SPEED_MIN, MANUAL_SPEED_MAX
)
from utils.widgets import StatusLed, WarningModal
from utils.card_framework import BladeTelemetryCard
from ui.mode_card import ModeCard
from ui.calibrate_page import CalibratePage
from utils.i18n import tr


class ManualControlView(QWidget):
    """
    Manual Operation Page:
    - Top: 3 Blade Telemetry Cards (same as Overview page)
    - Bottom: Blade Lubrication, HMI Blade Control, and Mode Request Card
    """
    def __init__(self, plc_state, opcua_service=None, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"
        self._user_edited_fast_spd = False
        self._user_edited_slow_spd = False

        self.init_ui()
        self.plc.state_changed.connect(self.update_ui_state)
        self.update_ui_state()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(8)

        # 1. Top Section: 3 Blade Cards (Same as Overview / InspectPage)
        blades_layout = QHBoxLayout()
        blades_layout.setSpacing(6)
        self.blade_cards = []
        for b in self.plc.blades:
            card = BladeTelemetryCard(b.name)
            blades_layout.addWidget(card, 1)
            self.blade_cards.append(card)
        main_layout.addLayout(blades_layout, 1)

        # 2. Bottom Section: Lubrication, Blade Control, Mode Card
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        # Left Column: Blade Lubrication
        self.grp_lub = self._create_lubrication_group()
        bottom_layout.addWidget(self.grp_lub, 1)

        # Middle Column: HMI Blade Control
        self.grp_blade_ctrl = self._create_blade_ctrl_group()
        bottom_layout.addWidget(self.grp_blade_ctrl, 2)

        # Right Column: Manual Mode Request Card
        self.grp_mode = self._create_mode_group()
        bottom_layout.addWidget(self.grp_mode, 0, Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(bottom_layout, 1)

        self.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                font-weight: bold;
                color: #1E293B;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
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

    def _create_lubrication_group(self):
        grp = QGroupBox("Blade Lubrication")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

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
        row_p1.setSpacing(8)
        self.led_pump1 = StatusLed(color="grey", shape="circle", size=14)
        self.lbl_p1_title = QLabel("Pump 1:")
        self.lbl_p1_title.setFixedWidth(56)
        self.lbl_p1_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.btn_pump1 = QPushButton("Activate Pump 1")
        self.btn_pump1.setFixedHeight(30)
        self.btn_pump1.clicked.connect(lambda: self.toggle_pump(1))
        row_p1.addWidget(self.led_pump1)
        row_p1.addWidget(self.lbl_p1_title)
        row_p1.addWidget(self.btn_pump1, 1)
        layout.addLayout(row_p1)

        # Pump 2 Card
        row_p2 = QHBoxLayout()
        row_p2.setSpacing(8)
        self.led_pump2 = StatusLed(color="grey", shape="circle", size=14)
        self.lbl_p2_title = QLabel("Pump 2:")
        self.lbl_p2_title.setFixedWidth(56)
        self.lbl_p2_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        self.btn_pump2 = QPushButton("Activate Pump 2")
        self.btn_pump2.setFixedHeight(30)
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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Status badge row
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

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Left Column: Blade selection & safety
        col_left = QVBoxLayout()
        col_left.setSpacing(3)
        self.lbl_blade_sel_title = QLabel("Blade selected")
        self.lbl_blade_sel_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        col_left.addWidget(self.lbl_blade_sel_title)

        grid_sel = QGridLayout()
        grid_sel.setHorizontalSpacing(6)
        grid_sel.setVerticalSpacing(3)
        grid_sel.setContentsMargins(0, 0, 0, 0)

        self.btn_group_blade = QButtonGroup(self)
        self.btn_group_blade.setExclusive(True)
        self.radio_blades = []
        self.chk_blades = self.radio_blades

        res_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
        chk_icon_path = os.path.join(res_dir, "chk_black.png").replace("\\", "/")

        chk_style = f"""
            QRadioButton {{ spacing: 0px; }}
            QRadioButton::indicator {{
                width: 15px; height: 15px;
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
        col_left.addSpacing(3)

        self.lbl_blade_safe_title = QLabel("Blade safe")
        self.lbl_blade_safe_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        col_left.addWidget(self.lbl_blade_safe_title)

        grid_safe = QGridLayout()
        grid_safe.setHorizontalSpacing(6)
        grid_safe.setVerticalSpacing(3)
        grid_safe.setContentsMargins(0, 0, 0, 0)
        self.safe_leds = []

        for col, b_name in enumerate(["A", "B", "C"]):
            lbl_b = QLabel(b_name)
            lbl_b.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B;")
            led = StatusLed(color="grey", shape="circle", size=13)
            led.set_state(False)
            self.safe_leds.append(led)

            h = QHBoxLayout()
            h.setSpacing(3)
            h.addWidget(lbl_b)
            h.addWidget(led)
            grid_safe.addLayout(h, 0, col)

        col_left.addLayout(grid_safe)
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
        self.edit_fast_spd.setFixedSize(50, 20)
        self.edit_fast_spd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_fast_spd.textEdited.connect(self._on_fast_spd_edited)
        self.edit_fast_spd.editingFinished.connect(self._on_fast_spd_finished)

        lbl_unit1 = QLabel("°/s")
        lbl_unit1.setStyleSheet("font-size: 10px; color: #64748B;")
        grid_spd.addWidget(self.lbl_fast_spd_title, 1, 0)
        grid_spd.addWidget(self.edit_fast_spd, 1, 1)
        grid_spd.addWidget(lbl_unit1, 1, 2)

        self.lbl_slow_spd_title = QLabel("Slow speed")
        self.lbl_slow_spd_title.setStyleSheet("font-size: 10px; color: #475569;")
        self.lbl_slow_spd_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit_slow_spd = QLineEdit(f"{MANUAL_SLOW_SPEED_DEFAULT:.1f}")
        self.edit_slow_spd.setFixedSize(50, 20)
        self.edit_slow_spd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_slow_spd.textEdited.connect(self._on_slow_spd_edited)
        self.edit_slow_spd.editingFinished.connect(self._on_slow_spd_finished)

        lbl_unit2 = QLabel("°/s")
        lbl_unit2.setStyleSheet("font-size: 10px; color: #64748B;")
        grid_spd.addWidget(self.lbl_slow_spd_title, 2, 0)
        grid_spd.addWidget(self.edit_slow_spd, 2, 1)
        grid_spd.addWidget(lbl_unit2, 2, 2)

        col_right.addLayout(grid_spd)

        # Current Pos Row
        row_pos = QHBoxLayout()
        row_pos.setSpacing(4)
        row_pos.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_pos_mon_title = QLabel("Current Pos.")
        self.lbl_pos_mon_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #1E293B;")
        self.lbl_current_pos = QLabel("89.0")
        self.lbl_current_pos.setFixedSize(50, 20)
        self.lbl_current_pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_current_pos.setStyleSheet("""
            background-color: #F8FAFC; border: 1px solid #CBD5E1;
            border-radius: 3px; font-size: 10px; font-weight: bold; color: #0F172A;
        """)
        lbl_unit3 = QLabel("°")
        lbl_unit3.setStyleSheet("font-size: 10px; color: #64748B;")
        row_pos.addWidget(self.lbl_pos_mon_title)
        row_pos.addWidget(self.lbl_current_pos)
        row_pos.addWidget(lbl_unit3)
        col_right.addLayout(row_pos)

        top_row.addLayout(col_right)
        layout.addLayout(top_row)
        layout.addSpacing(4)

        # Separator line
        h_line = QFrame()
        h_line.setFrameShape(QFrame.Shape.HLine)
        h_line.setStyleSheet("color: #E2E8F0; background-color: #E2E8F0;")
        h_line.setFixedHeight(1)
        layout.addWidget(h_line)
        layout.addSpacing(4)

        # Action Decks (Pitch lock, Speed, Move blade)
        bot_row = QHBoxLayout()
        bot_row.setSpacing(8)

        # 1. Pitch Lock Control Deck
        c1 = QVBoxLayout()
        c1.setSpacing(3)
        self.lbl_pitch_lock_title = QLabel("Pitch Lock Control")
        self.lbl_pitch_lock_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        self.lbl_pitch_lock_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_pitch_lock = QPushButton("Engaged")
        self.btn_pitch_lock.setCheckable(True)
        self.btn_pitch_lock.setFixedHeight(66)
        self.btn_pitch_lock.setStyleSheet(self._style_industrial_toggle_btn(False))
        self.btn_pitch_lock.clicked.connect(self.toggle_pitch_lock)
        c1.addWidget(self.lbl_pitch_lock_title)
        c1.addWidget(self.btn_pitch_lock)
        bot_row.addLayout(c1, stretch=1)

        # 2. Fast/Slow Speed Deck
        c2 = QVBoxLayout()
        c2.setSpacing(3)
        self.lbl_speed_mode_title = QLabel("Fast/Slow Speed")
        self.lbl_speed_mode_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        self.lbl_speed_mode_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_speed_mode = QPushButton("Slow Speed\nSelected")
        self.btn_speed_mode.setCheckable(True)
        self.btn_speed_mode.setFixedHeight(66)
        self.btn_speed_mode.setStyleSheet(self._style_industrial_toggle_btn(False))
        self.btn_speed_mode.clicked.connect(self.toggle_speed_mode)
        c2.addWidget(self.lbl_speed_mode_title)
        c2.addWidget(self.btn_speed_mode)
        bot_row.addLayout(c2, stretch=1)

        # 3. Move Blade Jogging Deck
        c3 = QVBoxLayout()
        c3.setSpacing(3)
        self.lbl_move_blade_title = QLabel("Move Blade")
        self.lbl_move_blade_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        self.lbl_move_blade_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_move_feather = QPushButton("Feather")
        self.btn_move_feather.setFixedHeight(29)
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
        self.btn_move_fine.setFixedHeight(29)
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
        c3.addSpacing(3)
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
                    color: #0F172A;
                }
                QPushButton:disabled {
                    background: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #94A3B8;
                }
            """
        else:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0284C7, stop:0.15 #0369A1, stop:1 #075985);
                    border: 1.5px solid #0369A1;
                    border-top: 3px solid #0C4A6E;
                    border-left: 2px solid #0C4A6E;
                    border-bottom: 1px solid #38BDF8;
                    border-right: 1px solid #38BDF8;
                    border-radius: 4px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0369A1, stop:1 #0284C7);
                }
                QPushButton:disabled {
                    background: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #94A3B8;
                }
            """

    def retranslate_ui(self, lang="EN"):
        self.current_lang = lang

        # Retranslate 3 Blade Cards
        for card in self.blade_cards:
            card.retranslate_ui(lang)

        self.grp_lub.setTitle(tr("Blade Lubrication", lang))
        self.grp_blade_ctrl.setTitle(tr("HMI Blade Control", lang))
        self.grp_mode.retranslate_ui(lang)

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

    def update_ui_state(self):
        # 1. Update 3 Blade Telemetry Cards
        for i, b in enumerate(self.plc.blades):
            if i < len(self.blade_cards):
                self.blade_cards[i].update_from_blade_data(b, self.current_lang)

        # 2. Check manual permission & lockouts
        is_manual = (self.plc.blade_mode == MODE_MANUAL)

        if is_manual:
            self.badge_lub_auth.setText(tr("🔓 Manual Active", self.current_lang))
            self.badge_lub_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #059669;
                background-color: #D1FAE5; border: 1px solid #A7F3D0;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.badge_ctrl_auth.setText(tr("🔓 Manual Active", self.current_lang))
            self.badge_ctrl_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #059669;
                background-color: #D1FAE5; border: 1px solid #A7F3D0;
                border-radius: 3px; padding: 2px 8px;
            """)
        else:
            self.badge_lub_auth.setText(tr("🔒 Require Manual Mode", self.current_lang))
            self.badge_lub_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #64748B;
                background-color: #F1F5F9; border: 1px solid #E2E8F0;
                border-radius: 3px; padding: 2px 8px;
            """)
            self.badge_ctrl_auth.setText(tr("🔒 Require Manual Mode", self.current_lang))
            self.badge_ctrl_auth.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #64748B;
                background-color: #F1F5F9; border: 1px solid #E2E8F0;
                border-radius: 3px; padding: 2px 8px;
            """)

        # 3. Update Lubrication Deck
        self.btn_pump1.setEnabled(is_manual)
        self.btn_pump2.setEnabled(is_manual)
        self.led_pump1.set_state(self.plc.pump1_active, "green", "grey")
        self.led_pump2.set_state(self.plc.pump2_active, "green", "grey")
        self.btn_pump1.setText(tr("Stop Pump 1" if self.plc.pump1_active else "Activate Pump 1", self.current_lang))
        self.btn_pump2.setText(tr("Stop Pump 2" if self.plc.pump2_active else "Activate Pump 2", self.current_lang))

        # 4. Update Blade Control Deck
        self.btn_move_feather.setEnabled(is_manual)
        self.btn_move_fine.setEnabled(is_manual)
        self.btn_pitch_lock.setEnabled(is_manual)
        self.btn_speed_mode.setEnabled(is_manual)
        for rb in self.radio_blades:
            rb.setEnabled(is_manual)
        self.edit_fast_spd.setEnabled(is_manual)
        self.edit_slow_spd.setEnabled(is_manual)

        # 5. Mode Request Card State
        if self.plc.blade_mode == MODE_MANUAL:
            self.grp_mode.set_state(
                is_active=True,
                can_enter=True,
                prompt_text=tr("Manual mode active. Ready to exit manual mode.", self.current_lang),
                badge_text=tr("Manual Active", self.current_lang),
                badge_type="ready"
            )
        else:
            can_enter = (self.plc.blade_state == STATE_STOPPED)
            if can_enter:
                prompt = tr("Pitch System is ready to enter manual mode.", self.current_lang)
                badge_text = tr("Ready", self.current_lang)
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

        # 6. Current Selected Blade & Position Display
        cur_blade = self.plc.blades[self.plc.selected_blade_idx]
        if self.plc.is_opcua_online and self.plc.manual_current_pos is not None:
            self.lbl_current_pos.setText(f"{self.plc.manual_current_pos:.1f}")
        else:
            self.lbl_current_pos.setText(f"{cur_blade.angle_deg:.1f}")
        if 0 <= self.plc.selected_blade_idx < len(self.radio_blades):
            self.radio_blades[self.plc.selected_blade_idx].setChecked(True)

        # Update Pitch Lock Toggle Button
        is_disengaged = self.plc.manual_pitch_lock_disengaged
        is_lock_pressed = is_disengaged
        self.btn_pitch_lock.blockSignals(True)
        self.btn_pitch_lock.setChecked(is_lock_pressed)
        self.btn_pitch_lock.blockSignals(False)

        lock_text_en = "Released" if is_disengaged else "Engaged"
        self.btn_pitch_lock.setText(tr(lock_text_en, self.current_lang))
        self.btn_pitch_lock.setStyleSheet(self._style_industrial_toggle_btn(is_lock_pressed))

        # Update Fast/Slow Speed Toggle Button
        is_fast = (self.plc.manual_speed_mode == "FAST")
        is_speed_pressed = is_fast
        self.btn_speed_mode.blockSignals(True)
        self.btn_speed_mode.setChecked(is_speed_pressed)
        self.btn_speed_mode.blockSignals(False)

        spd_mode_en = "Fast Speed\nSelected" if is_fast else "Slow Speed\nSelected"
        self.btn_speed_mode.setText(tr(spd_mode_en, self.current_lang))
        self.btn_speed_mode.setStyleSheet(self._style_industrial_toggle_btn(is_speed_pressed))

        if not self._user_edited_fast_spd and not self.edit_fast_spd.hasFocus():
            self.edit_fast_spd.setText(f"{self.plc.manual_fast_speed:.1f}")
        if not self._user_edited_slow_spd and not self.edit_slow_spd.hasFocus():
            self.edit_slow_spd.setText(f"{self.plc.manual_slow_speed:.1f}")

        # Safety LEDs
        for i, b in enumerate(self.plc.blades):
            is_safe = self.plc.blade_safe[i] if i < len(self.plc.blade_safe) else False
            if i < len(self.safe_leds):
                self.safe_leds[i].set_state(is_safe, "green", "grey")

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
            return
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
        if getattr(self.plc, "manual_moving_dir", 0) != 0:
            self.plc.set_move_dir(0)
            if self.opcua_service and getattr(self.plc, "is_opcua_online", False):
                self.opcua_service.set_move_feather(False)
                self.opcua_service.set_move_fine(False)

    def hideEvent(self, event):
        self._safety_stop_motion()
        super().hideEvent(event)


class ManualPage(QWidget):
    """
    Manual Container hosting both Manual Control View and Calibrate Page as sub-pages.
    """
    tab_changed = pyqtSignal(int)

    def __init__(self, plc_state, opcua_service=None, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(4)

        # Tab Widget for Manual vs Calibrate
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

        # 1. Manual Operation Sub-page
        self.manual_view = ManualControlView(self.plc, opcua_service=self.opcua_service, parent=self)

        # 2. Calibrate Sub-page
        self.calibrate_view = CalibratePage(self.plc, opcua_service=self.opcua_service, parent=self)

        self.tabs.addTab(self.manual_view, "Manual")
        self.tabs.addTab(self.calibrate_view, "Calibrate")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs)

    def _on_tab_changed(self, idx):
        self.tab_changed.emit(idx)

    def retranslate_ui(self, lang="EN"):
        self.current_lang = lang
        self.tabs.setTabText(0, tr("Manual", lang))
        self.tabs.setTabText(1, tr("Calibrate", lang))
        self.manual_view.retranslate_ui(lang)
        self.calibrate_view.retranslate_ui(lang)

    def update_ui_state(self):
        self.manual_view.update_ui_state()
        self.calibrate_view.update_ui_state()

    def __getattr__(self, name):
        """Forward attribute lookups to manual_view or calibrate_view for compatibility"""
        if hasattr(self, "manual_view") and hasattr(self.manual_view, name):
            return getattr(self.manual_view, name)
        if hasattr(self, "calibrate_view") and hasattr(self.calibrate_view, name):
            return getattr(self.calibrate_view, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
