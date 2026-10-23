# -*- coding: utf-8 -*-
"""
Internationalization (i18n) Module for Hydraulic Pitch HMI
Supports instantaneous runtime switching between English and Chinese
"""

from PyQt6.QtCore import QObject, pyqtSignal

# Master Translation Dictionary
TRANSLATIONS = {
    # --- Navigation & General ---
    "Overview": "总览",
    "Inspect": "总览",
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
    "Incorrect password for Maintenance Mode!": "维护模式密码不正确！",
    "Incorrect password!": "密码不正确！",

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
    "Status: Maintenance login required to update settings.": "状态: 修改网络参数需登录维护权限。",
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
    "Status: Super User logged in. All restrictions lifted.": "状态: 超级用户已登录，已解除所有操作限制。",
    "Super User active. All restrictions lifted.": "超级用户已就绪，所有限制已解除。",

    # --- Mode Card & Generic Status Badges ---
    "Manual Mode Control": "手动模式管理",
    "Maintenance Mode Control": "维护模式管理",
    "Access Status:": "准入状态:",
    "✔ Active": "✔ 运行中",
    "✔ In Maintenance": "✔ 维护中",
    "✔ Ready to Test": "✔ 允许动作测试",
    "✔ Ready to Enter": "✔ 具备准入条件",
    "✔ Ready": "✔ 就绪",
    "✔ Super Access": "✔ 超级权限",
    "🔓 Unlocked": "🔓 已解锁",
    "🔒 Offline": "🔒 离线",
    "🔒 Require Login": "🔒 需登录",
    "🔒 Require Stopped": "🔒 需处于已停止",
    "🔒 Need Aborted": "🔒 需处于已中止",
    "🔒 Require Maint.": "🔒 需维护模式",
    "🔒 Require Maint. & Login": "🔒 需维护模式并登录",
    "🔒 Require Manual Mode": "🔒 需手动模式",
    "Exit Manual Mode ✖": "退出手动模式 ✖",
    "Exit Maint. Mode ✖": "退出维护模式 ✖",
    "Request Manual Mode ⚙": "请求手动模式 ⚙",
    "Request Maint. Mode ⚙": "请求进入维护模式 ⚙",

    # --- Mode Prompts & Card Texts ---
    "PLC communication offline. Mode switch disabled.": "PLC 通信已断开，模式切换不可用。",
    "Active in Maintenance Mode. Testing enabled.": "当前处于维护模式，允许进行开关阀与动作测试。",
    "Preconditions met. Ready to enter maintenance mode.": "前置条件已满足，可请求维护模式。",
    "Must be in Aborted state and logged in.": "需处于已中止 (Aborted) 状态且已登录维护权限。",
    "System must be in Aborted state to enter.": "系统需处于已中止 (Aborted) 状态方可进入。",
    "Manual mode active. Ready to exit manual mode.": "手动模式运行中，可请求退出手动模式。",
    "Super User active. Ready to enter manual mode.": "超级用户已就绪，可直接进入手动模式。",
    "Pitch System is ready to enter manual mode.": "变桨系统已就绪，可请求进入手动模式。",
    "PAC must be STOPPED to enter manual mode.": "PAC 必须处于 STOPPED 状态方可进入手动模式。",
    "Fast Speed\nSelected": "快速模式\n(已选中)",
    "Slow Speed\nSelected": "慢速模式\n(已选中)",
    "Deactivate Pump 1": "停止润滑泵 1",
    "Deactivate Pump 2": "停止润滑泵 2",
    "Logged In": "已登录",

    # --- Manual Page Additional Labels ---
    "Blade": "叶片",
    "Offset [°]": "偏置",
    "Blade selected": "桨叶选择",
    "Blade safe": "桨叶安全",
    "Remote box speed": "手操盒速度",
    "Fast speed": "快速",
    "Slow speed": "慢速",
    "Current Pos.": "当前开度",
    "Pitch Lock Control": "变桨锁控制",
    "Engaged": "已落锁",
    "Released": "已释放",
    "Fast/Slow Speed": "快/慢速选择",
    "Move Blade": "移动桨叶",
    "Pump 1:": "润滑泵 1:",
    "Pump 2:": "润滑泵 2:",
    "Feather": "顺桨",
    "Fine": "开桨",
    "Warning - Manual Mode": "安全警告 - 手动模式",
    "Producing Mode": "生产模式",
    "Communication Offline": "通信断开",
    "Calibration": "标定",
    "Calibration Success": "标定成功",
    "Pitch Position Calibration applied successfully to PLC!": "变桨位置标定已成功下发至 PLC！",
    "GRD Calibration applied successfully to PLC!": "GRD 标定已成功下发至 PLC！",

    # --- Maintenance Page Additional Labels ---
    "Request HPU Buildup": "请求 HPU 泵站建压",
    "Lub. Pump 1": "润滑泵 1",
    "Lub. Pump 2": "润滑泵 2",
    "Apply": "应用",
    "Valve actuation & Prop. Valve 102A control": "多路阀动作与比例阀 102A 控制",

    # --- Network Page Additional Messages ---
    "Format Error": "格式错误",
    "PLC Symbol Missing Warning": "PLC 节点未导出警告",
    "Network Settings": "网络设置",
    "PLC Soft Restart Confirmation": "PLC 软重启确认",
    "PLC soft restart command sent successfully!": "PLC 软重启指令已成功下发！",
    "Offline, updated locally only": "当前离线，仅在本地更新",
    "PLC symbol missing, updated locally only": "PLC 节点未发布，参数仅在本地更新",
    "Sent to PLC. Restart controller to apply": "参数已下发至 PLC，重启控制器生效",

    # --- OPC UA Settings Dialog ---
    "OPC UA Connection Settings": "OPC UA 连接设置",
    "Offline / Disconnected": "离线 / Disconnected",
    "Frames:": "数据帧:",
    "Server IP / Host:": "PLC 服务器 IP:",
    "Test": "测试连接",
    "Disconnect": "断开连接",
    "Apply & Reconnect": "应用并重连",
    "Close": "关闭",
    "Testing connection...": "正在测试连接...",
    "Disconnected from server": "已主动断开连接",

    # --- Tooltips, Prompts & Dialogs ---
    "Offset Valid Range": "偏置有效范围",
    "GRD Valid Range": "GRD 有效范围",
    "Input Range Error": "输入范围错误",
    "Blade Selection": "桨叶选择",
    "Blade A (102A):": "叶片 A 比例阀:",
    "Blade B (102A):": "叶片 B 比例阀:",
    "Blade C (102A):": "叶片 C 比例阀:",
    "Spool FB:": "阀芯反馈:",
    "Interlock:": "准入状态:",
    "Notice: After setting valves or proportional command, click 'Apply Changes' to transmit to PLC.": "提示：修改阀门复选框或比例阀开度后，点击右下角【应用更改】下发至 PLC。",
    "⚠️ Authorized, but PLC Symbol Configuration does not export network variables (BadNodeIdUnknown).": "⚠️ 权限正常，但 PLC 符号配置未发布网络变量 (BadNodeIdUnknown)，修改仅在本地生效。",
    "Status: Maintenance login required. ⚠️ PLC symbol not exported.": "状态: 需维护登录。⚠️ PLC 符号配置未发布 Common.PVturbineSpecific.network",
    "WARNING: Entering the hub is NOT safe under any circumstances in Manual Mode!\n\nDo you want to proceed?": "⚠️ 严重警告：\n在手动模式下，任何情况下进入轮毂都是不安全的！\n\n是否确认请求进入手动模式？",
    "⚠️ PLC communication is offline. Cannot toggle pitch lock!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法切换变桨锁销动作！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot apply pitch position calibration to controller!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发变桨位置标定参数至控制器！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot apply GRD calibration to controller!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发 GRD 标定参数至控制器！\n\n请检查底层 OPC UA 通信连接。",
    "Warning - Maintenance Mode": "安全警告 - 维护模式",
    "WARNING: Entering the hub is NOT safe under any circumstances in Maintenance Mode!\n\nDo you want to proceed?": "⚠️ 严重警告：\n在维护模式下，任何情况下进入轮毂都是不安全的！\n\n是否确认请求进入维护模式？",
    "HPU pressure request applied to PLC successfully.": "HPU 建压请求已成功下发至 PLC。",
    "⚠️ PLC communication is offline. Cannot apply HPU settings!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发 HPU 动力单元设置！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot reset HPU settings!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法复位 HPU 动力单元！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot apply lubrication settings!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发润滑测试设置！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot reset lubrication settings!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法复位润滑测试设置！\n\n请检查底层 OPC UA 通信连接。",
    "Lubrication pump settings applied to PLC successfully.": "润滑泵测试设置已成功下发至 PLC。",
    "⚠️ PLC communication is offline. Cannot apply PAC valve actions!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发 PAC 阀门动作指令！\n\n请检查底层 OPC UA 通信连接。",
    "PAC Control": "PAC 阀门动作",
    "PAC valve matrix and proportional commands applied to PLC successfully!": "PAC 开关阀动作及比例阀指令已成功下发至 PLC！",
    "PAC valve actuations and proportional commands applied to PLC successfully!": "PAC 开关阀动作及比例阀指令已成功下发至 PLC！",
    "Interlock Restriction": "准入限制",
    "System is not in ABORTED state!\nPlease abort the pitch system before requesting Maintenance Mode.": "系统当前未处于 已中止 (Aborted) 状态！\n请先中止变桨系统，然后再请求进入维护模式。",
    "⚠️ PLC communication is offline. Cannot reset PAC valves!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法复位 PAC 阀门设置！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot toggle lubrication pump!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法切换润滑泵动作！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot acknowledge alarms!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法确认报警！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot reset safety!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法复位安全链！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot send START/STOP command!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发启动/停止指令！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ PLC communication is offline. Cannot switch operation mode!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法切换运行模式！\n\n请检查底层 OPC UA 通信连接。",

    # --- Authentication & Login Card ---
    "● Logged In": "● 已登录",
    "○ Logged Out": "○ 未登录",
    "Password Error": "密码错误",

    # --- Connectivity & Diagnostics ---
    "Online": "在线",
    "Offline": "离线",
    "OPC UA Server: {ep} [ONLINE]\nClick to configure": "OPC UA 服务器: {ep} [在线]\n点击打开连接设置",
    "OPC UA Server: {ep} [Disconnected]\nClick to configure": "OPC UA 服务器: {ep} [离线]\n点击打开连接设置",
    "🔍 Test": "🔍 测试连接",
    "Apply && Reconnect": "应用并重连",
    "Online: {url}": "在线: {url}",
    "Offline: {msg}": "离线: {msg}",
    "✔ Connection established successfully": "✔ 连接已成功建立，通信正常",
    "Reconnecting: {msg}...": "正在尝试连接: {msg}...",
    "Frames: {frames:,}": "数据帧: {frames:,}",
    "✔ Connected ({latency:.1f} ms)": "✔ 通信正常 (延迟: {latency:.1f} ms)",
    "✖ Failed: {msg}": "✖ 连接失败: {msg}",
    "Reconnecting to {url}...": "正在重连至 {url}...",

    # --- Network Page Validation & Action Dialogs ---
    "Invalid Hostname: '{host}'!\nOnly alphanumeric characters, underscores, and hyphens allowed (1-32 chars).": "无效的主机名: '{host}'！\n主机名仅支持字母、数字、下划线及连字符，长度 1~32 位。",
    "Invalid IPv4 address: '{ip}'!": "无效的 IPv4 地址: '{ip}'！",
    "Invalid subnet mask: '{mask}'!": "无效的子网掩码: '{mask}'！",
    "⚠️ PLC communication is offline. Cannot send network settings to controller!\n\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发网络配置至控制器！\n\n请检查底层 OPC UA 通信连接。",
    "⚠️ Write Failed (Error: BadNodeIdUnknown)\n\nThe node 'Common.PVturbineSpecific.network' is not published in CODESYS Symbol Configuration.\n\n• PLC hardware: NOT written (symbol not exported)\n\n💡 Solution: In CODESYS Symbol Configuration, check 'Common.PVturbineSpecific' and perform Online Change.": "⚠️ 写入失败 (错误: BadNodeIdUnknown)\n\n当前 CODESYS PLC 的【符号配置】(Symbol Configuration) 中未导出 'Common.PVturbineSpecific.network'，OPC UA 无法寻址该节点。\n\n• PLC 控制器硬件：未能写入（变量未发布）\n\n💡 解决建议：请在 CODESYS 项目的【Symbol Configuration】中勾选 'Common.PVturbineSpecific' 变量，并执行在线变更 (Online Change)。",
    "PLC symbol missing, cannot apply": "PLC 节点未发布，无法下发",
    "✔ Network parameters sent to PLC successfully!\n\nPlease perform PLC Soft Restart below to apply changes.": "✔ 网络参数已成功下发至 PLC！\n\n请在下方点击【🔄 PLC 软重启】使新网络配置生效。",
    "⚠️ WARNING: Are you sure you want to send Soft Restart (sysReset) to the PLC?\n\nThis will restart the PLC controller to apply settings. Please verify site safety and ensure no personnel in the hub!": "⚠️ 警告：确定要向 PLC 发送软重启指令 (sysReset) 吗？\n\n此操作将使 CODESYS PLC 控制器重启并应用新的网络设置，请确保现场设备安全并且人员不在轮毂内！",
    "⚠️ PLC communication is offline. Cannot send soft restart command!\nPlease check OPC UA connection.": "⚠️ 当前 PLC 通信已断开，无法下发软重启指令！\n请检查底层 OPC UA 通信连接。",

    # --- Manual Page Calibration Prompts ---
    "Offset Valid Range: {min_deg:.1f}° ~ {max_deg:.1f}°": "偏置有效范围: {min_deg:.1f}° ~ {max_deg:.1f}°",
    "GRD Valid Range: {min_val} ~ {max_val} pulse/(cm/s)": "GRD 有效范围: {min_val} ~ {max_val} pulse/(cm/s)",
    "Offset values must be within valid range [{min_deg:.1f}°, {max_deg:.1f}°]!\nOut of range:\n{items}": "偏置值必须在有效范围 [{min_deg:.1f}°, {max_deg:.1f}°] 内！\n超出范围项:\n{items}",

    # --- Remote Box Alert & MsgBox ---
    "Remote Box Disconnected Warning": "线控盒断开警告",
    "Remote box is not connected and blades are not safe. Please reconnect the remote box or abort the system.": "线控盒已断开且叶片未回到安全位置。请重新连接线控盒，或点击中止系统。",
    "Abort System": "中止系统",
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
            if text in TRANSLATIONS:
                return TRANSLATIONS[text]
            # Dynamic pattern matching for PAC countdown status messages
            if text.startswith('PAC: "Clearing - Waiting for acceptable accumulator pressure. Time left:'):
                sec = text.rsplit(":", 1)[-1].strip().rstrip('"').strip()
                return f'PAC: "清除中 - 等待蓄能器建压达标。剩余时间: {sec}"'
            if text.startswith('PAC: "Aborting - Waiting for blades feather & pitch locks. Time left:'):
                sec = text.rsplit(":", 1)[-1].strip().rstrip('"').strip()
                return f'PAC: "中止中 - 等待叶片顺桨并投入变桨锁。剩余时间: {sec}"'
            return TRANSLATIONS.get(text, text)
        else:
            # When requesting EN, return original English
            if text in TRANSLATIONS:
                return text
            if text.startswith('PAC: "清除中 - 等待蓄能器建压达标。剩余时间:'):
                sec = text.rsplit(":", 1)[-1].strip().rstrip('"').strip()
                return f'PAC: "Clearing - Waiting for acceptable accumulator pressure. Time left: {sec}"'
            if text.startswith('PAC: "中止中 - 等待叶片顺桨并投入变桨锁。剩余时间:'):
                sec = text.rsplit(":", 1)[-1].strip().rstrip('"').strip()
                return f'PAC: "Aborting - Waiting for blades feather & pitch locks. Time left: {sec}"'
            return REVERSE_TRANSLATIONS.get(text, text)


# Global singleton instance
I18N = I18nManager()


def tr(text: str, lang: str = None) -> str:
    """Convenience helper function for translations"""
    return I18N.tr(text, lang)
