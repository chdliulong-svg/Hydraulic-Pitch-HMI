# -*- coding: utf-8 -*-
"""
Internationalization (i18n) Module for SEC PAC 6MW Hydraulic Pitch HMI
Supports instantaneous runtime switching between English and Chinese
"""

from PyQt6.QtCore import QObject, pyqtSignal

# Master Translation Dictionary
TRANSLATIONS = {
    # --- Navigation & General ---
    "Inspect": "巡检",
    "Alarm": "报警",
    "Manual": "手动",
    "Maintenance": "维护",
    "Save/Load": "参数存取",
    "Network": "网络",

    # --- Header Subtitles ---
    "Pitch system data as pressure, temperature, etc. are shown in this page": "本页面显示压力、温度等变桨系统数据",
    "Active alarms and historical alarm logs": "当前活动报警与历史报警记录",
    "Manual pitching and valve test operations": "手动变桨与阀控测试操作",
    "Sensor calibration and diagnostic tools": "传感器标定与诊断工具",
    "Parameter file backup, restore, and user login": "参数文件备份、恢复与用户登录",
    "Ethernet configuration and PLC IP parameters": "以太网网络配置与 PLC IP 参数设置",
    "Ethernet configuration, PLC IP parameters, and communication diagnostics": "以太网网络配置与 PLC IP 参数设置",

    # --- Left Status Panel Labels ---
    "Blade State": "叶片状态",
    "Blade Mode": "叶片模式",
    "Manual Control": "手动控制",
    "Main Control": "主控控制",
    "Safety Ok": "安全链正常",
    "Emergency": "急停/未闭合",
    "Language": "语言切换",
    "Language Switch": "语言切换",

    # --- PackML Blade States ---
    "Aborted": "已中止",
    "Stopped": "已停止",
    "Execute": "运行中",
    "Clearing": "清除中",
    "Resetting": "复位中",
    "Starting": "启动中",
    "Holding": "保持中",
    "Unholding": "取消保持",
    "Suspending": "挂起中",
    "Unsuspending": "恢复中",
    "Completing": "完成中",
    "Complete": "已完成",
    "Aborting": "中止中",
    "Idle": "空闲",

    # --- Blade Modes ---
    "Production": "生产模式",
    "Manual Mode": "手动模式",
    "Maintenance Mode": "维护模式",

    # --- Control Authorities ---
    "HMI": "HMI",
    "Remote": "远控",
    "Remote Box": "手操盒",
    "None": "无",

    # --- Bottom Status Bar Messages ---
    'PAC: "Aborted - Waiting for Clear Command"': 'PAC: "已中止 - 等待清除命令"',
    'PAC: "Clearing - Checking Accumulator & Valves"': 'PAC: "清除中 - 正在检查蓄能器与阀门"',
    'PAC: "Clearing - Performing oil heating"': 'PAC: "清除中 - 正在进行油温加热"',
    'PAC: "Clearing - Starting timer"': 'PAC: "清除中 - 启动定时器"',
    'PAC: "Clearing - Opening valves"': 'PAC: "清除中 - 打开阀门"',
    'PAC: "Clearing - Software checking"': 'PAC: "清除中 - 软件自检中"',
    'PAC: "Clearing"': 'PAC: "清除中"',
    'PAC: "Resetting - Unlocking blades to standby"': 'PAC: "复位中 - 解锁叶片至待机状态"',
    'PAC: "Aborting - Stopping blades to feather"': 'PAC: "中止中 - 停止叶片并顺桨"',
    'PAC: "Aborting - Setting Timer"': 'PAC: "中止中 - 设置定时器"',
    'PAC: "Aborting - Enabling position controller"': 'PAC: "中止中 - 启用位置控制器"',
    'PAC: "Aborting - ramping the blades to sync pos"': 'PAC: "中止中 - 叶片同步位置斜坡"',
    'PAC: "Aborting - ramping the blades to idle pos"': 'PAC: "中止中 - 叶片待机位置斜坡"',
    'PAC: "Aborting - Blades in Idle, change to EMF"': 'PAC: "中止中 - 叶片就绪，切换至应急顺桨"',
    'PAC: "Aborting - Turbine is shutting down. Waiting for blades to fully feather and pitch locks engaged"': 'PAC: "中止中 - 风机停机，等待叶片顺桨并投入变桨锁"',
    'PAC: "Aborting - Turbine is shutting down.Waiting for blades to fully feather and pitch locks engaged"': 'PAC: "中止中 - 风机停机，等待叶片顺桨并投入变桨锁"',
    'PAC: "Aborting - Turbine is shutting down.Waiting for blades to fully feather and pitc"': 'PAC: "中止中 - 风机停机，等待叶片顺桨并投入变桨锁"',
    'PAC: "MANUAL OPERATION!"': 'PAC: "手动操作模式!"',
    'PAC: "Stopped - Ready for Production"': 'PAC: "已停止 - 生产就绪"',
    'PAC: "Stopped - Ready"': 'PAC: "已停止 - 就绪"',
    'PAC: "Stopped"': 'PAC: "已停止"',
    'PAC: "Execute - Running"': 'PAC: "运行中 - 正常"',
    'PAC: "Deactivated - Waiting for boot up"': 'PAC: "已停用 - 等待启动"',

    # --- Blade Telemetry Card ---
    "Blade A": "变桨 A",
    "Blade B": "变桨 B",
    "Blade C": "变桨 C",
    "Pressure accu (107)": "蓄能器压力 (107)",
    "Pressure piston (135)": "无杆腔压力 (135)",
    "Pressure rod (136)": "有杆腔压力 (136)",
    "Pitch reference": "变桨跟踪参考",
    "Active": "激活",
    "Inactive": "未激活",
    "Cyl. position": "油缸位移/角度",
    "Cyl. speed": "油缸速度/角速度",
    "Spool position": "阀芯开度",
    "Pitch lock engaged (135)": "变桨锁投入 (135)",

    # --- PAC Status Card ---
    "PAC Status": "PAC 状态",
    "Temperature Hub": "轮毂温度",
    "Temperature cabinet": "控制柜温度",
    "Temperature oil": "油箱温度",
    "Supply Current T1 PAC": "PAC 供电电流 T1",
    "Supply Current T2 PAC": "PAC 供电电流 T2",
    "PAC CPU temp.": "PAC CPU 温度",
    "Power supply OK": "电源状态正常",

    # --- Lubrication Status Card ---
    "Lubrication Status": "润滑状态",
    "Grease Level Lub Tank 1 OK": "润滑脂罐 1 油位正常",
    "Piston A Tank1 Moving": "活塞 A 罐 1 动作中",
    "Piston B Tank1 Moving": "活塞 B 罐 1 动作中",
    "Piston C Tank1 Moving": "活塞 C 罐 1 动作中",
    "Grease Level Lub Tank 2 OK": "润滑脂罐 2 油位正常",
    "Piston A Tank2 Moving": "活塞 A 罐 2 动作中",
    "Piston B Tank2 Moving": "活塞 B 罐 2 动作中",
    "Piston C Tank2 Moving": "活塞 C 罐 2 动作中",

    # --- HPU Status Card ---
    "HPU Status (From MC)": "HPU 泵站状态 (主控)",
    "HPU State": "HPU 状态",
    "Pressure accu": "蓄能器压力",
    "Oil level": "油位",
    "Standby": "待机中",
    "Running": "运行中",

    # --- Alarm Page ---
    "History": "历史记录",
    "State active": "激活时间",
    "Active or Reset Time": "发生时间 (激活/复位)",
    "Alarm Code": "报警代码",
    "Message": "报警信息",
    "Code": "代码",
    "State": "状态",
    "Action": "动作等级",
    "Alarm Name": "报警名称",
    "State Ack.": "确认状态",
    "Acknowledge\nselected ✔": "确认所选 ✔",
    "Acknowledge\nAll ✔✔": "全部确认 ✔✔",
    "Reset Safety ⚠": "复位安全链 ⚠",
    "Active (The problem has not been solved)": "活动 (故障未排除)",
    "Acknowledged": "已确认",
    "Unacknowledged": "未确认",

    # --- Manual Page ---
    "Pitch Position Calibration [deg]": "变桨位置标定 [deg]",
    "GRD Calibration [cm/s]": "GRD 标定 [cm/s]",
    "Blade Lubrication": "叶片润滑",
    "HMI Blade Control": "HMI 变桨控制",
    "All Blades": "所有叶片",
    "Offset:": "偏置量:",
    "Current": "当前值",
    "New": "设定值",
    "Apply Changes": "应用更改",
    "Require Login": "需先登录",
    "Activate Pump 1": "启动润滑泵 1",
    "Activate Pump 2": "启动润滑泵 2",
    "Stop Pump 1": "停止润滑泵 1",
    "Stop Pump 2": "停止润滑泵 2",
    "Require Manual Mode": "需进入手动模式",
    "Blade selected:": "选择叶片:",
    "Fast speed:": "快速速度:",
    "Slow speed:": "慢速速度:",
    "Blade safe:      ": "叶片安全:      ",
    "Move Feather (90°)": "向顺桨移动 (90°)",
    "Move Fine (0°)": "向开桨移动 (0°)",
    "Stop": "停止",
    "Pitch Lock": "机械锁",
    "Engage": "投入",
    "Disengage": "退出",
    "Enable HMI Control": "启用 HMI 控制",
    "Return to Main Control": "交回主控控制",
    "Login": "登录",
    "Logout": "注销",
    "Password:": "密码:",
    "Enter password...": "请输入密码...",

    # --- Maintenance Page ---
    "HPU": "液压动力单元 (HPU)",
    "HPU Hydraulic Power Unit": "液压动力单元 (HPU)",
    "Request pressure build up from HPU": "请求 HPU 泵站建压",
    "Lubrication": "润滑系统测试",
    "Lubrication System Test": "润滑系统测试 (Lubrication)",
    "Lubrication pump 1": "润滑泵 1",
    "Lubrication pump 2": "润滑泵 2",
    "Reset": "重置",
    "Apply Changes": "应用更改",
    "PAC": "PAC 阀组与比例阀测试",
    "PAC Valve Actuation & Prop. Control": "PAC 阀组与比例阀测试",
    "Valve Name": "阀门名称",
    "Valve 132 Pitch Lock": "132 变桨锁紧阀 (Pitch Lock)",
    "Valve 130 Pitch Lock": "130 变桨锁止阀 (Pitch Lock)",
    "Valve 120 EMF": "120 应急顺桨阀 (EMF)",
    "Valve 103 EMF": "103 应急顺桨阀 (EMF)",
    "Valve 119A Cut Off 1": "119A 截止阀 1 (Cut Off 1)",
    "Valve 119B Cut Off 2": "119B 截止阀 2 (Cut Off 2)",
    "Valve 109 Cut Off P": "109 压力截止阀 P (Cut Off P)",
    "Valve 116 Dump": "116 主卸荷阀 (Dump)",
    "Prop. Valve 102A": "比例阀 102A (-100% ~ +100%)",
    "Prop. Valve 102A (-100% ~ +100%)": "比例阀 102A (-100% ~ +100%)",
    "Prop. Valve 102A on A:": "A 桨比例阀 102A:",
    "Prop. Valve 102A on B:": "B 桨比例阀 102A:",
    "Prop. Valve 102A on C:": "C 桨比例阀 102A:",
    "Prop. Value Input": "设定开度",
    "Spool Feedback": "阀芯反馈",
    "Center 0%": "0% 归中",
    "Request Maintenance Mode": "请求进入维护模式 ⚙",
    "Exit Maintenance Mode": "退出维护模式 ✖",
    "Maintenance Authorization": "维护权限登录",
    "Maintenance Mode Control": "维护模式管理",
    "Maintenance Mode Safety Notice": "维护操作安全须知",
    "WARNING: Entering the hub is NOT safe under any circumstances in Maintenance Mode!": "⚠️ 警告：维护模式下严禁人员进入轮毂！",
    "Requirements to Enter:": "前置准入条件:",
    "1. PAC must be in ABORTED state": "1. PAC 状态必须为 已中止 (Aborted)",
    "2. Super/Maintenance password login required": "2. 需登录 Super/维护 权限密码",
    "3. Confirm hub is empty and secure": "3. 确认轮毂内部无作业人员且安全",
    "Require Login & Maint. Mode": "🔒 需维护模式并登录",
    "Maintenance Active": "✔ 维护模式已就绪",
    "Ready to Enter": "✔ 具备准入条件",
    "State Must Be Aborted": "🔒 需处于中止状态",
    "PAC Valve Test": "PAC 阀门动作测试",
    "Proportional Valve Manual Control": "比例阀手动控制",

    # --- Network Page ---
    "PLC Ethernet Configuration": "PLC 以太网网络配置",
    "Communication & Bus Diagnostics": "通信链路与总线诊断",
    "Parameter": "参数项",
    "Current Value": "当前设定值",
    "New Value (Editable)": "新设定值 (可编辑)",
    "Hostname": "主机名",
    "IP address": "IP 地址",
    "Subnet mask": "子网掩码",
    "🔄 Sync from PLC": "🔄 从 PLC 读取当前配置",
    "💾 Update Network Settings": "💾 应用网络设置",
    "User Authentication": "用户身份认证与登录",
    "Enter Password:": "请输入密码:",
    "Login": "登录",
    "Logout": "注销",
    "Authorization:": "当前权限级别:",
    "Authorization Guide": "用户权限说明",
    "Status: Authorized. Ready to apply network settings.": "状态: 授权已通过。具备修改网络参数权限。",
    "Status: Synchronized with PLC.": "状态: 已与 PLC 设定值同步。",
    "Status: Settings updated! Restart controller to take effect.": "状态: 网络参数已更新！控制器重启后生效。",
    "Status: Super User login required to update settings.": "状态: 修改网络参数需 Super User 登录权限。",
    "Ethernet Physical Link:": "以太网物理链路:",
    "Configuration Self-Check:": "网络配置自检状态:",
    "POWERLINK Node ID:": "POWERLINK 站号:",
    "Communication Stack:": "通信协议栈版本:",
    "Ping / Reachability Test:": "Ping / 连通性测试:",
    "100 Mbps Full-Duplex (Connected)": "100 Mbps 全双工 (已连接)",
    "OK (No Configuration Error)": "正常 (无配置故障)",
    "FAULT: Configuration Error": "故障: 网络配置异常",
    "Not logged in!": "未登录",
    "Super User": "超级用户",
    "Node": "站号",
    "PLC Controller Action": "PLC 控制器操作",
    "🔄 PLC Soft Restart": "🔄 PLC 软重启",
    "PLC Soft Restart": "PLC 软重启",
    "PLC soft restart required for IP changes. Super User required.": "修改网络参数后需软重启 PLC 生效。需超级用户权限。",
    "PLC soft restart required for IP changes. Maintenance login required.": "修改网络参数后需软重启 PLC 生效。需登录维护权限。",
    "Status: Maintenance login required to update settings.": "状态: 修改网络参数需登录维护权限。",
    "Status: Super User logged in. All restrictions lifted.": "状态: 超级用户已登录，已解除所有操作限制。",
    "Super User active. All restrictions lifted.": "超级用户已就绪，所有限制已解除。",
}

# Reverse lookup table for fallback
REVERSE_TRANSLATIONS = {v: k for k, v in TRANSLATIONS.items()}


class I18nManager(QObject):
    language_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._current_lang = "EN"

    @property
    def current_lang(self) -> str:
        return self._current_lang

    def set_language(self, lang: str):
        if lang not in ("EN", "CN"):
            return
        if self._current_lang != lang:
            self._current_lang = lang
            self.language_changed.emit(self._current_lang)

    def toggle(self) -> str:
        new_lang = "CN" if self._current_lang == "EN" else "EN"
        self.set_language(new_lang)
        return new_lang

    def tr(self, text: str, lang: str = None) -> str:
        """Translate text to target language (defaults to self.current_lang)"""
        if text is None:
            return ""
        target_lang = lang or self._current_lang
        if target_lang == "CN":
            return TRANSLATIONS.get(text, text)
        else:
            # When requesting EN, return original English
            if text in TRANSLATIONS:
                return text
            # If text is already in Chinese, look up English
            return REVERSE_TRANSLATIONS.get(text, text)


# Global singleton instance
I18N = I18nManager()


def tr(text: str, lang: str = None) -> str:
    """Convenience helper function for translations"""
    return I18N.tr(text, lang)
