# -*- coding: utf-8 -*-
"""
Main Window Framework for Hydraulic Pitch HMI
Implements header bar, left status panel, right navigation buttons, and bottom status line
"""

import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QButtonGroup, QFrame, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon

from config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    HMI_VERSION, UI_REFRESH_TIMER_MS,
    STATE_ABORTED, STATE_ABORTING,
    OPCUA_ENDPOINT
)
from utils.widgets import HexagonButton, StatusLed
from utils.i18n import tr, I18N
from ui.inspect_page import InspectPage
from ui.alarm_page import AlarmPage
from ui.manual_page import ManualPage
from ui.maintenance_page import MaintenancePage
from ui.network_page import NetworkPage


class MainWindow(QMainWindow):
    def __init__(self, plc_state, alarm_manager, opcua_service=None, file_manager=None, **kwargs):
        super().__init__()
        self.plc = plc_state
        self.alarm_mgr = alarm_manager
        # Backward compatibility if 3rd positional argument was legacy file_manager
        if opcua_service is not None and not hasattr(opcua_service, "endpoint_url") and not hasattr(opcua_service, "start"):
            opcua_service = kwargs.get("opcua_service")
        self.opcua_service = opcua_service
        self.current_lang = "EN"

        # Performance & Render State Cache (dirty-checking to avoid redundant setStyleSheet & disk I/O at 10Hz)
        self._last_has_unacked = None
        self._last_active_alarm_count = None
        self._last_safety_status_key = None
        self._last_opcua_state_key = None
        self._last_status_lang = None

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.init_ui()

        # Connect model signals
        self.plc.state_changed.connect(self.update_sidebar_status)
        self.plc.msgbox_triggered.connect(self._on_plc_msgbox_triggered)
        self.alarm_mgr.alarms_changed.connect(self.update_alarm_badge)

        # Simulation & Clock Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        self.timer.start(UI_REFRESH_TIMER_MS)

        self.update_sidebar_status()
        self.update_alarm_badge()
        self.apply_language()

    def init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        # 3-Column Root Layout: [ Left Column | Center Column | Right Column ]
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Status Panel (Full Height top to bottom)
        left_panel = self._create_left_status_panel()
        root_layout.addWidget(left_panel, 0)

        # Left Vertical Separator
        v_sep1 = QFrame()
        v_sep1.setFrameShape(QFrame.Shape.VLine)
        v_sep1.setStyleSheet("color: #9CA3AF; background-color: #9CA3AF;")
        v_sep1.setFixedWidth(1)
        root_layout.addWidget(v_sep1)

        # 2. Center Column (Center Header + Top Red Line + Stacked Pages + Bottom Red Line + Bottom Status Bar)
        center_panel = self._create_center_panel()
        root_layout.addWidget(center_panel, 1)

        # Right Vertical Separator
        v_sep2 = QFrame()
        v_sep2.setFrameShape(QFrame.Shape.VLine)
        v_sep2.setStyleSheet("color: #9CA3AF; background-color: #9CA3AF;")
        v_sep2.setFixedWidth(1)
        root_layout.addWidget(v_sep2)

        # 3. Right Navigation Bar (Full Height top to bottom)
        right_nav = self._create_right_nav_bar()
        root_layout.addWidget(right_nav, 0)

    def _create_left_status_panel(self):
        panel = QWidget()
        panel.setFixedWidth(135)
        panel.setStyleSheet("""
            QWidget#left_panel {
                background-color: #CFD4DA;
            }
            QLabel {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
            }
        """)
        panel.setObjectName("left_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(0)

        # 1. Clock & Version block (Top of Left Column)
        self.lbl_clock = QLabel("--:--:--")
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_clock.setStyleSheet("font-size: 15px; font-weight: bold; color: #9CA3AF;")
        self.lbl_date = QLabel("--/--/----")
        self.lbl_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_date.setStyleSheet("font-size: 12px; color: #9CA3AF; margin-top: 2px;")
        self.lbl_ver = QLabel(f"SW: {self.plc.pac_version_sw}\nHW: {self.plc.pac_version_hw}")
        self.lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ver.setStyleSheet("font-size: 13px; font-weight: bold; color: #1F2937; margin-top: 4px;")
        layout.addWidget(self.lbl_clock)
        layout.addWidget(self.lbl_date)
        layout.addWidget(self.lbl_ver)

        layout.addStretch(1)

        # 2. State & Mode block
        self.lbl_s_title = QLabel("Blade State")
        self.lbl_s_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_s_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #111827;")
        self.lbl_blade_state = QLabel(self.plc.blade_state)
        self.lbl_blade_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_blade_state.setStyleSheet("font-size: 12px; color: #1F2937; margin-top: 2px;")

        self.lbl_m_title = QLabel("Blade Mode")
        self.lbl_m_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_m_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #111827; margin-top: 10px;")
        self.lbl_blade_mode = QLabel(self.plc.blade_mode)
        self.lbl_blade_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_blade_mode.setStyleSheet("font-size: 12px; color: #1F2937; margin-top: 2px;")

        layout.addWidget(self.lbl_s_title)
        layout.addWidget(self.lbl_blade_state)
        layout.addWidget(self.lbl_m_title)
        layout.addWidget(self.lbl_blade_mode)

        layout.addStretch(1)

        # 3. Control Action Group (START / STOP Hexagon)
        self.btn_hex = HexagonButton(mode="START")
        self.btn_hex.clicked.connect(self.on_hexagon_clicked)
        layout.addWidget(self.btn_hex, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

        # 4. Control Authority & Safety Group
        self.lbl_c_title = QLabel("Manual Control")
        self.lbl_c_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_c_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #111827;")
        self.lbl_ctrl_source = QLabel(self.plc.manual_control_source)
        self.lbl_ctrl_source.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ctrl_source.setStyleSheet("font-size: 12px; color: #1F2937; margin-top: 2px;")

        self.lbl_safe_title = QLabel("Main Control")
        self.lbl_safe_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_safe_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #111827; margin-top: 10px;")
        self.lbl_safety_status = QLabel("--")
        self.lbl_safety_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_safety_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748B; margin-top: 2px;")

        layout.addWidget(self.lbl_c_title)
        layout.addWidget(self.lbl_ctrl_source)
        layout.addWidget(self.lbl_safe_title)
        layout.addWidget(self.lbl_safety_status)

        layout.addStretch(2)

        # 5. Language Flag & Label (Bottom of Left Column)
        self.lbl_lang_title = QLabel(tr("Language", self.current_lang))
        self.lbl_lang_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lang_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #111827; margin-bottom: 3px;")
        self.lbl_lang_title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_lang_title.mousePressEvent = lambda e: self.toggle_language()
        layout.addWidget(self.lbl_lang_title, 0, Qt.AlignmentFlag.AlignCenter)

        self.btn_lang = QPushButton()
        self.btn_lang.setFixedSize(48, 32)
        self.btn_lang.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lang.setStyleSheet("""
            QPushButton {
                border: 1px solid #9CA3AF;
                border-radius: 3px;
                background-color: transparent;
                padding: 1px;
            }
            QPushButton:hover {
                border: 1px solid #C8102E;
                background-color: #E2E8F0;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """)
        self.btn_lang.clicked.connect(self.toggle_language)
        self.update_flag_button()
        layout.addWidget(self.btn_lang, 0, Qt.AlignmentFlag.AlignCenter)

        return panel

    def _create_center_panel(self):
        panel = QWidget()
        panel.setObjectName("center_panel")
        panel.setStyleSheet("QWidget#center_panel { background-color: #ECEEF2; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Center Header Bar
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet("background-color: #FFFFFF;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(15, 6, 15, 6)

        # Left Title Box
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_page_title = QLabel("Overview")
        self.lbl_page_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #111111;")
        self.lbl_page_subtitle = QLabel("Pitch system data as pressure, temperature, etc. are shown in this page")
        self.lbl_page_subtitle.setStyleSheet("font-size: 11px; font-style: italic; color: #555555;")
        title_box.addWidget(self.lbl_page_title)
        title_box.addWidget(self.lbl_page_subtitle)
        hdr_layout.addLayout(title_box)

        hdr_layout.addStretch()

        # Right System Title / Logo
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "resources", "logo.png")
        lbl_logo = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                lbl_logo.setPixmap(pix.scaledToHeight(44, Qt.TransformationMode.SmoothTransformation))
            else:
                lbl_logo.setText("HYDRAULIC PITCH SYSTEM")
                lbl_logo.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E293B; letter-spacing: 1px;")
        else:
            lbl_logo.setText("HYDRAULIC PITCH SYSTEM")
            lbl_logo.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E293B; letter-spacing: 1px;")
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hdr_layout.addWidget(lbl_logo)
        layout.addWidget(hdr)

        # 2. Top Red Line (Only in Center Column!)
        red_line_top = QFrame()
        red_line_top.setFixedHeight(3)
        red_line_top.setStyleSheet("background-color: #C8102E;")
        layout.addWidget(red_line_top)

        # 3. Stacked Pages
        self.stacked_pages = QStackedWidget()
        self.page_inspect = InspectPage(self.plc)
        self.page_alarm = AlarmPage(self.alarm_mgr, self.plc, opcua_service=self.opcua_service)
        self.page_manual = ManualPage(self.plc, opcua_service=self.opcua_service)
        self.page_maint = MaintenancePage(self.plc, opcua_service=self.opcua_service)
        self.page_network = NetworkPage(self.plc, opcua_service=self.opcua_service)
        self.page_file = self.page_network  # backward compat

        self.stacked_pages.addWidget(self.page_inspect)
        self.stacked_pages.addWidget(self.page_alarm)
        self.stacked_pages.addWidget(self.page_manual)
        self.stacked_pages.addWidget(self.page_maint)
        self.stacked_pages.addWidget(self.page_network)
        layout.addWidget(self.stacked_pages, 1)

        # 4. Bottom Red Line (Only in Center Column!)
        red_line_bottom = QFrame()
        red_line_bottom.setFixedHeight(3)
        red_line_bottom.setStyleSheet("background-color: #C8102E;")
        layout.addWidget(red_line_bottom)

        # 5. Bottom Status Bar (Only in Center Column!)
        b_bar = QWidget()
        b_bar.setFixedHeight(30)
        b_bar.setStyleSheet("background-color: #ECEEF2;")
        b_layout = QHBoxLayout(b_bar)
        b_layout.setContentsMargins(15, 0, 15, 0)
        b_layout.setSpacing(8)

        self.lbl_bottom_status = QLabel(self.plc.bottom_status_msg)
        self.lbl_bottom_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #1F2937;")
        b_layout.addWidget(self.lbl_bottom_status)

        b_layout.addStretch()

        # OPC UA Status Indicator & Settings Button
        self.led_opcua = StatusLed(color="grey", shape="circle", size=10)
        b_layout.addWidget(self.led_opcua)

        self.lbl_opcua_status = QLabel("127.0.0.1: 离线")
        self.lbl_opcua_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_opcua_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_opcua_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")
        self.lbl_opcua_status.setToolTip("点击打开 OPC UA 连接设置 (Click to configure OPC UA)")
        self.lbl_opcua_status.mousePressEvent = lambda e: self.open_opcua_settings()
        b_layout.addWidget(self.lbl_opcua_status)

        self.btn_opcua_settings = QPushButton("⚙")
        self.btn_opcua_settings.setFixedSize(26, 22)
        self.btn_opcua_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_opcua_settings.setToolTip("OPC UA 连接设置 (OPC UA Settings)")
        self.btn_opcua_settings.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 13px;
                color: #334155;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #CBD5E1;
                border-color: #94A3B8;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #94A3B8;
            }
        """)
        self.btn_opcua_settings.clicked.connect(self.open_opcua_settings)
        b_layout.addWidget(self.btn_opcua_settings)

        layout.addWidget(b_bar)

        return panel

    def _create_right_nav_bar(self):
        panel = QWidget()
        panel.setFixedWidth(106)
        panel.setStyleSheet("background-color: #BAC1C9;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(6)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []

        res_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
        self._pix_alarm_red = QPixmap(os.path.join(res_dir, "nav_alarm.png")).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._pix_alarm_gray = QPixmap(os.path.join(res_dir, "nav_alarm_gray.png")).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        nav_items = [
            ("nav_inspect.png", "Overview", 0),
            ("nav_alarm.png", "Alarm", 1),
            ("nav_manual.png", "Manual", 2),
            ("nav_maintenance.png", "Maintenance", 3),
            ("nav_network.png", "Network", 4)
        ]

        for icon_file, text, page_idx in nav_items:
            icon_path = os.path.join(res_dir, icon_file)
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(72)
            btn.setProperty("class", "nav-btn")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ECEFF2;
                    border: 1px solid #94A3B8;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #DFE4E8;
                }
                QPushButton:checked {
                    background-color: #FFFFFF;
                    border: 2px solid #C8102E;
                }
            """)

            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(4, 6, 4, 6)
            btn_layout.setSpacing(3)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Icon Container (allows badge overlay on top-right of icon)
            icon_container = QWidget()
            icon_container.setFixedSize(54, 36)
            icon_container.setStyleSheet("background: transparent;")
            icon_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            lbl_icon = QLabel(icon_container)
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon.setGeometry(10, 2, 34, 34)
            lbl_icon.setStyleSheet("background: transparent;")
            lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path)
                lbl_icon.setPixmap(pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

            # Alarm count bubble badge (for page_idx == 1, Alarm)
            if page_idx == 1:
                badge_lbl = QLabel(icon_container)
                badge_lbl.setObjectName("alarm_badge")
                badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge_lbl.setStyleSheet("""
                    QLabel#alarm_badge {
                        background-color: #DC2626;
                        color: #FFFFFF;
                        border-radius: 9px;
                        border: 1.5px solid #FFFFFF;
                        font-family: 'Segoe UI', 'Microsoft YaHei', Arial;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 0px 3px;
                    }
                """)
                badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                badge_lbl.hide()
                self.alarm_badge = badge_lbl
                self.alarm_icon_container = icon_container

            btn_layout.addWidget(icon_container, 0, Qt.AlignmentFlag.AlignCenter)

            lbl_text = QLabel(text)
            lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_text.setStyleSheet("background: transparent; font-family: 'Segoe UI', 'Microsoft YaHei', Arial; font-size: 11px; font-weight: bold; color: #1F2937;")
            lbl_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            btn_layout.addWidget(lbl_text, 0, Qt.AlignmentFlag.AlignCenter)

            btn.lbl_icon = lbl_icon
            btn.lbl_text = lbl_text
            btn.raw_text = text
            btn.page_idx = page_idx

            self.nav_group.addButton(btn, page_idx)
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.PAGE_INFO = [
            ("Overview", "Pitch system data as pressure, temperature, etc. are shown in this page"),
            ("Alarm", "Active alarms and historical alarm logs"),
            ("Manual", "Manual pitching and valve test operations"),
            ("Maintenance", "Sensor calibration and diagnostic tools"),
            ("Network", "Ethernet configuration and PLC IP parameters"),
        ]

        self.nav_buttons[0].setChecked(True)
        self.nav_group.idClicked.connect(self.on_nav_clicked)

        layout.addStretch(1)  # Proper grouping at the top

        # Bottom-right HMI Version label
        self.lbl_hmi_version = QLabel(f"HMI: {HMI_VERSION}")
        self.lbl_hmi_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hmi_version.setFixedHeight(28)
        self.lbl_hmi_version.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 11px;
                font-weight: bold;
                color: #475569;
                background: transparent;
            }
        """)
        self.lbl_hmi_version.setToolTip(f"HMI Version: {HMI_VERSION}")
        layout.addWidget(self.lbl_hmi_version)

        return panel

    def on_nav_clicked(self, page_idx):
        self.stacked_pages.setCurrentIndex(page_idx)
        self.update_header_text()

    def update_header_text(self):
        page_idx = self.stacked_pages.currentIndex()
        if hasattr(self, "PAGE_INFO") and 0 <= page_idx < len(self.PAGE_INFO):
            title, sub = self.PAGE_INFO[page_idx]
            self.lbl_page_title.setText(tr(title, self.current_lang))
            self.lbl_page_subtitle.setText(tr(sub, self.current_lang))

    def update_flag_button(self):
        res_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
        # In EN mode: show Chinese flag to indicate clicking will switch to Chinese
        # In CN mode: show UK flag to indicate clicking will switch to English
        flag_file = "flag_cn.png" if self.current_lang == "EN" else "flag_en.png"
        flag_path = os.path.join(res_dir, flag_file)
        if os.path.exists(flag_path):
            pix = QPixmap(flag_path)
            self.btn_lang.setIcon(QIcon(pix))
            self.btn_lang.setIconSize(self.btn_lang.size() - QSize(6, 6))
        tooltip = "点击切换为中文 (Switch to Chinese)" if self.current_lang == "EN" else "Click to switch to English (切换为英文)"
        self.btn_lang.setToolTip(tooltip)

    def toggle_language(self):
        """Toggle between English ('EN') and Chinese ('CN')"""
        self.current_lang = "CN" if self.current_lang == "EN" else "EN"
        self.apply_language()

    def apply_language(self):
        """Apply language changes across all UI components"""
        I18N.set_language(self.current_lang)

        # 1. Update Flag Button icon & tooltip
        self.update_flag_button()

        # 2. Update Left Status Panel Titles
        if hasattr(self, "lbl_s_title"):
            self.lbl_s_title.setText(tr("Blade State", self.current_lang))
            self.lbl_m_title.setText(tr("Blade Mode", self.current_lang))
            self.lbl_c_title.setText(tr("Manual Control", self.current_lang))
            self.lbl_safe_title.setText(tr("Main Control", self.current_lang))
        if hasattr(self, "lbl_lang_title"):
            self.lbl_lang_title.setText(tr("Language", self.current_lang))
            self.lbl_lang_title.setToolTip(
                "点击切换为中文 (Switch to Chinese)" if self.current_lang == "EN" else "Click to switch to English (切换为英文)"
            )

        # 3. Update Left Status Panel Dynamic texts & bottom status bar
        self.update_sidebar_status()

        # 4. Update Right Navigation Bar labels
        for btn in self.nav_buttons:
            if hasattr(btn, "lbl_text") and hasattr(btn, "raw_text"):
                btn.lbl_text.setText(tr(btn.raw_text, self.current_lang))

        # 5. Update Center Header Bar title & subtitle
        self.update_header_text()

        # 6. Retranslate Child Pages
        if hasattr(self.page_inspect, "retranslate_ui"):
            self.page_inspect.retranslate_ui(self.current_lang)
        if hasattr(self.page_alarm, "retranslate_ui"):
            self.page_alarm.retranslate_ui(self.current_lang)
        if hasattr(self.page_manual, "retranslate_ui"):
            self.page_manual.retranslate_ui(self.current_lang)
        if hasattr(self.page_maint, "retranslate_ui"):
            self.page_maint.retranslate_ui(self.current_lang)
        if hasattr(self, "page_network") and hasattr(self.page_network, "retranslate_ui"):
            self.page_network.retranslate_ui(self.current_lang)
        elif hasattr(self.page_file, "retranslate_ui"):
            self.page_file.retranslate_ui(self.current_lang)

    def on_hexagon_clicked(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot send START/STOP command!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        if self.btn_hex.mode == "START":
            self.opcua_service.send_start(self.plc.blade_state)
        else:
            self.opcua_service.send_stop()

    def update_sidebar_status(self):
        self.update_clock()
        if hasattr(self, "lbl_ver"):
            self.lbl_ver.setText(f"SW: {self.plc.pac_version_sw}\nHW: {self.plc.pac_version_hw}")
        self.lbl_blade_state.setText(tr(self.plc.blade_state, self.current_lang))
        self.lbl_blade_mode.setText(tr(self.plc.blade_mode, self.current_lang))
        ctrl_src_text = tr(self.plc.manual_control_source, self.current_lang)
        self.lbl_ctrl_source.setText(ctrl_src_text)
        if self.plc.manual_control_source == "Remote Box":
            self.lbl_ctrl_source.setStyleSheet("font-size: 12px; font-weight: bold; color: #0284C7; margin-top: 2px;")
        else:
            self.lbl_ctrl_source.setStyleSheet("font-size: 12px; color: #1F2937; margin-top: 2px;")

        # Update Start/Stop button (Strictly adhering to PLC Main.st rules)
        # In PLC:
        # 1. STOP (abortButton) appears (status=0) whenever pac.state <> STATE_ABORTED and pac.state <> STATE_ABORTING
        # 2. START (startButton) appears (status=0) ONLY when pac.state = STATE_ABORTED
        if self.plc.is_opcua_online and getattr(self.plc, "plc_abort_btn_status", None) is not None:
            if self.plc.plc_abort_btn_status == 0:
                self.btn_hex.set_mode("STOP")
                self.btn_hex.setEnabled(True)
            elif self.plc.plc_start_btn_status == 0:
                self.btn_hex.set_mode("START")
                self.btn_hex.setEnabled(True)
            else:
                # In transition / Aborting
                self.btn_hex.setEnabled(False)
        else:
            self.btn_hex.setEnabled(False)

        # Update Safety status (with dirty check to avoid redundant setStyleSheet)
        safety_status_key = (self.plc.is_opcua_online, self.plc.safety_ok, self.current_lang)
        if safety_status_key != getattr(self, "_last_safety_status_key", None):
            self._last_safety_status_key = safety_status_key
            if not self.plc.is_opcua_online:
                self.lbl_safety_status.setText("--")
                self.lbl_safety_status.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 12px; font-weight: bold; color: #64748B; margin-top: 2px;")
            elif self.plc.safety_ok:
                self.lbl_safety_status.setText(tr("Safety Ok", self.current_lang))
                self.lbl_safety_status.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 12px; color: #111827; margin-top: 2px;")
            else:
                self.lbl_safety_status.setText(tr("Emergency", self.current_lang))
                self.lbl_safety_status.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 12px; font-weight: bold; color: #DC2626; margin-top: 2px;")

        # Update bottom line
        status_text = tr(self.plc.bottom_status_msg, self.current_lang)
        if self.lbl_bottom_status.text() != status_text:
            self.lbl_bottom_status.setText(status_text)
            self.lbl_bottom_status.setToolTip(status_text)

        # Update bottom OPC UA status (with dirty check)
        if hasattr(self, "lbl_opcua_status") and hasattr(self, "led_opcua"):
            ep = self.opcua_service.endpoint_url if self.opcua_service else OPCUA_ENDPOINT

            from urllib.parse import urlparse
            try:
                parsed = urlparse(ep)
                ip_str = parsed.hostname or "127.0.0.1"
            except Exception:
                ip_str = "127.0.0.1"

            opcua_key = (self.plc.is_opcua_online, ep, self.current_lang)
            if opcua_key != getattr(self, "_last_opcua_state_key", None):
                self._last_opcua_state_key = opcua_key
                if self.plc.is_opcua_online:
                    self.led_opcua.set_color("green")
                    self.lbl_opcua_status.setText(f"{ip_str}: {tr('Online', self.current_lang)}")
                    self.lbl_opcua_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D;")
                    tip_online = tr("OPC UA Server: {ep} [ONLINE]\nClick to configure", self.current_lang).format(ep=ep)
                    self.lbl_opcua_status.setToolTip(tip_online)
                else:
                    self.led_opcua.set_color("grey")
                    self.lbl_opcua_status.setText(f"{ip_str}: {tr('Offline', self.current_lang)}")
                    self.lbl_opcua_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B;")
                    tip_offline = tr("OPC UA Server: {ep} [Disconnected]\nClick to configure", self.current_lang).format(ep=ep)
                    self.lbl_opcua_status.setToolTip(tip_offline)

        # Auto-dismiss active alert dialog if PLC cleared msgbox_status (e.g. RemoteBox reconnected)
        if getattr(self, "_active_msgbox_dlg", None) is not None:
            if getattr(self.plc, "msgbox_status", 1) != 0:
                self._active_msgbox_dlg.close()
                self._active_msgbox_dlg = None

        self._last_status_lang = self.current_lang

    def open_opcua_settings(self):
        """Open the interactive OPC UA settings dialog"""
        from ui.opcua_settings_dialog import OpcUaSettingsDialog
        dlg = OpcUaSettingsDialog(self.opcua_service, self.plc, self)
        dlg.exec()

    def _on_plc_msgbox_triggered(self, msg_info):
        """Displays popup when PLC triggers hmi.msgBox.status == 0"""
        header = msg_info.get("header")
        if not header:
            header = tr("Remote Box Disconnected Warning", self.current_lang)

        content = msg_info.get("content")
        if not content:
            content = tr(
                "Remote box is not connected and blades are not safe. Please reconnect the remote box or abort the system.",
                self.current_lang
            )

        btn_ok = msg_info.get("btn_ok_status", 1) == 0
        btn_abort = True  # Always allow abort for site safety
        abort_text = tr("Abort System", self.current_lang)

        from utils.widgets import WarningModal
        self._active_msgbox_dlg = WarningModal(
            header, content, self,
            opcua_service=self.opcua_service,
            show_ok=btn_ok,
            show_abort=btn_abort,
            abort_text=abort_text
        )
        self._active_msgbox_dlg.exec()
        self._active_msgbox_dlg = None

    def closeEvent(self, event):
        if self.opcua_service:
            self.opcua_service.stop()
        event.accept()

    def update_alarm_badge(self):
        active_alarms = [a for a in self.alarm_mgr.active_alarms if a.is_active]
        active_count = len(active_alarms)
        has_unacked = any(not a.is_acked for a in active_alarms)
        alarm_btn = self.nav_buttons[1]

        # 1. Dirty check: Only update icon and text color if unacknowledged alarm state changed
        if has_unacked != self._last_has_unacked:
            self._last_has_unacked = has_unacked
            if hasattr(alarm_btn, 'lbl_icon') and hasattr(alarm_btn, 'lbl_text'):
                if has_unacked:
                    alarm_btn.lbl_text.setStyleSheet("background: transparent; font-family: 'Segoe UI', Arial; font-size: 11px; font-weight: bold; color: #DC2626;")
                    if hasattr(self, '_pix_alarm_red') and not self._pix_alarm_red.isNull():
                        alarm_btn.lbl_icon.setPixmap(self._pix_alarm_red)
                else:
                    alarm_btn.lbl_text.setStyleSheet("background: transparent; font-family: 'Segoe UI', Arial; font-size: 11px; font-weight: bold; color: #1F2937;")
                    if hasattr(self, '_pix_alarm_gray') and not self._pix_alarm_gray.isNull():
                        alarm_btn.lbl_icon.setPixmap(self._pix_alarm_gray)

        # 2. Dirty check: Dynamic alarm count bubble badge (only re-geometry if count changed)
        if active_count != self._last_active_alarm_count:
            self._last_active_alarm_count = active_count
            if hasattr(self, 'alarm_badge') and self.alarm_badge is not None:
                if active_count > 0:
                    txt = str(active_count) if active_count <= 999 else "999+"
                    self.alarm_badge.setText(txt)

                    # Dynamically size badge (circle for 1 digit, pill for multi-digit)
                    fm = self.alarm_badge.fontMetrics()
                    text_w = fm.horizontalAdvance(txt)
                    w = max(18, text_w + 8)
                    h = 18

                    # Align badge on the top-right corner of the 34x34 icon
                    container_w = self.alarm_icon_container.width() if hasattr(self, 'alarm_icon_container') else 54
                    x = min(container_w - w, max(10, 44 - w + 8))
                    self.alarm_badge.setGeometry(x, 0, w, h)
                    self.alarm_badge.show()
                    self.alarm_badge.raise_()
                else:
                    self.alarm_badge.hide()

    def update_clock(self):
        """Update clock and date display using PLC lower machine time if online, else placeholder."""
        if self.plc.is_opcua_online and getattr(self.plc, "plc_time", None) is not None:
            plc_dt = self.plc.plc_time
            time_str = plc_dt.strftime("%H:%M:%S")
            date_str = plc_dt.strftime("%m/%d/%Y")
            if self.lbl_clock.text() != time_str:
                self.lbl_clock.setText(time_str)
                self.lbl_clock.setStyleSheet("font-size: 15px; font-weight: bold; color: #111827;")
            if self.lbl_date.text() != date_str:
                self.lbl_date.setText(date_str)
                self.lbl_date.setStyleSheet("font-size: 12px; color: #374151; margin-top: 2px;")
        else:
            if self.lbl_clock.text() != "--:--:--":
                self.lbl_clock.setText("--:--:--")
                self.lbl_clock.setStyleSheet("font-size: 15px; font-weight: bold; color: #9CA3AF;")
            if self.lbl_date.text() != "--/--/----":
                self.lbl_date.setText("--/--/----")
                self.lbl_date.setStyleSheet("font-size: 12px; color: #9CA3AF; margin-top: 2px;")

    def on_timer_tick(self):
        self.update_clock()

