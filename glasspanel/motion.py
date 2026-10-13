"""可打断的弹簧动效 + 系统「减少动态效果」支持。"""
from __future__ import annotations

import ctypes

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal

from .theme import (SPRING_BOUNCE_DAMPING, SPRING_BOUNCE_RESPONSE, SPRING_DAMPING,  # noqa: F401
                    SPRING_RESPONSE)

SPI_GETCLIENTAREAANIMATION = 0x1042
_SPI_CACHE: bool | None = None


def animations_enabled() -> bool:
    """尊重 Windows「辅助功能 → 视觉效果 → 动画效果」。"""
    global _SPI_CACHE
    if _SPI_CACHE is None:
        enabled = True
        try:
            value = ctypes.c_int(1)
            ok = ctypes.WinDLL("user32").SystemParametersInfoW(
                SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0
            )
            if ok:
                enabled = bool(value.value)
        except Exception:
            pass
        _SPI_CACHE = enabled
    return _SPI_CACHE


def reset_preference_cache() -> None:
    """系统设置变化后重新读取。"""
    global _SPI_CACHE
    _SPI_CACHE = None


class Spring(QObject):
    """临界阻尼弹簧：从「当前值」出发，因此随时可被打断、反向。"""

    value_changed = Signal(float)
    finished = Signal()

    def __init__(self, value: float = 0.0, response: float = 0.32,
                 damping: float = 1.0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._value = float(value)
        self._target = float(value)
        self._velocity = 0.0
        self._response = response
        self._damping = damping
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    @property
    def value(self) -> float:
        return self._value

    @property
    def target(self) -> float:
        return self._target

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def jump_to(self, value: float) -> None:
        self._timer.stop()
        self._value = self._target = float(value)
        self._velocity = 0.0
        self.value_changed.emit(self._value)
        self.finished.emit()

    def set_target(self, target: float, velocity: float = 0.0) -> None:
        self._target = float(target)
        self._velocity = float(velocity)
        if not animations_enabled():
            self.jump_to(target)
            return
        if abs(self._value - self._target) < 1e-4 and abs(self._velocity) < 1e-3:
            self.jump_to(target)
            return
        self._clock.restart()
        if not self._timer.isActive():
            self._timer.start()

    def nudge(self, delta: float, target: float | None = None) -> None:
        """保持当前位移，重设目标（打断时用）。"""
        self._value += delta
        self.set_target(self._target if target is None else target)

    def _tick(self) -> None:
        dt = min(self._clock.restart() / 1000.0, 0.05)
        if dt <= 0:
            return
        omega = 6.283185307179586 / max(self._response, 0.05)
        for _ in range(2):  # 半步积分，值小时也稳
            sub = dt / 2.0
            accel = -omega * omega * (self._value - self._target) - 2.0 * self._damping * omega * self._velocity
            self._velocity += accel * sub
            self._value += self._velocity * sub
        if abs(self._value - self._target) < 0.0015 and abs(self._velocity) < 0.02:
            self._value = self._target
            self._velocity = 0.0
            self._timer.stop()
            self.value_changed.emit(self._value)
            self.finished.emit()
            return
        self.value_changed.emit(self._value)