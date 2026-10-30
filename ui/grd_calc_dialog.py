# -*- coding: utf-8 -*-
"""
=============================================================================
GRD 波导声速反向推算对话框 (GRD Reverse Calculation Dialog)
=============================================================================
依据油缸完全伸出时的固定机械全长 (标称设计全长: 822.0 mm) 进行反向精确推算：
GRD_new = GRD_cur * (S_fixed / S_measured)
=============================================================================
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt
from config import GRD_MIN_VALUE, GRD_MAX_VALUE
from utils.i18n import tr


class GrdCalcDialog(QDialog):
    """磁致伸缩传感器 GRD 反向推算向导对话框"""

    def __init__(
        self,
        blade_name: str = "Blade A",
        cur_grd: int = 279000,
        cur_pos_mm: float = 0.0,
        full_stroke_mm: float = 822.0,
        lang: str = "EN",
        parent=None
    ):
        super().__init__(parent)
        self.blade_name = blade_name
        self.cur_grd = int(cur_grd if cur_grd > 0 else 279000)
        self.cur_pos_mm = float(cur_pos_mm)
        self.full_stroke_mm = float(full_stroke_mm)
        self.lang = lang
        self.calculated_grd = self.cur_grd

        self.setWindowTitle(
            f"{self.blade_name} - " + ("GRD 波导声速反向推算" if self.lang == "CN" else "GRD Reverse Calculation")
        )
        self.setFixedWidth(440)
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
            }
            QLabel {
                color: #1E293B;
                font-size: 12px;
            }
        """)

        self._init_ui()
        self._recalculate()
        self.adjustSize()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. 参数输入表单组
        input_grp = QGroupBox("标定参数设定" if self.lang == "CN" else "Calibration Parameters")
        input_grp.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                font-weight: bold;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        grid = QGridLayout(input_grp)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        # 当前基准 GRD
        lbl_grd = QLabel("当前基准 GRD:" if self.lang == "CN" else "Current GRD:")
        self.spin_base_grd = QSpinBox()
        self.spin_base_grd.setRange(250000, 310000)
        self.spin_base_grd.setValue(self.cur_grd)
        self.spin_base_grd.setSuffix(" cm/s")
        self.spin_base_grd.setFixedHeight(26)
        self.spin_base_grd.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 3px; font-weight: bold;")
        self.spin_base_grd.valueChanged.connect(self._recalculate)

        grid.addWidget(lbl_grd, 0, 0)
        grid.addWidget(self.spin_base_grd, 0, 1)

        # 完全伸出固定物理全长
        lbl_full = QLabel("完全伸出固定全长:" if self.lang == "CN" else "Fixed Full Stroke:")
        self.spin_full_stroke = QDoubleSpinBox()
        self.spin_full_stroke.setRange(700.0, 950.0)
        self.spin_full_stroke.setDecimals(3)
        self.spin_full_stroke.setSingleStep(0.001)
        self.spin_full_stroke.setValue(self.full_stroke_mm)
        self.spin_full_stroke.setSuffix(" mm")
        self.spin_full_stroke.setFixedHeight(26)
        self.spin_full_stroke.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 3px; font-weight: bold; color: #0F172A;")
        self.spin_full_stroke.setToolTip("油缸制造物理全长硬挡块尺寸 (本系统标称为 822.000 mm)")
        self.spin_full_stroke.valueChanged.connect(self._recalculate)

        grid.addWidget(lbl_full, 1, 0)
        grid.addWidget(self.spin_full_stroke, 1, 1)

        # 当前油缸实测读数 (无损全精度 0.001 mm)
        lbl_meas = QLabel("伸出实测读数:" if self.lang == "CN" else "Measured Stroke:")
        self.spin_meas_stroke = QDoubleSpinBox()
        self.spin_meas_stroke.setRange(50.0, 950.0)
        self.spin_meas_stroke.setDecimals(3)
        self.spin_meas_stroke.setSingleStep(0.001)
        # 若当前油缸开度小于 100mm，预设为标称 822.0，避免在缩回位除零
        default_meas = self.cur_pos_mm if self.cur_pos_mm >= 100.0 else self.full_stroke_mm
        self.spin_meas_stroke.setValue(default_meas)
        self.spin_meas_stroke.setSuffix(" mm")
        self.spin_meas_stroke.setFixedHeight(26)
        self.spin_meas_stroke.setStyleSheet("background-color: white; border: 1px solid #0284C7; border-radius: 3px; font-weight: bold; color: #0284C7;")
        self.spin_meas_stroke.setToolTip("来自 PLC 实时采样的无损全精度油缸位移 (分辨率: 0.001 mm)")
        self.spin_meas_stroke.valueChanged.connect(self._recalculate)

        grid.addWidget(lbl_meas, 2, 0)
        grid.addWidget(self.spin_meas_stroke, 2, 1)

        main_layout.addWidget(input_grp)

        # 零位状态提示条
        if self.cur_pos_mm < 100.0:
            self.lbl_warn = QLabel(
                f"⚠️ 提示: 当前油缸未处于伸出状态 (读数: {self.cur_pos_mm:.3f} mm)。请先将油缸点动伸出至极限，或直接在上方手动输入实测读数。"
                if self.lang == "CN"
                else f"⚠️ Note: Current cylinder not fully extended ({self.cur_pos_mm:.3f} mm). Please extend cylinder or input measured value."
            )
            self.lbl_warn.setWordWrap(True)
            self.lbl_warn.setStyleSheet("color: #D97706; font-size: 10px; padding: 0 4px;")
            main_layout.addWidget(self.lbl_warn)

        # 3. 推算结果预览卡片
        res_card = QFrame()
        res_card.setStyleSheet("""
            QFrame {
                background-color: #F0FDF4;
                border: 1px solid #BBF7D0;
                border-radius: 6px;
            }
        """)
        r_layout = QVBoxLayout(res_card)
        r_layout.setContentsMargins(14, 10, 14, 10)
        r_layout.setSpacing(4)

        res_head = QHBoxLayout()
        lbl_res_t = QLabel("推算推荐 GRD:" if self.lang == "CN" else "Recommended GRD:")
        lbl_res_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #166534;")
        res_head.addWidget(lbl_res_t)

        self.lbl_result_val = QLabel("280,000 cm/s")
        self.lbl_result_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #15803D; font-family: 'Consolas', monospace;")
        res_head.addStretch()
        res_head.addWidget(self.lbl_result_val)
        r_layout.addLayout(res_head)

        delta_row = QHBoxLayout()
        self.lbl_delta = QLabel("校准修正量: +0 cm/s (+0.0%)")
        self.lbl_delta.setStyleSheet("font-size: 11px; color: #4B5563;")
        delta_row.addWidget(self.lbl_delta)
        delta_row.addStretch()

        self.lbl_status = QLabel("🟢 处于合理区间")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D;")
        delta_row.addWidget(self.lbl_status)
        r_layout.addLayout(delta_row)

        main_layout.addWidget(res_card)
        main_layout.addStretch()

        # 4. 底部动作按钮
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("取消" if self.lang == "CN" else "Cancel")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #CBD5E1;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("填入新数值" if self.lang == "CN" else "Apply to Input")
        self.btn_apply.setFixedHeight(30)
        self.btn_apply.setFixedWidth(120)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        btn_box.addWidget(self.btn_apply)

        main_layout.addLayout(btn_box)

    def _recalculate(self):
        base_grd = self.spin_base_grd.value()
        full_s = self.spin_full_stroke.value()
        meas_s = self.spin_meas_stroke.value()

        if meas_s <= 0.001:
            return

        calc = round(base_grd * (full_s / meas_s))
        self.calculated_grd = int(calc)

        self.lbl_result_val.setText(f"{self.calculated_grd:,} cm/s")

        delta = self.calculated_grd - base_grd
        pct = (delta / base_grd) * 100.0
        sign = "+" if delta >= 0 else ""
        self.lbl_delta.setText(
            f"校准修正量: {sign}{delta:,} cm/s ({sign}{pct:.3f}%)"
            if self.lang == "CN"
            else f"Correction: {sign}{delta:,} cm/s ({sign}{pct:.3f}%)"
        )

        # 范围合理性检查
        in_range = (GRD_MIN_VALUE <= self.calculated_grd <= GRD_MAX_VALUE)
        if in_range:
            self.lbl_status.setText("🟢 处于合理区间" if self.lang == "CN" else "🟢 In Range")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #15803D;")
            self.btn_apply.setEnabled(True)
        else:
            self.lbl_status.setText("⚠️ 超出推荐区间" if self.lang == "CN" else "⚠️ Out of Range")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #DC2626;")
            self.btn_apply.setEnabled(False)

    def _on_apply_clicked(self):
        self.accept()

    def get_calculated_grd(self) -> int:
        return self.calculated_grd
