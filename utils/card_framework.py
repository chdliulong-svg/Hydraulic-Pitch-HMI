# -*- coding: utf-8 -*-
"""
Universal Telemetry Card Framework for Industrial HMI
Implements pixel-perfect alignment, separate dual-output boxes for position and speed,
and standard reusable BladeTelemetryCard & TelemetryCard components.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QWidget
)
from PyQt6.QtCore import Qt
from utils.widgets import StatusLed


class ValueBox(QLabel):
    """Standardized white value display box with uniform width and height"""
    def __init__(self, text: str = "--", align=Qt.AlignmentFlag.AlignRight, width: int = 76, height: int = 22, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(width, height)
        self.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #B0B5B9;
            border-radius: 2px;
            padding: 1px 3px;
            font-size: 11px;
            font-weight: bold;
            color: #111111;
        """)


class TelemetryCard(QFrame):
    """
    通用遥测卡片框架 (Universal Telemetry Card Framework)
    - 采用 3 列严密网格布局，确保所有右侧数值框及 LED 指示灯在同一垂直线上 100% 像素级对齐。
    - 列 0: 变量名称标签（靠左对齐）
    - 列 1: 辅助数值框（如油缸位移 mm、线速度 mm/s，专用于双变量输出分框显示）
    - 列 2: 主数值框 / 角度框 / LED指示灯（靠右对齐，整列统一对齐基准线）
    """
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("telemetry_card")
        self.setStyleSheet("""
            QFrame#telemetry_card {
                background-color: #F8F9FA;
                border: 1px solid #B0B5B9;
                border-radius: 4px;
            }
            QLabel {
                background: transparent;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 11px;
                color: #222222;
            }
        """)

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(4)

        # Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #111111; margin-bottom: 2px;")
        self.main_layout.addWidget(self.lbl_title)

        # Internal 3-column Grid
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 2, 0, 0)
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(0, 1)  # Column 0 stretches to fill space
        self.main_layout.addLayout(self.grid)

        # Add stretch to push grid up directly below title, eliminating any blank gap
        self.main_layout.addStretch(1)

        # Registry for row controls: key -> ValueBox or StatusLed
        self._items: Dict[str, Any] = {}
        self._labels = []  # List of (QLabel, raw_text)
        self.raw_title = title
        self._current_row = 0

    def retranslate_ui(self, lang: str = "EN"):
        """Retranslate card title and all row labels to target language"""
        from utils.i18n import tr
        self.lbl_title.setText(tr(self.raw_title, lang))
        for lbl, raw_text in self._labels:
            lbl.setText(tr(raw_text, lang))

    def add_value_row(self, key: str, label: str, unit: str = "", default_val: str = "0.0") -> 'TelemetryCard':
        """
        添加标准单数值输出行（位于列2主数值列，保持全卡片右对齐基准线一致）
        标签跨 0-1 列以防止长文本在窄屏下被截断
        """
        lbl = QLabel(label)
        self.grid.addWidget(lbl, self._current_row, 0, 1, 2)
        self._labels.append((lbl, label))

        disp_text = f"{default_val} {unit}".strip() if unit else default_val
        box = ValueBox(disp_text, align=Qt.AlignmentFlag.AlignRight, width=76, height=22)
        self.grid.addWidget(box, self._current_row, 2)

        self._items[key] = (box, unit)
        self._current_row += 1
        return self

    def add_dual_output_row(self, key1: str, key2: str, label: str,
                            unit1: str = "", unit2: str = "",
                            default1: str = "0.0", default2: str = "0.0") -> 'TelemetryCard':
        """
        添加双数值独立分框输出行（位移与角度分开、线速度与角速度分开）
        - key1 输出位于列 1 框 (加长至 90px，支持 XX.X mm/s 及负数 -XX.X mm/s 完整显示)
        - key2 输出位于列 2 框 (76px，与单数值行保持统一右对齐基准线)
        """
        lbl = QLabel(label)
        self.grid.addWidget(lbl, self._current_row, 0)
        self._labels.append((lbl, label))

        # Output 1 (e.g. mm or mm/s) in Column 1: 90px
        text1 = f"{default1} {unit1}".strip() if unit1 else default1
        box1 = ValueBox(text1, align=Qt.AlignmentFlag.AlignRight, width=90, height=22)
        self.grid.addWidget(box1, self._current_row, 1)

        # Output 2 (e.g. ° or °/s) in Column 2: 76px
        text2 = f"{default2} {unit2}".strip() if unit2 else default2
        box2 = ValueBox(text2, align=Qt.AlignmentFlag.AlignRight, width=76, height=22)
        self.grid.addWidget(box2, self._current_row, 2)

        self._items[key1] = (box1, unit1)
        self._items[key2] = (box2, unit2)
        self._current_row += 1
        return self

    def add_status_row(self, key: str, label: str, default_status: str = "Inactive") -> 'TelemetryCard':
        """
        添加状态文本行（位于列2主数值列，居中对齐，加长至 76px）
        标签跨 0-1 列以防止长文本在窄屏下被截断
        """
        lbl = QLabel(label)
        self.grid.addWidget(lbl, self._current_row, 0, 1, 2)
        self._labels.append((lbl, label))

        box = ValueBox(default_status, align=Qt.AlignmentFlag.AlignCenter, width=76, height=22)
        self.grid.addWidget(box, self._current_row, 2)

        self._items[key] = (box, "")
        self._current_row += 1
        return self

    def add_led_row(self, key: str, label: str, color: str = "green", shape: str = "square", size: int = 14) -> 'TelemetryCard':
        """
        添加 LED 状态指示灯行（位于列2主数值列，精确靠右对齐）
        标签跨 0-1 列以防止长文本在窄屏下被截断
        """
        lbl = QLabel(label)
        self.grid.addWidget(lbl, self._current_row, 0, 1, 2)
        self._labels.append((lbl, label))

        led_holder = QWidget()
        led_holder.setFixedSize(76, 22)
        hl = QHBoxLayout(led_holder)
        hl.setContentsMargins(0, 0, 2, 0)
        hl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        led = StatusLed(color=color, shape=shape, size=size)
        hl.addWidget(led)
        self.grid.addWidget(led_holder, self._current_row, 2)

        self._items[key] = led
        self._current_row += 1
        return self

    def add_left_led_row(self, key: str, label: str, color: str = "grey", shape: str = "square", size: int = 14) -> 'TelemetryCard':
        """
        添加左侧指示灯行（指示灯在最左侧，文本标签在右侧，固定行高与其余行完全一致）
        """
        row_w = QWidget()
        row_w.setFixedHeight(22)
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(8)
        row_l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        led = StatusLed(color=color, shape=shape, size=size)
        lbl = QLabel(label)
        lbl.setStyleSheet("background: transparent; font-size: 11px; color: #222222;")

        row_l.addWidget(led, 0)
        row_l.addWidget(lbl, 1)

        self.grid.addWidget(row_w, self._current_row, 0, 1, 3)
        self._items[key] = led
        self._labels.append((lbl, label))
        self._current_row += 1
        return self

    def set_value(self, key: str, val: Any):
        """更新单个数值或状态框内容"""
        if key in self._items:
            entry = self._items[key]
            if isinstance(entry, tuple):
                box, unit = entry
                disp = f"{val} {unit}".strip() if unit else str(val)
                box.setText(disp)

    def set_led_state(self, key: str, is_active: bool, active_color: str = "green", inactive_color: str = "grey"):
        """更新单个 LED 状态"""
        if key in self._items:
            led = self._items[key]
            if isinstance(led, StatusLed):
                led.set_state(is_active, active_color, inactive_color)



class BladeTelemetryCard(TelemetryCard):
    """
    通用变桨叶片遥测卡片框架 (Standard Pitch Blade Telemetry Card)
    完整支持：
    1. 压力：蓄能器 (107)、活塞无杆腔 (135)、有杆腔 (136)
    2. 变桨跟踪参考值状态
    3. 油缸位移 (mm) 与叶片角度 (°) 独立分框输出
    4. 油缸速度 (mm/s) 与角速度 (°/s) 独立分框输出
    5. 比例阀开度 (%)
    6. 变桨锁指示灯 (135)
    """
    def __init__(self, blade_name: str, parent=None):
        super().__init__(blade_name, parent)
        self._setup_blade_rows()

    def _setup_blade_rows(self):
        # 1. 压力遥测行
        self.add_value_row("p_accu", "Pressure accu (107)", unit="bar", default_val="193.4")
        self.add_value_row("p_piston", "Pressure piston (135)", unit="bar", default_val="192.2")
        self.add_value_row("p_rod", "Pressure rod (136)", unit="bar", default_val="2.5")

        # 2. 变桨参考指令状态
        self.add_status_row("pitch_ref", "Pitch reference", default_status="Inactive")

        # 3. 位置输出行（严格分为两个独立显示框：油缸位移 mm + 叶片角度 °）
        self.add_dual_output_row("pos_cyl", "pos_ang", "Cyl. position",
                                unit1="mm", unit2="°",
                                default1="576", default2="89.0")

        # 4. 速度输出行（严格分为两个独立显示框：油缸速度 mm/s + 角速度 °/s）
        self.add_dual_output_row("spd_cyl", "spd_ang", "Cyl. speed",
                                unit1="mm/s", unit2="°/s",
                                default1="0.0", default2="0.0")

        # 5. 阀芯开度
        self.add_value_row("spool", "Spool position", unit="%", default_val="-0.1")

        # 6. 变桨机械锁
        self.add_led_row("pitch_lock", "Pitch lock engaged (135)", color="green", shape="square", size=14)

    def update_from_blade_data(self, b, lang="EN"):
        """
        根据 BladeData 模型对象自动刷新所有独立输出框
        """
        from utils.i18n import tr
        self.set_value("p_accu", f"{b.pressure_accu:.1f}")
        self.set_value("p_piston", f"{b.pressure_piston:.1f}")
        self.set_value("p_rod", f"{b.pressure_rod:.1f}")
        ref_text = tr("Active", lang) if b.pitch_reference_active else tr("Inactive", lang)
        self.set_value("pitch_ref", ref_text)

        # 两个输出严格分开更新
        self.set_value("pos_cyl", f"{b.cyl_pos_mm:.0f}")
        self.set_value("pos_ang", f"{b.angle_deg:.1f}")

        self.set_value("spd_cyl", f"{b.cyl_speed_mms:.1f}")
        self.set_value("spd_ang", f"{b.speed_degs:.1f}")

        self.set_value("spool", f"{b.spool_pos_pct:.1f}")
        self.set_led_state("pitch_lock", b.pitch_lock_engaged, "green", "grey")


class LubricationTelemetryCard(TelemetryCard):
    """
    通用润滑状态卡片框架 (Universal Lubrication Telemetry Card)
    完全基于 TelemetryCard 框架，保证与左右卡片标题严格水平对齐、行距严格一致
    """
    def __init__(self, parent=None):
        super().__init__("Lubrication Status", parent)
        self._setup_lubrication_rows()

    def _setup_lubrication_rows(self):
        items = [
            ("tank1_ok", "Grease Level Lub Tank 1 OK", "square"),
            ("piston_a1", "Piston A Tank1 Moving", "square"),
            ("piston_b1", "Piston B Tank1 Moving", "square"),
            ("piston_c1", "Piston C Tank1 Moving", "square"),
            ("tank2_ok", "Grease Level Lub Tank 2 OK", "square"),
            ("piston_a2", "Piston A Tank2 Moving", "square"),
            ("piston_b2", "Piston B Tank2 Moving", "square"),
            ("piston_c2", "Piston C Tank2 Moving", "square"),
        ]
        for key, text, shape in items:
            self.add_left_led_row(key, text, color="grey", shape=shape, size=13)

        # Default tank status OK
        self.set_led_state("tank1_ok", True, "green")
        self.set_led_state("tank2_ok", True, "green")

