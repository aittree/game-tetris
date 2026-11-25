# -*- coding: utf-8 -*-
"""主题：方块配色、字号、布局坐标与矩形工具。

分层：表现层。
允许依赖：config。
禁止依赖：game 状态、pygame（本模块只算坐标与常量，不绘制）。

实现依据：03 详细设计 §6.1、01 需求规格 §5.1。
"""

from __future__ import annotations

from ..config import (ACCENT, BOARD_X, BOARD_Y, CELL, COLS, HIDDEN_ROWS,
                      PIECE_RGB, VISIBLE_ROWS)

FONT_SIZES: dict[str, int] = {
    "logo": 44,
    "title": 40,
    "overlay_title": 36,
    "value": 30,
    "panel_value": 22,
    "button": 22,
    "panel_title": 18,
    "card_label": 16,
    "hint": 16,
    "small": 14,
}

# —— 顶部数值卡片 ——
CARD_W, CARD_H, CARD_GAP, CARD_TOP = 86, 78, 10, 40
CARD_XS = (384, 384 + CARD_W + CARD_GAP, 384 + 2 * (CARD_W + CARD_GAP))   # 384/480/576
CARD_RECTS = tuple((x, CARD_TOP, CARD_W, CARD_H) for x in CARD_XS)

# —— 右侧面板分区 ——
HOLD_BOX = (384, 136, 280, 164)
HOLD_CENTER = (524, 216)
NEXT_BOX = (384, 300, 280, 296)
NEXT_FIRST_CENTER = (524, 430)
NEXT_STEP = 56
HINT_BOX = (384, 596, 280, 140)

# —— 底部提示条 ——
HINT_BAR_Y = 752

# —— 主菜单 ——
MENU_BUTTON_RECTS = tuple((210, 360 + i * 68, 300, 56) for i in range(4))
MENU_BUTTON_LABELS = ("开始游戏", "排行榜", "设置", "退出")

# —— 设置页 ——
SETTINGS_ROW_YS = (180, 256, 332, 408)
SETTINGS_ROW_H = 64
SETTINGS_MINUS_X = 470
SETTINGS_PLUS_X = 600
SETTINGS_BACK = (210, 640, 300, 56)

# —— 排行榜 ——
RANKING_HEADER_Y = 138
RANKING_FIRST_Y = 180
RANKING_ROW_H = 46
RANKING_BACK = (210, 690, 300, 52)

# —— 浮层按钮：暂停与结束共用三格纵向布局 ——
OVERLAY_CARD = (140, 220, 440, 380)
OVERLAY_BUTTON_RECTS = tuple((210, 420 + i * 58, 300, 48) for i in range(3))
OVERLAY_PAUSE_LABELS = ("继续", "重新开始", "返回主菜单")
OVERLAY_OVER_LABELS = ("再来一局", "登记成绩", "返回主菜单")

# —— 昵称登记 ——
ENTRY_CARD = (120, 200, 480, 400)
ENTRY_NAME_BOX = (160, 370, 400, 56)

# —— 二次确认弹窗（退出 / 重开）——
CONFIRM_CARD = (140, 260, 440, 280)
CONFIRM_CANCEL = (170, 440, 180, 52)
CONFIRM_OK = (370, 440, 180, 52)


def piece_rgb(piece_type: str) -> tuple[int, int, int]:
    """方块类型 → RGB，未知类型回退强调色。"""
    return PIECE_RGB.get(piece_type, ACCENT)


def cell_rect(row: int, col: int) -> tuple[int, int, int, int]:
    """逻辑行（0～21）→ 画布矩形；隐藏行会得到负 y，调用方需裁剪。"""
    return (BOARD_X + col * CELL,
            BOARD_Y + (row - HIDDEN_ROWS) * CELL,
            CELL, CELL)


def board_rect() -> tuple[int, int, int, int]:
    """棋盘可见区矩形。"""
    return BOARD_X, BOARD_Y, COLS * CELL, VISIBLE_ROWS * CELL
