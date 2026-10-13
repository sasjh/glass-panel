"""右侧图片区：拖入 / 选择图片，每张照片都带删除键。"""
from __future__ import annotations

import os
import shutil

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QImageReader, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFileDialog, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme
from .icons import icon_pixmap, paint_icon
from .motion import (SPRING_BOUNCE_DAMPING, SPRING_BOUNCE_RESPONSE, SPRING_DAMPING,
                     SPRING_RESPONSE, Spring)
from .qtutil import font_for, rgba

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".gif", ".webp",
                  ".tif", ".tiff", ".ico", ".heic", ".avif")
PAD_PADDING = theme.SPACE_3
DELETE_SIZE = 26


def supported_suffixes() -> set[str]:
    """只接受当前 Qt 真能解码的格式，避免加进来变成空白卡片。"""
    formats = {bytes(f).decode("ascii", "ignore").lower() for f in QImageReader.supportedImageFormats()}
    return {s for s in IMAGE_SUFFIXES if s.lstrip(".") in formats}


SUPPORTED = supported_suffixes()


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED


def load_cover_pixmap(path: str, size: int, dpr: float) -> QPixmap | None:
    """按「填充裁切」读图：先让解码器缩到目标尺寸，避免整张大图进内存。"""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    target = max(1, int(round(size * dpr)))
    source = reader.size()
    if source.isValid():
        scaled = QSize(source)
        scaled.scale(QSize(target, target), Qt.KeepAspectRatioByExpanding)
        reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        return None
    pixmap = QPixmap.fromImage(image)
    if pixmap.width() < target or pixmap.height() < target:
        pixmap = pixmap.scaled(QSize(target, target), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    crop = QRect((pixmap.width() - target) // 2, (pixmap.height() - target) // 2, target, target)
    pixmap = pixmap.copy(crop)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class PrimaryButton(QWidget):
    """主操作按钮：强调色填充 + 白字。"""

    clicked = Signal()

    def __init__(self, text: str, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self._text = text
        self._theme = theme_ref
        self._hover = False
        self._pressed = False
        self._scale = 1.0
        self._spring = Spring(1.0, SPRING_RESPONSE, SPRING_DAMPING, self)
        self._spring.value_changed.connect(self._on_scale)
        self.setFont(font_for("section"))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(38)
        self.setMinimumWidth(self.sizeHint().width())
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _on_scale(self, value: float) -> None:
        self._scale = value
        self.update()

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(font_for("section"))
        return QSize(metrics.horizontalAdvance(self._text) + 2 * theme.SPACE_5 + 4, 38)

    def set_text(self, text: str) -> None:
        self._text = text
        self.setMinimumWidth(self.sizeHint().width())
        self.update()

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self.update()

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
            self._spring.set_target(theme.PRESS_SCALE)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self._spring.set_target(theme.HOVER_SCALE if self._hover else 1.0)
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._spring.set_target(PRESS_SCALE)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._spring.set_target(1.0)
            self.clicked.emit()
        super().keyReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        t = self._theme
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.width() / 2.0, -self.height() / 2.0)
        if self._pressed:
            fill = QColor(t.accent_pressed)
        elif self._hover:
            fill = QColor(t.accent_hover)
        else:
            fill = QColor(t.accent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        rim = QColor(255, 255, 255)
        rim.setAlphaF(0.28)
        pen = painter.pen()
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        painter.setPen(QColor(t.on_accent))
        painter.setFont(font_for("section"))
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        if self.hasFocus():
            painter.setPen(QColor(t.accent))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), theme.RADIUS_CONTROL + 3, theme.RADIUS_CONTROL + 3)
        painter.end()


class PhotoTile(QWidget):
    """一张照片：悬停浮起，右上角是删除键。"""

    delete_requested = Signal(str)
    open_requested = Signal(str)
    selection_toggled = Signal(str, bool)

    def __init__(self, path: str, size: int, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self.path = path
        self._size = size
        self._theme = theme_ref
        self._hover = False
        self._pressed = False
        self._delete_pressed = False
        self._selected = False
        self._scale = 1.0
        self._pixmap = load_cover_pixmap(path, size, self.devicePixelRatioF())
        self._spring = Spring(1.0, SPRING_RESPONSE, SPRING_DAMPING, self)
        self._spring.value_changed.connect(self._on_scale)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setToolTip("%s\n单击选中 · 双击打开 · Delete 删除" % os.path.basename(path))

    # ------------------------------------------------------------------ 状态

    def _on_scale(self, value: float) -> None:
        self._scale = value
        self.update()

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self.update()

    def _delete_rect(self) -> QRectF:
        return QRectF(self.width() - DELETE_SIZE - 8, 8, DELETE_SIZE, DELETE_SIZE)

    # ------------------------------------------------------------------ 交互

    def enterEvent(self, event):
        self._hover = True
        self._spring.set_target(theme.TILE_HOVER_SCALE)
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self._delete_pressed = False
        self._spring.set_target(1.0)
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        if self._delete_rect().contains(event.position()):
            self._delete_pressed = True
        else:
            self._pressed = True
            self._spring.set_target(PRESS_SCALE)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(event)
        pos = event.position()
        if self._delete_pressed:
            self._delete_pressed = False
            self.update()
            if self._delete_rect().contains(pos):
                self.delete_requested.emit(self.path)
            return
        if self._pressed:
            self._pressed = False
            self._spring.set_target(theme.TILE_HOVER_SCALE if self._hover else 1.0)
            self.update()
            if self.rect().contains(pos.toPoint()):
                self.setFocus(Qt.MouseFocusReason)
                self.selection_toggled.emit(self.path, not self._selected)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self._delete_rect().contains(event.position()):
            self.open_requested.emit(self.path)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_requested.emit(self.path)
        elif event.key() == Qt.Key_Space:
            self._spring.set_target(PRESS_SCALE)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.open_requested.emit(self.path)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._spring.set_target(1.0)
            self.selection_toggled.emit(self.path, not self._selected)
        else:
            super().keyReleaseEvent(event)

    def focusInEvent(self, event):
        self._spring.set_target(theme.TILE_HOVER_SCALE)
        self.update()

    def focusOutEvent(self, event):
        self._spring.set_target(1.0)
        self.update()

    # ------------------------------------------------------------------ 绘制

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        t = self._theme
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.width() / 2.0, -self.height() / 2.0)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        radius = theme.RADIUS_TILE
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.setClipPath(path)
        if self._pixmap is not None:
            target = QRectF((self.width() - self._pixmap.width() / self._pixmap.devicePixelRatio()) / 2.0,
                            (self.height() - self._pixmap.height() / self._pixmap.devicePixelRatio()) / 2.0,
                            self._pixmap.width() / self._pixmap.devicePixelRatio(),
                            self._pixmap.height() / self._pixmap.devicePixelRatio())
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(rgba(t.wash, 0.5))
            painter.drawRect(rect)
            paint_icon(painter, "placeholder", rect.adjusted(28, 28, -28, -28), QColor(t.text_secondary))
        painter.restore()

        if self._hover or self._pressed:
            veil = QColor(0, 0, 0, 40 if self._pressed else 22)
            painter.setPen(Qt.NoPen)
            painter.setBrush(veil)
            painter.drawPath(path)

        rim = QColor(255, 255, 255)
        rim.setAlphaF(0.55 if not t.is_dark else 0.30)
        pen = painter.pen()
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        if self._selected:
            pen.setColor(QColor(t.accent))
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawPath(path)
            badge = QRectF(8, 8, 22, 22)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(t.accent))
            painter.drawEllipse(badge)
            paint_icon(painter, "check", badge.adjusted(5, 5, -5, -5), QColor(t.on_accent), stroke_ratio=0.12)
        elif self.hasFocus():
            pen.setColor(QColor(t.accent))
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        # 删除键：常态就在，悬停加强
        delete_rect = self._delete_rect()
        if self._delete_pressed:
            bg = QColor(t.danger)
            bg.setAlphaF(1.0)
        elif self._hover:
            bg = QColor(t.danger)
            bg.setAlphaF(0.95)
        else:
            bg = QColor(16, 18, 24)
            bg.setAlphaF(0.62)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(delete_rect)
        rim.setAlphaF(0.35)
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(delete_rect.adjusted(0.5, 0.5, -0.5, -0.5))
        paint_icon(painter, "close", delete_rect.adjusted(7, 7, -7, -7), QColor("#FFFFFF"), stroke_ratio=0.10)
        painter.end()


class EmptyState(QWidget):
    """空状态：说清能做什么，并且只放一个主操作。"""

    pick_requested = Signal()

    def __init__(self, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self._theme = theme_ref
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_6, theme.SPACE_6, theme.SPACE_6, theme.SPACE_6)
        layout.setSpacing(theme.SPACE_2)
        layout.addStretch(1)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setPixmap(icon_pixmap("placeholder", 56, QColor(theme_ref.text_secondary), 2.0))
        layout.addWidget(self._icon)

        self._headline = QLabel("把图片拖到这里")
        self._headline.setFont(font_for("display"))
        self._headline.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._headline)

        self._hint = QLabel("支持 JPG / PNG / WEBP / GIF 等；也可以点下面的按钮选择")
        self._hint.setFont(font_for("body"))
        self._hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint)

        layout.addSpacing(theme.SPACE_3)
        self._button = PrimaryButton("选择图片…", theme_ref, self)
        self._button.clicked.connect(self.pick_requested)
        layout.addWidget(self._button, 0, Qt.AlignHCenter)
        layout.addStretch(1)
        self.set_theme(theme_ref)

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self._headline.setStyleSheet("color: %s;" % theme_ref.text)
        self._hint.setStyleSheet("color: %s;" % theme_ref.text_secondary)
        self._icon.setPixmap(icon_pixmap("placeholder", 56, QColor(theme_ref.text_secondary), 2.0))
        self._button.set_theme(theme_ref)


class ImagePad(QWidget):
    """图片区：托盘 + 卡片网格 + 空状态 + 拖放。"""

    changed = Signal()
    message = Signal(str)
    selection_changed = Signal(int)

    def __init__(self, theme_ref: theme.Theme, parent=None):
        super().__init__(parent)
        self._theme = theme_ref
        self._paths: list[str] = []
        self._tiles: list[PhotoTile] = []
        self._thumb = theme.THUMB_SIZES[1][1]
        self._sort_mode = "name"
        self._scroll = 0
        self._max_scroll = 0
        self._dropping = False
        self._drop_scale = 1.0
        self._drop_spring = Spring(1.0, SPRING_BOUNCE_RESPONSE, SPRING_BOUNCE_DAMPING, self)
        self._drop_spring.value_changed.connect(self._on_drop_scale)

        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._empty = EmptyState(theme_ref, self)
        self._empty.pick_requested.connect(self.choose_files)

        self._scroll_hint = QTimer(self)
        self._scroll_hint.setSingleShot(True)
        self._scroll_hint.timeout.connect(self.update)
        self._install_drop_filter(self)

    # ------------------------------------------------------------------ 数据

    @property
    def paths(self) -> list[str]:
        return list(self._paths)

    @property
    def count(self) -> int:
        return len(self._paths)

    def total_bytes(self) -> int:
        total = 0
        for path in self._paths:
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
        return total

    def selected_paths(self) -> list[str]:
        return [tile.path for tile in self._tiles if tile.selected]

    def add_paths(self, paths) -> int:
        """加入图片；目录展开一层。返回新增数量。"""
        incoming: list[str] = []
        for raw in paths:
            if not raw:
                continue
            if os.path.isdir(raw):
                try:
                    for name in sorted(os.listdir(raw)):
                        candidate = os.path.join(raw, name)
                        if os.path.isfile(candidate) and is_image(candidate):
                            incoming.append(candidate)
                except OSError:
                    continue
            elif os.path.isfile(raw) and is_image(raw):
                incoming.append(raw)

        existing = {os.path.normcase(os.path.abspath(p)) for p in self._paths}
        added = []
        for path in incoming:
            key = os.path.normcase(os.path.abspath(path))
            if key in existing:
                continue
            existing.add(key)
            added.append(path)
        if not added:
            skipped = len(incoming)
            self.message.emit("没有新增图片" if skipped == 0 else "这些图片已经在列表里了")
            return 0
        self._paths.extend(added)
        self._rebuild()
        self.message.emit("已添加 %d 张图片" % len(added))
        return len(added)

    def remove_path(self, path: str) -> None:
        if path not in self._paths:
            return
        index = next((i for i, tile in enumerate(self._tiles) if tile.path == path), None)
        self._paths.remove(path)
        self._rebuild()
        self.message.emit("已删除 1 张图片")
        if self._tiles and index is not None:
            neighbour = self._tiles[min(index, len(self._tiles) - 1)]
            neighbour.setFocus(Qt.OtherFocusReason)

    def delete_selected(self) -> None:
        selected = set(self.selected_paths())
        if not selected:
            self.message.emit("还没有选中图片")
            return
        self._paths = [p for p in self._paths if p not in selected]
        self._rebuild()
        self.message.emit("已删除 %d 张图片" % len(selected))

    def clear_all(self) -> None:
        if not self._paths:
            self.message.emit("列表已经是空的")
            return
        count = len(self._paths)
        self._paths = []
        self._rebuild()
        self.message.emit("已清空 %d 张图片" % count)

    def select_all(self) -> None:
        for tile in self._tiles:
            tile.set_selected(True)
        self.selection_changed.emit(len(self._tiles))
        self.update()

    def clear_selection(self) -> None:
        for tile in self._tiles:
            tile.set_selected(False)
        self.selection_changed.emit(0)
        self.update()

    def set_thumb_size(self, size: int) -> None:
        self._thumb = size
        self._rebuild()

    def set_sort_mode(self, mode: str) -> None:
        self._sort_mode = mode
        self._rebuild()

    # ------------------------------------------------------------------ 文件对话框

    def choose_files(self) -> None:
        patterns = " ".join("*" + s for s in sorted(SUPPORTED))
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "图片 (%s)" % patterns)
        if files:
            self.add_paths(files)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            self.add_paths([folder])

    def export_to(self) -> None:
        if not self._paths:
            self.message.emit("还没有可以导出的图片")
            return
        target = QFileDialog.getExistingDirectory(self, "导出到文件夹")
        if not target:
            return
        copied = 0
        for path in self._paths:
            name = os.path.basename(path)
            root, ext = os.path.splitext(name)
            candidate = os.path.join(target, name)
            index = 2
            while os.path.exists(candidate):
                candidate = os.path.join(target, "%s-%d%s" % (root, index, ext))
                index += 1
            try:
                shutil.copy2(path, candidate)
                copied += 1
            except OSError:
                continue
        self.message.emit("已导出 %d 张到 %s" % (copied, os.path.basename(target) or target))

    # ------------------------------------------------------------------ 布局

    def _sorted_paths(self) -> list[str]:
        if self._sort_mode == "time":
            def key(path):
                try:
                    return os.path.getmtime(path)
                except OSError:
                    return 0
            return sorted(self._paths, key=key, reverse=True)
        return sorted(self._paths, key=lambda p: os.path.basename(p).lower())

    def _rebuild(self) -> None:
        for tile in self._tiles:
            tile.setParent(None)
            tile.deleteLater()
        self._tiles = []
        for path in self._sorted_paths():
            tile = PhotoTile(path, self._thumb, self._theme, self)
            tile.delete_requested.connect(self.remove_path)
            tile.open_requested.connect(self._open_path)
            tile.selection_toggled.connect(self._on_tile_toggle)
            tile.show()
            self._tiles.append(tile)
        self._scroll = 0
        self._empty.setVisible(not self._paths)
        self._install_drop_filter(self)
        self._relayout()
        self.changed.emit()

    def _on_tile_toggle(self, path: str, selected: bool) -> None:
        for tile in self._tiles:
            if tile.path == path:
                tile.set_selected(selected)
        self.selection_changed.emit(len(self.selected_paths()))
        self.update()

    def _open_path(self, path: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.message.emit("已交给系统打开：%s" % os.path.basename(path))

    def _on_drop_scale(self, value: float) -> None:
        self._drop_scale = value
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        inner = self.rect().adjusted(PAD_PADDING, PAD_PADDING, -PAD_PADDING, -PAD_PADDING)
        self._empty.setGeometry(inner)
        if not self._tiles:
            self._max_scroll = 0
            return
        thumb = max(1, int(self._thumb * self._drop_scale))
        gap = theme.GRID_GAP
        columns = max(1, (inner.width() + gap) // (thumb + gap))
        rows = (len(self._tiles) + columns - 1) // columns
        used = columns * thumb + (columns - 1) * gap
        offset_x = inner.x() + max(0, (inner.width() - used) // 2)
        content = rows * thumb + (rows - 1) * gap
        self._max_scroll = max(0, content - inner.height())
        self._scroll = max(0, min(self._scroll, self._max_scroll))
        for index, tile in enumerate(self._tiles):
            row, column = divmod(index, columns)
            tile.setGeometry(offset_x + column * (thumb + gap),
                             inner.y() + row * (thumb + gap) - self._scroll,
                             thumb, thumb)

    def wheelEvent(self, event):
        if self._max_scroll <= 0:
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        self._scroll = max(0, min(self._scroll - delta, self._max_scroll))
        self._relayout()
        self._scroll_hint.start(700)
        event.accept()

    # ------------------------------------------------------------------ 拖放

    def _install_drop_filter(self, root: QWidget) -> None:
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            child.setAcceptDrops(True)
            child.installEventFilter(self)

    def _urls_accept(self, event) -> bool:
        if not event.mimeData().hasUrls():
            return False
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and (os.path.isdir(local) or is_image(local)):
                return True
        return False

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.DragEnter:
            if self._urls_accept(event):
                event.acceptProposedAction()
                self._set_dropping(True)
                return True
            event.ignore()
            return True
        if kind == QEvent.Type.DragMove:
            if self._urls_accept(event):
                event.acceptProposedAction()
            return True
        if kind == QEvent.Type.DragLeave:
            self._set_dropping(False)
            return True
        if kind == QEvent.Type.Drop:
            if self._urls_accept(event):
                event.acceptProposedAction()
                paths = [url.toLocalFile() for url in event.mimeData().urls()]
                self._set_dropping(False)
                self.add_paths(paths)
                return True
            event.ignore()
            return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event):
        if self._urls_accept(event):
            event.acceptProposedAction()
            self._set_dropping(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_dropping(False)

    def dragMoveEvent(self, event):
        if self._urls_accept(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self._urls_accept(event):
            event.acceptProposedAction()
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            self._set_dropping(False)
            self.add_paths(paths)
        else:
            event.ignore()

    def _set_dropping(self, dropping: bool) -> None:
        if self._dropping == dropping:
            return
        self._dropping = dropping
        self._drop_spring.set_target(theme.DROP_SCALE if dropping else 1.0)
        self.update()

    # ------------------------------------------------------------------ 绘制

    def set_theme(self, theme_ref: theme.Theme) -> None:
        self._theme = theme_ref
        self._empty.set_theme(theme_ref)
        for tile in self._tiles:
            tile.set_theme(theme_ref)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        t = self._theme
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        radius = theme.RADIUS_TILE
        painter.setPen(Qt.NoPen)
        painter.setBrush(rgba(t.recess_wash, t.well_alpha))
        painter.drawRoundedRect(rect, radius, radius)
        rim = QColor(255, 255, 255)
        rim.setAlphaF(0.45 if not t.is_dark else 0.22)
        pen = painter.pen()
        pen.setColor(rim)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        if self._dropping:
            pen.setColor(QColor(t.accent))
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), radius - 2, radius - 2)

        if self._max_scroll > 0 and self._scroll_hint.isActive():
            track_h = self.height() - 2 * theme.SPACE_4
            thumb_h = max(28.0, track_h * self.height() / (self.height() + self._max_scroll))
            travel = track_h - thumb_h
            position = theme.SPACE_4 + travel * (self._scroll / self._max_scroll if self._max_scroll else 0)
            bar = QRectF(self.width() - 8.0, position, 3.0, thumb_h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(rgba("#0C0E12", 0.22 if not t.is_dark else 0.35))
            painter.drawRoundedRect(bar, 1.5, 1.5)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            self.clear_selection()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.selected_paths():
            self.delete_selected()
        else:
            super().keyPressEvent(event)