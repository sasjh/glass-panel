"""装配窗口：左侧功能键 + 右侧图片区。"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox

from . import theme
from .pad import ImagePad
from .qtutil import font_for
from .rail import FunctionRail
from .shell import GlassWindow


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%d B" % size


class ImagePanelWindow(GlassWindow):
    """整窗：功能键栏 + 图片区。"""

    def __init__(self):
        super().__init__("图片面板", theme.LIGHT)
        self.rail = FunctionRail(self.theme_ref)
        self.pad = ImagePad(self.theme_ref, self)

        body = QHBoxLayout(self.body)
        body.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_4)
        body.setSpacing(theme.SPACE_4)
        body.addWidget(self.rail)
        body.addWidget(self.pad, 1)

        self._sort_mode = "name"
        self._size_index = 1
        self._selection = 0

        self.rail.add_images.connect(self.pad.choose_files)
        self.rail.add_folder.connect(self.pad.choose_folder)
        self.rail.cycle_sort.connect(self._cycle_sort)
        self.rail.cycle_size.connect(self._cycle_size)
        self.rail.export_images.connect(self.pad.export_to)
        self.rail.clear_images.connect(self._confirm_clear)
        self.rail.toggle_theme.connect(self._toggle_theme)

        self.pad.message.connect(self.show_toast)
        self.pad.changed.connect(self._refresh_meta)
        self.pad.selection_changed.connect(self._on_selection)

        QShortcut(QKeySequence("Ctrl+O"), self, self.pad.choose_files)
        QShortcut(QKeySequence("Ctrl+A"), self, self.pad.select_all)
        QShortcut(QKeySequence("Esc"), self, self.pad.clear_selection)

        self.rail.set_sort_mode(self._sort_mode)
        self.rail.set_size_label(theme.THUMB_SIZES[self._size_index][0])
        self._refresh_meta()
        self.pad.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------------------ 事件

    def _cycle_sort(self) -> None:
        self._sort_mode = "time" if self._sort_mode == "name" else "name"
        self.pad.set_sort_mode(self._sort_mode)
        self.rail.set_sort_mode(self._sort_mode)
        self.show_toast("按%s排序" % ("时间" if self._sort_mode == "time" else "名称"))

    def _cycle_size(self) -> None:
        self._size_index = (self._size_index + 1) % len(theme.THUMB_SIZES)
        label, size = theme.THUMB_SIZES[self._size_index]
        self.pad.set_thumb_size(size)
        self.rail.set_size_label(label)
        self.show_toast("缩略图：%s" % label)

    def _toggle_theme(self) -> None:
        target = theme.DARK if self.theme_ref is theme.LIGHT else theme.LIGHT
        self.apply_theme(target)
        self.rail.set_theme(target)
        self.pad.set_theme(target)
        self.show_toast("%s模式" % target.name)

    def _confirm_clear(self) -> None:
        if self.pad.count == 0:
            self.show_toast("列表已经是空的")
            return
        box = QMessageBox(self)
        box.setWindowTitle("清空图片")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("要清空这 %d 张图片吗？" % self.pad.count)
        box.setInformativeText("只会从列表里移除，不会删除磁盘上的原图。")
        clear = box.addButton("清空", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is clear:
            self.pad.clear_all()

    def _on_selection(self, count: int) -> None:
        self._selection = count
        self._refresh_meta()

    def _refresh_meta(self) -> None:
        count = self.pad.count
        if count == 0:
            self.titlebar.set_subtitle("")
            return
        text = "%d 张 · %s" % (count, human_bytes(self.pad.total_bytes()))
        if self._selection:
            text += " · 已选 %d" % self._selection
        self.titlebar.set_subtitle(text)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("图片面板")
    app.setOrganizationName("GlassPanel")
    app.setApplicationDisplayName("图片面板")
    app.setFont(font_for("body"))
    metrics = QFontMetrics(font_for("body"))
    del metrics
    window = ImagePanelWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())