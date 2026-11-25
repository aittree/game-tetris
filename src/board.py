# -*- coding: utf-8 -*-
"""棋盘地形：22×10 网格、碰撞检测、锁定、消行与快照导出。

分层：模型层。
允许依赖：config、pieces（仅类型标注）。
禁止依赖：pygame、game、ui、audio、storage。

实现依据：03 详细设计 §3。
约定：grid 存方块类型字母（"I"…"Z"）而不是 1/2/3，空格为 0，便于调试输出。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from .config import COLS, HIDDEN_ROWS, ROWS

if TYPE_CHECKING:
    from .pieces import Piece

EMPTY: str | int = 0


class Board:
    """固定 22 行 × 10 列地形，行 0/1 为隐藏缓冲区，2～21 为可见区。"""

    def __init__(self) -> None:
        self.grid: list[list[str | int]] = []
        self.reset()

    # —— 查询 ——
    def collides(self, cells: Iterable[tuple[int, int]]) -> bool:
        """任一格越界或已被占用即冲突；行号 < 0 视为场内自由空间（SRS 踢墙可能把方块顶出画面）。"""
        for r, c in cells:
            if c < 0 or c >= COLS or r >= ROWS:
                return True
            if r >= 0 and self.grid[r][c] != EMPTY:
                return True
        return False

    def full_rows(self) -> list[int]:
        """返回所有已填满的行号。"""
        return [r for r in range(ROWS)
                if all(self.grid[r][c] != EMPTY for c in range(COLS))]

    def visible_count(self) -> int:
        """可见区（行 2～21）内的方块格数，用于锁出判定。"""
        return sum(1 for r in range(HIDDEN_ROWS, ROWS)
                   for c in range(COLS) if self.grid[r][c] != EMPTY)

    # —— 变更 ——
    def lock(self, piece: Piece) -> None:
        """把方块写入地形；隐藏区以上的格子按越界忽略。"""
        for r, c in piece.cells():
            if 0 <= r < ROWS and 0 <= c < COLS:
                self.grid[r][c] = piece.type

    def clear_rows(self, rows: list[int]) -> None:
        """一次性移除所有满行，并在顶部补等量空行。

        必须「过滤 + 顶部补行」而不是逐行 pop/insert，否则一次消多行时行号会错乱。
        """
        keep = [row for r, row in enumerate(self.grid) if r not in rows]
        self.grid = [[EMPTY] * COLS for _ in range(len(rows))] + keep

    def reset(self) -> None:
        """清空地形。"""
        self.grid = [[EMPTY] * COLS for _ in range(ROWS)]

    # —— 测试 / 调试 ——
    def load_from(self, rows: list[str]) -> None:
        """按字符画构造地形（仅测试/调试用）：'.' 空，'I'…'Z' 为对应方块。"""
        self.reset()
        for r, line in enumerate(rows[:ROWS]):
            for c, ch in enumerate(line[:COLS]):
                self.grid[r][c] = EMPTY if ch == "." else ch

    def dump(self) -> str:
        """调试用文本视图，'.' 表示空，字母表示对应方块。"""
        return "\n".join("".join("." if v == EMPTY else str(v) for v in row)
                         for row in self.grid)
