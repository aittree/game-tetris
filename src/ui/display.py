# -*- coding: utf-8 -*-
"""显示层：720×800 逻辑画布、窗口/全屏切换、等比缩放居中与坐标映射。

分层：表现层。
允许依赖：pygame、config。
禁止依赖：game / board / storage（本模块只负责把画布送到屏幕）。

实现依据：03 详细设计 §6.4。刻意不用 pygame.SCALED，避免部分环境
「failed to create renderer」以及请求尺寸被忽略的问题。
"""

from __future__ import annotations

import pygame

from ..config import CANVAS_H, CANVAS_W

# 窗口模式下为边框与任务栏预留的像素
_WINDOW_MARGIN_X = 40
_WINDOW_MARGIN_Y = 120


class Display:
    """把固定尺寸画布按需缩放后呈现，并把鼠标坐标换算回画布坐标。"""

    def __init__(self, fullscreen: bool = False) -> None:
        self.fullscreen = fullscreen
        self.scale = 1.0
        self.offset = (0, 0)
        self.scaled: pygame.Surface | None = None
        self.screen = pygame.display.set_mode((CANVAS_W, CANVAS_H))
        self.apply_mode(fullscreen)
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H)).convert()

    def apply_mode(self, fullscreen: bool) -> None:
        """切换窗口/全屏；全屏只放大到能完整容纳画布的比例，多余区域留黑边。"""
        self.fullscreen = fullscreen
        if fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            sw, sh = self.screen.get_size()
            self.scale = min(sw / CANVAS_W, sh / CANVAS_H)
            w, h = int(CANVAS_W * self.scale), int(CANVAS_H * self.scale)
            self.scaled = pygame.Surface((w, h))
            self.offset = ((sw - w) // 2, (sh - h) // 2)
            return

        # 窗口模式：固定 720×800 逻辑画布、不可手动拉伸；
        # 桌面可用区域不足时自动等比缩小，避免窗口超出屏幕
        dw, dh = pygame.display.get_desktop_sizes()[0]
        self.scale = min(1.0, (dw - _WINDOW_MARGIN_X) / CANVAS_W,
                         (dh - _WINDOW_MARGIN_Y) / CANVAS_H)
        w, h = int(CANVAS_W * self.scale), int(CANVAS_H * self.scale)
        self.screen = pygame.display.set_mode((w, h))
        self.scaled = pygame.Surface((w, h)) if self.scale < 1.0 else None
        self.offset = (0, 0)

    def present(self) -> None:
        """把画布送到屏幕并翻转；全屏黑边不参与缩放。"""
        if self.fullscreen and self.scaled is not None:
            pygame.transform.smoothscale(self.canvas, self.scaled.get_size(), self.scaled)
            self.screen.fill((0, 0, 0))
            self.screen.blit(self.scaled, self.offset)
        elif self.scaled is not None:
            pygame.transform.smoothscale(self.canvas, self.scaled.get_size(), self.scaled)
            self.screen.blit(self.scaled, (0, 0))
        else:
            self.screen.blit(self.canvas, (0, 0))
        pygame.display.flip()

    def to_canvas(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """窗口/屏幕坐标 → 画布坐标；落在黑边或画布外时返回 None。"""
        x = (pos[0] - self.offset[0]) / self.scale
        y = (pos[1] - self.offset[1]) / self.scale
        if 0 <= x < CANVAS_W and 0 <= y < CANVAS_H:
            return int(x), int(y)
        return None

    def canvas_rect_to_screen(self, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """画布矩形 → 屏幕矩形，供输入法候选框（set_text_input_rect）定位。"""
        x, y, w, h = rect
        return (int(self.offset[0] + x * self.scale),
                int(self.offset[1] + y * self.scale),
                max(1, int(w * self.scale)),
                max(1, int(h * self.scale)))
