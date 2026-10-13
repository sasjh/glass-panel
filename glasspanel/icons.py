"""图标：以 24x24 设计栅格描边绘制，不依赖图标字体。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

GRID = 24.0

ICONS: dict[str, list[tuple]] = {
    "add_photo": [
        ("rect", 2.5, 4.0, 14.5, 12.0, 2.6),
        ("path", [(6.0, 13.4), (9.4, 9.6), (11.7, 12.1), (13.4, 10.3), (16.2, 13.4)]),
        ("dot", 7.0, 7.6, 1.4),
        ("line", 19.5, 15.0, 19.5, 21.4),
        ("line", 16.3, 18.2, 22.7, 18.2),
    ],
    "add_folder": [
        ("path", [(2.8, 17.0), (2.8, 5.6), (8.4, 5.6), (10.4, 8.2), (18.6, 8.2), (18.6, 17.0)], True),
        ("line", 20.8, 15.0, 20.8, 21.2),
        ("line", 17.7, 18.1, 23.9, 18.1),
    ],
    "sort_name": [
        ("line", 7.0, 20.0, 7.0, 5.2),
        ("path", [(3.9, 8.3), (7.0, 5.0), (10.1, 8.3)]),
        ("line", 17.0, 4.0, 17.0, 18.8),
        ("path", [(13.9, 15.7), (17.0, 19.0), (20.1, 15.7)]),
    ],
    "sort_time": [
        ("ellipse", 12.0, 12.0, 8.6, 8.6),
        ("line", 12.0, 6.9, 12.0, 12.0),
        ("line", 12.0, 12.0, 15.9, 13.9),
    ],
    "size": [
        ("rect", 3.4, 3.4, 7.2, 7.2, 2.0),
        ("rect", 13.4, 3.4, 7.2, 7.2, 2.0),
        ("rect", 3.4, 13.4, 7.2, 7.2, 2.0),
        ("rect", 13.4, 13.4, 7.2, 7.2, 2.0),
    ],
    "export": [
        ("path", [(4.0, 15.2), (4.0, 20.0), (20.0, 20.0), (20.0, 15.2)]),
        ("line", 12.0, 3.4, 12.0, 15.0),
        ("path", [(7.9, 7.2), (12.0, 3.1), (16.1, 7.2)]),
    ],
    "trash": [
        ("line", 3.8, 6.6, 20.2, 6.6),
        ("path", [(6.4, 6.6), (7.4, 20.2), (16.6, 20.2), (17.6, 6.6)], True),
        ("path", [(9.6, 6.6), (9.6, 4.2), (14.4, 4.2), (14.4, 6.6)]),
        ("line", 10.6, 10.2, 10.6, 16.6),
        ("line", 13.4, 10.2, 13.4, 16.6),
    ],
    "theme": [
        ("ellipse", 12.0, 12.0, 8.4, 8.4),
        ("pie_fill", 3.6, 3.6, 16.8, 16.8, 90.0, 180.0),
    ],
    "close": [
        ("line", 6.6, 6.6, 17.4, 17.4),
        ("line", 17.4, 6.6, 6.6, 17.4),
    ],
    "minimize": [("line", 5.8, 12.0, 18.2, 12.0)],
    "maximize": [("rect", 5.6, 5.6, 12.8, 12.8, 2.4)],
    "restore": [
        ("rect", 3.4, 8.6, 11.0, 11.0, 2.2),
        ("path", [(8.4, 8.6), (8.4, 4.4), (20.6, 4.4), (20.6, 15.4), (15.6, 15.4)]),
    ],
    "placeholder": [
        ("rect", 2.6, 3.8, 18.8, 16.4, 3.2),
        ("path", [(6.4, 16.6), (10.4, 11.4), (13.4, 14.6), (15.6, 12.2), (19.0, 16.0)]),
        ("dot", 8.4, 8.6, 1.7),
    ],
    "check": [("path", [(5.2, 12.6), (10.0, 17.4), (18.8, 7.2)])],
    "search": [("ellipse", 10.6, 10.6, 6.4, 6.4), ("line", 15.4, 15.4, 20.4, 20.4)],
}


def _build_path(commands: list[tuple], scale: float) -> tuple[QPainterPath, QPainterPath, list]:
    stroke = QPainterPath()
    fill = QPainterPath()
    pies: list[tuple[QRectF, float, float]] = []
    for cmd in commands:
        kind = cmd[0]
        if kind == "rect":
            _, x, y, w, h, r = cmd
            stroke.addRoundedRect(QRectF(x * scale, y * scale, w * scale, h * scale), r * scale, r * scale)
        elif kind == "path":
            _, points, *rest = cmd
            if not points:
                continue
            path = QPainterPath(QPointF(points[0][0] * scale, points[0][1] * scale))
            for px, py in points[1:]:
                path.lineTo(px * scale, py * scale)
            if rest and rest[0]:
                path.closeSubpath()
            stroke.addPath(path)
        elif kind == "ellipse":
            _, cx, cy, rx, ry = cmd
            stroke.addEllipse(QPointF(cx * scale, cy * scale), rx * scale, ry * scale)
        elif kind == "line":
            _, x1, y1, x2, y2 = cmd
            path = QPainterPath(QPointF(x1 * scale, y1 * scale))
            path.lineTo(x2 * scale, y2 * scale)
            stroke.addPath(path)
        elif kind == "dot":
            _, cx, cy, r = cmd
            fill.addEllipse(QPointF(cx * scale, cy * scale), r * scale, r * scale)
        elif kind == "pie_fill":
            _, x, y, w, h, start, span = cmd
            pies.append((QRectF(x * scale, y * scale, w * scale, h * scale), start, span))
    return stroke, fill, pies


def paint_icon(painter: QPainter, name: str, rect: QRectF, color: QColor,
               stroke_ratio: float = 0.075, filled_color: QColor | None = None) -> None:
    """在 rect 内居中绘制图标；stroke_ratio 相对于图标边长。"""
    commands = ICONS.get(name)
    if not commands:
        return
    size = min(rect.width(), rect.height())
    scale = size / GRID
    stroke, fill, pies = _build_path(commands, scale)
    origin_x = rect.x() + (rect.width() - size) / 2.0
    origin_y = rect.y() + (rect.height() - size) / 2.0
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.translate(origin_x, origin_y)
    pen = QPen(color)
    pen.setWidthF(max(1.0, size * stroke_ratio))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(stroke)
    if not fill.isEmpty():
        painter.setPen(Qt.NoPen)
        painter.setBrush(filled_color or color)
        painter.drawPath(fill)
    for pie_rect, start, span in pies:
        painter.setPen(Qt.NoPen)
        painter.setBrush(filled_color or color)
        painter.drawPie(pie_rect, int(start * 16), int(span * 16))
    painter.restore()


def icon_pixmap(name: str, size: int, color: QColor, dpr: float = 2.0):
    """离屏渲染一个图标（用于测试 / 缓存）。"""
    from PySide6.QtGui import QPixmap

    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    paint_icon(painter, name, QRectF(0, 0, size, size), color)
    painter.end()
    return pm