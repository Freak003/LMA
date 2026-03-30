# -*- coding: utf-8 -*-
"""
EVE-LMA FlowLayout 流式布局
自动换行的流式布局，用于角色复选框区域
"""
from typing import List, Optional

from PyQt5.QtCore import Qt, QRect, QSize, QPoint
from PyQt5.QtWidgets import QLayout, QLayoutItem, QSizePolicy


class FlowLayout(QLayout):
    """
    自动换行的流式布局
    
    当子控件超出当前行宽度时自动换行到下一行显示。
    适用于标签、复选框等需要动态排列的场景。
    """

    def __init__(self, parent=None, spacing: int = 10):
        """
        初始化流式布局
        
        Args:
            parent: 父控件
            spacing: 控件间距
        """
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self._spacing = spacing

    def addItem(self, item: QLayoutItem) -> None:
        """添加布局项"""
        self._items.append(item)

    def count(self) -> int:
        """返回项目数量"""
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        """获取指定索引的项目"""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        """移除并返回指定索引的项目"""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self) -> bool:
        """支持根据宽度计算高度"""
        return True

    def heightForWidth(self, width: int) -> int:
        """根据宽度计算所需高度"""
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        """设置布局区域"""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        """返回建议尺寸"""
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """返回最小尺寸"""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """
        执行布局计算
        
        Args:
            rect: 布局区域
            test_only: 是否仅测试（不实际设置位置）
        
        Returns:
            布局后的总高度
        """
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        row_height = 0

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            
            # 检查是否需要换行
            if x + w > effective.right() + 1 and row_height > 0:
                x = effective.x()
                y += row_height + self._spacing
                row_height = 0
            
            # 设置控件位置（非测试模式）
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            
            x += w + self._spacing
            row_height = max(row_height, h)

        return y + row_height - rect.y() + m.bottom()

    def clear(self) -> None:
        """清空所有项目"""
        while self._items:
            item = self._items.pop()
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                item.layout().setParent(None)