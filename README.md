# Hydraulic-Pitch-HMI

**大型风电机组液压变桨控制系统上位机人机界面 (Hydraulic Pitch Control System HMI)**

本项目基于 **Python + PyQt6 + asyncua** 构建，专为大型兆瓦级风力发电机组液压变桨系统设计，符合工业人机界面标准与 PackML 状态机控制规范，通过 OPC UA 协议与下位机 CODESYS PLC 进行实时高速通信与数据交互。

---

## 🌟 主要功能特性

1. **实时巡检与状态监控 (Inspect Page)**
   - **三叶片实时遥测 (Blade A / B / C)**：实时采集液压缸位移 (`cylPos`)、实际变桨角 (`posActDeg`)、变桨速率 (`rateActDeg`)、活塞腔/杆腔压力及蓄能器压力。
   - **系统核心遥测**：PAC 控制器运行状态、润滑系统泵路与油箱、液压动力单元 (HPU) 压力与油温。

2. **手动控制与零位标定 (Manual & Calibration Page)**
   - **手动变桨控制**：支持快速 (Fast) / 慢速 (Slow) 变桨操作及角度微调。
   - **机械锁销控制**：叶片机械锁销投入/脱开状态切换。
   - **传感器零偏与齿轮比标定**：支持编码器齿轮传动比 (GRD) 与传感器零偏零位角度 (Zero Offset) 读取与在线配置。

3. **维护测试与执行机构诊断 (Maintenance Page)**
   - **液压换向阀独立控制**：支持对 8 组关键换向阀（V109、V119A、V119B、V116、V103、V120、V130、V132）的分叶片动作测试与诊断。
   - **比例伺服阀阀芯开度调节**：支持 -100% ~ +100% 比例阀开度设定与指令下发。

4. **报警管理与事件顺序记录 (Alarm Page)**
   - **实时报警监控**：与 CODESYS 下位机 `gAlarmCoreTable` 实时同步。
   - **历史事件追溯**：记录报警触发、确认与复位事件时序日志 (`gHistoryAlarmLog`)。
   - **指令下发**：支持全局报警确认 (`Acknowledge All`) 与安全链复位脉冲 (`Reset Safety`)。

5. **网络与通信诊断 (Network & Diagnostics Page)**
   - 实时监控 OPC UA 通信链路状态、丢包率与收发数据帧计数。
   - 内置通信参数配置与诊断测试弹窗，支持掉线自动重连与节点自适应校验。

6. **中英文双语界面与工业风格 (Bilingual & Industrial UI)**
   - 全页面支持一键切换简体中文 / 英文界面。
   - 遵循工业设计规范的高对比度中性灰工业主题。

---

## 🏗️ 目录结构

```text
hmi_python/
├── config.py                 # 全局配置参数 (OPC UA 端点、通信周期、角色口令等)
├── main.py                   # 上位机程序入口与自测执行
├── requirements.txt          # Python 依赖包清单
├── start_hmi.bat             # 一键启动批处理脚本
├── models/                   # 数据模型与核心服务层
│   ├── alarm_manager.py      # 报警管理模型与事件处理
│   ├── opcua_service.py      # 异步 OPC UA 通信客户端与命令队列服务
│   └── plc_state.py          # PAC 状态机、叶片参数及实时遥测数据模型
├── ui/                       # 界面视图层 (PyQt6)
│   ├── alarm_page.py         # 报警与历史记录页面
│   ├── inspect_page.py       # 状态巡检页面
│   ├── login_card.py         # 用户登录卡片组件
│   ├── maintenance_page.py   # 维护模式与液压阀诊断页面
│   ├── main_window.py        # 主窗口与侧边栏导航框架
│   ├── manual_page.py        # 手动控制与传感器标定页面
│   ├── mode_card.py          # 模式请求与状态卡片
│   ├── network_page.py       # 网络与系统参数页面
│   ├── opcua_settings_dialog.py # 通信连接配置对话框
│   └── styles.py             # 统一工业 QSS 样式表定义
├── utils/                    # 通用工具库
│   ├── card_framework.py     # 工业遥测卡片框架
│   ├── logger.py             # 循环日志记录器
│   └── widgets.py            # 自定义 UI 控件 (状态灯、数显组件、弹窗等)
├── resources/                # UI 静态资源与矢量图标
└── logs/                     # 运行日志输出目录
```

---

## 🚀 快速上手

### 环境依赖
* Python 3.10+
* Windows 10 / 11 (支持 CODESYS Control Win V3 运行环境)

### 1. 克隆仓库
```bash
git clone https://github.com/chdliulong-svg/Hydraulic-Pitch-HMI.git
cd Hydraulic-Pitch-HMI
```

### 2. 创建并激活虚拟环境
```bash
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. 安装依赖库
```bash
pip install -r requirements.txt
```

### 4. 启动运行
```bash
# 方式一：直接运行启动脚本
start_hmi.bat

# 方式二：命令行运行
python main.py

# 自动化测试/静默自检：
python main.py --test
```

---

## ⚙️ CODESYS OPC UA 节点配置说明
上位机默认连接服务端地址为：`opc.tcp://127.0.0.1:4840`，命名空间索引为 4 (`ns=4`)。
在 CODESYS 项目的**符号配置 (Symbol Configuration)** 中勾选发布以下变量即可完成对接：
* `Common.pac.*` (PackML 系统控制状态机与版本号)
* `Common.blade[0..2].*` (三叶片实时传感器及参数)
* `Common.hmi.*` (HMI 按钮命令与维护模式测试点位)
* `Common.gAlarmCoreTable.*` (报警状态核心表)
* `Common.gHistoryAlarmLog.*` (历史事件记录环形缓冲)
