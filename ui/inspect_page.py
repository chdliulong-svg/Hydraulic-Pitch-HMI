# -*- coding: utf-8 -*-
"""
Inspect Page (Overview / General Information)
Matching Figure 8 of DFB1001650_DFB011019
Fully refactored to use the unified TelemetryCard & BladeTelemetryCard framework
with separated dual outputs for position and speed, and pixel-perfect column alignment.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from utils.card_framework import TelemetryCard, BladeTelemetryCard, LubricationTelemetryCard


class InspectPage(QWidget):
    def __init__(self, plc_state, parent=None):
        super().__init__(parent)
        self.plc = plc_state
        self.current_lang = "EN"
        self.init_ui()
        self.plc.state_changed.connect(self.update_values)
        self.update_values()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(6)

        # Top Section: 3 Blade Cards referencing BladeTelemetryCard framework
        blades_layout = QHBoxLayout()
        blades_layout.setSpacing(6)

        self.blade_cards = []
        for b in self.plc.blades:
            card = BladeTelemetryCard(b.name)
            blades_layout.addWidget(card, 1)
            self.blade_cards.append(card)
        main_layout.addLayout(blades_layout, 1)

        # Bottom Section: PAC Status, Lubrication Status, HPU Status
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(6)

        # 1. PAC Status Card (using TelemetryCard framework)
        self.pac_card = TelemetryCard("PAC Status")
        self.pac_card.add_value_row("t_hub", "Temperature Hub", unit="°C", default_val="0.0")
        self.pac_card.add_value_row("t_cab", "Temperature cabinet", unit="°C", default_val="0.0")
        self.pac_card.add_value_row("t_oil", "Temperature oil", unit="°C", default_val="0.0")
        self.pac_card.add_value_row("cur_t1", "Supply Current T1 PAC", unit="A", default_val="0.00")
        self.pac_card.add_value_row("cur_t2", "Supply Current T2 PAC", unit="A", default_val="0.00")
        self.pac_card.add_value_row("cpu_temp", "PAC CPU temp.", unit="°C", default_val="0.0")
        self.pac_card.add_led_row("pwr_ok", "Power supply OK", color="grey", shape="square", size=14)
        bottom_layout.addWidget(self.pac_card, 1)

        # 2. Lubrication Status Card (using unified LubricationTelemetryCard framework)
        self.lub_card = LubricationTelemetryCard()
        bottom_layout.addWidget(self.lub_card, 1)

        # 3. HPU Status Card (using TelemetryCard framework)
        self.hpu_card = TelemetryCard("HPU Status (From MC)")
        self.hpu_card.add_status_row("state", "HPU State", default_status="Stopped")
        self.hpu_card.add_value_row("t_oil", "Temperature oil", unit="°C", default_val="0.0")
        self.hpu_card.add_value_row("p_accu", "Pressure accu", unit="bar", default_val="0.0")
        self.hpu_card.add_value_row("oil_lvl", "Oil level", unit="l", default_val="0")
        bottom_layout.addWidget(self.hpu_card, 1)

        main_layout.addLayout(bottom_layout, 2)

    def retranslate_ui(self, lang="EN"):
        """Retranslate all 3 Blade cards, PAC card, Lubrication card, and HPU card"""
        self.current_lang = lang
        for card in self.blade_cards:
            card.retranslate_ui(lang)
        self.pac_card.retranslate_ui(lang)
        self.lub_card.retranslate_ui(lang)
        self.hpu_card.retranslate_ui(lang)
        self.update_values()

    def update_values(self):
        """Sync live values from PLCStateManager to all telemetry cards"""
        from utils.i18n import tr
        for i, b in enumerate(self.plc.blades):
            self.blade_cards[i].update_from_blade_data(b, self.current_lang)

        # 1. Update PAC Status card
        self.pac_card.set_value("t_hub", f"{self.plc.temp_hub:.1f}")
        self.pac_card.set_value("t_cab", f"{self.plc.temp_cabinet:.1f}")
        self.pac_card.set_value("t_oil", f"{self.plc.temp_oil:.1f}")
        self.pac_card.set_value("cur_t1", f"{self.plc.current_t1:.2f}")
        self.pac_card.set_value("cur_t2", f"{self.plc.current_t2:.2f}")
        self.pac_card.set_value("cpu_temp", f"{self.plc.cpu_temp:.1f}")
        self.pac_card.set_led_state("pwr_ok", self.plc.power_supply_ok, "green", "grey")

        # 2. Update Lubrication Status card
        self.lub_card.set_led_state("tank1_ok", self.plc.lub_tank1_ok, "green", "grey")
        self.lub_card.set_led_state("piston_a1", self.plc.lub_piston_a1, "green", "grey")
        self.lub_card.set_led_state("piston_b1", self.plc.lub_piston_b1, "green", "grey")
        self.lub_card.set_led_state("piston_c1", self.plc.lub_piston_c1, "green", "grey")
        self.lub_card.set_led_state("tank2_ok", self.plc.lub_tank2_ok, "green", "grey")
        self.lub_card.set_led_state("piston_a2", self.plc.lub_piston_a2, "green", "grey")
        self.lub_card.set_led_state("piston_b2", self.plc.lub_piston_b2, "green", "grey")
        self.lub_card.set_led_state("piston_c2", self.plc.lub_piston_c2, "green", "grey")

        # 3. Update HPU card
        hpu_state_tr = tr(self.plc.hpu_state, self.current_lang)
        self.hpu_card.set_value("state", hpu_state_tr)
        self.hpu_card.set_value("p_accu", f"{self.plc.hpu_pressure_accu:.1f}")
        self.hpu_card.set_value("t_oil", f"{self.plc.hpu_temp_oil:.1f}")
        self.hpu_card.set_value("oil_lvl", f"{self.plc.hpu_oil_level:.0f}")
