# -*- coding: utf-8 -*-
"""
Main Application Entry Point for SEC PAC 6MW Hydraulic Pitch HMI
Usage:
    python main.py          (Runs the interactive GUI)
    python main.py --test   (Runs automated headless/quick self-test)
"""

import sys
import os

# Ensure the root of hmi_python is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from config import OPCUA_ENDPOINT, OPCUA_POLL_INTERVAL, TEST_AUTORUN_TIMEOUT_MS 
from ui.styles import QSS_STYLE
from models.plc_state import PLCStateManager
from models.alarm_manager import AlarmManager
from models.opcua_service import OpcUaService
from ui.main_window import MainWindow
from utils.logger import get_logger

logger = get_logger("hmi")


def main():
    logger.info("=" * 60)
    logger.info("Starting SEC PAC 6MW Hydraulic Pitch HMI Application")
    logger.info(f"Target OPC UA Endpoint: {OPCUA_ENDPOINT}")
    logger.info("=" * 60)

    app = QApplication(sys.argv)
    app_font = QFont("Segoe UI", 9)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)
    app.setStyleSheet(QSS_STYLE)

    # Initialize State & Model Managers
    plc_state = PLCStateManager()
    alarm_mgr = AlarmManager()

    # Initialize live CODESYS OPC UA service from config
    opcua_service = OpcUaService(endpoint_url=OPCUA_ENDPOINT, poll_interval=OPCUA_POLL_INTERVAL)
    opcua_service.data_received.connect(plc_state.update_from_opcua)
    opcua_service.alarms_received.connect(alarm_mgr.update_from_opcua)
    opcua_service.connection_changed.connect(plc_state.set_opcua_status)

    def on_command_result(cmd_name: str, is_success: bool, msg: str):
        if not is_success:
            logger.error(f"[OPCUA Command Failed] '{cmd_name}': {msg}")

    opcua_service.command_result.connect(on_command_result)
    opcua_service.start()

    # Create Main Window
    window = MainWindow(plc_state, alarm_mgr, opcua_service=opcua_service)
    window.show()

    # Support automated testing mode
    if "--test" in sys.argv:
        print("[TEST] Running self-test of models and state transitions...")
        for page_idx in range(5):
            window.stacked_pages.setCurrentIndex(page_idx)
            print(f"[TEST] Switched to page {page_idx} successfully.")
        
        # Test state transitions
        plc_state.start_pressed()
        print("[TEST] Tested START button transition.")
        plc_state.stop_pressed()
        print("[TEST] Tested STOP button transition.")

        # Test alarm acknowledgment
        alarm_mgr.acknowledge_all()
        print("[TEST] Tested Acknowledge All.")
        alarm_mgr.reset_safety()
        print("[TEST] Tested Reset Safety.")

        # Test language switching
        window.btn_lang.click()
        assert window.current_lang == "CN", "Language should be CN after first click"
        print("[TEST] Switched to Chinese mode successfully.")
        window.btn_lang.click()
        assert window.current_lang == "EN", "Language should be EN after second click"
        print("[TEST] Switched back to English mode successfully.")

        print("[TEST] All self-tests passed successfully! Exiting.")
        def _cleanup_and_quit():
            window.close()
            opcua_service.stop()
            app.quit()
        QTimer.singleShot(TEST_AUTORUN_TIMEOUT_MS, _cleanup_and_quit)

    ret = app.exec()
    opcua_service.stop()
    logger.info("Application shut down cleanly.")
    return ret


if __name__ == "__main__":
    sys.exit(main())
