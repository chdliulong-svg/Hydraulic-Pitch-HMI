# -*- coding: utf-8 -*-
"""
Alarm Page
Matching Figures 9, 10, 11 of DFB1001650_DFB011019
Includes Active Alarms, Alarm History, Details Box, Acknowledge, and Reset Safety
Aligned with PLC MpAlarmXStateEnum and FB_HistoryAlarm.st
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QGroupBox, QLabel, QPushButton, QHeaderView, QAbstractItemView,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPixmap
from utils.widgets import ValueDisplay
from utils.i18n import tr


class AlarmPage(QWidget):
    def __init__(self, alarm_manager, plc_state, parent=None, opcua_service=None):
        super().__init__(parent)
        self.mgr = alarm_manager
        self.plc = plc_state
        self.opcua_service = opcua_service
        self.current_lang = "EN"
        self.res_dir = Path(__file__).resolve().parent.parent / "resources"
        self.init_ui()
        self.mgr.alarms_changed.connect(self.refresh_tables)
        self.refresh_tables()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(8)

        # Tab Widget for Alarm / History with explicit font to prevent Windows CJK bitmap clipping
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
        """)

        self.tab_active = QWidget()
        self.tab_history = QWidget()

        self._setup_active_tab()
        self._setup_history_tab()

        self.tabs.addTab(self.tab_active, "Alarm")
        self.tabs.addTab(self.tab_history, "History")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs, 3)

        # Details Box & Action Buttons Row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(15)

        # Alarm Details Box
        grp_details = QGroupBox()
        grp_details.setObjectName("details_box")
        grp_details.setStyleSheet("""
            QGroupBox#details_box {
                background-color: #FFFFFF;
                border: 1px solid #B0B5B9;
                border-radius: 4px;
            }
        """)
        det_layout = QVBoxLayout(grp_details)
        det_layout.setContentsMargins(15, 10, 15, 10)
        det_layout.setSpacing(4)

        self.det_code = ValueDisplay("Alarm Code", label_width=110, stretch_val=True, align=Qt.AlignmentFlag.AlignLeft)
        self.det_name = ValueDisplay("Alarm Name", label_width=110, stretch_val=True, align=Qt.AlignmentFlag.AlignLeft)
        self.det_state_active = ValueDisplay("State active", label_width=110, stretch_val=True, align=Qt.AlignmentFlag.AlignLeft)
        self.det_state_ack = ValueDisplay("State Ack.", label_width=110, stretch_val=True, align=Qt.AlignmentFlag.AlignLeft)
        self.det_message = ValueDisplay("Message", label_width=110, stretch_val=True, align=Qt.AlignmentFlag.AlignLeft)

        det_layout.addWidget(self.det_code)
        det_layout.addWidget(self.det_name)
        det_layout.addWidget(self.det_state_active)
        det_layout.addWidget(self.det_state_ack)
        det_layout.addWidget(self.det_message)
        bottom_row.addWidget(grp_details, 3)

        # Action Buttons Layout
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        ack_btn_style = """
            QPushButton {
                background-color: #374151;
                border: 1px solid #1F2937;
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
            QPushButton:pressed {
                background-color: #1F2937;
            }
        """

        self.btn_ack_sel = QPushButton("Acknowledge\nselected ✔")
        self.btn_ack_sel.setFixedHeight(45)
        self.btn_ack_sel.setStyleSheet(ack_btn_style)
        self.btn_ack_sel.clicked.connect(self.ack_selected)

        self.btn_ack_all = QPushButton("Acknowledge\nAll ✔✔")
        self.btn_ack_all.setFixedHeight(45)
        self.btn_ack_all.setStyleSheet(ack_btn_style)
        self.btn_ack_all.clicked.connect(self._on_ack_all_clicked)

        self.btn_reset_safety = QPushButton("Reset Safety ⚠")
        self.btn_reset_safety.setFixedHeight(50)
        self.btn_reset_safety.setStyleSheet("""
            background-color: #1D4ED8; color: #FEF08A; font-weight: bold;
            font-size: 13px; border-radius: 4px;
        """)
        self.btn_reset_safety.clicked.connect(self._on_reset_safety_clicked)

        btn_layout.addWidget(self.btn_ack_sel)
        btn_layout.addWidget(self.btn_ack_all)
        btn_layout.addWidget(self.btn_reset_safety)
        btn_layout.addStretch()
        bottom_row.addLayout(btn_layout, 1)

        main_layout.addLayout(bottom_row, 2)

    def _setup_active_tab(self):
        layout = QHBoxLayout(self.tab_active)
        layout.setContentsMargins(5, 5, 5, 5)

        self.tbl_active = QTableWidget()
        self.tbl_active.setColumnCount(5)
        self.tbl_active.setHorizontalHeaderLabels(["State active", "Alarm Code", "Message", "Code", "State"])
        self.tbl_active.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_active.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_active.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_active.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_active.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl_active.setColumnWidth(4, 85)
        self.tbl_active.verticalHeader().setDefaultSectionSize(32)
        self.tbl_active.verticalHeader().setVisible(False)
        self.tbl_active.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_active.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #B0B5B9;
                gridline-color: #E0E0E0;
                font-size: 11px;
                selection-background-color: #DC2626;
                selection-color: #FFFFFF;
            }
            QTableWidget::item:selected {
                background-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.tbl_active.itemSelectionChanged.connect(self.on_active_row_selected)
        layout.addWidget(self.tbl_active)

    def _setup_history_tab(self):
        layout = QHBoxLayout(self.tab_history)
        layout.setContentsMargins(5, 5, 5, 5)

        self.tbl_history = QTableWidget()
        self.tbl_history.setColumnCount(5)
        self.tbl_history.setHorizontalHeaderLabels(["State active", "Alarm Code", "Message", "Code", "State"])
        self.tbl_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_history.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_history.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_history.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_history.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl_history.setColumnWidth(4, 85)
        self.tbl_history.verticalHeader().setDefaultSectionSize(32)
        self.tbl_history.verticalHeader().setVisible(False)
        self.tbl_history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_history.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #B0B5B9;
                gridline-color: #E0E0E0;
                font-size: 11px;
                selection-background-color: #DC2626;
                selection-color: #FFFFFF;
            }
            QTableWidget::item:selected {
                background-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.tbl_history.itemSelectionChanged.connect(self.on_history_row_selected)
        layout.addWidget(self.tbl_history)

    def _create_active_state_widget(self, is_acked):
        """Creates cell widget for Active Alarms State column with high-def icons"""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_acked:
            # Blue checkmark badge (Acknowledged)
            lbl_ack = QLabel()
            pix_ack = QPixmap(str(self.res_dir / "icon_alarm_ack.png")).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_ack.setPixmap(pix_ack)
            layout.addWidget(lbl_ack)
        else:
            # Spacer for consistent alignment
            spacer = QLabel()
            spacer.setFixedSize(18, 18)
            layout.addWidget(spacer)

        # Yellow alert triangle (Active)
        lbl_active = QLabel()
        pix_active = QPixmap(str(self.res_dir / "icon_alarm_active.png")).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        lbl_active.setPixmap(pix_active)
        layout.addWidget(lbl_active)

        return container

    def _create_history_trans_widget(self, event_type):
        """Creates cell widget for History transition icons: Active [△ > ⚠], Reset [⚠ > ↻], Ack [✔ > ✔]"""
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel()
        if event_type == "ACTIVE":
            pix = QPixmap(str(self.res_dir / "icon_trans_active.png")).scaledToHeight(20, Qt.TransformationMode.SmoothTransformation)
        elif event_type == "RESET":
            pix = QPixmap(str(self.res_dir / "icon_trans_reset.png")).scaledToHeight(20, Qt.TransformationMode.SmoothTransformation)
        elif event_type == "ACK":
            pix = QPixmap(str(self.res_dir / "icon_trans_ack.png")).scaledToHeight(20, Qt.TransformationMode.SmoothTransformation)
        else:
            pix = QPixmap(str(self.res_dir / "icon_trans_active.png")).scaledToHeight(20, Qt.TransformationMode.SmoothTransformation)

        lbl.setPixmap(pix)
        layout.addWidget(lbl)
        return container

    def refresh_tables(self):
        # Refresh Active Table
        self.tbl_active.setRowCount(len(self.mgr.active_alarms))
        for r, a in enumerate(self.mgr.active_alarms):
            self.tbl_active.setItem(r, 0, QTableWidgetItem(a.timestamp))
            self.tbl_active.setItem(r, 1, QTableWidgetItem(a.name))
            self.tbl_active.setItem(r, 2, QTableWidgetItem(a.get_message(self.current_lang)))
            self.tbl_active.setItem(r, 3, QTableWidgetItem(str(a.code)))

            dummy = QTableWidgetItem()
            self.tbl_active.setItem(r, 4, dummy)
            self.tbl_active.setCellWidget(r, 4, self._create_active_state_widget(a.is_acked))

        # Refresh History Table
        self.tbl_history.setRowCount(len(self.mgr.history_alarms))
        for r, a in enumerate(self.mgr.history_alarms):
            self.tbl_history.setItem(r, 0, QTableWidgetItem(a.timestamp))
            self.tbl_history.setItem(r, 1, QTableWidgetItem(a.name))
            self.tbl_history.setItem(r, 2, QTableWidgetItem(a.get_message(self.current_lang)))
            self.tbl_history.setItem(r, 3, QTableWidgetItem(str(a.code)))

            dummy = QTableWidgetItem()
            self.tbl_history.setItem(r, 4, dummy)
            self.tbl_history.setCellWidget(r, 4, self._create_history_trans_widget(a.event_type))

        # Maintain current selection or default to first row
        if self.mgr.active_alarms:
            cur_row = self.tbl_active.currentRow()
            target_row = cur_row if (0 <= cur_row < len(self.mgr.active_alarms)) else 0
            self.tbl_active.selectRow(target_row)
            self.show_alarm_details(self.mgr.active_alarms[target_row])
        else:
            self.clear_alarm_details()

    def on_active_row_selected(self):
        row = self.tbl_active.currentRow()
        if 0 <= row < len(self.mgr.active_alarms):
            self.show_alarm_details(self.mgr.active_alarms[row])

    def on_history_row_selected(self):
        row = self.tbl_history.currentRow()
        if 0 <= row < len(self.mgr.history_alarms):
            self.show_alarm_details(self.mgr.history_alarms[row])

    def on_tab_changed(self, idx):
        if idx == 0 and self.mgr.active_alarms:
            row = self.tbl_active.currentRow()
            target_idx = row if (0 <= row < len(self.mgr.active_alarms)) else 0
            self.show_alarm_details(self.mgr.active_alarms[target_idx])
        elif idx == 1 and self.mgr.history_alarms:
            row = self.tbl_history.currentRow()
            target_idx = row if (0 <= row < len(self.mgr.history_alarms)) else 0
            self.show_alarm_details(self.mgr.history_alarms[target_idx])

    def retranslate_ui(self, lang="EN"):
        from utils.i18n import tr
        self.current_lang = lang
        self.tabs.setTabText(0, tr("Alarm", lang))
        self.tabs.setTabText(1, tr("History", lang))

        headers_active = [
            tr("State active", lang),
            tr("Alarm Code", lang),
            tr("Message", lang),
            tr("Code", lang),
            tr("State", lang)
        ]
        headers_history = [
            tr("Active or Reset Time", lang),
            tr("Alarm Code", lang),
            tr("Message", lang),
            tr("Code", lang),
            tr("State", lang)
        ]
        self.tbl_active.setHorizontalHeaderLabels(headers_active)
        self.tbl_history.setHorizontalHeaderLabels(headers_history)

        self.det_code.retranslate_ui(lang)
        self.det_name.retranslate_ui(lang)
        self.det_state_active.retranslate_ui(lang)
        self.det_state_ack.retranslate_ui(lang)
        self.det_message.retranslate_ui(lang)

        self.btn_ack_sel.setText(tr("Acknowledge\nselected ✔", lang))
        self.btn_ack_all.setText(tr("Acknowledge\nAll ✔✔", lang))
        self.btn_reset_safety.setText(tr("Reset Safety ⚠", lang))
        self.refresh_tables()

    def show_alarm_details(self, a):
        from utils.i18n import tr
        self.det_code.set_value(str(a.code))
        self.det_name.set_value(a.name)
        active_str = tr("Active (The problem has not been solved)", self.current_lang) if a.is_active else tr("Inactive", self.current_lang)
        self.det_state_active.set_value(active_str)
        ack_str = tr("Acknowledged", self.current_lang) if a.is_acked else tr("Unacknowledged", self.current_lang)
        self.det_state_ack.set_value(ack_str)
        self.det_message.set_value(a.get_message(self.current_lang))

    def clear_alarm_details(self):
        self.det_code.set_value("-")
        self.det_name.set_value("-")
        self.det_state_active.set_value("-")
        self.det_state_ack.set_value("-")
        self.det_message.set_value("-")

    def ack_selected(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot acknowledge alarms!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        row = self.tbl_active.currentRow()
        if 0 <= row < len(self.mgr.active_alarms):
            self.opcua_service.send_ack_all()
            self.opcua_service.force_poll_alarms()

    def _on_ack_all_clicked(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot acknowledge alarms!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        self.opcua_service.send_ack_all()
        self.opcua_service.force_poll_alarms()

    def _on_reset_safety_clicked(self):
        if not (self.opcua_service and getattr(self.plc, "is_opcua_online", False)):
            title = tr("Communication Offline", self.current_lang)
            msg = tr("⚠️ PLC communication is offline. Cannot reset safety!\n\nPlease check OPC UA connection.", self.current_lang)
            QMessageBox.warning(self, title, msg)
            return

        self.opcua_service.send_reset_safety()
        self.opcua_service.force_poll_alarms()

    def reset_safety_clicked(self):
        self._on_reset_safety_clicked()
