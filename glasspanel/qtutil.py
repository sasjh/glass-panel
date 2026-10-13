"""Qt 侧的小工具：颜色 / 字体角色解析。"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont

from . import theme


def rgba(color: str, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def mix(base: str, alpha: float) -> QColor:
    return rgba(base, alpha)


def font_for(role: str) -> QFont:
    """按角色取字体：字号 + 字重 + 字距是一组，不单独调。"""
    spec = theme.TYPE[role]
    f = QFont()
    f.setFamilies(list(theme.FONT_STACK))
    f.setPixelSize(spec.size)
    f.setWeight(QFont.Weight(spec.weight))
    # Qt 的 PercentageSpacing 以 100 为「正常」，所以这里要加上 100
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0 + spec.tracking)
    return f


def line_height(role: str) -> float:
    spec = theme.TYPE[role]
    return spec.size * spec.leading