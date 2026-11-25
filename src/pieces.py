# -*- coding: utf-8 -*-
"""七种四格骨牌、SRS 旋转态与踢墙表、7-bag 随机生成器。

分层：模型层。
允许依赖：标准库（random）、config。
禁止依赖：pygame、board、game、ui、audio。

实现依据：03 详细设计 §2（形状矩阵、四态生成、踢墙表、Piece、SevenBag）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

PIECE_TYPES: tuple[str, ...] = ("I", "J", "L", "O", "S", "T", "Z")
SPAWN_X: dict[str, int] = {"I": 3, "J": 3, "L": 3, "O": 4, "S": 3, "T": 3, "Z": 3}
SPAWN_Y = 0                         # 生成于隐藏缓冲区

# —— 生成态矩阵（1 表示填充）——
# I 用 4×4、O 用 2×2、其余用 3×3，与 SRS 的旋转边界一致，旋转后形状才不会偏移。
SHAPES: dict[str, tuple[tuple[int, ...], ...]] = {
    "I": ((0, 0, 0, 0),
          (1, 1, 1, 1),
          (0, 0, 0, 0),
          (0, 0, 0, 0)),
    "J": ((1, 0, 0),
          (1, 1, 1),
          (0, 0, 0)),
    "L": ((0, 0, 1),
          (1, 1, 1),
          (0, 0, 0)),
    "O": ((1, 1),
          (1, 1)),
    "S": ((0, 1, 1),
          (1, 1, 0),
          (0, 0, 0)),
    "T": ((0, 1, 0),
          (1, 1, 1),
          (0, 0, 0)),
    "Z": ((1, 1, 0),
          (0, 1, 1),
          (0, 0, 0)),
}


def _rotate_cw(matrix: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    """矩阵顺时针旋转 90°：先上下翻转，再转置。"""
    return tuple(tuple(row) for row in zip(*matrix[::-1]))


def _build_states() -> dict[str, tuple[tuple[tuple[int, ...], ...], ...]]:
    """由生成态推出四个旋转态，避免手写 28 个矩阵导致状态间不一致。"""
    states: dict[str, tuple[tuple[tuple[int, ...], ...], ...]] = {}
    for name, shape in SHAPES.items():
        if name == "O":
            # O 块旋转外观不变
            states[name] = (shape, shape, shape, shape)
        else:
            s0 = shape
            s1 = _rotate_cw(s0)
            s2 = _rotate_cw(s1)
            s3 = _rotate_cw(s2)
            states[name] = (s0, s1, s2, s3)
    return states


# ROTATIONS["T"][2] 即 T 块的 180° 态；状态编号 0/1/2/3 = 生成态/R/180°/L
ROTATIONS = _build_states()

# —— SRS 踢墙表 ——
# 偏移量写作 (dx, dy)，dy 为正表示向上；落子坐标系行号向下增大，故实际为 row = y - dy。
# J L S T Z 共用一套表
KICKS_JLSTZ: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}

# I 块独有
KICKS_I: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}


def kicks_for(piece_type: str, from_rot: int, to_rot: int) -> tuple[tuple[int, int], ...]:
    """返回 SRS 踢墙的候选偏移序列（首项恒为 (0, 0)），见 03 §2.3。"""
    if piece_type == "O":
        return ((0, 0),)
    table = KICKS_I if piece_type == "I" else KICKS_JLSTZ
    return table[(from_rot, to_rot)]


@dataclass
class Piece:
    """活动方块：类型、朝向（0/R/2/L = 0/1/2/3）、矩阵左上角坐标。"""

    type: str
    rot: int = 0
    x: int = 0
    y: int = 0

    @property
    def matrix(self) -> tuple[tuple[int, ...], ...]:
        """当前旋转态的填充矩阵（查 03 §2.2 的 ROTATIONS）。"""
        return ROTATIONS[self.type][self.rot]

    def cells(self, dx: int = 0, dy: int = 0, rot: int | None = None) -> list[tuple[int, int]]:
        """返回全部填充格的 (row, col)；dx/dy 为试探偏移，dy 向上为正（见 03 §2.4）。"""
        matrix = ROTATIONS[self.type][self.rot if rot is None else rot]
        ox, oy = self.x + dx, self.y - dy     # dy 向上为正 → 行号相减
        return [(oy + r, ox + c)
                for r, row in enumerate(matrix)
                for c, value in enumerate(row) if value]


class SevenBag:
    """7-bag 随机生成器：每袋含七种各一个，洗牌后逐个发放，袋空再洗下一袋。"""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self._bag: list[str] = []

    def next(self) -> str:
        """取下一个方块类型；一袋发完再洗下一袋（见 03 §2.5）。"""
        if not self._bag:
            self._bag = list(PIECE_TYPES)
            self.rng.shuffle(self._bag)
        return self._bag.pop()
