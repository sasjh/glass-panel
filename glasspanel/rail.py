"""左侧功能键：圆形毛玻璃按键，按下即反馈，可打断的弹簧缩放。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme
from .icons import paint_icon
from .motion import SPRING_DAMPING, SPRING_RESPONSE, Spring
from .qtutil import font_for, rgba

CAPTION_BLOCK = theme.SPACE_3 + 6   # 圆形下方的说明文字所占高度


class GlassButton(QWidget):
    """一个功能键 = 圆形图标 + 一行说明文字。"""

    activated = Signal()

    def __init__(self, icon: str, label: str, theme_ref: theme.Theme,
                 danger: bool = False, show_caption: bool = True, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._theme = theme_ref
        self._danger = danger
        self._show_caption = show_caption
        self._hover = False
        self._pressed = False
        self._active = False
        self._scale = 1.0
        self._compact = False
        self._diameter = theme.RAIL_BUTTON
        self._spring = Spring(1.0, SPRING_RESPONSE, SPRING_DAMPING, self)
        self._spring.value_changed.connect(self._on_scale)

        self._resize_to_state()
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    # ------------------------------------------------------------------ 状态

    def _on_scale(self, value: float) -> None:
        self._scale = value
        self.update()

    def _resize_to_state(self) -> None:
        caption = CAPTION_BLOCK if self._show_caption else 0
        self.setFixedSize(theme.RAIL_WIDTH - 2 * theme.SPACE_3, self._diameter + caption)

    def set_compact(self, compact: bool) -> None:
        """窗口太矮时收成纯图标：说明文字交给 tooltip，按钮仍然可点。"""
        if compact == self._compact:
            return
        self._compact = compact
        self._show_caption = not compact
        self._diameter = theme.RAIL_BUTTON_COMPACT if compact else theme.RAIL_BUTTON
        self._resize_to_state()
        self.update()

    def set_icon(self, icon: str) -> None:
        self._icon = icon
        self.update()

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self.update()

    # ------------------------------------------------------------------ 交互

    def enterEvent(self, event):
        self._hover = True
        self._spring.set_target(theme.HOVER_SCALE)
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self._spring.set_target(1.0)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self._spring.set_target(theme.PRESS_SCALE)   # 按下瞬间就反馈
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._pressed:
            return super().mouseReleaseEvent(event)
        self._pressed = False
        inside = self.rect().contains(event.position().toPoint())
        self._spring.set_target(theme.HOVER_SCALE if inside else 1.0)
        if inside:
            self.activated.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._pressed = True
            self._spring.set_target(theme.PRESS_SCALE)
            self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self._pressed:
            self._pressed = False
            self._spring.set_target(1.0)
            self.activated.emit()
        else:
            super().keyReleaseEvent(event)

    def focusInEvent(self, event):
        self.update()

    def focusOutEvent(self, event):
        self.update()

    # ------------------------------------------------------------------ 绘制

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        t = self._theme
        diameter = self._diameter
        cx = self.width() / 2.0
        cy = diameter / 2.0
        rect = QRectF(cx - diameter / 2.0, cy - diameter / 2.0, diameter, diameter)

        painter.save()
        painter.translate(QPointF(cx, cy))
        painter.scale(self._scale, self._scale)
        painter.translate(QPointF(-cx, -cy))

        if self._active:
            fill = QColor(t.accent_pressed if self._pressed else t.accent)
        elif self._pressed:
            fill = rgba("#FFFFFF", t.surface_pressed)
        elif self._hover:
            fill = rgba("#FFFFFF", t.surface_hover)
        else:
            fill = rgba("#FFFFFF", t.surface)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(rect)

        # 顶边受光：小控件也要有材质感
        rim = QColor(255, 255, 255)
        rim.setAlphaF(0.55 if not t.is_dark else 0.22)
        pen = painter.pen()
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        if self._active:
            icon_color = QColor(t.on_accent)
        elif self._danger and self._hover:
            icon_color = QColor(t.danger)
        else:
            icon_color = QColor(t.icon)
        inset = diameter * 0.288
        paint_icon(painter, self._icon, rect.adjusted(inset, inset, -inset, -inset), icon_color)
        painter.restore()

        if self.hasFocus():
            ring = QColor(t.accent)
            ring.setAlphaF(0.9)
            pen = painter.pen()
            pen.setColor(ring)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect.adjusted(-3, -3, 3, 3))

        if self._show_caption:
            painter.setFont(font_for("caption"))
            if self._active:
                caption = t.text
            elif self._danger and self._hover:
                caption = t.danger
            else:
                caption = t.text_secondary
            painter.setPen(QColor(caption))
            caption_rect = QRectF(0, diameter + theme.SPACE_1, self.width(), self.height() - diameter)
            painter.drawText(caption_rect, Qt.AlignHCenter | Qt.AlignTop, self._label)
        painter.end()


class RailSeparator(QWidget):
    def __init__(self, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self._theme = theme_ref
        self._compact = False
        self.setFixedHeight(theme.SPACE_4)

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self.setFixedHeight(theme.SPACE_2 if compact else theme.SPACE_3)
        self.update()

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor("#14161C") if not self._theme.is_dark else QColor("#FFFFFF")
        color.setAlphaF(0.10)
        painter.setPen(color)
        y = self.height() / 2.0
        painter.drawLine(theme.SPACE_3 + 2, int(y), self.width() - theme.SPACE_3 - 2, int(y))
        painter.end()


class FunctionRail(QWidget):
    """左侧功能键栏。"""

    add_images = Signal()
    add_folder = Signal()
    cycle_sort = Signal()
    cycle_size = Signal()
    export_images = Signal()
    clear_images = Signal()
    toggle_theme = Signal()

    def __init__(self, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self._theme = theme_ref
        self._compact = False
        self.setFixedWidth(theme.RAIL_WIDTH)
        self.setAttribute(Qt.WA_StyledBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_3, theme.SPACE_3, theme.SPACE_3, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_2)

        self.add_button = GlassButton("add_photo", "添加图片", theme_ref)
        self.folder_button = GlassButton("add_folder", "添加文件夹", theme_ref)
        self.sort_button = GlassButton("sort_name", "排序·名称", theme_ref)
        self.size_button = GlassButton("size", "尺寸·中", theme_ref)
        self.export_button = GlassButton("export", "导出", theme_ref)
        self.theme_button = GlassButton("theme", theme_ref.name, theme_ref)
        self.clear_button = GlassButton("trash", "清空", theme_ref, danger=True)

        layout.addWidget(self.add_button)
        layout.addWidget(self.folder_button)
        layout.addWidget(RailSeparator(theme_ref))
        layout.addWidget(self.sort_button)
        layout.addWidget(self.size_button)
        layout.addWidget(RailSeparator(theme_ref))
        layout.addWidget(self.export_button)
        layout.addWidget(self.theme_button)
        layout.addStretch(1)
        layout.addWidget(self.clear_button)

        self.add_button.activated.connect(self.add_images)
        self.folder_button.activated.connect(self.add_folder)
        self.sort_button.activated.connect(self.cycle_sort)
        self.size_button.activated.connect(self.cycle_size)
        self.export_button.activated.connect(self.export_images)
        self.theme_button.activated.connect(self.toggle_theme)
        self.clear_button.activated.connect(self.clear_images)

    @property
    def buttons(self):
        return (self.add_button, self.folder_button, self.sort_button, self.size_button,
                self.export_button, self.theme_button, self.clear_button)

    def set_sort_mode(self, mode: str) -> None:
        self.sort_button.set_icon("sort_name" if mode == "name" else "sort_time")
        self.sort_button.set_label("排序·名称" if mode == "name" else "排序·时间")

    def set_size_label(self, label: str) -> None:
        self.size_button.set_label("尺寸·%s" % label)

    def _needed_height(self, compact: bool) -> int:
        caption = 0 if compact else CAPTION_BLOCK
        diameter = theme.RAIL_BUTTON_COMPACT if compact else theme.RAIL_BUTTON
        spacing = theme.SPACE_1 if compact else theme.SPACE_2
        separator = theme.SPACE_2 if compact else theme.SPACE_3
        count = len(self.buttons)
        return (2 * theme.SPACE_3 + count * (diameter + caption)
                + 2 * separator + spacing * (count + 2))

    def _apply_density(self) -> None:
        compact = self.height() < self._needed_height(False)
        if compact == self._compact:
            return
        self._compact = compact
        self.layout().setSpacing(theme.SPACE_1 if compact else theme.SPACE_2)
        for button in self.buttons:
            button.set_compact(compact)
        for separator in self.findChildren(RailSeparator):
            separator.set_compact(compact)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_density()

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        for button in self.buttons:
            button.set_theme(theme_ref)
        self.theme_button.set_label(theme_ref.name)
        for sep in self.findChildren(RailSeparator):
            sep.set_theme(theme_ref)
        self.update()

    def paintEvent(self, event):
        """侧栏是一块更重的材质：靠底色 + 边界和内容区分开，不用硬分割线。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        t = self._theme
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        radius = theme.RADIUS_TILE
        painter.setPen(Qt.NoPen)
        painter.setBrush(rgba(t.recess_wash, t.rail_alpha))
        painter.drawRoundedRect(rect, radius, radius)
        rim = QColor(255, 255, 255)
        rim.setAlphaF(0.40 if not t.is_dark else 0.20)
        pen = painter.pen()
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()