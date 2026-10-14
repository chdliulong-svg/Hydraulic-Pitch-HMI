# -*- coding: utf-8 -*-
"""
OPC UA Client Service for SEC PAC 6MW Hydraulic Pitch Control System
Connects asynchronously to CODESYS OPC UA Server (opc.tcp://127.0.0.1:4840)
Reads live IEC variables from 'ns=4;s=|var|CODESYS Control Win V3.PAC.Common.*'
and emits Qt signals to update HMI models in real-time.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from config import (
    OPCUA_ENDPOINT, OPCUA_POLL_INTERVAL, BASE_NODE_PREFIX,
    OPCUA_CONNECT_TIMEOUT, OPCUA_RETRY_INTERVAL,
    OPCUA_PULSE_RESET_DELAY, OPCUA_PULSE_RESET_INT_DELAY, OPCUA_DISCONNECT_WAIT_MS,
    ALARM_POLL_DECIMATION, ALARM_CHUNK_SIZE, ALARM_HISTORY_MAX_FETCH,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG,
    OPCUA_STRICT_RAISE_EXCEPTIONS
)
from utils.logger import get_logger, OpcUaWriteError

logger = get_logger("opcua")

try:
    from asyncua import Client, ua
except ImportError:
    Client = None
    ua = None

# CODESYS Maintenance Mode Directional Valves IEC Field Mapping
MAINT_VALVE_PLC_FIELDS = {
    "v109": "cutOffV109Open",
    "v119a": "cutOffV119AOpen",
    "v119b": "cutOffV119BOpen",
    "v116": "dumpV116Closed",
    "v103": "EMFV103Closed",
    "v120": "EMFV120Closed",
    "v130": "pLockPV130Open",
    "v132": "pLockTV132Open",
}
MAINTENANCE_VALVES = list(MAINT_VALVE_PLC_FIELDS.keys())


class OpcUaWorker(QObject):
    """Async worker running an event loop inside a QThread"""
    data_updated = pyqtSignal(dict)
    alarms_updated = pyqtSignal(list, list)  # (active_alarms, history_alarms)
    connection_status = pyqtSignal(bool, str)  # (is_connected, message)
    command_result = pyqtSignal(str, bool, str)  # (cmd_name, is_success, message)


    def __init__(self, endpoint_url: str = OPCUA_ENDPOINT, poll_interval: float = OPCUA_POLL_INTERVAL):
        super().__init__()
        self.endpoint_url = endpoint_url
        self.poll_interval = poll_interval
        self._running = False
        self._enabled = True
        self._need_reconnect = False
        self.frames_received = 0
        self._write_queue: asyncio.Queue = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.last_write_error: Optional[Exception] = None

    def stop(self):
        self._running = False

    def update_endpoint(self, endpoint_url: str, poll_interval: float = 0.1):
        """Update endpoint URL and trigger dynamic reconnection"""
        self.endpoint_url = endpoint_url
        self.poll_interval = poll_interval
        self._enabled = True
        self._need_reconnect = True

    def set_enabled(self, enabled: bool):
        """Enable or disable active connection"""
        self._enabled = enabled
        if not enabled:
            self._need_reconnect = True

    def enqueue_command(self, cmd_name: str, value: Any = True):
        """Enqueue a command to be written to the PLC"""
        if self._loop and self._write_queue:
            asyncio.run_coroutine_threadsafe(
                self._write_queue.put((cmd_name, value)),
                self._loop
            )

    def write_hmi_blade_offset(self, blade_idx: int, val: float):
        """Write Common.hmi.fromHMI.manualPage.pitchposition[idx].offsetpos (Float)"""
        if 0 <= blade_idx < 3:
            clamped = max(OFFSET_MIN_DEG, min(OFFSET_MAX_DEG, float(val)))
            self.enqueue_command(f"hmi_pos_off_{blade_idx}", clamped)
            # Also enqueue to PVturbineSpecific as persistence fallback
            self.enqueue_command(f"par_{blade_idx}_posOffDeg", clamped)

    def apply_pitch_position_calib(self):
        """Pulse Common.hmi.buttons.applyPPCSelection = 1"""
        self.enqueue_command("hmi_apply_ppc", 1)

    def write_hmi_blade_grd(self, blade_idx: int, val: int):
        """Write Common.hmi.fromHMI.manualPage.blade<A/B/C>grdtemp (UInt32)"""
        if 0 <= blade_idx < 3:
            clamped = max(GRD_MIN_VALUE, min(GRD_MAX_VALUE, int(val)))
            self.enqueue_command(f"hmi_grd_temp_{blade_idx}", clamped)
            # Also enqueue to PVturbineSpecific as persistence fallback
            self.enqueue_command(f"par_{blade_idx}_grd", clamped)

    def apply_grd_calib(self):
        """Pulse Common.hmi.buttons.applyGRDSelection = 1"""
        self.enqueue_command("hmi_apply_grd", 1)

    def write_blade_offset(self, blade_idx: int, val: float):
        self.write_hmi_blade_offset(blade_idx, val)

    def write_blade_grd(self, blade_idx: int, val: int):
        self.write_hmi_blade_grd(blade_idx, val)

    def write_network_hostname(self, val: str):
        self.enqueue_command("net_hostName", str(val))

    def write_network_ip(self, val: str):
        self.enqueue_command("net_IPAddr", str(val))

    def write_network_subnet(self, val: str):
        self.enqueue_command("net_subnetMask", str(val))

    def write_network_settings(self, hostname: str, ip: str, subnet: str):
        self.write_network_hostname(hostname)
        self.write_network_ip(ip)
        self.write_network_subnet(subnet)
        self.enqueue_command("allow_net_update", True)
        self.enqueue_command("hmi_update_network", 1)

    # HMI Blade Control Methods
    def select_blade(self, blade_idx: int):
        """Select active blade (0=A, 1=B, 2=C) in Common.hmi.fromHMI.manualPage"""
        if 0 <= blade_idx < 3:
            self.enqueue_command("hmi_blade_a_sel", blade_idx == 0)
            self.enqueue_command("hmi_blade_b_sel", blade_idx == 1)
            self.enqueue_command("hmi_blade_c_sel", blade_idx == 2)
            self.enqueue_command("hmi_active_blade", blade_idx)

    def set_pitch_lock(self, disengaged: bool):
        """Set pitch lock state: True = open/disengage, False = engaged/locked"""
        self.enqueue_command("hmi_pitch_lock", bool(disengaged))

    def set_speed_mode(self, mode: str):
        """Set fast/slow speed mode ('FAST' or 'SLOW')"""
        is_fast = (str(mode).upper() == "FAST")
        self.enqueue_command("hmi_fast_chosen", is_fast)
        self.enqueue_command("hmi_slow_chosen", not is_fast)

    def write_fast_speed(self, speed: float):
        """Write Common.hmi.fromHMI.manualPage.fastSpeed (Float)"""
        self.enqueue_command("hmi_fast_speed", float(speed))

    def write_slow_speed(self, speed: float):
        """Write Common.hmi.fromHMI.manualPage.slowSpeed (Float)"""
        self.enqueue_command("hmi_slow_speed", float(speed))

    def set_move_feather(self, pressed: bool):
        """Jog feather command (Hold to move)"""
        self.enqueue_command("hmi_feather", bool(pressed))

    def set_move_fine(self, pressed: bool):
        """Jog fine command (Hold to move)"""
        self.enqueue_command("hmi_fine", bool(pressed))

    def set_lubrication_pump(self, pump_no: int, active: bool):
        """Activate/Deactivate lubrication pump 1 or 2 (Sustained state)"""
        val = 1 if active else 0
        if pump_no == 1:
            self.enqueue_command("hmi_activate_lub1", val)
        elif pump_no == 2:
            self.enqueue_command("hmi_activate_lub2", val)

    def request_manual_mode(self):
        """Request manual mode in Common.hmi.buttons.requestManualmode = 1"""
        self.enqueue_command("hmi_req_manual", 1)

    def request_producing_mode(self):
        """Exit manual mode, reset Common.hmi.buttons.requestManualmode = 0"""
        self.enqueue_command("hmi_req_manual", 0)

    # Maintenance Page Methods
    def apply_maint_hpu(self, request_pressure: bool):
        """Apply HPU pressure buildup request in maintenance mode"""
        self.enqueue_command("hmi_req_pressure", bool(request_pressure))
        self.enqueue_command("hmi_apply_hpu", 1)

    def reset_maint_hpu(self):
        """Reset HPU selection in maintenance mode"""
        self.enqueue_command("hmi_reset_hpu", 1)

    def apply_maint_lub(self, pump1: bool, pump2: bool):
        """Apply lubrication pump 1 & 2 test in maintenance mode"""
        self.enqueue_command("hmi_maint_lub1", bool(pump1))
        self.enqueue_command("hmi_maint_lub2", bool(pump2))
        self.enqueue_command("hmi_apply_lub", 1)

    def reset_maint_lub(self):
        """Reset lubrication selection in maintenance mode"""
        self.enqueue_command("hmi_reset_lub", 1)

    def apply_maint_pac(self, valves_by_blade: dict, spool_cmds: list):
        """Apply 8 directional valves and proportional spool position command for 3 blades"""
        for b_idx in range(3):
            b_valves = valves_by_blade.get(b_idx, {})
            for vk in MAINTENANCE_VALVES:
                self.enqueue_command(f"hmi_bld_{b_idx}_{vk}", bool(b_valves.get(vk, False)))
            if b_idx < len(spool_cmds):
                self.enqueue_command(f"hmi_bld_{b_idx}_spool_cmd", float(spool_cmds[b_idx]))
        self.enqueue_command("hmi_apply_pac", 1)

    def reset_maint_pac(self):
        """Reset all PAC valve selections and proportional commands"""
        self.enqueue_command("hmi_reset_pac", 1)

    def request_maintenance_mode(self):
        """Pulse Common.hmi.buttons.modeSelect = 1 to request maintenance mode"""
        self.enqueue_command("hmi_mode_select", 1)

    def login_maintenance(self):
        """Pulse Common.hmi.buttons.loginMaintenance = 1"""
        self.enqueue_command("hmi_login_maint", 1)

    def send_plc_sys_reset(self):
        """Pulse Common.hmi.buttons.sysReset = 1 to request PLC soft restart"""
        self.enqueue_command("hmi_sys_reset", 1)

    def send_msgbox_ok(self):
        """Pulse Common.hmi.msgBox.btnOk = 1"""
        self.enqueue_command("hmi_msgbox_btn_ok", 1)

    def send_msgbox_abort(self):
        """Pulse Common.hmi.msgBox.btnAbort = 1"""
        self.enqueue_command("hmi_msgbox_btn_abort", 1)

    def exit_maintenance_mode(self):
        """Set Common.hmi.buttons.modeSelect = 0 to exit maintenance mode"""
        self.enqueue_command("hmi_mode_select", 0)

    async def _pulse_reset(self, node, cmd_name: str, delay: float = OPCUA_PULSE_RESET_DELAY):
        await asyncio.sleep(delay)
        try:
            dv = ua.DataValue(ua.Variant(False, ua.VariantType.Boolean))
            await node.write_value(dv)
            print(f"[OPCUA] Auto-reset pulse {cmd_name} = False")
        except Exception as e:
            print(f"[OPCUA] Error auto-resetting {cmd_name}: {e}")

    async def _pulse_reset_int(self, node, cmd_name: str, delay: float = OPCUA_PULSE_RESET_INT_DELAY):
        await asyncio.sleep(delay)
        try:
            try:
                dv = ua.DataValue(ua.Variant(0, ua.VariantType.Int16))
                await node.write_value(dv)
            except Exception:
                dv = ua.DataValue(ua.Variant(0, ua.VariantType.UInt16))
                await node.write_value(dv)
            print(f"[OPCUA] Auto-reset pulse {cmd_name} = 0")
        except Exception as e:
            print(f"[OPCUA] Error auto-resetting {cmd_name}: {e}")

    async def _fetch_alarms(self, client):
        """Fetch active alarms and history log from CODESYS gAlarmCoreTable & gHistoryAlarmLog"""
        try:
            core_prefix = f"{BASE_NODE_PREFIX}gAlarmCoreTable."
            reg_cnt = int(await client.get_node(f"{core_prefix}RegisteredCount").read_value())
            if reg_cnt <= 0:
                return [], []

            # 1. Read State for all registered alarms in chunks of ALARM_CHUNK_SIZE
            nodes_state = [client.get_node(f"{core_prefix}Alarms[{i}].State") for i in range(1, reg_cnt + 1)]
            states = []
            for i in range(0, len(nodes_state), ALARM_CHUNK_SIZE):
                chunk = nodes_state[i:i+ALARM_CHUNK_SIZE]
                states.extend(await client.read_values(chunk))

            # Filter active alarms (State != 0)
            active_indices = [idx + 1 for idx, st in enumerate(states) if st != 0]

            # 2. Fetch details for active alarms in chunks of ALARM_CHUNK_SIZE
            detail_nodes = []
            for idx in active_indices:
                detail_nodes.extend([
                    client.get_node(f"{core_prefix}Alarms[{idx}].Code"),
                    client.get_node(f"{core_prefix}Alarms[{idx}].Name"),
                    client.get_node(f"{core_prefix}Alarms[{idx}].Message"),
                    client.get_node(f"{core_prefix}Alarms[{idx}].Severity"),
                    client.get_node(f"{core_prefix}Alarms[{idx}].State"),
                ])

            active_list = []
            if detail_nodes:
                detail_vals = []
                for i in range(0, len(detail_nodes), ALARM_CHUNK_SIZE):
                    chunk = detail_nodes[i:i+ALARM_CHUNK_SIZE]
                    detail_vals.extend(await client.read_values(chunk))

                for i in range(len(active_indices)):
                    active_list.append({
                        "code": int(detail_vals[i*5]),
                        "name": str(detail_vals[i*5+1]),
                        "message": str(detail_vals[i*5+2]),
                        "severity": int(detail_vals[i*5+3]),
                        "state": int(detail_vals[i*5+4]),
                    })

            # 3. Fetch History alarms from gHistoryAlarmLog
            hist_prefix = f"{BASE_NODE_PREFIX}gHistoryAlarmLog."
            hist_cur = int(await client.get_node(f"{hist_prefix}CurrentCount").read_value())
            history_list = []
            if hist_cur > 0:
                fetch_len = min(hist_cur, ALARM_HISTORY_MAX_FETCH)  # Max history entries
                hist_nodes = []
                for i in range(1, fetch_len + 1):
                    hist_nodes.extend([
                        client.get_node(f"{hist_prefix}Items[{i}].Code"),
                        client.get_node(f"{hist_prefix}Items[{i}].Name"),
                        client.get_node(f"{hist_prefix}Items[{i}].Message"),
                        client.get_node(f"{hist_prefix}Items[{i}].Severity"),
                        client.get_node(f"{hist_prefix}Items[{i}].TimeString"),
                        client.get_node(f"{hist_prefix}Items[{i}].State"),
                    ])
                hist_vals = []
                for i in range(0, len(hist_nodes), ALARM_CHUNK_SIZE):
                    chunk = hist_nodes[i:i+ALARM_CHUNK_SIZE]
                    hist_vals.extend(await client.read_values(chunk))

                for i in range(fetch_len):
                    history_list.append({
                        "code": int(hist_vals[i*6]),
                        "name": str(hist_vals[i*6+1]),
                        "message": str(hist_vals[i*6+2]),
                        "severity": int(hist_vals[i*6+3]),
                        "timestamp": str(hist_vals[i*6+4]),
                        "state": int(hist_vals[i*6+5]),
                    })

            return active_list, history_list
        except Exception as e:
            print(f"[OPCUA] Error fetching alarms: {e}")
            return [], []

    async def _run_loop(self):
        self._write_queue = asyncio.Queue()
        
        while self._running:
            if not self._enabled:
                self.connection_status.emit(False, "Disconnected by user")
                await asyncio.sleep(0.5)
                continue

            try:
                self.connection_status.emit(False, f"Connecting to {self.endpoint_url}...")
                async with Client(url=self.endpoint_url, timeout=OPCUA_CONNECT_TIMEOUT) as client:
                    self.connection_status.emit(True, f"Connected to CODESYS ({self.endpoint_url})")
                    self._need_reconnect = False

                    # Cache node objects for fast polling
                    nodes = {
                        # PAC States
                        "state": client.get_node(f"{BASE_NODE_PREFIX}pac.state"),
                        "mode": client.get_node(f"{BASE_NODE_PREFIX}pac.mode"),
                        "description": client.get_node(f"{BASE_NODE_PREFIX}pac.description"),
                        "abortType": client.get_node(f"{BASE_NODE_PREFIX}pac.abortType"),
                        "temp_hub": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.tempHub"),
                        "temp_oil": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.tempOil"),
                        "temp_cabinet": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.tempCabinet"),
                        "temp_cpu": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.tempCPU"),
                        "current_t1": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.current2T1"),
                        "current_t2": client.get_node(f"{BASE_NODE_PREFIX}pac.io.ai.current2T2"),
                        "power_supply_ok": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.supply230VOk"),

                        # PAC Version (HW & SW)
                        "pac_version_hw": client.get_node(f"{BASE_NODE_PREFIX}pac.version.HW"),
                        "pac_version_sw": client.get_node(f"{BASE_NODE_PREFIX}pac.version.SW"),

                        # Lubrication Status
                        "lub_tank1_ok": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub1OilLevelOk"),
                        "lub_piston_a1": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub1PistonAMoving"),
                        "lub_piston_b1": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub1PistonBMoving"),
                        "lub_piston_c1": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub1PistonCMoving"),
                        "lub_tank2_ok": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub2OilLevelOk"),
                        "lub_piston_a2": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub2PistonAMoving"),
                        "lub_piston_b2": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub2PistonBMoving"),
                        "lub_piston_c2": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.hubLub2PistonCMoving"),

                        # HPU Status (From MC) - Optional nodes under Common.WTG.hpu
                        "hpu_pressure": client.get_node(f"{BASE_NODE_PREFIX}WTG.hpu.pressure"),
                        "hpu_oil_level": client.get_node(f"{BASE_NODE_PREFIX}WTG.hpu.oilLevel"),
                        "hpu_temp": client.get_node(f"{BASE_NODE_PREFIX}WTG.hpu.temp"),
                        "hpu_state": client.get_node(f"{BASE_NODE_PREFIX}WTG.hpu.state"),
                        
                        # Commands
                        "cmd_start": client.get_node(f"{BASE_NODE_PREFIX}pac.cmd.start"),
                        "cmd_stop": client.get_node(f"{BASE_NODE_PREFIX}pac.cmd.stop"),
                        "cmd_reset": client.get_node(f"{BASE_NODE_PREFIX}pac.cmd.reset"),
                        "cmd_clear": client.get_node(f"{BASE_NODE_PREFIX}pac.cmd.clear"),
                        "cmd_abort": client.get_node(f"{BASE_NODE_PREFIX}pac.cmd.abort"),
                        "ack_all": client.get_node(f"{BASE_NODE_PREFIX}xAcknowledgeAll"),
                    }

                    # Blades nodes (0=A, 1=B, 2=C)
                    for i in range(3):
                        prefix = f"{BASE_NODE_PREFIX}blade[{i}]."
                        nodes[f"bld_{i}_pres_accu"] = client.get_node(f"{prefix}io.ai.presAccu")
                        nodes[f"bld_{i}_pres_piston"] = client.get_node(f"{prefix}io.ai.presPiston")
                        nodes[f"bld_{i}_pres_rod"] = client.get_node(f"{prefix}io.ai.presRod")
                        nodes[f"bld_{i}_cyl_pos"] = client.get_node(f"{prefix}io.ai.cylPos")
                        nodes[f"bld_{i}_spool_fb"] = client.get_node(f"{prefix}io.ai.spoolPosFb")
                        nodes[f"bld_{i}_pos_deg"] = client.get_node(f"{prefix}vars.posActDeg")
                        nodes[f"bld_{i}_rate_deg"] = client.get_node(f"{prefix}vars.rateActDeg")
                        nodes[f"bld_{i}_locked"] = client.get_node(f"{prefix}io.dIn.pitchLockEngaged")

                    # Common.PVturbineSpecific (9 nodes: 3 blades posOffDeg + 3 blades grd + 3 network fields)
                    for i in range(3):
                        p_node = client.get_node(f"{BASE_NODE_PREFIX}PVturbineSpecific.par[{i}].posOffDeg")
                        g_node = client.get_node(f"{BASE_NODE_PREFIX}PVturbineSpecific.par[{i}].grd")
                        nodes[f"par_{i}_posOffDeg"] = p_node
                        nodes[f"par_{i}_grd"] = g_node
                        nodes[f"PVturbineSpecific.par[{i}].posOffDeg"] = p_node
                        nodes[f"PVturbineSpecific.par[{i}].grd"] = g_node

                    net_h = client.get_node(f"{BASE_NODE_PREFIX}PVturbineSpecific.network.hostName")
                    net_i = client.get_node(f"{BASE_NODE_PREFIX}PVturbineSpecific.network.IPAddr")
                    net_s = client.get_node(f"{BASE_NODE_PREFIX}PVturbineSpecific.network.subnetMask")
                    nodes["net_hostName"] = net_h
                    nodes["net_hostname"] = net_h
                    nodes["PVturbineSpecific.network.hostName"] = net_h
                    nodes["net_IPAddr"] = net_i
                    nodes["net_ip"] = net_i
                    nodes["PVturbineSpecific.network.IPAddr"] = net_i
                    nodes["net_subnetMask"] = net_s
                    nodes["net_subnet"] = net_s
                    nodes["PVturbineSpecific.network.subnetMask"] = net_s

                    net_nodes = [
                        nodes["net_hostName"], nodes["net_IPAddr"], nodes["net_subnetMask"]
                    ]

                    has_net_nodes = True
                    try:
                        await nodes["net_hostName"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        has_net_nodes = False

                    par_nodes = [
                        nodes["par_0_posOffDeg"], nodes["par_0_grd"],
                        nodes["par_1_posOffDeg"], nodes["par_1_grd"],
                        nodes["par_2_posOffDeg"], nodes["par_2_grd"],
                    ]
                    has_par_nodes = True
                    try:
                        await nodes["par_0_posOffDeg"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        has_par_nodes = False


                    # Common.hmi (ManualPage PitchPosition, GRD temp, Buttons, and ColorControl)
                    # 1. Pitch Position Calibration (HMI buffer variables)
                    for i in range(3):
                        p_off_node = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.pitchposition[{i}].offsetpos")
                        nodes[f"hmi_pos_off_{i}"] = p_off_node
                        nodes[f"Common.hmi.fromHMI.manualPage.pitchposition[{i}].offsetpos"] = p_off_node

                    # 2. GRD Calibration (HMI buffer variables)
                    grd_names = ["bladeAgrdtemp", "bladeBgrdtemp", "bladeCgrdtemp"]
                    for i, gname in enumerate(grd_names):
                        g_temp_node = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.{gname}")
                        nodes[f"hmi_grd_temp_{i}"] = g_temp_node
                        nodes[f"Common.hmi.fromHMI.manualPage.{gname}"] = g_temp_node

                    # 3. Apply Handshake Buttons
                    nodes["hmi_apply_ppc"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyPPCSelection")
                    nodes["Common.hmi.buttons.applyPPCSelection"] = nodes["hmi_apply_ppc"]
                    nodes["hmi_apply_grd"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyGRDSelection")
                    nodes["Common.hmi.buttons.applyGRDSelection"] = nodes["hmi_apply_grd"]
                    nodes["hmi_update_network"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.updateNetwork")
                    nodes["Common.hmi.buttons.updateNetwork"] = nodes["hmi_update_network"]
                    nodes["allow_net_update"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromfile.allowNetworkUpt")
                    nodes["Common.hmi.fromfile.allowNetworkUpt"] = nodes["allow_net_update"]
                    nodes["hmi_req_manual"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.requestManualmode")
                    nodes["Common.hmi.buttons.requestManualmode"] = nodes["hmi_req_manual"]

                    # 4. Running parameters: Common.blade[i].par
                    for i in range(3):
                        nodes[f"bld_{i}_par_pos_off"] = client.get_node(f"{BASE_NODE_PREFIX}blade[{i}].par.posOffDeg")
                        nodes[f"Common.blade[{i}].par.posOffDeg"] = nodes[f"bld_{i}_par_pos_off"]
                        nodes[f"bld_{i}_par_grd"] = client.get_node(f"{BASE_NODE_PREFIX}blade[{i}].par.grd")
                        nodes[f"Common.blade[{i}].par.grd"] = nodes[f"bld_{i}_par_grd"]

                    # 5. Color control feedback
                    nodes["color_apply_app"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.colorControl.applyAPP")
                    nodes["color_apply_grd"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.colorControl.applyGRD")

                    # 6. HMI Blade Control & Lubrication Nodes
                    nodes["hmi_blade_a_sel"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxBladeA")
                    nodes["hmi_blade_b_sel"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxBladeB")
                    nodes["hmi_blade_c_sel"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxBladeC")
                    nodes["hmi_active_blade"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.activeBlade")

                    nodes["hmi_blade_safe_a"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.bladeASafe")
                    nodes["hmi_blade_safe_b"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.bladeBSafe")
                    nodes["hmi_blade_safe_c"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.bladeCSafe")
                    nodes["hmi_current_pos"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.CurrentPos")

                    nodes["hmi_fast_speed"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.fastSpeed")
                    nodes["hmi_slow_speed"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.slowSpeed")
                    nodes["hmi_fast_chosen"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxFastSpeedChosen")
                    nodes["hmi_slow_chosen"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxSlowSpeedChosen")

                    nodes["hmi_pitch_lock"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxPitchlock")
                    nodes["hmi_feather"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxFeather")
                    nodes["hmi_fine"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.manualPage.remoteboxFine")

                    # Lubrication buttons and pump DO feedback
                    nodes["hmi_activate_lub1"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.activateLub1")
                    nodes["hmi_activate_lub2"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.activateLub2")
                    nodes["pac_lub1_pump_on"] = client.get_node(f"{BASE_NODE_PREFIX}pac.io.dOut.hubLubPump1On")
                    nodes["pac_lub2_pump_on"] = client.get_node(f"{BASE_NODE_PREFIX}pac.io.dOut.hubLubPump2On")

                    # 7. Maintenance Page Nodes (HPU, Lub, PAC Valves & Prop, Buttons, SysReset)
                    nodes["hmi_req_pressure"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.requestPressure")
                    nodes["hmi_apply_hpu"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyHPUSelection")
                    nodes["hmi_reset_hpu"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.resetHPUSelection")

                    nodes["hmi_maint_lub1"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.PAC.io.dOut.hubLubPump1On")
                    nodes["hmi_maint_lub2"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.PAC.io.dOut.hubLubPump2On")
                    nodes["hmi_apply_lub"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyLubSelection")
                    nodes["hmi_reset_lub"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.resetLubSelection")

                    nodes["hmi_maint_pitch_lock"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.PAC.io.dOut.pitchLockValve")
                    nodes["hmi_apply_pitch_lock"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyPitchLockSelection")
                    nodes["hmi_reset_pitch_lock"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.resetPitchLockSelection")

                    for i in range(3):
                        for vk, field in MAINT_VALVE_PLC_FIELDS.items():
                            nodes[f"hmi_bld_{i}_{vk}"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.blades[{i}].io.dOut.{field}")
                        nodes[f"hmi_bld_{i}_spool_cmd"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.fromHMI.blades[{i}].io.ao.spoolPosCmd")

                    nodes["hmi_apply_pac"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.applyPACSelection")
                    nodes["hmi_reset_pac"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.resetPACSelection")

                    nodes["hmi_mode_select"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.modeSelect")
                    nodes["hmi_login_maint"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.loginMaintenance")
                    nodes["hmi_sys_reset"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.sysReset")
                    nodes["hmi_maint_btn_enb"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.maintenanceButtonEnb")
                    nodes["hmi_maint_help_enb"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.helpTextMaintenanceEnb")

                    # HMI Message Box Nodes
                    nodes["hmi_msgbox_btn_ok"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.btnOk")
                    nodes["hmi_msgbox_btn_abort"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.btnAbort")
                    nodes["hmi_msgbox_status"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.status")
                    nodes["hmi_msgbox_header"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.header")
                    nodes["hmi_msgbox_content"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.content")
                    nodes["hmi_msgbox_btn_ok_status"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.btnOkStatus")
                    nodes["hmi_msgbox_btn_abort_status"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.btnAbortStatus")
                    nodes["hmi_msgbox_icon"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.msgBox.icon")

                    # HMI Main Start & Abort buttons and status
                    nodes["hmi_btn_start"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.start")
                    nodes["hmi_btn_abort"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.buttons.abort")
                    nodes["hmi_status_abort_btn"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.status.abortButton")
                    nodes["hmi_status_start_btn"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.status.startButton")

                    has_hmi_nodes = True
                    try:
                        await nodes["hmi_apply_ppc"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        has_hmi_nodes = False

                    has_pac_nodes = True
                    try:
                        await nodes["state"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        has_pac_nodes = False

                    # Check if optional ack_all node is published in CODESYS symbol config
                    try:
                        await nodes["ack_all"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        nodes["ack_all"] = None

                    # Check if optional WTG.hpu nodes are published
                    try:
                        await nodes["hpu_pressure"].read_attribute(ua.AttributeIds.NodeId)
                    except Exception:
                        nodes["hpu_pressure"] = None
                        nodes["hpu_oil_level"] = None
                        nodes["hpu_temp"] = None
                        nodes["hpu_state"] = None

                    alarm_poll_counter = 0
                    last_act_cnt = -1
                    last_hist_cnt = -1

                    while self._running and not self._need_reconnect and self._enabled:
                        # 1. Process pending write commands
                        while not self._write_queue.empty():
                            cmd_name, val = self._write_queue.get_nowait()
                            target_node = nodes.get(cmd_name)
                            if target_node is None:
                                if cmd_name == "ack_all":
                                    print("[OPCUA] [提示] CODESYS 符号配置未发布 'Common.xAcknowledgeAll'，跳过 PLC 写入（本地报警已确认）。可在 CODESYS 符号配置中勾选并在线变更。")
                                continue

                            if not has_net_nodes and cmd_name.startswith("net_"):
                                err_msg = f"CODESYS 符号配置未发布节点 (BadNodeIdUnknown): {cmd_name}"
                                print(f"[OPCUA] [警告] {err_msg}")
                                self.command_result.emit(cmd_name, False, err_msg)
                                continue

                            if not has_par_nodes and cmd_name.startswith("par_"):
                                continue


                            try:
                                c_clean = cmd_name.lower().replace("_", "")
                                if "posoffdeg" in c_clean or "offsetpos" in c_clean or "posoff" in c_clean or "speed" in c_clean or "spoolcmd" in c_clean:
                                    dv = ua.DataValue(ua.Variant(float(val), ua.VariantType.Float))
                                    await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote {cmd_name} = {val} (Float)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                elif "activeblade" in c_clean:
                                    try:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.Int16))
                                        await target_node.write_value(dv)
                                    except Exception:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.Byte))
                                        await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote {cmd_name} = {val} (Int16/Enum)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                elif "activatelub" in c_clean or "requestmanualmode" in c_clean or "reqmanual" in c_clean:
                                    try:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.Int16))
                                        await target_node.write_value(dv)
                                    except Exception:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.UInt16))
                                        await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote state/mode command {cmd_name} = {val} (Int16)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                elif "apply" in c_clean or "button" in c_clean or "btn" in c_clean or "updatenetwork" in c_clean or "sysreset" in c_clean or "hmireset" in c_clean or "modeselect" in c_clean or "loginmaint" in c_clean or "msgbox" in c_clean:
                                    try:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.Int16))
                                        await target_node.write_value(dv)
                                    except Exception:
                                        dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.UInt16))
                                        await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote button command {cmd_name} = {val} (Int16)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                    if int(val) == 1:
                                        asyncio.create_task(self._pulse_reset_int(target_node, cmd_name))
                                elif "grd" in c_clean or "grdtemp" in c_clean:
                                    dv = ua.DataValue(ua.Variant(int(val), ua.VariantType.UInt32))
                                    await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote {cmd_name} = {val} (UInt32)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                elif cmd_name.startswith("net_") or "hostname" in c_clean or "ipaddr" in c_clean or "subnet" in c_clean or "network." in cmd_name:
                                    dv = ua.DataValue(ua.Variant(str(val), ua.VariantType.String))
                                    await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote {cmd_name} = '{val}' (String)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                else:
                                    dv = ua.DataValue(ua.Variant(bool(val), ua.VariantType.Boolean))
                                    await target_node.write_value(dv)
                                    print(f"[OPCUA] Wrote command {cmd_name} = {val} (Boolean)")
                                    self.command_result.emit(cmd_name, True, "OK")
                                    if val is True and cmd_name.startswith("cmd_"):
                                        asyncio.create_task(self._pulse_reset(target_node, cmd_name))
                            except Exception as we:
                                write_err = OpcUaWriteError(cmd_name, val, we)
                                self.last_write_error = write_err
                                logger.error(
                                    f"[OPCUA 写入异常 / Write Error] 指令 '{cmd_name}' 写入失败 (值={val}, 节点={target_node}): {we}",
                                    exc_info=True
                                )
                                print(f"[OPCUA] Error writing command {cmd_name}: {we}")
                                self.command_result.emit(cmd_name, False, str(we))
                                if OPCUA_STRICT_RAISE_EXCEPTIONS:
                                    raise write_err

                        # 2. Poll read values
                        data_payload: Dict[str, Any] = {}
                        data_payload["has_network_nodes"] = has_net_nodes
                        try:
                            # Read PAC state (if Common.pac is published)
                            if has_pac_nodes:
                                try:
                                    data_payload["state"] = await nodes["state"].read_value()
                                    data_payload["mode"] = await nodes["mode"].read_value()
                                    data_payload["description"] = await nodes["description"].read_value()
                                    data_payload["abortType"] = await nodes["abortType"].read_value()
                                except Exception:
                                    pass

                                # Temperatures & Power
                                try:
                                    data_payload["temp_hub"] = float(await nodes["temp_hub"].read_value())
                                    data_payload["temp_oil"] = float(await nodes["temp_oil"].read_value())
                                    data_payload["temp_cabinet"] = float(await nodes["temp_cabinet"].read_value())
                                    data_payload["cpu_temp"] = float(await nodes["temp_cpu"].read_value())
                                    data_payload["current_t1"] = float(await nodes["current_t1"].read_value())
                                    data_payload["current_t2"] = float(await nodes["current_t2"].read_value())
                                    data_payload["power_supply_ok"] = bool(await nodes["power_supply_ok"].read_value())
                                except Exception:
                                    pass

                                # PAC Version (HW & SW)
                                try:
                                    data_payload["pac_version_hw"] = await nodes["pac_version_hw"].read_value()
                                    data_payload["pac_version_sw"] = await nodes["pac_version_sw"].read_value()
                                except Exception:
                                    pass

                                # Lubrication Status
                                try:
                                    data_payload["lub_tank1_ok"] = bool(await nodes["lub_tank1_ok"].read_value())
                                    data_payload["lub_piston_a1"] = bool(await nodes["lub_piston_a1"].read_value())
                                    data_payload["lub_piston_b1"] = bool(await nodes["lub_piston_b1"].read_value())
                                    data_payload["lub_piston_c1"] = bool(await nodes["lub_piston_c1"].read_value())
                                    data_payload["lub_tank2_ok"] = bool(await nodes["lub_tank2_ok"].read_value())
                                    data_payload["lub_piston_a2"] = bool(await nodes["lub_piston_a2"].read_value())
                                    data_payload["lub_piston_b2"] = bool(await nodes["lub_piston_b2"].read_value())
                                    data_payload["lub_piston_c2"] = bool(await nodes["lub_piston_c2"].read_value())
                                except Exception:
                                    pass

                            # HPU Status (if available in PLC)
                            if nodes.get("hpu_pressure") is not None:
                                try:
                                    data_payload["hpu_pressure"] = float(await nodes["hpu_pressure"].read_value())
                                    data_payload["hpu_oil_level"] = float(await nodes["hpu_oil_level"].read_value())
                                    data_payload["hpu_temp"] = float(await nodes["hpu_temp"].read_value())
                                    st_val = await nodes["hpu_state"].read_value()
                                    hpu_map = {0: "Stopped", 1: "Execute", 2: "Ready"}
                                    data_payload["hpu_state"] = hpu_map.get(st_val, str(st_val))
                                except Exception:
                                    pass

                            # Read 3 blades
                            for i in range(3):
                                bld_dict = {}
                                bld_dict["pres_accu"] = float(await nodes[f"bld_{i}_pres_accu"].read_value())
                                bld_dict["pres_piston"] = float(await nodes[f"bld_{i}_pres_piston"].read_value())
                                bld_dict["pres_rod"] = float(await nodes[f"bld_{i}_pres_rod"].read_value())
                                bld_dict["cyl_pos"] = float(await nodes[f"bld_{i}_cyl_pos"].read_value())
                                bld_dict["spool_pos_fb"] = float(await nodes[f"bld_{i}_spool_fb"].read_value())
                                bld_dict["pos_act_deg"] = float(await nodes[f"bld_{i}_pos_deg"].read_value())
                                bld_dict["rate_act_deg"] = float(await nodes[f"bld_{i}_rate_deg"].read_value())
                                bld_dict["pitch_lock_engaged"] = bool(await nodes[f"bld_{i}_locked"].read_value())
                                data_payload[f"blade_{i}"] = bld_dict

                            # 1. Read Common.PVturbineSpecific.network independently and reliably
                            data_payload["has_network_nodes"] = has_net_nodes
                            if has_net_nodes:
                                try:
                                    net_vals = await client.read_values(net_nodes)
                                    if net_vals[0] is not None:
                                        data_payload["net_hostName"] = str(net_vals[0])
                                        data_payload["net_hostname"] = str(net_vals[0])
                                    if net_vals[1] is not None:
                                        data_payload["net_IPAddr"] = str(net_vals[1])
                                        data_payload["net_ip"] = str(net_vals[1])
                                    if net_vals[2] is not None:
                                        data_payload["net_subnetMask"] = str(net_vals[2])
                                        data_payload["net_subnet"] = str(net_vals[2])
                                    data_payload["has_network_nodes"] = True
                                except Exception as ne:
                                    print(f"[OPCUA] Error reading net_nodes: {ne}")
                                    data_payload["has_network_nodes"] = False

                            # 2. Read Common.PVturbineSpecific.par safely without throwing on None
                            if has_par_nodes:
                                try:
                                    p_vals = await client.read_values(par_nodes)
                                    for i in range(3):
                                        if p_vals[i*2] is not None:
                                            data_payload[f"par_{i}_posOffDeg"] = float(p_vals[i*2])
                                        if p_vals[i*2+1] is not None:
                                            data_payload[f"par_{i}_grd"] = int(p_vals[i*2+1])
                                except Exception:
                                    pass


                            # Read Common.blade[i].par and Common.hmi buffer nodes if available
                            if has_hmi_nodes:
                                try:
                                    for i in range(3):
                                        if f"bld_{i}_par_pos_off" in nodes:
                                            data_payload[f"bld_{i}_par_pos_off"] = float(await nodes[f"bld_{i}_par_pos_off"].read_value())
                                        if f"bld_{i}_par_grd" in nodes:
                                            data_payload[f"bld_{i}_par_grd"] = int(await nodes[f"bld_{i}_par_grd"].read_value())
                                        if f"hmi_pos_off_{i}" in nodes:
                                            data_payload[f"hmi_pos_off_{i}"] = float(await nodes[f"hmi_pos_off_{i}"].read_value())
                                        if f"hmi_grd_temp_{i}" in nodes:
                                            data_payload[f"hmi_grd_temp_{i}"] = int(await nodes[f"hmi_grd_temp_{i}"].read_value())
                                    if "color_apply_app" in nodes:
                                        data_payload["color_apply_app"] = bool(await nodes["color_apply_app"].read_value())
                                    if "color_apply_grd" in nodes:
                                        data_payload["color_apply_grd"] = bool(await nodes["color_apply_grd"].read_value())

                                    # HMI Blade Control Telemetry
                                    if "hmi_active_blade" in nodes:
                                        data_payload["hmi_active_blade"] = int(await nodes["hmi_active_blade"].read_value())
                                    if "hmi_current_pos" in nodes:
                                        data_payload["hmi_current_pos"] = float(await nodes["hmi_current_pos"].read_value())
                                    if "hmi_blade_safe_a" in nodes:
                                        data_payload["hmi_blade_safe_a"] = bool(await nodes["hmi_blade_safe_a"].read_value())
                                    if "hmi_blade_safe_b" in nodes:
                                        data_payload["hmi_blade_safe_b"] = bool(await nodes["hmi_blade_safe_b"].read_value())
                                    if "hmi_blade_safe_c" in nodes:
                                        data_payload["hmi_blade_safe_c"] = bool(await nodes["hmi_blade_safe_c"].read_value())
                                    if "hmi_fast_speed" in nodes:
                                        data_payload["hmi_fast_speed"] = float(await nodes["hmi_fast_speed"].read_value())
                                    if "hmi_slow_speed" in nodes:
                                        data_payload["hmi_slow_speed"] = float(await nodes["hmi_slow_speed"].read_value())
                                    if "hmi_fast_chosen" in nodes:
                                        data_payload["hmi_fast_chosen"] = bool(await nodes["hmi_fast_chosen"].read_value())
                                    if "hmi_slow_chosen" in nodes:
                                        data_payload["hmi_slow_chosen"] = bool(await nodes["hmi_slow_chosen"].read_value())
                                    if "hmi_pitch_lock" in nodes:
                                        data_payload["hmi_pitch_lock"] = bool(await nodes["hmi_pitch_lock"].read_value())
                                    if has_pac_nodes and "pac_lub1_pump_on" in nodes:
                                        data_payload["pac_lub1_pump_on"] = bool(await nodes["pac_lub1_pump_on"].read_value())
                                    if has_pac_nodes and "pac_lub2_pump_on" in nodes:
                                        data_payload["pac_lub2_pump_on"] = bool(await nodes["pac_lub2_pump_on"].read_value())
                                    if "hmi_maint_btn_enb" in nodes:
                                        data_payload["maint_btn_enb"] = int(await nodes["hmi_maint_btn_enb"].read_value())
                                    if "hmi_maint_help_enb" in nodes:
                                        data_payload["maint_help_enb"] = int(await nodes["hmi_maint_help_enb"].read_value())
                                    if "hmi_msgbox_status" in nodes:
                                        data_payload["msgbox_status"] = int(await nodes["hmi_msgbox_status"].read_value())
                                    if "hmi_msgbox_header" in nodes:
                                        data_payload["msgbox_header"] = str(await nodes["hmi_msgbox_header"].read_value())
                                    if "hmi_msgbox_content" in nodes:
                                        data_payload["msgbox_content"] = str(await nodes["hmi_msgbox_content"].read_value())
                                    if "hmi_msgbox_btn_ok" in nodes:
                                        data_payload["msgbox_btn_ok"] = int(await nodes["hmi_msgbox_btn_ok"].read_value())
                                    if "hmi_msgbox_btn_abort" in nodes:
                                        data_payload["msgbox_btn_abort"] = int(await nodes["hmi_msgbox_btn_abort"].read_value())
                                    if "hmi_status_abort_btn" in nodes:
                                        data_payload["plc_abort_btn_status"] = int(await nodes["hmi_status_abort_btn"].read_value())
                                    if "hmi_status_start_btn" in nodes:
                                        data_payload["plc_start_btn_status"] = int(await nodes["hmi_status_start_btn"].read_value())
                                except Exception:
                                    pass

                            self.data_updated.emit(data_payload)
                            self.frames_received += 1

                            # 3. Poll Alarms (every ~1s or when counts change)
                            alarm_poll_counter += 1
                            if alarm_poll_counter >= ALARM_POLL_DECIMATION or last_act_cnt == -1:
                                alarm_poll_counter = 0
                                try:
                                    core_prefix = f"{BASE_NODE_PREFIX}gAlarmCoreTable."
                                    act_cnt = int(await client.get_node(f"{core_prefix}ActiveAlarmsCount").read_value())
                                    hist_cnt = int(await client.get_node(f"{BASE_NODE_PREFIX}gHistoryAlarmLog.CurrentCount").read_value())
                                    if act_cnt != last_act_cnt or hist_cnt != last_hist_cnt:
                                        active_list, history_list = await self._fetch_alarms(client)
                                        self.alarms_updated.emit(active_list, history_list)
                                        last_act_cnt = act_cnt
                                        last_hist_cnt = hist_cnt
                                except Exception:
                                    pass

                        except Exception as re:
                            err_str = str(re)
                            if "BadNodeIdUnknown" in err_str or "BadSession" in err_str:
                                logger.info("[OPCUA] 检测到 CODESYS PLC 重启或执行在线变更 (Online Change)，正在重新同步节点...")
                                print("[OPCUA] [通知] 检测到 CODESYS PLC 重启或执行在线变更 (Online Change)，正在重新同步节点...")
                            else:
                                logger.warning(f"[OPCUA] Read cycle error: {re}")
                                print(f"[OPCUA] Read cycle error: {re}")
                            break  # reconnect and refresh node handles

                        await asyncio.sleep(self.poll_interval)

            except Exception as conn_err:
                logger.warning(f"[OPCUA] Connection failed or dropped: {conn_err}")
                self.connection_status.emit(False, f"Offline ({conn_err})")
                await asyncio.sleep(OPCUA_RETRY_INTERVAL)  # Retry delay

    def start_loop(self):
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_loop())
        finally:
            self._loop.close()


class OpcUaService(QThread):
    """
    QThread wrapper providing high-level interface to the OPC UA worker
    """
    data_received = pyqtSignal(dict)
    alarms_received = pyqtSignal(list, list)  # (active_alarms, history_alarms)
    connection_changed = pyqtSignal(bool, str)
    command_result = pyqtSignal(str, bool, str)  # (cmd_name, is_success, message)

    def __init__(self, endpoint_url: str = OPCUA_ENDPOINT, poll_interval: float = OPCUA_POLL_INTERVAL):
        super().__init__()
        self.endpoint_url = endpoint_url
        self.poll_interval = poll_interval
        self.worker: Optional[OpcUaWorker] = None
        self.is_connected = False

    def run(self):
        if Client is None:
            self.connection_changed.emit(False, "asyncua library not installed")
            return

        self.worker = OpcUaWorker(self.endpoint_url, self.poll_interval)
        self.worker.data_updated.connect(self.data_received.emit)
        self.worker.alarms_updated.connect(self.alarms_received.emit)
        self.worker.connection_status.connect(self._on_connection_status)
        self.worker.command_result.connect(self.command_result.emit)
        self.worker.start_loop()

    def _on_connection_status(self, connected: bool, msg: str):
        self.is_connected = connected
        self.connection_changed.emit(connected, msg)

    def stop(self):
        if self.worker:
            self.worker.stop()
        self.quit()
        self.wait(OPCUA_DISCONNECT_WAIT_MS)

    @property
    def last_write_error(self) -> Optional[Exception]:
        """Returns the most recent command write error, if any."""
        return getattr(self.worker, "last_write_error", None) if self.worker else None

    # Command sending shortcuts
    def send_start(self):
        """Send Start command: Pulse Common.hmi.buttons.start = 1 and clear command"""
        if self.worker:
            self.worker.enqueue_command("hmi_btn_start", 1)
            self.worker.enqueue_command("cmd_clear", True)
            self.worker.enqueue_command("cmd_start", True)

    def send_stop(self):
        """Send Stop command: Pulse Common.hmi.buttons.abort = 1 and abort command"""
        if self.worker:
            self.worker.enqueue_command("hmi_btn_abort", 1)
            self.worker.enqueue_command("cmd_abort", True)
            self.worker.enqueue_command("cmd_stop", True)

    def send_reset(self):
        if self.worker:
            self.worker.enqueue_command("cmd_reset", True)

    def send_clear(self):
        if self.worker:
            self.worker.enqueue_command("cmd_clear", True)

    def send_ack_all(self):
        if self.worker:
            self.worker.enqueue_command("ack_all", True)

    @property
    def frames_received(self) -> int:
        return self.worker.frames_received if self.worker else 0

    def update_connection(self, endpoint_url: str, poll_interval: float = OPCUA_POLL_INTERVAL):
        self.endpoint_url = endpoint_url
        self.poll_interval = poll_interval
        if self.worker:
            self.worker.update_endpoint(endpoint_url, poll_interval)

    def disconnect_client(self):
        if self.worker:
            self.worker.set_enabled(False)

    def connect_client(self):
        if self.worker:
            self.worker.set_enabled(True)

    # Common.hmi / Common.PVturbineSpecific Offset and GRD write methods
    def write_hmi_blade_offset(self, blade_idx: int, val: float):
        """Write Common.hmi.fromHMI.manualPage.pitchposition[idx].offsetpos (Float)"""
        if self.worker and 0 <= blade_idx < 3:
            self.worker.write_hmi_blade_offset(blade_idx, val)

    def apply_pitch_position_calib(self):
        """Pulse Common.hmi.buttons.applyPPCSelection = 1"""
        if self.worker:
            self.worker.apply_pitch_position_calib()

    def write_hmi_blade_grd(self, blade_idx: int, val: int):
        """Write Common.hmi.fromHMI.manualPage.blade<A/B/C>grdtemp (UInt32)"""
        if self.worker and 0 <= blade_idx < 3:
            self.worker.write_hmi_blade_grd(blade_idx, val)

    def apply_grd_calib(self):
        """Pulse Common.hmi.buttons.applyGRDSelection = 1"""
        if self.worker:
            self.worker.apply_grd_calib()

    def write_blade_offset(self, blade_idx: int, val: float):
        """Write blade offset to HMI buffer and PVturbineSpecific"""
        if self.worker and 0 <= blade_idx < 3:
            self.worker.write_blade_offset(blade_idx, val)

    def write_blade_grd(self, blade_idx: int, val: int):
        """Write blade GRD to HMI buffer and PVturbineSpecific"""
        if self.worker and 0 <= blade_idx < 3:
            self.worker.write_blade_grd(blade_idx, val)

    def write_network_hostname(self, val: str):
        """Write Common.PVturbineSpecific.network.hostName (String)"""
        if self.worker:
            self.worker.write_network_hostname(val)

    def write_network_ip(self, val: str):
        """Write Common.PVturbineSpecific.network.IPAddr (String)"""
        if self.worker:
            self.worker.write_network_ip(val)

    def write_network_subnet(self, val: str):
        """Write Common.PVturbineSpecific.network.subnetMask (String)"""
        if self.worker:
            self.worker.write_network_subnet(val)

    def write_network_settings(self, hostname: str, ip: str, subnet: str):
        """Write all 3 network settings to Common.PVturbineSpecific.network"""
        if self.worker:
            self.worker.write_network_settings(hostname, ip, subnet)

    # HMI Blade Control & Lubrication methods
    def select_blade(self, blade_idx: int):
        """Select active blade (0=A, 1=B, 2=C)"""
        if self.worker:
            self.worker.select_blade(blade_idx)

    def set_pitch_lock(self, disengaged: bool):
        """Set pitch lock state: True = open/disengage, False = engaged/locked"""
        if self.worker:
            self.worker.set_pitch_lock(disengaged)

    def set_speed_mode(self, mode: str):
        """Set fast/slow speed mode ('FAST' or 'SLOW')"""
        if self.worker:
            self.worker.set_speed_mode(mode)

    def write_fast_speed(self, speed: float):
        """Write fast speed (deg/s)"""
        if self.worker:
            self.worker.write_fast_speed(speed)

    def write_slow_speed(self, speed: float):
        """Write slow speed (deg/s)"""
        if self.worker:
            self.worker.write_slow_speed(speed)

    def set_move_feather(self, pressed: bool):
        """Jog feather (Hold to move)"""
        if self.worker:
            self.worker.set_move_feather(pressed)

    def set_move_fine(self, pressed: bool):
        """Jog fine (Hold to move)"""
        if self.worker:
            self.worker.set_move_fine(pressed)

    def set_lubrication_pump(self, pump_no: int, active: bool):
        """Activate/Deactivate lubrication pump 1 or 2"""
        if self.worker:
            self.worker.set_lubrication_pump(pump_no, active)

    def request_manual_mode(self):
        """Request manual mode in PLC"""
        if self.worker:
            self.worker.request_manual_mode()

    def request_producing_mode(self):
        """Exit manual mode and return to producing mode in PLC"""
        if self.worker:
            self.worker.request_producing_mode()

    # Maintenance Page Methods
    def apply_maint_hpu(self, request_pressure: bool):
        """Apply HPU pressure buildup request in maintenance mode"""
        if self.worker:
            self.worker.apply_maint_hpu(request_pressure)

    def reset_maint_hpu(self):
        """Reset HPU selection in maintenance mode"""
        if self.worker:
            self.worker.reset_maint_hpu()

    def apply_maint_lub(self, pump1: bool, pump2: bool):
        """Apply lubrication pump 1 & 2 test in maintenance mode"""
        if self.worker:
            self.worker.apply_maint_lub(pump1, pump2)

    def reset_maint_lub(self):
        """Reset lubrication selection in maintenance mode"""
        if self.worker:
            self.worker.reset_maint_lub()

    def apply_maint_pac(self, valves_by_blade: dict, spool_cmds: list):
        """Apply 8 directional valves and proportional spool position command for 3 blades"""
        if self.worker:
            self.worker.apply_maint_pac(valves_by_blade, spool_cmds)

    def reset_maint_pac(self):
        """Reset all PAC valve selections and proportional commands"""
        if self.worker:
            self.worker.reset_maint_pac()

    def request_maintenance_mode(self):
        """Pulse Common.hmi.buttons.modeSelect = 1 to request maintenance mode"""
        if self.worker:
            self.worker.request_maintenance_mode()

    def login_maintenance(self):
        """Pulse Common.hmi.buttons.loginMaintenance = 1"""
        if self.worker:
            self.worker.login_maintenance()

    def send_plc_sys_reset(self):
        """Pulse Common.hmi.buttons.sysReset = 1 to request PLC soft restart"""
        if self.worker:
            self.worker.send_plc_sys_reset()

    def send_msgbox_ok(self):
        """Pulse Common.hmi.msgBox.btnOk = 1"""
        if self.worker:
            self.worker.send_msgbox_ok()

    def send_msgbox_abort(self):
        """Pulse Common.hmi.msgBox.btnAbort = 1"""
        if self.worker:
            self.worker.send_msgbox_abort()

    def exit_maintenance_mode(self):
        """Set Common.hmi.buttons.modeSelect = 0 to exit maintenance mode"""
        if self.worker:
            self.worker.exit_maintenance_mode()

    # Aliases
    write_par_pos_off = write_blade_offset
    write_par_grd = write_blade_grd
    write_net_hostname = write_network_hostname
    write_net_ip = write_network_ip
    write_net_subnet = write_network_subnet
