# -*- coding: utf-8 -*-
"""
Global Qt Stylesheet (QSS) for PAC Hydraulic Pitch HMI
Matching modern industrial wind power design guidelines:
- Clean neutral gray palette (#E6E8EA background, #F8F9FA cards)
- High-contrast typography (Segoe UI / Microsoft YaHei)
- Industrial control states (hover, pressed, checked, disabled)
"""

QSS_STYLE = """
* {
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
}

QMainWindow {
    background-color: #E6E8EA;
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
}

QWidget {
    font-size: 12px;
    color: #222222;
}

QGroupBox {
    border: 1px solid #B0B5B9;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 14px;
    background-color: #F8F9FA;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #111111;
}

QLabel {
    background: transparent;
    color: #222222;
}

QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #A0A5AA;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1.5px solid #0284C7;
}

QLineEdit.highlight-yellow {
    background-color: #FFFDE7;
    border: 2px solid #FBC02D;
    color: #E65100;
    font-weight: bold;
}

QPushButton {
    background-color: #E4E7EB;
    border: 1px solid #A0A5AA;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
    color: #222222;
}

QPushButton:hover {
    background-color: #D6DADF;
    border-color: #80858A;
}

QPushButton:pressed {
    background-color: #C0C5CA;
}

QPushButton:disabled {
    background-color: #EAECEE;
    border-color: #D0D4D8;
    color: #9CA3AF;
}

QPushButton.nav-btn {
    background-color: #7B8085;
    border: 1px solid #63676B;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 4px;
}

QPushButton.nav-btn:hover {
    background-color: #63686D;
}

QPushButton.nav-btn:checked {
    background-color: #4A4E52;
    border: 2px solid #FFFFFF;
}

QPushButton.danger-btn {
    background-color: #D32F2F;
    border: 1px solid #B71C1C;
    color: white;
    font-weight: bold;
}

QPushButton.danger-btn:hover {
    background-color: #B71C1C;
}

QPushButton.primary-btn {
    background-color: #1976D2;
    border: 1px solid #0D47A1;
    color: white;
    font-weight: bold;
}

QPushButton.primary-btn:hover {
    background-color: #1565C0;
}

QPushButton.action-apply {
    background-color: #2E7D32;
    border: 1px solid #1B5E20;
    color: white;
    font-weight: bold;
}

QPushButton.action-apply:hover {
    background-color: #1B5E20;
}

QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #B0B5B9;
    gridline-color: #E0E0E0;
    font-size: 11px;
}

QHeaderView::section {
    background-color: #EAECEE;
    border: 1px solid #D0D4D8;
    font-weight: bold;
    padding: 4px;
    color: #333333;
}

QTabWidget::pane {
    border: 1px solid #B0B5B9;
    background-color: #FFFFFF;
}

QTabBar::tab {
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
    background-color: #E4E7EB;
    border: 1px solid #B0B5B9;
    border-bottom: none;
    min-width: 80px;
    height: 26px;
    padding: 3px 18px;
    margin-right: 3px;
    font-weight: bold;
    font-size: 12px;
    color: #222222;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    border-bottom: 2px solid #FFFFFF;
    color: #111111;
}

QSlider::groove:horizontal {
    border: 1px solid #999999;
    height: 6px;
    background: #DDDDDD;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #1976D2;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #555555;
    width: 16px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 8px;
}

QCheckBox {
    font-size: 12px;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #888888;
    border-radius: 2px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #2E7D32;
    border-color: #1B5E20;
    image: none;
}
"""
