# -*- coding: utf-8 -*-
"""
Alarm Management System
Matches B&R mapp AlarmX architecture and PLC source code (MpAlarmXStateEnum, FB_HistoryAlarm)
Handles Active Alarms and History events (Active/Reset/Ack).
Alarms are reported by the PLC; HMI displays and resets them without local severity mapping.
"""

from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from models.alarm_database import get_alarm_def, AlarmDefinition


class MpAlarmXStateEnum:
    """Matches PLC DUT: MpAlarmXStateEnum.st"""
    INACTIVE = 0        # 报警未激活且已确认 (正常)
    ACTIVE = 1          # 报警激活且未确认 (触发报警中)
    ACKNOWLEDGED = 2    # 报警激活且已确认 (报警持续，但已确认)
    UNACKNOWLEDGED = 3  # 报警已消除但未确认 (已复位消除，待确认)


class AlarmEvent:
    """Historical event transition types matching manual section 2.5"""
    EVENT_ACTIVE = "ACTIVE"  # (3) 激活: 从非活动到活动 (Inactive -> Active)
    EVENT_RESET = "RESET"    # (4) 复位: 从活动到非活动 (Active -> Inactive)
    EVENT_ACK = "ACK"        # (5) 确认: 从未确认到确认 (Unack -> Ack)


class AlarmItem:
    """Active Alarm entry enriched with static metadata from alarm_database"""
    def __init__(self, code, name=None, message=None, state=MpAlarmXStateEnum.ACTIVE, active_time=None, severity=None):
        self.code = int(code)
        self.def_info = get_alarm_def(self.code)
        self.name = name if (name and name != f"Alarm_{self.code}") else self.def_info.name
        self._custom_message = message if (message and not message.startswith("Alarm code ") and not message.startswith("未知报警代码 ")) else None
        self.severity = severity if severity is not None else self.def_info.severity
        self.state = state
        self.active_time = active_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.reset_time = None
        self.ack_time = None

    def get_message(self, lang="EN") -> str:
        if self._custom_message:
            return self._custom_message
        return self.def_info.get_message(lang)

    @property
    def message(self) -> str:
        return self.get_message("EN")

    @property
    def is_active(self):
        return self.state in [MpAlarmXStateEnum.ACTIVE, MpAlarmXStateEnum.ACKNOWLEDGED]

    @property
    def is_acked(self):
        return self.state in [MpAlarmXStateEnum.ACKNOWLEDGED, MpAlarmXStateEnum.INACTIVE]

    @is_acked.setter
    def is_acked(self, val):
        if val:
            self.state = MpAlarmXStateEnum.ACKNOWLEDGED if self.is_active else MpAlarmXStateEnum.INACTIVE
        else:
            self.state = MpAlarmXStateEnum.ACTIVE if self.is_active else MpAlarmXStateEnum.UNACKNOWLEDGED

    @property
    def timestamp(self):
        return self.active_time


class HistoryLogItem:
    """History Log Item matching PLC ST_HistoryAlarmItem.st enriched with alarm_database"""
    def __init__(self, code, name=None, message=None, event_type=AlarmEvent.EVENT_ACTIVE, timestamp=None, state_before=None, state_after=None, severity=None):
        self.code = int(code)
        self.def_info = get_alarm_def(self.code)
        self.name = name if (name and name != f"Alarm_{self.code}") else self.def_info.name
        self._custom_message = message if (message and not message.startswith("Alarm code ") and not message.startswith("未知报警代码 ")) else None
        self.severity = severity if severity is not None else self.def_info.severity
        self.event_type = event_type  # AlarmEvent.EVENT_ACTIVE / EVENT_RESET / EVENT_ACK
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.state_before = state_before
        self.state_after = state_after

    def get_message(self, lang="EN") -> str:
        if self._custom_message:
            return self._custom_message
        return self.def_info.get_message(lang)

    @property
    def message(self) -> str:
        return self.get_message("EN")

    @property
    def is_active(self):
        return self.event_type == AlarmEvent.EVENT_ACTIVE

    @property
    def is_acked(self):
        return self.event_type == AlarmEvent.EVENT_ACK or self.state_after in [MpAlarmXStateEnum.ACKNOWLEDGED, MpAlarmXStateEnum.INACTIVE]


class AlarmManager(QObject):
    alarms_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.active_alarms = []
        self.history_alarms = []

    def update_from_opcua(self, active_list: list, history_list: list):
        """Update active and history alarms directly from CODESYS PLC with local database enrichment"""
        # 1. Update active alarms
        new_active = []
        for item in active_list:
            code = item.get("code", 0)
            name = item.get("name")
            msg = item.get("message")
            sev = item.get("severity")
            state = item.get("state", MpAlarmXStateEnum.ACTIVE)
            t_str = item.get("timestamp")
            a_item = AlarmItem(code, name=name, message=msg, state=state, active_time=t_str, severity=sev)
            new_active.append(a_item)
        self.active_alarms = new_active

        # 2. Update history alarms if provided
        if history_list:
            new_history = []
            for item in history_list:
                code = item.get("code", 0)
                name = item.get("name")
                msg = item.get("message")
                sev = item.get("severity")
                t_str = item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                state = item.get("state", MpAlarmXStateEnum.ACTIVE)
                
                if state == MpAlarmXStateEnum.ACTIVE:
                    evt = AlarmEvent.EVENT_ACTIVE
                elif state == MpAlarmXStateEnum.ACKNOWLEDGED:
                    evt = AlarmEvent.EVENT_ACK
                else:
                    evt = AlarmEvent.EVENT_RESET

                h_item = HistoryLogItem(code, name=name, message=msg, event_type=evt, timestamp=t_str, state_after=state, severity=sev)
                new_history.append(h_item)
            self.history_alarms = new_history

        self.alarms_changed.emit()

    def acknowledge_selected(self, code):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for a in self.active_alarms:
            if a.code == code and a.state == MpAlarmXStateEnum.ACTIVE:
                a.state = MpAlarmXStateEnum.ACKNOWLEDGED
                a.ack_time = now_str
                # Record Acknowledgment event in History
                self.history_alarms.insert(0, HistoryLogItem(a.code, a.name, a._custom_message,
                                                             AlarmEvent.EVENT_ACK, now_str,
                                                             MpAlarmXStateEnum.ACTIVE, MpAlarmXStateEnum.ACKNOWLEDGED,
                                                             severity=a.severity))
        self.alarms_changed.emit()

    def acknowledge_all(self):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for a in self.active_alarms:
            if a.state == MpAlarmXStateEnum.ACTIVE:
                a.state = MpAlarmXStateEnum.ACKNOWLEDGED
                a.ack_time = now_str
                self.history_alarms.insert(0, HistoryLogItem(a.code, a.name, a._custom_message,
                                                             AlarmEvent.EVENT_ACK, now_str,
                                                             MpAlarmXStateEnum.ACTIVE, MpAlarmXStateEnum.ACKNOWLEDGED,
                                                             severity=a.severity))
        self.alarms_changed.emit()

    def reset_safety(self):
        """Reset active alarms upon operator command and log Reset events"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        for a in self.active_alarms:
            a.state = MpAlarmXStateEnum.INACTIVE
            a.reset_time = now_str
            self.history_alarms.insert(0, HistoryLogItem(a.code, a.name, a._custom_message,
                                                         AlarmEvent.EVENT_RESET, now_str,
                                                         MpAlarmXStateEnum.ACTIVE, MpAlarmXStateEnum.INACTIVE,
                                                         severity=a.severity))
        self.active_alarms.clear()
        self.alarms_changed.emit()

    def trigger_alarm(self, code, name=None, message=None):
        """Trigger a new alarm and log Activation event (记录激活时间)"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        item = AlarmItem(code, name=name, message=message, state=MpAlarmXStateEnum.ACTIVE, active_time=now_str)
        self.active_alarms.insert(0, item)
        self.history_alarms.insert(0, HistoryLogItem(code, name=name, message=message,
                                                     event_type=AlarmEvent.EVENT_ACTIVE, timestamp=now_str,
                                                     state_before=MpAlarmXStateEnum.INACTIVE, state_after=MpAlarmXStateEnum.ACTIVE,
                                                     severity=item.severity))
        self.alarms_changed.emit()
