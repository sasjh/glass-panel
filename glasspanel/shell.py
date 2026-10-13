"""无边框毛玻璃窗口：真实桌面模糊 + 圆角裁剪 + 八向缩放。"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QRect, QRectF, QSettings, QSize,
                            Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFontMetrics, QGuiApplication, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme
from .effect import MODE_SOLID, GlassMaterial
from .icons import paint_icon
from .motion import animations_enabled
from .qtutil import font_for, rgba

WIN_MARGIN = 8          # 窗口按钮与右边缘的距离
TITLE_PADDING = 18


class CircleButton(QWidget):
    """标题栏上的小圆钮：按下即反馈，悬停有材质变化。"""

    clicked = Signal()

    def __init__(self, icon: str, tooltip: str, theme_ref: theme.Theme, danger: bool = False, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._theme = theme_ref
        self._danger = danger
        self._hover = False
        self._pressed = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True          # 反馈发生在按下瞬间，而不是抬起
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        if self._pressed:
            fill = rgba("#FFFFFF", self._theme.surface_pressed)
        elif self._hover and self._danger:
            fill = QColor(self._theme.danger)
        elif self._hover:
            fill = rgba("#FFFFFF", self._theme.surface_hover)
        else:
            fill = QColor(0, 0, 0, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawEllipse(rect)
        if self._danger and self._hover:
            icon_color = QColor("#FFFFFF")
        else:
            icon_color = QColor(self._theme.icon)
        paint_icon(p, self._icon, rect.adjusted(6, 6, -6, -6), icon_color, stroke_ratio=0.082)
        p.end()


class TitleBar(QWidget):
    """标题栏：整块都可拖动，右侧是窗口控制。"""

    def __init__(self, window: "GlassWindow", title: str):
        super().__init__(window)
        self._window = window
        self.setFixedHeight(theme.TITLEBAR_HEIGHT)
        self.setAttribute(Qt.WA_Hover, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TITLE_PADDING, 0, WIN_MARGIN, 0)
        layout.setSpacing(theme.SPACE_2)

        self._title = QLabel(title)
        self._title.setFont(font_for("title"))
        layout.addWidget(self._title)
        layout.addStretch(1)

        self._min_btn = CircleButton("minimize", "最小化", window.theme_ref)
        self._max_btn = CircleButton("maximize", "最大化", window.theme_ref)
        self._close_btn = CircleButton("close", "关闭", window.theme_ref, danger=True)
        self._min_btn.clicked.connect(window.showMinimized)
        self._max_btn.clicked.connect(window.toggle_maximized)
        self._close_btn.clicked.connect(window.close)
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            layout.addWidget(btn)

        self._subtitle = QLabel("")
        self._subtitle.setFont(font_for("caption"))
        layout.insertWidget(1, self._subtitle)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def set_button_icon(self, which: str, icon: str) -> None:
        button = {"max": self._max_btn}.get(which)
        if button:
            button._icon = icon
            button.update()

    def apply_theme(self, theme_ref: theme.Theme) -> None:
        self._title.setStyleSheet("color: %s;" % theme_ref.text)
        self._subtitle.setStyleSheet("color: %s;" % theme_ref.text_secondary)
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            btn.set_theme(theme_ref)

    # ------------------------------------------------------------------ 拖动

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._window.begin_system_move(event)
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._window.toggle_maximized()


class GlassWindow(QWidget):
    """毛玻璃外壳。"""

    resized = Signal()

    def __init__(self, title: str = "图片面板", theme_ref: theme.Theme | None = None):
        super().__init__(None)
        self.theme_ref = theme_ref or theme.LIGHT
        self.material = GlassMaterial()
        self._radius = theme.RADIUS_WINDOW
        self._drag_origin: QPoint | None = None
        self._resize_session: dict | None = None
        self._settings = QSettings("GlassPanel", "ImagePad")

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumSize(QSize(*theme.MIN_WINDOW))
        self.setMouseTracking(True)

        self._titlebar = TitleBar(self, title)
        self._body = QWidget(self)
        self._body.setMouseTracking(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._titlebar)
        root.addWidget(self._body, 1)

        self._titlebar.apply_theme(self.theme_ref)
        self._toast = Toast(self)

    # ------------------------------------------------------------------ 内容

    def set_body_layout(self, layout) -> None:
        self._body.setLayout(layout)

    @property
    def body(self) -> QWidget:
        return self._body

    @property
    def titlebar(self) -> TitleBar:
        return self._titlebar

    def show_toast(self, text: str) -> None:
        self._toast.show_text(text)

    # ------------------------------------------------------------------ 材质

    def showEvent(self, event):
        super().showEvent(event)
        self.material.attach(int(self.winId()), self.theme_ref.acrylic_abgr)
        self._update_region()
        self._restore_geometry()

    def _restore_geometry(self) -> None:
        stored = self._settings.value("geometry")
        if stored is not None:
            self.restoreGeometry(stored)
        else:
            self.resize(QSize(*theme.DEFAULT_WINDOW))
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.move(area.center() - QPoint(self.width() // 2, self.height() // 2))
        self._update_region()

    def save_geometry(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())

    def apply_theme(self, theme_ref: theme.Theme) -> None:
        self.theme_ref = theme_ref
        self.material.set_tint(theme_ref.acrylic_abgr)
        self._titlebar.apply_theme(theme_ref)
        self.update()

    def _update_region(self) -> None:
        maximized = self.isMaximized()
        self.material.set_rounded(self.width(), self.height(), self._radius,
                                  self.devicePixelRatioF(), enabled=not maximized)

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._titlebar.set_button_icon("max", "restore" if self.isMaximized() else "maximize")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._titlebar.set_button_icon("max", "restore" if self.isMaximized() else "maximize")
            QTimer.singleShot(0, self._update_region)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_region()
        self._toast.reposition()
        self.resized.emit()

    def closeEvent(self, event):
        self.save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------ 拖动 / 缩放

    def begin_system_move(self, event) -> None:
        handle = self.windowHandle()
        if handle is not None and handle.startSystemMove():
            return
        self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _edges_at(self, pos: QPoint):
        m = theme.RESIZE_MARGIN
        edges = None
        if pos.x() <= m:
            edges = Qt.LeftEdge
        elif pos.x() >= self.width() - m:
            edges = Qt.RightEdge
        if pos.y() <= m:
            edges = Qt.TopEdge if edges is None else edges | Qt.TopEdge
        elif pos.y() >= self.height() - m:
            edges = Qt.BottomEdge if edges is None else edges | Qt.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges):
        left = bool(edges & Qt.LeftEdge)
        right = bool(edges & Qt.RightEdge)
        top = bool(edges & Qt.TopEdge)
        bottom = bool(edges & Qt.BottomEdge)
        if (left and top) or (right and bottom):
            return Qt.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.SizeBDiagCursor
        if left or right:
            return Qt.SizeHorCursor
        return Qt.SizeVerCursor

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edges = self._edges_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    return
                self._begin_manual_resize(edges, event.globalPosition().toPoint())
                return
        super().mousePressEvent(event)

    def _begin_manual_resize(self, edges, global_pos: QPoint) -> None:
        self._resize_session = {
            "edges": edges,
            "origin": global_pos,
            "geometry": QRect(self.geometry()),
        }
        self.material.suspend()
        self.setCursor(self._cursor_for(edges))

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            return
        if self._resize_session is not None:
            self._apply_manual_resize(event.globalPosition().toPoint())
            return
        edges = self._edges_at(event.position().toPoint())
        if edges:
            self.setCursor(self._cursor_for(edges))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def _apply_manual_resize(self, global_pos: QPoint) -> None:
        session = self._resize_session
        edges = session["edges"]
        delta = global_pos - session["origin"]
        rect = QRect(session["geometry"])
        min_w, min_h = theme.MIN_WINDOW
        if edges & Qt.LeftEdge:
            rect.setLeft(min(rect.left() + delta.x(), rect.right() - min_w))
        elif edges & Qt.RightEdge:
            rect.setRight(max(rect.right() + delta.x(), rect.left() + min_w))
        if edges & Qt.TopEdge:
            rect.setTop(min(rect.top() + delta.y(), rect.bottom() - min_h))
        elif edges & Qt.BottomEdge:
            rect.setBottom(max(rect.bottom() + delta.y(), rect.top() + min_h))
        self.setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if self._drag_origin is not None:
            self._drag_origin = None
            return
        if self._resize_session is not None:
            self._resize_session = None
            self.unsetCursor()
            QTimer.singleShot(120, self.material.resume)   # 拖动结束再恢复亚克力
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ 绘制

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        t = self.theme_ref
        radius = 0 if self.isMaximized() else self._radius
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        # 降级路径：拿不到真实模糊时，画一层半透明浅玻璃
        if self.material.mode == MODE_SOLID:
            base = QLinearGradient(0, 0, 0, self.height())
            if t.is_dark:
                base.setColorAt(0.0, rgba(t.wash, 0.10))
                base.setColorAt(1.0, rgba(t.wash_dark, 0.16))
            else:
                base.setColorAt(0.0, rgba("#FFFFFF", 0.90))
                base.setColorAt(1.0, rgba("#EDF1F6", 0.88))
            painter.setPen(Qt.NoPen)
            painter.setBrush(base)
            painter.drawPath(path)

        # 顶部受光：让材质看起来有厚度
        rim = QLinearGradient(0, 0, 0, self.height())
        top_alpha = t.highlight
        rim.setColorAt(0.0, rgba("#FFFFFF", top_alpha))
        rim.setColorAt(0.35, rgba("#FFFFFF", top_alpha * 0.35))
        rim.setColorAt(1.0, rgba("#FFFFFF", top_alpha * 0.16 if not t.is_dark else top_alpha * 0.35))
        pen = QPen()
        pen.setBrush(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # 底部内阴影：交代厚度，别用硬分割线
        shade = QLinearGradient(0, self.height() * 0.72, 0, self.height())
        shade.setColorAt(0.0, rgba("#000000", 0.0))
        shade.setColorAt(1.0, rgba("#000000", 0.16 if t.is_dark else 0.07))
        painter.setPen(Qt.NoPen)
        painter.setBrush(shade)
        painter.save()
        painter.setClipPath(path)
        painter.drawRect(QRectF(0, self.height() * 0.72, self.width(), self.height() * 0.28))
        painter.restore()
        painter.end()


class Toast(QWidget):
    """轻量反馈：淡入 + 上浮，尊重系统「减少动态效果」。"""

    def __init__(self, parent: GlassWindow):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._text = ""
        self._progress = 0.0
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_value)
        self.hide()

    def _on_value(self, value):
        self._progress = float(value)
        self.reposition()
        self.update()

    def show_text(self, text: str, duration_ms: int = 2000) -> None:
        self._text = text
        self._hide_timer.stop()
        if not animations_enabled():
            self._progress = 1.0
            self.show()
            self.raise_()
            self.reposition()
            self.update()
            self._hide_timer.start(duration_ms)
            return
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hide_timer.start(duration_ms)

    def _fade_out(self) -> None:
        if not animations_enabled():
            self.hide()
            return
        self._anim.stop()
        self._anim.setDuration(200)
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_fade_done)
        self._anim.start()

    def _on_fade_done(self):
        try:
            self._anim.finished.disconnect(self._on_fade_done)
        except (RuntimeError, TypeError):
            pass
        if self._progress <= 0.01:
            self.hide()

    def reposition(self) -> None:
        if not self._text:
            return
        fm = QFontMetrics(font_for("section"))
        width = fm.horizontalAdvance(self._text) + 2 * theme.SPACE_4
        height = theme.SPACE_6 + theme.SPACE_2
        x = (self.parent().width() - width) // 2
        y = self.parent().height() - height - theme.SPACE_5 - int(10 * (1.0 - self._progress))
        self.setGeometry(x, y, width, height)

    def paintEvent(self, event):
        if not self._text or self._progress <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self._progress)
        t = self.parent().theme_ref
        bg = QColor("#14161C") if not t.is_dark else QColor("#F2F4F8")
        bg.setAlphaF(0.92)
        fg = QColor("#FFFFFF") if not t.is_dark else QColor("#14161C")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)
        painter.setPen(fg)
        painter.setFont(font_for("section"))
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()