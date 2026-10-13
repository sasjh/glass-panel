"""设计令牌：颜色 / 字体 / 间距 / 圆角 / 动效。

数值来源：apple-design 规范（WWDC 设计原则）
  - 字体：字号 + 字重 + 字距作为一组协同；行高与字号反向；最小可读字号 11px
  - 间距：4pt 网格
  - 圆角：统一阶梯，不留随手值
  - 材质：分层表达层级，浅色材质不叠浅色材质
"""
from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- 对比度工具

def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: str) -> float:
    """sRGB 相对亮度（WCAG 2.1）。"""
    h = rgb.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * _to_linear(r) + 0.7152 * _to_linear(g) + 0.0722 * _to_linear(b)


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    lo, hi = min(a, b), max(a, b)
    return (hi + 0.05) / (lo + 0.05)


def blend(fg: str, bg: str, alpha: float) -> str:
    """把 alpha 前景压在实色背景上，得到等效实色，用于对比度校验。"""
    f, b = fg.lstrip("#"), bg.lstrip("#")
    out = []
    for i in (0, 2, 4):
        fv, bv = int(f[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(fv * alpha + bv * (1 - alpha)))
    return "#%02X%02X%02X" % tuple(out)


# --------------------------------------------------------------------------- 间距 / 圆角

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6, SPACE_8 = 4, 8, 12, 16, 20, 24, 32

RADIUS_WINDOW = 22      # 整窗（也是亚克力裁剪半径）
RADIUS_TILE = 14        # 图片卡片
RADIUS_CONTROL = 10     # 输入框 / 分段控件
RADIUS_CIRCLE = 999     # 圆形功能键

TITLEBAR_HEIGHT = 44
RAIL_WIDTH = 96
RAIL_BUTTON = 52        # 圆形功能键直径（触达区域 >= 44）
RAIL_BUTTON_COMPACT = 44  # 窗口很矮时收成纯图标，直径仍 >= 44
RAIL_ICON = 22
MIN_WINDOW = (760, 480)
DEFAULT_WINDOW = (1040, 660)
RESIZE_MARGIN = 6       # 无边框窗口的手动缩放热区

THUMB_SIZES = (("小", 104), ("中", 148), ("大", 196))
GRID_GAP = SPACE_3


# --------------------------------------------------------------------------- 字体

@dataclass(frozen=True)
class TypeRole:
    size: int
    weight: int        # Qt 字重数值：400 Normal / 500 Medium / 600 DemiBold
    tracking: float    # 百分比字距，大字号收紧、小字号略放
    leading: float     # 行高倍数，与字号反向


TYPE = {
    "display": TypeRole(22, 600, -0.6, 1.20),
    "title":   TypeRole(15, 600, -0.3, 1.35),
    "section": TypeRole(13, 500, 0.0, 1.45),
    "body":    TypeRole(13, 400, 0.0, 1.50),
    "caption": TypeRole(11, 400, 1.0, 1.50),
    "micro":   TypeRole(11, 500, 1.5, 1.40),
}

FONT_STACK = ("Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei")


# --------------------------------------------------------------------------- 调色板

@dataclass(frozen=True)
class Theme:
    name: str
    is_dark: bool
    acrylic_abgr: int        # Windows 亚克力着色（ABGR，最高字节为不透明度）
    text: str
    text_secondary: str
    icon: str
    accent: str              # 仅作强调填充
    accent_hover: str
    accent_pressed: str
    on_accent: str           # 强调色上的文字/图标
    danger: str
    danger_hover: str
    surface: float           # 功能键 / 控件底色不透明度（叠在材质上）
    surface_hover: float
    surface_pressed: float
    rail_alpha: float        # 侧栏是「更重的材质」，用来分隔结构分区
    well_alpha: float        # 图片区的凹陷托盘，只做极轻的暗示
    recess_wash: str         # 结构分区 / 托盘的基色
    hairline: float
    highlight: float         # 顶边受光，让材质看起来有厚度
    wash: str = "#FFFFFF"    # 控件底色的基色
    wash_dark: str = "#0C0E12"


LIGHT = Theme(
    name="浅色",
    is_dark=False,
    acrylic_abgr=0xB8FFFFFF,
    text="#14161C",
    text_secondary="#39424F",
    icon="#2A3240",
    accent="#2E6CB0",
    accent_hover="#2A61A0",
    accent_pressed="#24568F",
    on_accent="#FFFFFF",
    danger="#B3403C",
    danger_hover="#9C3532",
    surface=0.55,
    surface_hover=0.80,
    surface_pressed=0.40,
    rail_alpha=0.09,
    well_alpha=0.05,
    recess_wash="#0C0E12",
    hairline=0.50,
    highlight=0.72,
    wash="#FFFFFF",
    wash_dark="#0C0E12",
)

DARK = Theme(
    name="深色",
    is_dark=True,
    acrylic_abgr=0xCC1B1917,
    text="#F2F4F8",
    text_secondary="#A8B0BC",
    icon="#DCE1E8",
    accent="#2F6FA8",
    accent_hover="#3579B4",
    accent_pressed="#2A6394",
    on_accent="#FFFFFF",
    danger="#D2625E",
    danger_hover="#DE7370",
    surface=0.26,
    surface_hover=0.40,
    surface_pressed=0.20,
    rail_alpha=0.10,
    well_alpha=0.05,
    recess_wash="#FFFFFF",
    hairline=0.26,
    highlight=0.22,
    wash="#FFFFFF",
    wash_dark="#000000",
)


# --------------------------------------------------------------------------- 动效

SPRING_RESPONSE = 0.32      # 默认临界阻尼弹簧：无过冲
SPRING_DAMPING = 1.0
SPRING_BOUNCE_RESPONSE = 0.34
SPRING_BOUNCE_DAMPING = 0.8  # 仅有动量输入时才允许轻微回弹

PRESS_SCALE = 0.94          # 按下即时反馈
HOVER_SCALE = 1.04
TILE_HOVER_SCALE = 1.03
DROP_SCALE = 1.012
FRAME_INTERVAL_MS = 16