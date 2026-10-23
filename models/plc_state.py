# -*- coding: utf-8 -*-
"""
PAC State and Telemetry Model for Hydraulic Pitch HMI
Holds PackML states, blade parameters, and OPC UA telemetry
"""

import time
from PyQt6.QtCore import QObject, pyqtSignal
from config import (
    STATE_ABORTED, STATE_CLEARING, STATE_STOPPED, STATE_RESETTING,
    STATE_IDLE, STATE_STARTING, STATE_EXECUTE, STATE_ABORTING,
    MODE_PRODUCTION, MODE_MANUAL, MODE_MAINTENANCE,
    MANUAL_FAST_SPEED_DEFAULT, MANUAL_SLOW_SPEED_DEFAULT,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG,
    DEFAULT_PLC_HOSTNAME, DEFAULT_PLC_IP, DEFAULT_PLC_SUBNET,
    ROLE_NOT_LOGGED_IN, ROLE_MAINTENANCE, ROLE_SUPER_USER,
    PASSWORD_SUPER_USER, PASSWORD_MAINT_LOGIN, PASSWORD_MANUAL_CALIB,
    HASH_SUPER_USER, HASH_MAINTENANCE, hash_password
)
from models.opcua_service import MAINTENANCE_VALVES

# Hydraulic pitch blades architecture (3 blades: Blade A, B, C)
BLADE_NAMES = ["Blade A", "Blade B", "Blade C"]
BLADE_COUNT = len(BLADE_NAMES)


class BladeData:
    def __init__(self, name):
        self.name = name
        self.pressure_accu = 0.0  # bar
        self.pressure_piston = 0.0  # bar
        self.pressure_rod = 0.0  # bar
        self.pitch_reference_active = False
        
        # Position & Kinematics
        self.cyl_pos_mm = 0.0  # mm
        self.angle_deg = 0.0    # deg (90° is feathered/safe, ~0° is fine/operating)
        self.cyl_speed_mms = 0.0 # mm/s
        self.speed_degs = 0.0    # °/s
        self.spool_pos_pct = 0.0 # %
        self.pitch_lock_engaged = False  # True = locked
        
        # Calibration
        self.calib_offset_deg = 0.00
        self.hmi_offset_temp = 0.00
        self.grd_current = 0  # pulse / cm/s
        self.grd_new = 0

        # Maintenance Valves (1 = energized)
        self.valves = {vk: False for vk in MAINTENANCE_VALVES}
        self.prop_valve_cmd = 0.0  # -100% to +100%


class PLCStateManager(QObject):
    state_changed = pyqtSignal()
    message_updated = pyqtSignal(str)
    auth_changed = pyqtSignal(str)
    msgbox_triggered = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        # State machine
        self.blade_state = STATE_ABORTED
        self.blade_mode = MODE_PRODUCTION
        
        # Control Source
        self.remote_box_connected = False
        self.remote_box_in_control = False
        self.manual_control_source = "HMI"  # "HMI" or "Remote Box"
        self.safety_ok = False
        
        # Selected blade for manual operation (0=A, 1=B, 2=C)
        self.selected_blade_idx = 0
        
        # Manual Mode Settings
        self.manual_fast_speed = MANUAL_FAST_SPEED_DEFAULT  # °/s (0.1 ~ 2.5)
        self.manual_slow_speed = MANUAL_SLOW_SPEED_DEFAULT  # °/s
        self.manual_speed_mode = "FAST" # "FAST" or "SLOW"
        self.manual_pitch_lock_disengaged = False  # False = Engaged (已落锁), True = Released (已释放)
        self.manual_moving_dir = 0    # 1=Feather, -1=Fine, 0=Stop
        self.blade_safe = [False] * BLADE_COUNT
        self.manual_current_pos = None

        # Lubrication
        self.pump1_active = False
        self.pump2_active = False
        self.lub_tank1_ok = False
        self.lub_piston_a1 = False
        self.lub_piston_b1 = False
        self.lub_piston_c1 = False
        self.lub_tank2_ok = False
        self.lub_piston_a2 = False
        self.lub_piston_b2 = False
        self.lub_piston_c2 = False

        # Blades
        self.blades = [BladeData(name) for name in BLADE_NAMES]

        # Environmental / PAC Status
        self.temp_hub = 0.0
        self.temp_cabinet = 0.0
        self.temp_oil = 0.0
        self.current_t1 = 0.0
        self.current_t2 = 0.0
        self.cpu_temp = 0.0
        self.power_supply_ok = False

        # PAC System Version from OPC UA (Common.pac.version.HW, Common.pac.version.SW)
        self.pac_version_hw = "---"
        self.pac_version_sw = "---"

        # Network parameters from PVturbineSpecific.network
        self.net_hostname = DEFAULT_PLC_HOSTNAME
        self.net_ip = DEFAULT_PLC_IP
        self.net_subnet = DEFAULT_PLC_SUBNET
        self.has_network_nodes = False  # True only if CODESYS symbol config exports PVturbineSpecific.network


        # HPU Status
        self.hpu_state = "Stopped"
        self.hpu_temp_oil = 0.0
        self.hpu_pressure_accu = 0.0
        self.hpu_oil_level = 0.0
        self.hpu_pressure_buildup_req = False

        # Maintenance pending changes
        self.maint_hpu_req_pending = False
        self.maint_pump1_pending = False
        self.maint_pump2_pending = False
        self.maint_valves_pending = [[False]*len(MAINTENANCE_VALVES) for _ in range(BLADE_COUNT)]
        self.maint_prop_pending = [0.0] * BLADE_COUNT

        # Login state
        self.current_role = ROLE_NOT_LOGGED_IN
        self.manual_logged_in = False
        self.maint_logged_in = False
        self.file_logged_level = ROLE_NOT_LOGGED_IN
        self.is_super_user = False

        # Status text
        self.bottom_status_msg = 'PAC: "Aborted - Waiting for Clear Command"'

        # HMI Message Box telemetry
        self.msgbox_status = 1  # 0: Show, 1: Hidden
        self.msgbox_header = ""
        self.msgbox_content = ""
        self.msgbox_btn_ok = 0
        self.msgbox_btn_abort = 0
        self.msgbox_btn_ok_status = 0
        self.msgbox_btn_abort_status = 0
        self.msgbox_icon = 0

        # PLC Main Start/Abort button visibility from Common.hmi.status (0=Show, 1=Hide)
        self.plc_abort_btn_status = 0
        self.plc_start_btn_status = 1

        # OPC UA live connection state
        self.is_opcua_online = False
        self.opcua_status_msg = "OPC UA: Disconnected"
        self.plc_time = None

    def set_opcua_status(self, connected: bool, msg: str):
        self.is_opcua_online = connected
        self.opcua_status_msg = msg
        if not connected:
            self.plc_time = None
            self.pac_version_hw = "---"
            self.pac_version_sw = "---"
            self.safety_ok = False
            self.blade_safe = [False] * BLADE_COUNT
            self.pump1_active = False
            self.pump2_active = False
            self.lub_tank1_ok = False
            self.lub_tank2_ok = False
            self.lub_piston_a1 = False
            self.lub_piston_b1 = False
            self.lub_piston_c1 = False
            self.lub_piston_a2 = False
            self.lub_piston_b2 = False
            self.lub_piston_c2 = False
            self.power_supply_ok = False
            for bld in self.blades:
                bld.pitch_reference_active = False
                bld.pitch_lock_engaged = False
        self.state_changed.emit()

    def update_from_opcua(self, data: dict):
        """Update PLC state with live telemetry from CODESYS OPC UA"""
        self.is_opcua_online = True

        # PackML state mapping
        state_int = data.get("state")
        if state_int is not None:
            state_map = {
                1: STATE_CLEARING,
                2: STATE_STOPPED,
                3: STATE_STARTING,
                4: STATE_IDLE,
                6: STATE_EXECUTE,
                8: STATE_ABORTING,
                9: STATE_ABORTED,
                15: STATE_RESETTING
            }
            self.blade_state = state_map.get(state_int, f"State_{state_int}")

        # Mode mapping
        mode_int = data.get("mode")
        if mode_int is not None:
            mode_map = {
                1: MODE_PRODUCTION,
                2: MODE_MAINTENANCE,
                3: MODE_MANUAL
            }
            self.blade_mode = mode_map.get(mode_int, f"Mode_{mode_int}")

        # Status description
        desc = data.get("description")
        if desc:
            # Fix known 80-character PLC STRING truncation (CODESYS default STRING(80) limit)
            if "Aborting - Turbine is shutting down.Waiting for blades to fully feather and pitc" in desc:
                desc = "Aborting - Turbine is shutting down. Waiting for blades to fully feather and pitch locks engaged"
            self.bottom_status_msg = f'PAC: "{desc}"'
            self.message_updated.emit(self.bottom_status_msg)

        # Update 3 blades (all telemetry directly from lower machine PLC without host calculations)
        for i, bld in enumerate(self.blades):
            b_data = data.get(f"blade_{i}")
            if b_data:
                bld.pressure_accu = float(b_data.get("pres_accu", bld.pressure_accu))
                bld.pressure_piston = float(b_data.get("pres_piston", bld.pressure_piston))
                bld.pressure_rod = float(b_data.get("pres_rod", bld.pressure_rod))
                bld.cyl_pos_mm = float(b_data.get("cyl_pos", bld.cyl_pos_mm))
                bld.cyl_speed_mms = float(b_data.get("cyl_spd", bld.cyl_speed_mms))
                bld.angle_deg = float(b_data.get("pos_act_deg", bld.angle_deg))
                bld.speed_degs = float(b_data.get("rate_act_deg", bld.speed_degs))
                bld.spool_pos_pct = float(b_data.get("spool_pos_fb", bld.spool_pos_pct))
                if "pitch_lock_engaged" in b_data:
                    bld.pitch_lock_engaged = bool(b_data["pitch_lock_engaged"])
                bld.pitch_reference_active = bool(b_data.get("pitch_ref_active", bld.pitch_reference_active))

        # PAC Version from OPC UA
        if "pac_version_hw" in data and data["pac_version_hw"] is not None:
            val_hw = str(data["pac_version_hw"]).strip()
            self.pac_version_hw = val_hw if val_hw else "---"
        if "pac_version_sw" in data and data["pac_version_sw"] is not None:
            val_sw = str(data["pac_version_sw"]).strip()
            self.pac_version_sw = val_sw if val_sw else "---"

        # Common.blade[i].par & Common.PVturbineSpecific & Common.hmi buffers
        for i, bld in enumerate(self.blades):
            # 1. Active Offset: Prefer blade[i].par.posOffDeg, fallback to par_{i}_posOffDeg
            bld_par_off = data.get(f"bld_{i}_par_pos_off")
            if bld_par_off is not None:
                try:
                    val = float(bld_par_off)
                    if OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG:
                        bld.calib_offset_deg = val
                except (ValueError, TypeError):
                    pass
            else:
                off_key = f"par_{i}_posOffDeg"
                if off_key in data and data[off_key] is not None:
                    try:
                        val = float(data[off_key])
                        if OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG:
                            bld.calib_offset_deg = val
                    except (ValueError, TypeError):
                        pass

            # HMI buffer offset
            hmi_off = data.get(f"hmi_pos_off_{i}")
            if hmi_off is not None:
                try:
                    val = float(hmi_off)
                    if OFFSET_MIN_DEG <= val <= OFFSET_MAX_DEG:
                        bld.hmi_offset_temp = val
                except (ValueError, TypeError):
                    pass

            # 2. Active GRD: Prefer blade[i].par.grd, fallback to par_{i}_grd
            bld_par_g = data.get(f"bld_{i}_par_grd")
            if bld_par_g is not None:
                try:
                    val = int(bld_par_g)
                    if GRD_MIN_VALUE <= val <= GRD_MAX_VALUE:
                        bld.grd_current = val
                except (ValueError, TypeError):
                    pass
            else:
                grd_key = f"par_{i}_grd"
                if grd_key in data and data[grd_key] is not None:
                    try:
                        val = int(data[grd_key])
                        if GRD_MIN_VALUE <= val <= GRD_MAX_VALUE:
                            bld.grd_current = val
                    except (ValueError, TypeError):
                        pass

            # HMI buffer GRD
            hmi_g = data.get(f"hmi_grd_temp_{i}")
            if hmi_g is not None:
                try:
                    val = int(hmi_g)
                    if GRD_MIN_VALUE <= val <= GRD_MAX_VALUE:
                        bld.grd_new = val
                except (ValueError, TypeError):
                    pass

        # Common.PVturbineSpecific: Network parameters
        if "has_network_nodes" in data:
            self.has_network_nodes = bool(data["has_network_nodes"])
        if "net_hostName" in data and data["net_hostName"] is not None:
            self.net_hostname = str(data["net_hostName"])
        if "net_IPAddr" in data and data["net_IPAddr"] is not None:
            self.net_ip = str(data["net_IPAddr"])
        if "net_subnetMask" in data and data["net_subnetMask"] is not None:
            self.net_subnet = str(data["net_subnetMask"])

        # Environmental / PAC Status
        if "temp_hub" in data: self.temp_hub = data["temp_hub"]
        if "temp_oil" in data: self.temp_oil = data["temp_oil"]
        if "temp_cabinet" in data: self.temp_cabinet = data["temp_cabinet"]
        if "cpu_temp" in data: self.cpu_temp = data["cpu_temp"]
        if "current_t1" in data: self.current_t1 = data["current_t1"]
        if "current_t2" in data: self.current_t2 = data["current_t2"]
        if "power_supply_ok" in data: self.power_supply_ok = data["power_supply_ok"]
        if "safety_ok" in data and data["safety_ok"] is not None: self.safety_ok = bool(data["safety_ok"])

        # Lubrication
        if "lub_tank1_ok" in data: self.lub_tank1_ok = data["lub_tank1_ok"]
        if "lub_piston_a1" in data: self.lub_piston_a1 = data["lub_piston_a1"]
        if "lub_piston_b1" in data: self.lub_piston_b1 = data["lub_piston_b1"]
        if "lub_piston_c1" in data: self.lub_piston_c1 = data["lub_piston_c1"]
        if "lub_tank2_ok" in data: self.lub_tank2_ok = data["lub_tank2_ok"]
        if "lub_piston_a2" in data: self.lub_piston_a2 = data["lub_piston_a2"]
        if "lub_piston_b2" in data: self.lub_piston_b2 = data["lub_piston_b2"]
        if "lub_piston_c2" in data: self.lub_piston_c2 = data["lub_piston_c2"]

        # HPU Status
        if "hpu_state" in data: self.hpu_state = data["hpu_state"]
        if "hpu_pressure" in data: self.hpu_pressure_accu = data["hpu_pressure"]
        if "hpu_temp" in data: self.hpu_temp_oil = data["hpu_temp"]
        if "hpu_oil_level" in data: self.hpu_oil_level = data["hpu_oil_level"]

        # HMI Blade Control Telemetry
        if "hmi_active_blade" in data and data["hmi_active_blade"] is not None:
            val = int(data["hmi_active_blade"])
            if not getattr(self, "is_super_user", False):
                if 0 <= val < 3:
                    self.selected_blade_idx = val

        if "hmi_current_pos" in data and data["hmi_current_pos"] is not None:
            self.manual_current_pos = float(data["hmi_current_pos"])

        if "hmi_blade_safe_a" in data and data["hmi_blade_safe_a"] is not None:
            self.blade_safe[0] = bool(data["hmi_blade_safe_a"])
        if "hmi_blade_safe_b" in data and data["hmi_blade_safe_b"] is not None:
            self.blade_safe[1] = bool(data["hmi_blade_safe_b"])
        if "hmi_blade_safe_c" in data and data["hmi_blade_safe_c"] is not None:
            self.blade_safe[2] = bool(data["hmi_blade_safe_c"])

        if "hmi_fast_speed" in data and data["hmi_fast_speed"] is not None:
            self.manual_fast_speed = float(data["hmi_fast_speed"])
        if "hmi_slow_speed" in data and data["hmi_slow_speed"] is not None:
            self.manual_slow_speed = float(data["hmi_slow_speed"])

        if "hmi_fast_chosen" in data and data["hmi_fast_chosen"] is not None:
            self.manual_speed_mode = "FAST" if bool(data["hmi_fast_chosen"]) else "SLOW"

        if "hmi_pitch_lock" in data and data["hmi_pitch_lock"] is not None:
            self.manual_pitch_lock_disengaged = bool(data["hmi_pitch_lock"])

        # Remote Box connection & manual control source telemetry
        rb_conn_candidates = []
        if "sim_remote_box_connected" in data and data["sim_remote_box_connected"] is not None:
            rb_conn_candidates.append(bool(data["sim_remote_box_connected"]))
        if "pac_remote_box_connected" in data and data["pac_remote_box_connected"] is not None:
            rb_conn_candidates.append(bool(data["pac_remote_box_connected"]))
        if "hmi_remote_box_enabled" in data and data["hmi_remote_box_enabled"] is not None:
            rb_conn_candidates.append(bool(int(data["hmi_remote_box_enabled"]) & 2))
        if rb_conn_candidates:
            self.remote_box_connected = any(rb_conn_candidates)

        rb_ctrl_candidates = []
        if "sim_remote_box_in_control" in data and data["sim_remote_box_in_control"] is not None:
            rb_ctrl_candidates.append(bool(data["sim_remote_box_in_control"]))
        if "hmi_user_input" in data and data["hmi_user_input"] is not None:
            rb_ctrl_candidates.append(int(data["hmi_user_input"]) == 40)
        if rb_ctrl_candidates:
            self.remote_box_in_control = any(rb_ctrl_candidates)

        if self.remote_box_connected or getattr(self, "remote_box_in_control", False):
            self.manual_control_source = "Remote Box"
        else:
            self.manual_control_source = "HMI"

        # Lubrication pump feedback from pac.io.dOut
        if "pac_lub1_pump_on" in data and data["pac_lub1_pump_on"] is not None:
            self.pump1_active = bool(data["pac_lub1_pump_on"])
        if "pac_lub2_pump_on" in data and data["pac_lub2_pump_on"] is not None:
            self.pump2_active = bool(data["pac_lub2_pump_on"])

        # HMI Message Box telemetry
        prev_msgbox_status = self.msgbox_status
        if "msgbox_status" in data and data["msgbox_status"] is not None:
            self.msgbox_status = int(data["msgbox_status"])
        if "msgbox_header" in data and data["msgbox_header"] is not None:
            self.msgbox_header = str(data["msgbox_header"])
        if "msgbox_content" in data and data["msgbox_content"] is not None:
            self.msgbox_content = str(data["msgbox_content"])
        if "msgbox_btn_ok_status" in data and data["msgbox_btn_ok_status"] is not None:
            self.msgbox_btn_ok_status = int(data["msgbox_btn_ok_status"])
        elif "msgbox_btn_ok" in data and data["msgbox_btn_ok"] is not None:
            self.msgbox_btn_ok_status = int(data["msgbox_btn_ok"])
        if "msgbox_btn_abort_status" in data and data["msgbox_btn_abort_status"] is not None:
            self.msgbox_btn_abort_status = int(data["msgbox_btn_abort_status"])
        elif "msgbox_btn_abort" in data and data["msgbox_btn_abort"] is not None:
            self.msgbox_btn_abort_status = int(data["msgbox_btn_abort"])
        if "msgbox_icon" in data and data["msgbox_icon"] is not None:
            self.msgbox_icon = int(data["msgbox_icon"])

        if prev_msgbox_status != 0 and self.msgbox_status == 0:
            self.msgbox_triggered.emit({
                "header": self.msgbox_header,
                "content": self.msgbox_content,
                "icon": self.msgbox_icon,
                "btn_ok_status": self.msgbox_btn_ok_status,
                "btn_abort_status": self.msgbox_btn_abort_status
            })

        # PLC Main Start/Abort button visibility (0=Show, 1=Hide)
        if "plc_abort_btn_status" in data:
            self.plc_abort_btn_status = int(data["plc_abort_btn_status"])
        if "plc_start_btn_status" in data:
            self.plc_start_btn_status = int(data["plc_start_btn_status"])

        # PLC Server Real-Time Clock
        if "plc_time" in data and data["plc_time"] is not None:
            self.plc_time = data["plc_time"]

        self.state_changed.emit()

    # --- PackML State Transitions (Strictly PLC-Driven) ---
    def start_pressed(self):
        """Deprecated: PackML state transitions are strictly driven by PLC telemetry via OPC UA."""
        pass

    def stop_pressed(self):
        """Deprecated: PackML state transitions are strictly driven by PLC telemetry via OPC UA."""
        pass

    def request_manual_mode(self):
        """Deprecated: PackML mode transitions are strictly driven by PLC telemetry via OPC UA."""
        return True, ""

    def request_producing_mode(self):
        """Deprecated: PackML mode transitions are strictly driven by PLC telemetry via OPC UA."""
        return True, ""

    def request_maintenance_mode(self):
        """Deprecated: PackML mode transitions are strictly driven by PLC telemetry via OPC UA."""
        return True, ""

    def exit_maintenance_mode(self):
        """Deprecated: PackML mode transitions are strictly driven by PLC telemetry via OPC UA."""
        return True, ""

    # --- Manual Controls ---
    def select_blade(self, idx):
        """Switch active blade view on HMI"""
        self.selected_blade_idx = idx
        self.state_changed.emit()
        return True, f"Selected {self.blades[idx].name}"

    def toggle_pitch_lock(self):
        """Toggle manual pitch lock command (False=Engaged, True=Released)"""
        self.manual_pitch_lock_disengaged = not self.manual_pitch_lock_disengaged
        self.state_changed.emit()
        return self.manual_pitch_lock_disengaged

    def set_move_dir(self, direction):
        """direction: 1=Feather, -1=Fine, 0=Stop"""
        self.manual_moving_dir = direction
        return True, "Moving"

    # --- Authentication Management ---
    def authenticate(self, password: str) -> tuple[bool, str, str]:
        """
        Unified authentication method for Super User and Maintenance roles.
        Synchronizes state across Manual, Maintenance, and Network pages.
        """
        pwd = str(password).strip()
        pwd_hash = hash_password(pwd)
        if pwd_hash == HASH_SUPER_USER or pwd == PASSWORD_SUPER_USER:
            self.current_role = ROLE_SUPER_USER
            self.is_super_user = True
            self.manual_logged_in = True
            self.maint_logged_in = True
            self.auth_changed.emit(ROLE_SUPER_USER)
            self.state_changed.emit()
            return True, "", ROLE_SUPER_USER
        elif pwd_hash == HASH_MAINTENANCE or pwd in (PASSWORD_MAINT_LOGIN, PASSWORD_MANUAL_CALIB):
            self.current_role = ROLE_MAINTENANCE
            self.is_super_user = False
            self.manual_logged_in = True
            self.maint_logged_in = True
            self.auth_changed.emit(ROLE_MAINTENANCE)
            self.state_changed.emit()
            return True, "", ROLE_MAINTENANCE
        return False, "Incorrect password!", ROLE_NOT_LOGGED_IN

    def logout(self):
        """Unified logout resetting roles and permissions globally"""
        self.current_role = ROLE_NOT_LOGGED_IN
        self.is_super_user = False
        self.manual_logged_in = False
        self.maint_logged_in = False
        self.auth_changed.emit(ROLE_NOT_LOGGED_IN)
        self.state_changed.emit()

