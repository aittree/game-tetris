# -*- coding: utf-8 -*-
"""全局常量与纯配置计算。

分层：模型层 / 配置。
允许依赖：标准库。
禁止依赖：任何业务模块（pieces、board、game、ui、audio 等）。
"""

from __future__ import annotations

APP_NAME = "俄罗斯方块"
APP_ID = "TetrisDesktop"
VERSION = "1.0.0"
DEBUG = False                       # 发布前必须为 False

# —— 画布与棋盘尺寸 ——
CANVAS_W, CANVAS_H = 720, 800
CELL = 30                           # 单格像素
COLS = 10
VISIBLE_ROWS = 20
HIDDEN_ROWS = 2                     # 顶部隐藏缓冲区
ROWS = VISIBLE_ROWS + HIDDEN_ROWS   # 22

BOARD_X, BOARD_Y = 56, 136
BOARD_W, BOARD_H = COLS * CELL, VISIBLE_ROWS * CELL      # 300 × 600
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 384, 136, 280, 600

# —— 节奏与规则参数 ——
FPS = 60
LOCK_DELAY_MS = 500                 # 锁定延迟
LOCK_RESET_MAX = 15                 # 锁定延迟最多重置次数
DAS_MS = 170                        # 按住方向键的首次延迟
ARR_MS = 40                         # 之后的连发间隔
SOFT_DROP_MS = 50                   # 按住 ↓ 的连发间隔
NEXT_COUNT = 5                      # 预览数量

SOFT_DROP_PER_CELL = 1
HARD_DROP_PER_CELL = 2
LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}

MAX_NAME_LEN = 12                   # 排行榜昵称上限
SAVE_DIR_NAME = "TetrisDesktop"     # %APPDATA%\TetrisDesktop

# —— 配色（与 01 §5.2、assets/images/blocks.png 一致）——
PIECE_RGB = {
    "I": (0, 229, 255),
    "J": (61, 90, 254),
    "L": (255, 159, 28),
    "O": (255, 214, 10),
    "S": (46, 230, 168),
    "T": (177, 78, 255),
    "Z": (255, 77, 109),
}
GHOST_RGB = (120, 130, 160)

BG_COLOR = (5, 7, 15)
BOARD_BG = (10, 14, 26)
GRID_COLOR = (30, 42, 68)
BORDER_COLOR = (0, 229, 255)
TEXT_MAIN = (232, 241, 255)
TEXT_SUB = (143, 160, 191)
ACCENT = (0, 229, 255)
CARD_BG = (16, 22, 38)

# —— 下落速度表（毫秒／格，见 01 FR-08）——
_GRAVITY_TABLE = {
    1: 800, 2: 717, 3: 633, 4: 550, 5: 467,
    6: 383, 7: 300, 8: 217, 9: 133, 10: 100,
}


def gravity_ms(level: int) -> float:
    """按等级返回每下落一格所需毫秒；11 级以后按区间取固定值。"""
    if level <= 10:
        return _GRAVITY_TABLE[max(1, level)]
    if level <= 13:
        return 83
    if level <= 16:
        return 67
    if level <= 19:
        return 50
    if level <= 28:
        return 33
    return 17


def level_from_lines(lines: int) -> int:
    """累计消行数 → 等级（每 10 行 +1，从 1 级起）。"""
    return 1 + lines // 10
