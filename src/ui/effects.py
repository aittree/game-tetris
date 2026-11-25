# -*- coding: utf-8 -*-
"""画面特效：消行白闪、四行消除震动、落点提示框。

分层：表现层。
允许依赖：标准库 random。
禁止依赖：game / board / storage。

实现依据：03 详细设计 §6.3。特效只影响绘制，不参与任何规则计算。
"""

from __future__ import annotations

import random

FLASH_MS = 180
SHAKE_MS = 200
LAND_MS = 120


class Effects:
    """以毫秒为单位维护特效剩余时间，由 main.py 每帧 update(dt)。"""

    def __init__(self) -> None:
        self.flashes: list[list] = []        # [[rows, elapsed_ms], ...]
        self.shake_until: float = 0.0        # 剩余震动毫秒
        self.land_rects: list[list] = []     # [[cells, elapsed_ms], ...]

    def on_clear(self, rows: list[int], count: int) -> None:
        """开始行消除白闪；四行消除额外触发震动。"""
        self.flashes.append([list(rows), 0.0])
        if count == 4:
            self.shake_until = SHAKE_MS

    def on_land(self, cells: list[tuple[int, int]]) -> None:
        """硬降落地后，在落点格上短暂描边。"""
        self.land_rects.append([list(cells), 0.0])

    def update(self, dt_ms: float) -> None:
        """推进并清理过期特效。"""
        for flash in self.flashes:
            flash[1] += dt_ms
        self.flashes = [flash for flash in self.flashes if flash[1] < FLASH_MS]

        for mark in self.land_rects:
            mark[1] += dt_ms
        self.land_rects = [mark for mark in self.land_rects if mark[1] < LAND_MS]

        self.shake_until = max(0.0, self.shake_until - dt_ms)

    def offset(self) -> tuple[int, int]:
        """随剩余时间线性衰减的随机抖动；无震动时返回 (0, 0)。"""
        if self.shake_until <= 0:
            return 0, 0
        amp = max(1, int(3 * (self.shake_until / SHAKE_MS)))
        return random.randint(-amp, amp), random.randint(-amp, amp)
