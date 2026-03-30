# -*- coding: utf-8 -*-
"""
EVE-LMA 弹窗对话框模块
"""
from typing import Dict, Optional

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton

from constants import (
    ALERT_AUTO_CLOSE_BOSS, ALERT_AUTO_CLOSE_DREAD, ALERT_AUTO_CLOSE_SILENCE,
    ALERT_AUTO_CLOSE_CLOAK, ALERT_AUTO_CLOSE_PVP, DEFAULT_ALERT_AUTO_CLOSE
)
from styles import ALERT_STYLES


# 警报类型到自动关闭时间的映射
_AUTO_CLOSE_TIMES: Dict[str, int] = {
    'boss': ALERT_AUTO_CLOSE_BOSS,
    'dread': ALERT_AUTO_CLOSE_DREAD,
    'silence': ALERT_AUTO_CLOSE_SILENCE,
    'cloak': ALERT_AUTO_CLOSE_CLOAK,
    'pvp': ALERT_AUTO_CLOSE_PVP,
}


class AlertDialog(QDialog):
    """
    彩色警报弹窗对话框
    
    根据警报类型显示不同颜色的弹窗，支持自动关闭倒计时。
    """

    def __init__(self, alert_type: str, message: str, parent=None):
        """
        初始化警报弹窗
        
        Args:
            alert_type: 警报类型 ('boss', 'dread', 'cloak', 'silence', 'pvp')
            message: 显示的消息内容
            parent: 父控件
        """
        super().__init__(parent)
        
        style = ALERT_STYLES.get(alert_type, ALERT_STYLES['boss'])
        self.setWindowTitle(style['title'])
        self.setMinimumSize(420, 200)
        
        # 设置弹窗样式
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {style['bg']};
                border: 3px solid {style['fg']};
            }}
            QLabel {{
                color: {style['fg']};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {style['fg']};
                color: {style['bg']};
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 8px 30px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)

        layout = QVBoxLayout(self)
        
        # 标题标签
        title_lbl = QLabel(style['title'])
        title_lbl.setStyleSheet("font-size: 22px;")
        layout.addWidget(title_lbl)
        layout.addSpacing(10)

        # 消息标签
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)
        layout.addStretch()

        # 确认按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self._ok_btn = QPushButton("确认")
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._ok_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 自动关闭倒计时
        self._countdown = 0
        self._auto_timer: Optional[QTimer] = None
        
        if alert_type in _AUTO_CLOSE_TIMES:
            self._countdown = _AUTO_CLOSE_TIMES[alert_type]
            self._ok_btn.setText(f"确认 ({self._countdown})")
            
            self._auto_timer = QTimer(self)
            self._auto_timer.setInterval(1000)
            self._auto_timer.timeout.connect(self._tick)
            self._auto_timer.start()

    def _tick(self) -> None:
        """每秒倒计时"""
        self._countdown -= 1
        
        if self._countdown <= 0:
            if self._auto_timer:
                self._auto_timer.stop()
            self.accept()
        else:
            self._ok_btn.setText(f"确认 ({self._countdown})")

    def closeEvent(self, event) -> None:
        """关闭事件处理，确保停止定时器"""
        if self._auto_timer:
            self._auto_timer.stop()
        super().closeEvent(event)

    def reject(self) -> None:
        """拒绝（ESC键关闭）时停止定时器"""
        if self._auto_timer:
            self._auto_timer.stop()
        super().reject()