# -*- coding: utf-8 -*-
"""
Custom Industrial UI Widgets
Provides Hexagonal Start/Stop buttons, Status LEDs, and Value Display Cards
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import (
    QPainter, QPolygonF, QColor, QBrush, QPen, QFont, QPixmap, QIcon,
    QLinearGradient, QRadialGradient, QPainterPath
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSize


def _get_hex_points(cx, cy, r):
    points = []
    for i in range(6):
        deg = 60 * i - 30
        rad = math.radians(deg)
        points.append(QPointF(cx + r * math.cos(rad), cy + r * math.sin(rad)))
    return points


def _create_hex_poly(cx, cy, r):
    return QPolygonF(_get_hex_points(cx, cy, r))


class HexagonButton(QPushButton):
    """
    High-End Embedded Industrial Hexagonal Start/Stop Button.
    Features CNC-machined recessed bezel sunken into the machine panel,
    anodized titanium retaining ring, illuminated satin cap, laser-etched
    legend, and tactile physical press travel.
    """
    def __init__(self, mode="START", parent=None):
        super().__init__(parent)
        self.setFixedSize(86, 96)
        self.mode = mode.upper()  # "START" or "STOP"
        self.hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

    def set_mode(self, mode):
        self.mode = mode.upper()
        self.update()

    def enterEvent(self, e):
        self.hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        is_pressed = self.isDown()
        is_start = (self.mode == "START")

        # -------------------------------------------------------------
        # LAYER 1: SUNKEN EMBEDDED SOCKET (Milled into #CFD4DA panel)
        # -------------------------------------------------------------
        r_outer_bevel = 43.0
        r_cavity = 41.0

        # Outer milled chamfer on panel
        poly_bevel = _create_hex_poly(cx, cy, r_outer_bevel)
        bevel_grad = QLinearGradient(cx, cy - r_outer_bevel, cx, cy + r_outer_bevel)
        bevel_grad.setColorAt(0.0, QColor(160, 170, 182, 160))  # Top shadow
        bevel_grad.setColorAt(1.0, QColor(255, 255, 255, 180))  # Bottom specular highlight
        painter.setPen(QPen(bevel_grad, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly_bevel)

        # Deep Cavity Fill: gradient from dark socket ceiling to ambient floor
        poly_cavity = _create_hex_poly(cx, cy, r_cavity)
        cav_grad = QLinearGradient(cx - 15, cy - r_cavity, cx + 15, cy + r_cavity)
        cav_grad.setColorAt(0.0, QColor(22, 27, 34))    # Deep dark socket roof
        cav_grad.setColorAt(0.35, QColor(36, 44, 56))   # Inner dark wall
        cav_grad.setColorAt(0.75, QColor(55, 65, 81))   # Subtle bottom floor
        cav_grad.setColorAt(1.0, QColor(75, 85, 99))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cav_grad))
        painter.drawPolygon(poly_cavity)

        # Cavity Lip: Inner drop shadow at top, soft specular highlight at bottom
        pts_c = _get_hex_points(cx, cy, r_cavity)
        # Top 3 segments (shadow cast into recess)
        pen_top_shadow = QPen(QColor(10, 14, 20, 240), 1.6)
        painter.setPen(pen_top_shadow)
        painter.drawLine(pts_c[4].toPoint(), pts_c[5].toPoint())
        painter.drawLine(pts_c[5].toPoint(), pts_c[0].toPoint())
        painter.drawLine(pts_c[0].toPoint(), pts_c[1].toPoint())

        # Bottom 3 segments (soft specular highlight)
        pen_bot_highlight = QPen(QColor(241, 245, 249, 140), 1.2)
        painter.setPen(pen_bot_highlight)
        painter.drawLine(pts_c[1].toPoint(), pts_c[2].toPoint())
        painter.drawLine(pts_c[2].toPoint(), pts_c[3].toPoint())
        painter.drawLine(pts_c[3].toPoint(), pts_c[4].toPoint())

        # -------------------------------------------------------------
        # LAYER 2: MACHINED TITANIUM / STEEL BEZEL RING
        # -------------------------------------------------------------
        # Physical tactile travel: shifts 2px into socket when pressed
        travel = 2.0 if is_pressed else 0.0
        bcx = cx
        bcy = cy + travel

        r_bezel = 36.5
        poly_bezel = _create_hex_poly(bcx, bcy, r_bezel)

        # Cast shadow from the elevated button onto the socket bottom
        if not is_pressed:
            sh_poly = _create_hex_poly(bcx, bcy + 2.5, r_bezel)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 110)))
            painter.drawPolygon(sh_poly)

        # CNC Brushed Titanium Gradient
        bezel_grad = QLinearGradient(bcx - r_bezel, bcy - r_bezel, bcx + r_bezel, bcy + r_bezel)
        bezel_grad.setColorAt(0.00, QColor(241, 245, 249))  # Specular glint
        bezel_grad.setColorAt(0.20, QColor(148, 163, 184))  # Brushed metal body
        bezel_grad.setColorAt(0.50, QColor(226, 232, 240))  # Central sheen
        bezel_grad.setColorAt(0.80, QColor(100, 116, 139))
        bezel_grad.setColorAt(1.00, QColor(51, 65, 85))    # Dark underside
        painter.setPen(QPen(QColor(30, 41, 59), 1.0))
        painter.setBrush(QBrush(bezel_grad))
        painter.drawPolygon(poly_bezel)

        # -------------------------------------------------------------
        # LAYER 3: LUXURY TRANSLUCENT INDUSTRIAL BUTTON CAP
        # -------------------------------------------------------------
        r_cap = 31.0
        poly_cap = _create_hex_poly(bcx, bcy, r_cap)

        # Subtle dark bezel-to-cap bevel groove
        painter.setPen(QPen(QColor(15, 23, 42, 200), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly_cap)

        # Button Face Radial / Linear Gradient
        cap_grad = QLinearGradient(bcx, bcy - r_cap, bcx, bcy + r_cap)
        if is_start:
            if is_pressed:
                cap_grad.setColorAt(0.0, QColor(4, 120, 87))    # Darker emerald pressed
                cap_grad.setColorAt(0.5, QColor(5, 150, 105))
                cap_grad.setColorAt(1.0, QColor(6, 78, 59))
            elif self.hovered:
                cap_grad.setColorAt(0.0, QColor(52, 211, 153))  # Vibrant hover glow
                cap_grad.setColorAt(0.35, QColor(16, 185, 129))
                cap_grad.setColorAt(0.85, QColor(5, 150, 105))
                cap_grad.setColorAt(1.0, QColor(4, 90, 68))
            else:
                cap_grad.setColorAt(0.0, QColor(34, 197, 94))   # Crisp industrial green
                cap_grad.setColorAt(0.35, QColor(16, 185, 129))
                cap_grad.setColorAt(0.85, QColor(5, 120, 85))
                cap_grad.setColorAt(1.0, QColor(4, 78, 59))
            inner_rim = QColor(167, 243, 208, 140)
        else:  # STOP
            if is_pressed:
                cap_grad.setColorAt(0.0, QColor(185, 28, 28))
                cap_grad.setColorAt(0.5, QColor(220, 38, 38))
                cap_grad.setColorAt(1.0, QColor(127, 29, 29))
            elif self.hovered:
                cap_grad.setColorAt(0.0, QColor(248, 113, 113))
                cap_grad.setColorAt(0.35, QColor(239, 68, 68))
                cap_grad.setColorAt(0.85, QColor(220, 38, 38))
                cap_grad.setColorAt(1.0, QColor(153, 27, 27))
            else:
                cap_grad.setColorAt(0.0, QColor(239, 68, 68))
                cap_grad.setColorAt(0.35, QColor(220, 38, 38))
                cap_grad.setColorAt(0.85, QColor(185, 28, 28))
                cap_grad.setColorAt(1.0, QColor(127, 29, 29))
            inner_rim = QColor(254, 202, 202, 140)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cap_grad))
        painter.drawPolygon(poly_cap)

        # Delicate precision inner facet rim
        r_facet = 28.0
        poly_facet = _create_hex_poly(bcx, bcy, r_facet)
        painter.setPen(QPen(inner_rim, 0.9))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly_facet)

        # Upper glass highlight
        pts_f = _get_hex_points(bcx, bcy, r_facet)
        pen_glass = QPen(QColor(255, 255, 255, 160), 1.2)
        painter.setPen(pen_glass)
        painter.drawLine(pts_f[4].toPoint(), pts_f[5].toPoint())
        painter.drawLine(pts_f[5].toPoint(), pts_f[0].toPoint())

        # -------------------------------------------------------------
        # LAYER 4: LASER ETCHED ILLUMINATED TYPOGRAPHY
        # -------------------------------------------------------------
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
        painter.setFont(font)

        text_rect = QRectF(bcx - 34, bcy - 12, 68, 24)

        # Crisp clean pure white lettering
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.mode)



class StatusLed(QWidget):
    """Circular or square LED indicator"""
    def __init__(self, color="grey", shape="square", size=16, parent=None):
        super().__init__(parent)
        self._color = color
        self._shape = shape
        self._size = size
        self.setFixedSize(size + 4, size + 4)

    def set_color(self, color):
        self._color = color
        self.update()

    def set_state(self, is_active, true_color="green", false_color="grey"):
        self.set_color(true_color if is_active else false_color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_map = {
            "green": QColor(34, 197, 94),
            "red": QColor(239, 68, 68),
            "yellow": QColor(245, 158, 11),
            "blue": QColor(59, 130, 246),
            "grey": QColor(209, 213, 219),
            "darkgrey": QColor(107, 114, 128)
        }
        fill_color = color_map.get(self._color.lower(), QColor(200, 200, 200))
        border_color = fill_color.darker(130)

        pen = QPen(border_color, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill_color))

        rect_offset = 2
        s = self._size

        if self._shape == "circle":
            painter.drawEllipse(rect_offset, rect_offset, s, s)
        else:
            painter.drawRect(rect_offset, rect_offset, s, s)


class ValueDisplay(QWidget):
    """Standard Industrial Name - Value Box with Unit"""
    def __init__(self, label_text, unit="", initial_val="0.0", label_width=110,
                 stretch_val=True, width=80, align=Qt.AlignmentFlag.AlignLeft, label_boxed=True, parent=None):
        super().__init__(parent)
        self.raw_label = label_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # 1. Left Label (Compact fixed width, avoiding 50/50 equal split)
        self.lbl_name = QLabel(label_text)
        self.lbl_name.setFixedWidth(label_width)
        self.lbl_name.setFixedHeight(24)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if label_boxed:
            self.lbl_name.setStyleSheet("""
                background-color: #F8F9FA;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                color: #374151;
            """)
        else:
            self.lbl_name.setStyleSheet("""
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: bold;
                color: #374151;
                padding: 2px 4px;
            """)

        # 2. Right Value Display (Stretches to fill remaining space, preventing text clipping)
        self.box_val = QLabel(initial_val)
        self.box_val.setFixedHeight(24)
        self.box_val.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self.box_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.box_val.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #B0B5B9;
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 500;
            color: #111827;
        """)

        layout.addWidget(self.lbl_name, 0)
        if stretch_val:
            layout.addWidget(self.box_val, 1)
        else:
            self.box_val.setFixedWidth(width)
            layout.addWidget(self.box_val, 0)
            layout.addStretch(1)

        if unit:
            self.lbl_unit = QLabel(unit)
            self.lbl_unit.setStyleSheet("color: #666666; font-size: 11px; background: transparent; border: none;")
            self.lbl_unit.setFixedWidth(28)
            layout.addWidget(self.lbl_unit, 0)

    def set_value(self, val):
        self.box_val.setText(str(val))
        self.box_val.setToolTip(str(val))

    def retranslate_ui(self, lang="EN"):
        from utils.i18n import tr
        self.lbl_name.setText(tr(self.raw_label, lang))


class WarningModal(QDialog):
    """Safety Warning Modal dialog before entering manual/maintenance mode.
    Directly associated with CODESYS Common.hmi.msgBox.btnOk / btnAbort.
    """
    def __init__(self, title, message, parent=None, opcua_service=None):
        super().__init__(parent)
        self.opcua_service = opcua_service
        self.setWindowTitle(title)
        self.setFixedSize(450, 180)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("font-size: 13px; font-weight: bold; color: #B71C1C;")
        layout.addWidget(lbl_msg)

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        layout.addWidget(self.btns)

    def accept(self):
        """User clicked OK: Pulse Common.hmi.msgBox.btnOk = 1"""
        if self.opcua_service:
            try:
                self.opcua_service.send_msgbox_ok()
            except Exception as e:
                print(f"[WarningModal] Error pulsing msgbox OK: {e}")
        super().accept()

    def reject(self):
        """User clicked Cancel: Pulse Common.hmi.msgBox.btnAbort = 1"""
        if self.opcua_service:
            try:
                self.opcua_service.send_msgbox_abort()
            except Exception as e:
                print(f"[WarningModal] Error pulsing msgbox Abort: {e}")
        super().reject()

