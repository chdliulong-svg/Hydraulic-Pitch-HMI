# -*- coding: utf-8 -*-
"""
OPC UA Client Service for Hydraulic Pitch Control System
Connects asynchronously to CODESYS OPC UA Server (opc.tcp://127.0.0.1:4840)
Reads live IEC variables from 'ns=4;s=|var|CODESYS Control Win V3.PAC.Common.*'
and emits Qt signals to update HMI models in real-time.
"""

import asyncio
import math
import time
import queue
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple, Callable
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QTimer

from config import (
    OPCUA_ENDPOINT, OPCUA_POLL_INTERVAL, BASE_NODE_PREFIX, SIM_NODE_PREFIX,
    OPCUA_CONNECT_TIMEOUT, OPCUA_RETRY_INTERVAL,
    OPCUA_PULSE_RESET_DELAY, OPCUA_PULSE_RESET_INT_DELAY, OPCUA_DISCONNECT_WAIT_MS,
    ALARM_POLL_DECIMATION, ALARM_CHUNK_SIZE, ALARM_HISTORY_MAX_FETCH,
    GRD_MIN_VALUE, GRD_MAX_VALUE,
    OFFSET_MIN_DEG, OFFSET_MAX_DEG,
    OPCUA_STRICT_RAISE_EXCEPTIONS,
    STATE_ABORTED, STATE_STOPPED, STATE_IDLE,
    TELEMETRY_GLITCH_FILTER_ENABLED, TELEMETRY_GLITCH_MAX_HOLD_FRAMES
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


def cyl_mm_to_pitch_deg(cyl_mm: float, pos_off_deg: float = -2.10, mech_off_deg: float = -1.0) -> float:
    """
    Standard PAC IEC 61131-3 CylToPitch kinematic conversion:
    Calculates pitch angle (deg) from hydraulic cylinder stroke (mm).
    Kinematics parameters match PAC CylToPitch FB & PRG_main_pac.st:
      rc = 0.669 m (crank radius)
      rp = 1.730 m (pitch radius)
      lCylMin = 1.401 m (minimum retracted cylinder length)
      mechOffSetDeg = -1.0 deg (mechanical mounting offset)
      posOffDeg = calibration zero offset (-2.10 deg default)
    """
    rc = 0.669
    rp = 1.730
    lCylMin = 1.401
    cyl_m = max(0.0, float(cyl_mm)) / 1000.0
    try:
        start_angle = math.acos((rc**2 + rp**2 - lCylMin**2) / (2 * rc * rp))
        ratio = (rc**2 + rp**2 - (lCylMin + cyl_m)**2) / (2 * rc * rp)
        ratio = max(-1.0, min(1.0, ratio))
        pitch_pos_rad = math.acos(ratio) - start_angle
        return pitch_pos_rad * (180.0 / math.pi) + pos_off_deg + mech_off_deg
    except Exception:
        return 0.0


@dataclass(frozen=True)
class NodeSpec:
    """Declarative specification for OPC UA command writes"""
    vtype: Any
    is_pulse: bool = False
    pulse_delay: float = OPCUA_PULSE_RESET_DELAY
    pulse_type: str = "bool"  # "bool" or "int"
    converter: Optional[Callable[[Any], Any]] = None


def _make_node_spec_registry() -> Dict[str, NodeSpec]:
    """Build declarative mapping of known OPC UA write nodes and their properties"""
    if ua is None:
        return {}

    specs: Dict[str, NodeSpec] = {}

    # 1. Boolean commands with pulse auto-reset (0.2s)
    for c in ["cmd_start", "cmd_clear", "cmd_abort", "cmd_reset", "ack_all"]:
        specs[c] = NodeSpec(ua.VariantType.Boolean, is_pulse=True, pulse_delay=OPCUA_PULSE_RESET_DELAY, pulse_type="bool", converter=bool)

    # 2. Int16 button / handshake pulse commands (0.5s auto-reset to 0 on 1)
    for c in [
        "hmi_btn_start", "hmi_btn_abort", "hmi_btn_reset", "hmi_btn_ack_all",
        "hmi_apply_ppc", "hmi_apply_grd", "hmi_update_network",
        "hmi_apply_hpu", "hmi_reset_hpu", "hmi_apply_lub", "hmi_reset_lub",
        "hmi_apply_pac", "hmi_reset_pac", "hmi_apply_pitch_lock", "hmi_reset_pitch_lock",
        "hmi_login_maint", "hmi_sys_reset", "hmi_msgbox_btn_ok", "hmi_msgbox_btn_abort"
    ]:
        specs[c] = NodeSpec(ua.VariantType.Int16, is_pulse=True, pulse_delay=OPCUA_PULSE_RESET_INT_DELAY, pulse_type="int", converter=int)

    # 3. Sustained Int16 / Enum commands
    specs["hmi_active_blade"] = NodeSpec(ua.VariantType.Int16, is_pulse=False, converter=int)
    specs["hmi_activate_lub1"] = NodeSpec(ua.VariantType.Int16, is_pulse=False, converter=int)
    specs["hmi_activate_lub2"] = NodeSpec(ua.VariantType.Int16, is_pulse=False, converter=int)
    specs["hmi_req_manual"] = NodeSpec(ua.VariantType.Int16, is_pulse=False, converter=int)
    specs["hmi_mode_select"] = NodeSpec(ua.VariantType.Int16, is_pulse=False, converter=int)

    # 4. Sustained Float commands (Speed, calibration offsets, proportional valve spool commands)
    specs["hmi_fast_speed"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
    specs["hmi_slow_speed"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
    for i in range(3):
        specs[f"hmi_pos_off_{i}"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
        specs[f"par_{i}_posOffDeg"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
        specs[f"bld_{i}_par_pos_off"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
        specs[f"hmi_bld_{i}_spool_cmd"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
        specs[f"Common.blade[{i}].par.posOffDeg"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
        specs[f"Common.hmi.fromHMI.manualPage.pitchposition[{i}].offsetpos"] = NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)

    # 5. Sustained UInt32 commands (GRD calibration degrees)
    grd_names = ["bladeAgrdtemp", "bladeBgrdtemp", "bladeCgrdtemp"]
    for i in range(3):
        specs[f"hmi_grd_temp_{i}"] = NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)
        specs[f"par_{i}_grd"] = NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)
        specs[f"bld_{i}_par_grd"] = NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)
        specs[f"Common.blade[{i}].par.grd"] = NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)
        specs[f"Common.hmi.fromHMI.manualPage.{grd_names[i]}"] = NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)

    # 6. String commands (Network configuration)
    for c in ["net_hostName", "net_IPAddr", "net_subnetMask", "net_hostname", "net_ip", "net_subnet"]:
        specs[c] = NodeSpec(ua.VariantType.String, is_pulse=False, converter=str)

    # 7. Boolean sustained commands (Valves, selector switches, jogging commands)
    for c in [
        "allow_net_update", "hmi_pitch_lock", "hmi_maint_pitch_lock",
        "hmi_fast_chosen", "hmi_slow_chosen",
        "hmi_blade_a_sel", "hmi_blade_b_sel", "hmi_blade_c_sel",
        "hmi_feather", "hmi_fine",
        "hmi_req_pressure", "hmi_maint_lub1", "hmi_maint_lub2",
    ]:
        specs[c] = NodeSpec(ua.VariantType.Boolean, is_pulse=False, converter=bool)

    # 8. Directional valves (8 valves x 3 blades)
    for b_idx in range(3):
        for vk in MAINTENANCE_VALVES:
            specs[f"hmi_bld_{b_idx}_{vk}"] = NodeSpec(ua.VariantType.Boolean, is_pulse=False, converter=bool)

    return specs


def resolve_node_spec(cmd_name: str, registry: Dict[str, NodeSpec]) -> NodeSpec:
    """Resolves write specification using registry lookup with pattern fallbacks"""
    if cmd_name in registry:
        return registry[cmd_name]

    if ua is None:
        return NodeSpec(None, is_pulse=False)

    c_clean = cmd_name.lower().replace("_", "")
    if "spoolcmd" in c_clean or "posoff" in c_clean or "offsetpos" in c_clean or "speed" in c_clean:
        return NodeSpec(ua.VariantType.Float, is_pulse=False, converter=float)
    if "grd" in c_clean:
        return NodeSpec(ua.VariantType.UInt32, is_pulse=False, converter=int)
    if cmd_name.startswith("net_") or "hostname" in c_clean or "ipaddr" in c_clean or "subnet" in c_clean or "network." in cmd_name:
        return NodeSpec(ua.VariantType.String, is_pulse=False, converter=str)
    if "btn" in c_clean or "button" in c_clean or "apply" in c_clean or "reset" in c_clean or "msgbox" in c_clean:
        return NodeSpec(ua.VariantType.Int16, is_pulse=True, pulse_delay=OPCUA_PULSE_RESET_INT_DELAY, pulse_type="int", converter=int)
    if cmd_name.startswith("cmd_"):
        return NodeSpec(ua.VariantType.Boolean, is_pulse=True, pulse_delay=OPCUA_PULSE_RESET_DELAY, pulse_type="bool", converter=bool)

    return NodeSpec(ua.VariantType.Boolean, is_pulse=False, converter=bool)


class TelemetryGlitchFilter:
    """
    方案 2: 上位机采集平滑与零点毛刺防抖过滤器 (Anti-Glitch / Zero-Drop Debounce Filter)

    解决在数字孪生仿真机 (pitchsim) 与下位机 PLC 联合运行场景下，
    由于 PLC 任务周期 (MainTask 10ms) 内部时序竞争：
    PRG_main_pac（未插物理硬件传感器通道置零）与 PRG_pitch_sim（仿真值覆盖注入）
    在 10ms 扫描周期内的“双写竞争”。上位机以 100ms 异步采样时，若读取时机落在
    PRG_main_pac 与 PRG_pitch_sim 之间，会瞬态读到 0.0，造成上位机界面高频跳变。

    本过滤器对油缸位移、蓄能器/腔室压力、阀芯开度反馈、桨叶角度与速度等核心遥测物理量，
    执行轻量级非零保持与瞬态毛刺抑制：
    1. 当上一次采样处于正常非零工作区间时，若当前帧瞬态突跌至 0.0（或物理不可能的零点毛刺），
       启动防抖计数器，在 MAX_HOLD_FRAMES (默认 5 帧 / 500ms) 内保持上一帧有效值；
    2. 当零值持续超过 MAX_HOLD_FRAMES 时，认定为真实停机、泄压或仿真断开，正常下发 0.0；
    3. 当新有效非零采样到达时，立即更新并清零防抖计数器（零延迟跟踪）；
    4. 消除由位移/角度零点瞬跌引起的离散微分速度伪跳变（速度毛刺消除）。
    """
    def __init__(self, max_hold_frames: int = TELEMETRY_GLITCH_MAX_HOLD_FRAMES, enabled: bool = TELEMETRY_GLITCH_FILTER_ENABLED):
        self.max_hold_frames = max_hold_frames
        self.enabled = enabled
        self._blade_telemetry_cache: Dict[int, Dict[str, Any]] = {}
        self._blade_glitch_counter: Dict[int, int] = {0: 0, 1: 0, 2: 0}
        self._hpu_pressure_cache: Optional[float] = None
        self._hpu_glitch_counter: int = 0
        self._current_pos_cache: Optional[float] = None
        self._current_pos_glitch_counter: int = 0

    def reset(self):
        """重置过滤器缓存与防抖计数器（在网络重连或断开时调用）"""
        self._blade_telemetry_cache.clear()
        self._blade_glitch_counter = {0: 0, 1: 0, 2: 0}
        self._hpu_pressure_cache = None
        self._hpu_glitch_counter = 0
        self._current_pos_cache = None
        self._current_pos_glitch_counter = 0

    def filter_blade_telemetry(self, blade_idx: int, raw_payload: Dict[str, Any],
                               is_ref_active: bool, locked: bool) -> Dict[str, Any]:
        """对单支桨叶 (Blade A/B/C) 的全套传感器遥测进行零点毛刺抑制与平滑"""
        if not self.enabled:
            return {
                "pres_accu": float(raw_payload.get(f"bld_{blade_idx}_pres_accu", 0.0) or 0.0),
                "pres_piston": float(raw_payload.get(f"bld_{blade_idx}_pres_piston", 0.0) or 0.0),
                "pres_rod": float(raw_payload.get(f"bld_{blade_idx}_pres_rod", 0.0) or 0.0),
                "cyl_pos": float(raw_payload.get(f"bld_{blade_idx}_cyl_pos", 0.0) or 0.0),
                "cyl_spd": float(raw_payload.get(f"bld_{blade_idx}_cyl_spd", 0.0) or 0.0),
                "spool_pos_fb": float(raw_payload.get(f"bld_{blade_idx}_spool_fb", 0.0) or 0.0),
                "pos_act_deg": float(raw_payload.get(f"bld_{blade_idx}_pos_deg", 0.0) or 0.0),
                "rate_act_deg": float(raw_payload.get(f"bld_{blade_idx}_rate_deg", 0.0) or 0.0),
                "pitch_lock_engaged": locked,
                "pitch_ref_active": is_ref_active,
            }

        raw_pres_accu = float(raw_payload.get(f"bld_{blade_idx}_pres_accu", 0.0) or 0.0)
        raw_pres_piston = float(raw_payload.get(f"bld_{blade_idx}_pres_piston", 0.0) or 0.0)
        raw_pres_rod = float(raw_payload.get(f"bld_{blade_idx}_pres_rod", 0.0) or 0.0)
        raw_cyl_pos = float(raw_payload.get(f"bld_{blade_idx}_cyl_pos", 0.0) or 0.0)
        raw_cyl_spd = float(raw_payload.get(f"bld_{blade_idx}_cyl_spd", 0.0) or 0.0)
        raw_spool_fb = float(raw_payload.get(f"bld_{blade_idx}_spool_fb", 0.0) or 0.0)
        raw_pos_deg = float(raw_payload.get(f"bld_{blade_idx}_pos_deg", 0.0) or 0.0)
        raw_rate_deg = float(raw_payload.get(f"bld_{blade_idx}_rate_deg", 0.0) or 0.0)

        cached = self._blade_telemetry_cache.get(blade_idx)

        # 诊断是否存在由 PLC 周期时序冲突导致的零点毛刺或微分尖峰
        is_glitch = False
        if cached is not None:
            # 1. 蓄能器压力异常跌零（工作压力通常在 50~260 bar 之间）
            accu_glitch = (raw_pres_accu < 5.0 and cached["pres_accu"] > 20.0)
            # 2. 油缸位移异常跌零（正常运行行程通常 >= 10mm）
            cyl_glitch = (raw_cyl_pos < 1.0 and cached["cyl_pos"] > 5.0)
            # 3. 油缸工作腔压力瞬态跌零
            chamber_glitch = (raw_pres_piston < 1.0 and raw_pres_rod < 1.0 and (cached["pres_piston"] > 10.0 or cached["pres_rod"] > 10.0))
            # 4. 桨叶角度异常跌至零位偏置
            angle_glitch = (abs(raw_pos_deg) < 0.2 and abs(cached["pos_act_deg"]) > 2.0)
            # 5. 由零点跳变引发的微分速度假毛刺
            rate_glitch = (abs(raw_rate_deg) > 12.0 and abs(cached["rate_act_deg"]) < 8.0)
            spd_glitch = (abs(raw_cyl_spd) > 200.0 and abs(cached["cyl_spd"]) < 100.0)

            is_glitch = accu_glitch or cyl_glitch or chamber_glitch or angle_glitch or rate_glitch or spd_glitch

        if is_glitch:
            count = self._blade_glitch_counter.get(blade_idx, 0) + 1
            if count <= self.max_hold_frames:
                self._blade_glitch_counter[blade_idx] = count
                # 保持前一帧健康数据，同时保留当前最新离散锁与参考状态
                return {
                    "pres_accu": cached["pres_accu"],
                    "pres_piston": cached["pres_piston"],
                    "pres_rod": cached["pres_rod"],
                    "cyl_pos": cached["cyl_pos"],
                    "cyl_spd": cached["cyl_spd"],
                    "spool_pos_fb": cached["spool_pos_fb"],
                    "pos_act_deg": cached["pos_act_deg"],
                    "rate_act_deg": cached["rate_act_deg"],
                    "pitch_lock_engaged": locked,
                    "pitch_ref_active": is_ref_active,
                }
            else:
                # 零值已持续超过门限帧数 (> 500ms)，判定为真实停机/断开状态
                self._blade_glitch_counter[blade_idx] = 0
                val = {
                    "pres_accu": raw_pres_accu,
                    "pres_piston": raw_pres_piston,
                    "pres_rod": raw_pres_rod,
                    "cyl_pos": raw_cyl_pos,
                    "cyl_spd": 0.0 if (abs(raw_cyl_spd) > 200.0) else raw_cyl_spd,
                    "spool_pos_fb": raw_spool_fb,
                    "pos_act_deg": raw_pos_deg,
                    "rate_act_deg": 0.0 if (abs(raw_rate_deg) > 12.0) else raw_rate_deg,
                    "pitch_lock_engaged": locked,
                    "pitch_ref_active": is_ref_active,
                }
                self._blade_telemetry_cache[blade_idx] = val
                return val
        else:
            self._blade_glitch_counter[blade_idx] = 0
            val = {
                "pres_accu": raw_pres_accu,
                "pres_piston": raw_pres_piston,
                "pres_rod": raw_pres_rod,
                "cyl_pos": raw_cyl_pos,
                "cyl_spd": raw_cyl_spd,
                "spool_pos_fb": raw_spool_fb,
                "pos_act_deg": raw_pos_deg,
                "rate_act_deg": raw_rate_deg,
                "pitch_lock_engaged": locked,
                "pitch_ref_active": is_ref_active,
            }
            self._blade_telemetry_cache[blade_idx] = val
            return val

    def filter_hpu_pressure(self, raw_hpu_p: Optional[float]) -> Optional[float]:
        """过滤 HPU 泵站母管供油压力零点毛刺"""
        if not self.enabled or raw_hpu_p is None:
            return raw_hpu_p
        cached = self._hpu_pressure_cache
        if cached is not None and raw_hpu_p < 5.0 and cached > 20.0:
            if self._hpu_glitch_counter < self.max_hold_frames:
                self._hpu_glitch_counter += 1
                return cached
            else:
                self._hpu_glitch_counter = 0
                self._hpu_pressure_cache = raw_hpu_p
                return raw_hpu_p
        self._hpu_glitch_counter = 0
        self._hpu_pressure_cache = raw_hpu_p
        return raw_hpu_p

    def filter_current_pos(self, raw_pos: Optional[float], active_blade: int = 0) -> Optional[float]:
        """过滤手动控制页面 CurrentPos 零点跳变"""
        if not self.enabled or raw_pos is None:
            return raw_pos
        cached = self._current_pos_cache
        bld_glitching = (self._blade_glitch_counter.get(active_blade, 0) > 0)
        if cached is not None and (bld_glitching or (abs(raw_pos) < 0.2 and abs(cached) > 2.0)):
            if self._current_pos_glitch_counter < self.max_hold_frames:
                self._current_pos_glitch_counter += 1
                return cached
            else:
                self._current_pos_glitch_counter = 0
                self._current_pos_cache = raw_pos
                return raw_pos
        self._current_pos_glitch_counter = 0
        self._current_pos_cache = raw_pos
        return raw_pos


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
        self._command_queue: queue.Queue = queue.Queue()
        self._pulse_tasks: Dict[str, asyncio.Task] = {}
        self._force_alarm_poll: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.last_write_error: Optional[Exception] = None
        self._prev_pitch_angles: Dict[int, float] = {}
        self.glitch_filter = TelemetryGlitchFilter(
            max_hold_frames=TELEMETRY_GLITCH_MAX_HOLD_FRAMES,
            enabled=TELEMETRY_GLITCH_FILTER_ENABLED
        )

    def stop(self):
        self._running = False

    def set_glitch_filter_enabled(self, enabled: bool):
        """Enable or disable telemetry anti-glitch / zero-drop debounce filter"""
        self.glitch_filter.enabled = enabled
        logger.info(f"[OPCUA] Telemetry glitch filter {'ENABLED' if enabled else 'DISABLED'}")

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
        """Thread-safe enqueue a command to be written to the PLC"""
        self._command_queue.put((cmd_name, value))

    def trigger_alarm_poll(self):
        """Signal worker to perform an immediate alarm check"""
        self._force_alarm_poll = True

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
        try:
            await asyncio.sleep(delay)
            dv = ua.DataValue(ua.Variant(False, ua.VariantType.Boolean))
            await node.write_value(dv)
            logger.debug(f"[OPCUA] Auto-reset pulse {cmd_name} = False")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[OPCUA] Error auto-resetting {cmd_name}: {e}")
        finally:
            self._pulse_tasks.pop(cmd_name, None)

    async def _pulse_reset_int(self, node, cmd_name: str, delay: float = OPCUA_PULSE_RESET_INT_DELAY, vtype = None):
        try:
            await asyncio.sleep(delay)
            target_vtype = vtype if vtype is not None else ua.VariantType.Int16
            dv = ua.DataValue(ua.Variant(0, target_vtype))
            await node.write_value(dv)
            logger.debug(f"[OPCUA] Auto-reset pulse {cmd_name} = 0")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[OPCUA] Error auto-resetting {cmd_name}: {e}")
        finally:
            self._pulse_tasks.pop(cmd_name, None)

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

            # 2. Fetch Code for active alarms (Name/Message/Severity enriched locally from alarm_database)
            detail_nodes = []
            for idx in active_indices:
                detail_nodes.append(client.get_node(f"{core_prefix}Alarms[{idx}].Code"))

            active_list = []
            if detail_nodes:
                codes = []
                for i in range(0, len(detail_nodes), ALARM_CHUNK_SIZE):
                    chunk = detail_nodes[i:i+ALARM_CHUNK_SIZE]
                    codes.extend(await client.read_values(chunk))

                for i, idx in enumerate(active_indices):
                    active_list.append({
                        "code": int(codes[i]),
                        "state": int(states[idx - 1]),
                    })

            # 3. Fetch History alarms from gHistoryAlarmLog (Only Code, TimeString, State required)
            hist_prefix = f"{BASE_NODE_PREFIX}gHistoryAlarmLog."
            hist_cur = int(await client.get_node(f"{hist_prefix}CurrentCount").read_value())
            history_list = []
            if hist_cur > 0:
                fetch_len = min(hist_cur, ALARM_HISTORY_MAX_FETCH)  # Max history entries
                hist_nodes = []
                for i in range(1, fetch_len + 1):
                    hist_nodes.extend([
                        client.get_node(f"{hist_prefix}Items[{i}].Code"),
                        client.get_node(f"{hist_prefix}Items[{i}].TimeString"),
                        client.get_node(f"{hist_prefix}Items[{i}].State"),
                    ])
                hist_vals = []
                for i in range(0, len(hist_nodes), ALARM_CHUNK_SIZE):
                    chunk = hist_nodes[i:i+ALARM_CHUNK_SIZE]
                    hist_vals.extend(await client.read_values(chunk))

                for i in range(fetch_len):
                    history_list.append({
                        "code": int(hist_vals[i*3]),
                        "timestamp": str(hist_vals[i*3+1]),
                        "state": int(hist_vals[i*3+2]),
                    })

            return active_list, history_list
        except Exception as e:
            logger.error(f"[OPCUA] Error fetching alarms: {e}")
            return [], []

    async def _fetch_pv_alarm_limits(self, client):
        """Fetch dynamic threshold limits from CODESYS PVAlarms.limitSet via OPC UA"""
        try:
            from models.alarm_database import PV_ALARM_FIELDS, update_pv_alarm_limits
            pv_prefix = f"{BASE_NODE_PREFIX}PVAlarms.limitSet."
            nodes = [client.get_node(f"{pv_prefix}{f}") for f in PV_ALARM_FIELDS]

            vals = []
            for i in range(0, len(nodes), ALARM_CHUNK_SIZE):
                chunk = nodes[i:i+ALARM_CHUNK_SIZE]
                vals.extend(await client.read_values(chunk))

            limits = {}
            for f, v in zip(PV_ALARM_FIELDS, vals):
                if v is not None:
                    try:
                        limits[f] = float(v)
                    except (ValueError, TypeError):
                        pass
            if limits:
                update_pv_alarm_limits(limits)
                logger.info(f"[OPCUA] Read {len(limits)} dynamic alarm limits from PVAlarms.limitSet via OPC UA")
        except Exception as e:
            logger.debug(f"[OPCUA] Note: PVAlarms.limitSet fetch skipped: {e}")

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
                        "safety_ok": client.get_node(f"{BASE_NODE_PREFIX}safety.safetyOK"),

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
                        "ack_all": client.get_node(f"{BASE_NODE_PREFIX}xAcknowledgeAll"),
                        # Standard OPC UA Server CurrentTime (ns=0;i=2258)
                        "server_current_time": client.get_node("ns=0;i=2258"),

                        # Remote Box / Manual Control Source Nodes
                        "sim_rb_connected": client.get_node(f"{SIM_NODE_PREFIX}bRemoteBoxConnected"),
                        "sim_rb_in_control": client.get_node(f"{SIM_NODE_PREFIX}bRemoteBoxInControl"),
                        "pac_rb_connected": client.get_node(f"{BASE_NODE_PREFIX}pac.io.dIn.remoteBoxConnected"),
                        "hmi_user_input": client.get_node(f"{BASE_NODE_PREFIX}hmi.sUserInput"),
                        "hmi_rb_enabled": client.get_node(f"{BASE_NODE_PREFIX}hmi.remoteboxEnbaled"),
                    }

                    # Blades nodes (0=A, 1=B, 2=C) - Standard Common.blade[i]
                    for i in range(3):
                        prefix = f"{BASE_NODE_PREFIX}blade[{i}]."
                        nodes[f"bld_{i}_pres_accu"] = client.get_node(f"{prefix}io.ai.presAccu")
                        nodes[f"bld_{i}_pres_piston"] = client.get_node(f"{prefix}io.ai.presPiston")
                        nodes[f"bld_{i}_pres_rod"] = client.get_node(f"{prefix}io.ai.presRod")
                        nodes[f"bld_{i}_cyl_pos"] = client.get_node(f"{prefix}io.ai.cylPos")
                        nodes[f"bld_{i}_cyl_spd"] = client.get_node(f"{prefix}io.ai.cylSpd")
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

                    # 5. HMI Blade Control & Lubrication Nodes
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

                    # Pitch Reference status from PLC (Common.hmi.hidePitchRefBldA/B/C)
                    nodes["hmi_hide_pitch_ref_a"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.hidePitchRefBldA")
                    nodes["hmi_hide_pitch_ref_b"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.hidePitchRefBldB")
                    nodes["hmi_hide_pitch_ref_c"] = client.get_node(f"{BASE_NODE_PREFIX}hmi.hidePitchRefBldC")

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

                    # Check optional Remote Box nodes
                    for rb_key in ["sim_rb_connected", "sim_rb_in_control", "pac_rb_connected", "hmi_user_input", "hmi_rb_enabled"]:
                        try:
                            await nodes[rb_key].read_attribute(ua.AttributeIds.NodeId)
                        except Exception:
                            nodes[rb_key] = None

                    # Build declarative batch read specifications for single round-trip polling
                    batch_read_specs = [
                        ("plc_time", nodes["server_current_time"], lambda v: v.astimezone() if hasattr(v, "astimezone") else v),
                    ]

                    # Remote Box telemetry specs
                    if nodes.get("sim_rb_connected") is not None:
                        batch_read_specs.append(("sim_remote_box_connected", nodes["sim_rb_connected"], bool))
                    if nodes.get("sim_rb_in_control") is not None:
                        batch_read_specs.append(("sim_remote_box_in_control", nodes["sim_rb_in_control"], bool))
                    if nodes.get("pac_rb_connected") is not None:
                        batch_read_specs.append(("pac_remote_box_connected", nodes["pac_rb_connected"], bool))
                    if nodes.get("hmi_user_input") is not None:
                        batch_read_specs.append(("hmi_user_input", nodes["hmi_user_input"], int))
                    if nodes.get("hmi_rb_enabled") is not None:
                        batch_read_specs.append(("hmi_remote_box_enabled", nodes["hmi_rb_enabled"], int))

                    if has_pac_nodes:
                        batch_read_specs.extend([
                            ("state", nodes["state"], int),
                            ("mode", nodes["mode"], int),
                            ("description", nodes["description"], str),
                            ("abortType", nodes["abortType"], int),
                            ("temp_hub", nodes["temp_hub"], float),
                            ("temp_oil", nodes["temp_oil"], float),
                            ("temp_cabinet", nodes["temp_cabinet"], float),
                            ("cpu_temp", nodes["temp_cpu"], float),
                            ("current_t1", nodes["current_t1"], float),
                            ("current_t2", nodes["current_t2"], float),
                            ("power_supply_ok", nodes["power_supply_ok"], bool),
                            ("safety_ok", nodes["safety_ok"], bool),
                            ("pac_version_hw", nodes["pac_version_hw"], str),
                            ("pac_version_sw", nodes["pac_version_sw"], str),
                            ("lub_tank1_ok", nodes["lub_tank1_ok"], bool),
                            ("lub_piston_a1", nodes["lub_piston_a1"], bool),
                            ("lub_piston_b1", nodes["lub_piston_b1"], bool),
                            ("lub_piston_c1", nodes["lub_piston_c1"], bool),
                            ("lub_tank2_ok", nodes["lub_tank2_ok"], bool),
                            ("lub_piston_a2", nodes["lub_piston_a2"], bool),
                            ("lub_piston_b2", nodes["lub_piston_b2"], bool),
                            ("lub_piston_c2", nodes["lub_piston_c2"], bool),
                            ("pac_lub1_pump_on", nodes["pac_lub1_pump_on"], bool),
                            ("pac_lub2_pump_on", nodes["pac_lub2_pump_on"], bool),
                        ])

                    if nodes.get("hpu_pressure") is not None:
                        batch_read_specs.extend([
                            ("hpu_pressure", nodes["hpu_pressure"], float),
                            ("hpu_oil_level", nodes["hpu_oil_level"], float),
                            ("hpu_temp", nodes["hpu_temp"], float),
                            ("hpu_state_raw", nodes["hpu_state"], int),
                        ])

                    for i in range(3):
                        batch_read_specs.extend([
                            (f"bld_{i}_pres_accu", nodes[f"bld_{i}_pres_accu"], float),
                            (f"bld_{i}_pres_piston", nodes[f"bld_{i}_pres_piston"], float),
                            (f"bld_{i}_pres_rod", nodes[f"bld_{i}_pres_rod"], float),
                            (f"bld_{i}_cyl_pos", nodes[f"bld_{i}_cyl_pos"], float),
                            (f"bld_{i}_cyl_spd", nodes[f"bld_{i}_cyl_spd"], float),
                            (f"bld_{i}_spool_fb", nodes[f"bld_{i}_spool_fb"], float),
                            (f"bld_{i}_pos_deg", nodes[f"bld_{i}_pos_deg"], float),
                            (f"bld_{i}_rate_deg", nodes[f"bld_{i}_rate_deg"], float),
                            (f"bld_{i}_locked", nodes[f"bld_{i}_locked"], bool),
                        ])

                    if has_net_nodes:
                        batch_read_specs.extend([
                            ("net_hostName", nodes["net_hostName"], str),
                            ("net_IPAddr", nodes["net_IPAddr"], str),
                            ("net_subnetMask", nodes["net_subnetMask"], str),
                        ])

                    if has_par_nodes:
                        for i in range(3):
                            batch_read_specs.extend([
                                (f"par_{i}_posOffDeg", nodes[f"par_{i}_posOffDeg"], float),
                                (f"par_{i}_grd", nodes[f"par_{i}_grd"], int),
                            ])

                    if has_hmi_nodes:
                        for i in range(3):
                            batch_read_specs.extend([
                                (f"bld_{i}_par_pos_off", nodes[f"bld_{i}_par_pos_off"], float),
                                (f"bld_{i}_par_grd", nodes[f"bld_{i}_par_grd"], int),
                                (f"hmi_pos_off_{i}", nodes[f"hmi_pos_off_{i}"], float),
                                (f"hmi_grd_temp_{i}", nodes[f"hmi_grd_temp_{i}"], int),
                            ])
                        batch_read_specs.extend([
                            ("hmi_active_blade", nodes["hmi_active_blade"], int),
                            ("hmi_current_pos", nodes["hmi_current_pos"], float),
                            ("hmi_blade_safe_a", nodes["hmi_blade_safe_a"], bool),
                            ("hmi_blade_safe_b", nodes["hmi_blade_safe_b"], bool),
                            ("hmi_blade_safe_c", nodes["hmi_blade_safe_c"], bool),
                            ("hmi_fast_speed", nodes["hmi_fast_speed"], float),
                            ("hmi_slow_speed", nodes["hmi_slow_speed"], float),
                            ("hmi_fast_chosen", nodes["hmi_fast_chosen"], bool),
                            ("hmi_slow_chosen", nodes["hmi_slow_chosen"], bool),
                            ("hmi_pitch_lock", nodes["hmi_pitch_lock"], bool),
                            ("maint_btn_enb", nodes["hmi_maint_btn_enb"], int),
                            ("maint_help_enb", nodes["hmi_maint_help_enb"], int),
                            ("msgbox_status", nodes["hmi_msgbox_status"], int),
                            ("msgbox_header", nodes["hmi_msgbox_header"], str),
                            ("msgbox_content", nodes["hmi_msgbox_content"], str),
                            ("msgbox_btn_ok_status", nodes["hmi_msgbox_btn_ok_status"], int),
                            ("msgbox_btn_abort_status", nodes["hmi_msgbox_btn_abort_status"], int),
                            ("msgbox_icon", nodes["hmi_msgbox_icon"], int),
                            ("plc_abort_btn_status", nodes["hmi_status_abort_btn"], int),
                            ("plc_start_btn_status", nodes["hmi_status_start_btn"], int),
                            ("hmi_hide_pitch_ref_a", nodes["hmi_hide_pitch_ref_a"], int),
                            ("hmi_hide_pitch_ref_b", nodes["hmi_hide_pitch_ref_b"], int),
                            ("hmi_hide_pitch_ref_c", nodes["hmi_hide_pitch_ref_c"], int),
                        ])

                    batch_nodes = [spec[1] for spec in batch_read_specs]

                    # Cache alarm count nodes
                    node_act_cnt = client.get_node(f"{BASE_NODE_PREFIX}gAlarmCoreTable.ActiveAlarmsCount")
                    node_hist_cnt = client.get_node(f"{BASE_NODE_PREFIX}gHistoryAlarmLog.CurrentCount")

                    alarm_poll_counter = 0
                    alarm_full_resync_counter = 0
                    last_act_cnt = -1
                    last_hist_cnt = -1
                    # Load dynamic alarm limits from PVAlarms.limitSet via OPC UA upon initial connection
                    await self._fetch_pv_alarm_limits(client)

                    write_spec_registry = _make_node_spec_registry()

                    while self._running and not self._need_reconnect and self._enabled:
                        # 1. Process pending write commands from thread-safe queue
                        while not self._command_queue.empty():
                            cmd_name, val = self._command_queue.get_nowait()
                            target_node = nodes.get(cmd_name)
                            if target_node is None:
                                if cmd_name == "ack_all":
                                    logger.info("[OPCUA] CODESYS 符号配置未发布 'Common.xAcknowledgeAll'，跳过 PLC 写入（本地报警已确认）")
                                continue

                            if not has_net_nodes and cmd_name.startswith("net_"):
                                err_msg = f"CODESYS 符号配置未发布节点 (BadNodeIdUnknown): {cmd_name}"
                                logger.warning(f"[OPCUA] {err_msg}")
                                self.command_result.emit(cmd_name, False, err_msg)
                                continue

                            if not has_par_nodes and cmd_name.startswith("par_"):
                                continue

                            try:
                                spec = resolve_node_spec(cmd_name, write_spec_registry)
                                conv_val = spec.converter(val) if spec.converter else val
                                dv = ua.DataValue(ua.Variant(conv_val, spec.vtype))
                                await target_node.write_value(dv)
                                logger.debug(f"[OPCUA] Wrote {cmd_name} = {conv_val} ({spec.vtype.name})")
                                self.command_result.emit(cmd_name, True, "OK")

                                if spec.is_pulse:
                                    if spec.pulse_type == "int" and int(val) == 1:
                                        if cmd_name in self._pulse_tasks:
                                            self._pulse_tasks[cmd_name].cancel()
                                        self._pulse_tasks[cmd_name] = asyncio.create_task(
                                            self._pulse_reset_int(target_node, cmd_name, spec.pulse_delay, spec.vtype)
                                        )
                                    elif spec.pulse_type == "bool" and bool(val) is True:
                                        if cmd_name in self._pulse_tasks:
                                            self._pulse_tasks[cmd_name].cancel()
                                        self._pulse_tasks[cmd_name] = asyncio.create_task(
                                            self._pulse_reset(target_node, cmd_name, spec.pulse_delay)
                                        )
                            except Exception as we:
                                write_err = OpcUaWriteError(cmd_name, val, we)
                                self.last_write_error = write_err
                                logger.error(
                                    f"[OPCUA 写入异常 / Write Error] 指令 '{cmd_name}' 写入失败 (值={val}, 节点={target_node}): {we}",
                                    exc_info=True
                                )
                                self.command_result.emit(cmd_name, False, str(we))
                                if OPCUA_STRICT_RAISE_EXCEPTIONS:
                                    raise write_err

                        # 2. Batch poll all telemetry nodes in a single network round-trip
                        data_payload: Dict[str, Any] = {}
                        data_payload["has_network_nodes"] = has_net_nodes

                        try:
                            vals = await client.read_values(batch_nodes)
                            for (key, _, fn), val in zip(batch_read_specs, vals):
                                if val is not None:
                                    try:
                                        data_payload[key] = fn(val)
                                    except Exception:
                                        data_payload[key] = val

                            # Structure 3 blades directly from lower machine PLC Common.blade[i]
                            ref_status_keys = ["hmi_hide_pitch_ref_a", "hmi_hide_pitch_ref_b", "hmi_hide_pitch_ref_c"]
                            for i in range(3):
                                raw_ref = data_payload.get(ref_status_keys[i], 0)
                                is_ref_active = bool(int(raw_ref) & 1) if raw_ref is not None else False
                                locked = bool(data_payload.get(f"bld_{i}_locked", False))

                                # Process Common.blade[i] with glitch filter
                                blade_data = self.glitch_filter.filter_blade_telemetry(
                                    blade_idx=i,
                                    raw_payload=data_payload,
                                    is_ref_active=is_ref_active,
                                    locked=locked
                                )

                                data_payload[f"blade_{i}"] = blade_data

                                # Synchronize top-level fields
                                data_payload[f"bld_{i}_pres_accu"] = blade_data["pres_accu"]
                                data_payload[f"bld_{i}_pres_piston"] = blade_data["pres_piston"]
                                data_payload[f"bld_{i}_pres_rod"] = blade_data["pres_rod"]
                                data_payload[f"bld_{i}_cyl_pos"] = blade_data["cyl_pos"]
                                data_payload[f"bld_{i}_cyl_spd"] = blade_data["cyl_spd"]
                                data_payload[f"bld_{i}_spool_fb"] = blade_data["spool_pos_fb"]
                                data_payload[f"bld_{i}_pos_deg"] = blade_data["pos_act_deg"]
                                data_payload[f"bld_{i}_rate_deg"] = blade_data["rate_act_deg"]

                            # Filter or pass HPU pressure
                            if "hpu_pressure" in data_payload:
                                data_payload["hpu_pressure"] = self.glitch_filter.filter_hpu_pressure(
                                    data_payload["hpu_pressure"]
                                )

                            # Filter or update manual page CurrentPos
                            if "hmi_current_pos" in data_payload:
                                active_b = data_payload.get("hmi_active_blade", 0)
                                data_payload["hmi_current_pos"] = self.glitch_filter.filter_current_pos(
                                    data_payload["hmi_current_pos"], active_blade=active_b
                                )

                            # Map HPU state
                            if "hpu_state_raw" in data_payload:
                                hpu_map = {0: "Stopped", 1: "Execute", 2: "Ready"}
                                st_raw = data_payload["hpu_state_raw"]
                                data_payload["hpu_state"] = hpu_map.get(st_raw, str(st_raw))

                            # Map network aliases
                            if has_net_nodes:
                                data_payload["net_hostname"] = data_payload.get("net_hostName", "")
                                data_payload["net_ip"] = data_payload.get("net_IPAddr", "")
                                data_payload["net_subnet"] = data_payload.get("net_subnetMask", "")

                            self.data_updated.emit(data_payload)
                            self.frames_received += 1

                            # 3. Poll Alarms (every ~1s, on count changes, or on full resync/force request)
                            alarm_poll_counter += 1
                            alarm_full_resync_counter += 1
                            need_alarm_poll = (
                                alarm_poll_counter >= ALARM_POLL_DECIMATION
                                or last_act_cnt == -1
                                or self._force_alarm_poll
                                or alarm_full_resync_counter >= 30
                            )
                            if need_alarm_poll:
                                alarm_poll_counter = 0
                                is_force = self._force_alarm_poll or (alarm_full_resync_counter >= 30) or (last_act_cnt == -1)
                                if is_force:
                                    alarm_full_resync_counter = 0
                                    await self._fetch_pv_alarm_limits(client)
                                self._force_alarm_poll = False
                                try:
                                    act_cnt = int(await node_act_cnt.read_value())
                                    hist_cnt = int(await node_hist_cnt.read_value())
                                    if is_force or act_cnt != last_act_cnt or hist_cnt != last_hist_cnt:
                                        active_list, history_list = await self._fetch_alarms(client)
                                        self.alarms_updated.emit(active_list, history_list)
                                        last_act_cnt = act_cnt
                                        last_hist_cnt = hist_cnt
                                except Exception as ae:
                                    logger.debug(f"[OPCUA] Alarm poll check: {ae}")

                        except Exception as re:
                            err_str = str(re)
                            if "BadNodeIdUnknown" in err_str or "BadSession" in err_str:
                                logger.info("[OPCUA] 检测到 CODESYS PLC 重启或执行在线变更 (Online Change)，正在重新同步节点...")
                            else:
                                logger.warning(f"[OPCUA] Read cycle error: {re}")
                            break  # reconnect and refresh node handles

                        await asyncio.sleep(self.poll_interval)

                    # Cancel any active pulse tasks on disconnect
                    for t in self._pulse_tasks.values():
                        t.cancel()
                    self._pulse_tasks.clear()
                    self._prev_pitch_angles.clear()
                    self.glitch_filter.reset()

            except Exception as conn_err:
                logger.warning(f"[OPCUA] Connection failed or dropped: {conn_err}")
                self._prev_pitch_angles.clear()
                self.glitch_filter.reset()
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

    def set_glitch_filter_enabled(self, enabled: bool):
        """Enable or disable telemetry anti-glitch / zero-drop debounce filter"""
        if self.worker:
            self.worker.set_glitch_filter_enabled(enabled)

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
    def send_start(self, current_state: Optional[str] = None):
        """
        Send Start command adhering to PackML transition rules:
        - In ABORTED: triggers Clear
        - In STOPPED/IDLE: triggers Start
        - Always pulses Common.hmi.buttons.start = 1
        """
        if self.worker:
            self.worker.enqueue_command("hmi_btn_start", 1)
            if current_state == STATE_ABORTED:
                self.worker.enqueue_command("cmd_clear", True)
            elif current_state in (STATE_STOPPED, STATE_IDLE):
                self.worker.enqueue_command("cmd_start", True)

    def send_stop(self):
        """Send Stop/Abort command: pulse Common.hmi.buttons.abort = 1 and cmd_abort = True"""
        if self.worker:
            self.worker.enqueue_command("hmi_btn_abort", 1)
            self.worker.enqueue_command("cmd_abort", True)

    def send_reset(self):
        if self.worker:
            self.worker.enqueue_command("cmd_reset", True)
            self.worker.trigger_alarm_poll()

    def send_clear(self):
        if self.worker:
            self.worker.enqueue_command("cmd_clear", True)

    def send_ack_all(self):
        if self.worker:
            self.worker.enqueue_command("ack_all", True)
            self.worker.trigger_alarm_poll()

    def force_poll_alarms(self):
        """Trigger immediate full alarm polling from PLC"""
        if self.worker:
            self.worker.trigger_alarm_poll()

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
