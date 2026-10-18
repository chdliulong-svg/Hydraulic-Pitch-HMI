# -*- coding: utf-8 -*-
"""
Compact & Modern OPC UA Settings Dialog for SEC PAC 6MW Hydraulic Pitch HMI
Eliminates redundant frames, duplicate text labels, and bulky nesting.
"""

import re
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from utils.widgets import StatusLed
from utils.i18n import tr
from config import OPCUA_HOST, OPCUA_PORT, OPCUA_POLL_INTERVAL, OPCUA_TEST_TIMEOUT

try:
    from asyncua import Client
except ImportError:
    Client = None


class ConnectionTesterThread(QThread):
    """Background thread to test connection without freezing UI"""
    test_finished = pyqtSignal(bool, str, float)  # (success, message, latency_ms)

    def __init__(self, endpoint_url: str, timeout: float = OPCUA_TEST_TIMEOUT):
        super().__init__()
        self.endpoint_url = endpoint_url
        self.timeout = timeout

    def run(self):
        import asyncio
        if Client is None:
            self.test_finished.emit(False, "asyncua library not installed", 0.0)
            return

        async def _test():
            t0 = time.time()
            try:
                async with Client(url=self.endpoint_url, timeout=self.timeout) as client:
                    ns = await client.get_namespace_array()
                    latency = (time.time() - t0) * 1000.0
                    return True, f"OK ({latency:.1f}ms, {len(ns)} ns)", latency
            except Exception as e:
                latency = (time.time() - t0) * 1000.0
                return False, str(e), latency

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, msg, latency = loop.run_until_complete(_test())
            self.test_finished.emit(success, msg, latency)
        finally:
            loop.close()


class OpcUaSettingsDialog(QDialog):
    """Compact OPC UA Settings & Diagnostics Window"""
    def __init__(self, opcua_service, plc_state, parent=None):
        super().__init__(parent)
        self.service = opcua_service
        self.plc = plc_state
        self.tester_thread = None
        self._port = OPCUA_PORT
        self._poll_interval = OPCUA_POLL_INTERVAL
        self._is_reconnecting = False

        self.current_lang = getattr(parent, "current_lang", "EN") if parent else "EN"

        self.setWindowTitle(tr("OPC UA Connection Settings", self.current_lang))
        self.resize(440, 210)
        self.setMinimumSize(420, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
            }
            QLabel {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 12px;
                color: #1E293B;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563EB;
            }
            QPushButton {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
            }
        """)

        self.init_ui()
        self.load_current_values()

        # Update diagnostics periodically (every 500ms)
        self.diag_timer = QTimer(self)
        self.diag_timer.timeout.connect(self.update_diagnostics)
        self.diag_timer.start(500)
        self.update_diagnostics()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 14)
        main_layout.setSpacing(10)

        # 1. Top Status & Telemetry Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self.led_status = StatusLed(color="grey", shape="circle", size=12)
        hdr.addWidget(self.led_status)

        self.lbl_diag_status = QLabel(tr("Offline / Disconnected", self.current_lang))
        self.lbl_diag_status.setStyleSheet("font-weight: bold; font-size: 12px; color: #64748B;")
        hdr.addWidget(self.lbl_diag_status)
        hdr.addStretch()

        self.lbl_stat_frames = QLabel(tr("Frames: {frames:,}", self.current_lang).format(frames=0))
        self.lbl_stat_frames.setStyleSheet("font-size: 11px; color: #94A3B8;")
        hdr.addWidget(self.lbl_stat_frames)
        main_layout.addLayout(hdr)

        # Subtle Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E2E8F0;")
        main_layout.addWidget(sep)

        # 2. Server IP & Test Connection Row
        ip_row = QHBoxLayout()
        ip_row.setSpacing(8)

        lbl_ip = QLabel(tr("Server IP / Host:", self.current_lang))
        lbl_ip.setStyleSheet("font-weight: 500;")
        ip_row.addWidget(lbl_ip)

        self.txt_ip = QLineEdit("127.0.0.1")
        self.txt_ip.setPlaceholderText("127.0.0.1")
        self.txt_ip.editingFinished.connect(self._on_ip_edit_finished)
        ip_row.addWidget(self.txt_ip, 1)

        self.btn_test = QPushButton(tr("🔍 Test", self.current_lang))
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background-color: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE;
            }
            QPushButton:hover {
                background-color: #DBEAFE;
            }
        """)
        self.btn_test.clicked.connect(self.on_test_clicked)
        ip_row.addWidget(self.btn_test)
        main_layout.addLayout(ip_row)

        # 3. Test Result / Status Message
        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setStyleSheet("font-size: 11px; color: #64748B;")
        main_layout.addWidget(self.lbl_test_result)

        main_layout.addStretch()

        # 4. Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_disconnect = QPushButton(tr("Disconnect", self.current_lang))
        self.btn_disconnect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_disconnect.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
            }
            QPushButton:disabled {
                background-color: #F1F5F9; color: #CBD5E1; border: 1px solid #E2E8F0;
            }
        """)
        self.btn_disconnect.clicked.connect(self.on_disconnect_clicked)
        btn_box.addWidget(self.btn_disconnect)

        btn_box.addStretch()

        self.btn_apply = QPushButton(tr("Apply && Reconnect", self.current_lang))
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #16A34A; color: #FFFFFF; border: none;
            }
            QPushButton:hover {
                background-color: #15803D;
            }
        """)
        self.btn_apply.clicked.connect(self.on_apply_clicked)
        btn_box.addWidget(self.btn_apply)

        self.btn_close = QPushButton(tr("Close", self.current_lang))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0; color: #334155; border: 1px solid #CBD5E1;
            }
            QPushButton:hover {
                background-color: #CBD5E1;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        btn_box.addWidget(self.btn_close)

        main_layout.addLayout(btn_box)

    def get_endpoint_url(self):
        ip = self.txt_ip.text().strip() or OPCUA_HOST
        return f"opc.tcp://{ip}:{self._port}"

    def _on_ip_edit_finished(self):
        if not self.txt_ip.text().strip():
            self.txt_ip.setText(OPCUA_HOST)

    def load_current_values(self):
        if not self.service:
            return
        curr_url = self.service.endpoint_url
        match = re.search(r"opc\.tcp://([^:/]+):?(\d+)?", curr_url)
        if match:
            ip = match.group(1)
            port = int(match.group(2)) if match.group(2) else OPCUA_PORT
            self.txt_ip.setText(ip)
            self._port = port
        self._poll_interval = getattr(self.service, "poll_interval", OPCUA_POLL_INTERVAL)

    def update_diagnostics(self):
        if not self.service or not self.plc:
            return

        is_online = getattr(self.plc, "is_opcua_online", False)
        status_msg = getattr(self.plc, "opcua_status_msg", "Disconnected")

        if is_online:
            self.led_status.set_color("green")
            self.lbl_diag_status.setText(tr("Online: {url}", self.current_lang).format(url=self.service.endpoint_url))
            self.lbl_diag_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #16A34A;")
            self.btn_disconnect.setEnabled(True)

            # If waiting for reconnect, update prompt text to success
            if self._is_reconnecting:
                self._is_reconnecting = False
                self.lbl_test_result.setText(tr("✔ Connection established successfully", self.current_lang))
                self.lbl_test_result.setStyleSheet("font-size: 11px; color: #16A34A; font-weight: bold;")
        else:
            self.led_status.set_color("grey")
            self.lbl_diag_status.setText(tr("Offline: {msg}", self.current_lang).format(msg=status_msg))
            self.lbl_diag_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #DC2626;")
            self.btn_disconnect.setEnabled(False)

            if self._is_reconnecting and status_msg and status_msg != "Disconnected":
                self.lbl_test_result.setText(tr("Reconnecting: {msg}...", self.current_lang).format(msg=status_msg))
                self.lbl_test_result.setStyleSheet("font-size: 11px; color: #D97706; font-weight: bold;")

        # Telemetry frames count
        frames = getattr(self.service, "frames_received", 0)
        self.lbl_stat_frames.setText(tr("Frames: {frames:,}", self.current_lang).format(frames=frames))

    def on_test_clicked(self):
        url = self.get_endpoint_url()
        self.lbl_test_result.setText(tr("Testing connection...", self.current_lang))
        self.lbl_test_result.setStyleSheet("font-size: 11px; color: #D97706; font-weight: bold;")
        self.btn_test.setEnabled(False)

        self.tester_thread = ConnectionTesterThread(url, timeout=3.0)
        self.tester_thread.test_finished.connect(self._on_test_finished)
        self.tester_thread.start()

    def _on_test_finished(self, success, msg, latency):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_result.setText(tr("✔ Connected ({latency:.1f} ms)", self.current_lang).format(latency=latency))
            self.lbl_test_result.setStyleSheet("font-size: 11px; color: #16A34A; font-weight: bold;")
        else:
            self.lbl_test_result.setText(tr("✖ Failed: {msg}", self.current_lang).format(msg=msg))
            self.lbl_test_result.setStyleSheet("font-size: 11px; color: #DC2626;")

    def on_apply_clicked(self):
        new_url = self.get_endpoint_url()
        poll_sec = getattr(self, "_poll_interval", OPCUA_POLL_INTERVAL)

        self._is_reconnecting = True
        if self.service:
            if hasattr(self.service, "update_connection"):
                self.service.update_connection(new_url, poll_sec)
            else:
                self.service.endpoint_url = new_url
                self.service.poll_interval = poll_sec

        self.lbl_test_result.setText(tr("Reconnecting to {url}...", self.current_lang).format(url=new_url))
        self.lbl_test_result.setStyleSheet("font-size: 11px; color: #2563EB; font-weight: bold;")

    def on_disconnect_clicked(self):
        self._is_reconnecting = False
        if hasattr(self.service, "disconnect_client"):
            self.service.disconnect_client()
        self.lbl_test_result.setText(tr("Disconnected from server", self.current_lang))
        self.lbl_test_result.setStyleSheet("font-size: 11px; color: #64748B;")
        self.update_diagnostics()

    def closeEvent(self, event):
        if self.tester_thread and self.tester_thread.isRunning():
            try:
                self.tester_thread.test_finished.disconnect(self._on_test_finished)
            except Exception:
                pass
            self.tester_thread.wait(500)
        super().closeEvent(event)
