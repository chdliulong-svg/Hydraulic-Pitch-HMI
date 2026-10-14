# -*- coding: utf-8 -*-
"""
HMI Configuration, Theme, Constants and Styling
"""

import os

# =============================================================================
# 1. Window & UI Framework Settings
# =============================================================================
WINDOW_TITLE = "SEC PAC HMI -  Hydraulic Pitch Control System"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 680
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 680

HMI_VERSION = "1.0"
UI_REFRESH_TIMER_MS = 100       # UI clock and state refresh timer in milliseconds
TEST_AUTORUN_TIMEOUT_MS = 500   # Automated self-test quit delay in milliseconds

# =============================================================================
# 2. User Roles & Authentication Passwords
# =============================================================================
ROLE_NOT_LOGGED_IN = "Not logged in!"
ROLE_MAINTENANCE = "Maintenance"
ROLE_SUPER_USER = "Super User"

PASSWORD_MANUAL_CALIB = "asdf"
PASSWORD_MAINT_LOGIN = "asdf"
PASSWORD_SUPER_USER = "super"

# =============================================================================
# 3. OPC UA Communication & CODESYS Architecture
# =============================================================================
OPCUA_HOST = "127.0.0.1"
OPCUA_PORT = 4840
OPCUA_POLL_INTERVAL = 0.1  # Polling cycle in seconds (0.1s = 100ms)
OPCUA_ENDPOINT = f"opc.tcp://{OPCUA_HOST}:{OPCUA_PORT}"

# CODESYS Device Architecture & Symbol Naming Parameters
OPCUA_DEVICE_NAME = "CODESYS Control Win V3"  # PLC platform runtime name in device tree
OPCUA_APP_NAME = "PAC"                        # Application name under PLC Logic
OPCUA_GVL_NAME = "Common"                     # Global Variable List (GVL) name
OPCUA_NAMESPACE_INDEX = 4                     # Namespace index for CODESYS user variables

# Full OPC UA Node Base Prefix: "ns=4;s=|var|CODESYS Control Win V3.PAC.Common."
BASE_NODE_PREFIX = f"ns={OPCUA_NAMESPACE_INDEX};s=|var|{OPCUA_DEVICE_NAME}.{OPCUA_APP_NAME}.{OPCUA_GVL_NAME}."

# OPC UA Handshake & Connection Timeouts
OPCUA_CONNECT_TIMEOUT = 4.0          # Client connection handshake timeout (seconds)
OPCUA_TEST_TIMEOUT = 3.0             # Diagnostics test connection timeout (seconds)
OPCUA_RETRY_INTERVAL = 1.5           # Disconnect retry interval (seconds)
OPCUA_PULSE_RESET_DELAY = 0.2        # Boolean pulse auto-reset delay (seconds)
OPCUA_PULSE_RESET_INT_DELAY = 0.5    # Integer command pulse auto-reset delay (seconds)
OPCUA_DISCONNECT_WAIT_MS = 2000      # Thread termination wait timeout (milliseconds)

# =============================================================================
# 4. PLC Network Configuration Defaults
# =============================================================================
DEFAULT_PLC_HOSTNAME = "PAC_HUB_01"
DEFAULT_PLC_IP = "172.160.1.111"
DEFAULT_PLC_SUBNET = "255.255.0.0"

# =============================================================================
# 5. PackML States & Modes
# =============================================================================
STATE_ABORTED = "Aborted"
STATE_CLEARING = "Clearing"
STATE_STOPPED = "Stopped"
STATE_RESETTING = "Resetting"
STATE_IDLE = "Idle"
STATE_STARTING = "Starting"
STATE_EXECUTE = "Execute"
STATE_ABORTING = "Aborting"

MODE_PRODUCTION = "Production"
MODE_MANUAL = "Manual"
MODE_MAINTENANCE = "Maintenance"

# =============================================================================
# 6. Motion, Kinematics & Manual Control Parameters
# =============================================================================
MANUAL_FAST_SPEED_DEFAULT = 1.5  # °/s (Fast pitching rate default)
MANUAL_SLOW_SPEED_DEFAULT = 0.5  # °/s (Slow pitching rate default)
MANUAL_SPEED_MIN = 0.1           # °/s (Speed lower limit)
MANUAL_SPEED_MAX = 2.5           # °/s (Speed upper limit)

# =============================================================================
# 7. Sensor & Kinematics Calibration Parameters (GRD & Zero Offset)
# =============================================================================
GRD_MIN_VALUE = 260000      # pulse / cm/s (Minimum valid GRD value)
GRD_MAX_VALUE = 290000      # pulse / cm/s (Maximum valid GRD value)
OFFSET_MIN_DEG = -5.0       # ° (Minimum pitch position calibration offset)
OFFSET_MAX_DEG = 5.0        # ° (Maximum pitch position calibration offset)

# =============================================================================
# 8. Alarm System Configuration
# =============================================================================
ALARM_POLL_DECIMATION = 10     # Alarm polling decimation (every 10 cycles = 1.0s)
ALARM_CHUNK_SIZE = 50          # OPC UA batch chunk size for reading alarm nodes
ALARM_HISTORY_MAX_FETCH = 50   # Max history entries fetched per refresh

# =============================================================================
# 9. Logging Configuration & Error Reporting
# =============================================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE_PATH = os.path.join(LOG_DIR, "hmi.log")
LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per log file
LOG_BACKUP_COUNT = 5              # 5 rolling backup files
LOG_LEVEL = "DEBUG"                # Root logging level (DEBUG, INFO, WARNING, ERROR)
OPCUA_STRICT_RAISE_EXCEPTIONS = False  # Set True in debug tests to raise write exceptions
