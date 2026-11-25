# -*- coding: utf-8 -*-
"""pieces.py 单元测试：四态一致性、SRS 踢墙表、7-bag 公平性与坐标语义。

对应用例编号：05 测试计划 §2.1 UT-P-01～UT-P-12。
本模块不依赖 pygame，可无图形环境运行。
"""

from __future__ import annotations

import random

import pytest

# noinspection PyProtectedMember
from src.pieces import (KICKS_I, KICKS_JLSTZ, PIECE_TYPES, ROTATIONS, SHAPES,
                        Piece, SevenBag, _rotate_cw, kicks_for)

ALL_TRANSITIONS = {(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2), (3, 0), (0, 3)}


def test_all_rotations_have_four_cells():
    """UT-P-01：七种方块的所有 4 个状态都恰好有 4 个填充格。"""
    for name in PIECE_TYPES:
        for rot in range(4):
            cells = sum(sum(row) for row in ROTATIONS[name][rot])
            assert cells == 4, f"{name} rot={rot}"


def test_o_piece_never_changes():
    """UT-P-02：O 块的 4 个状态矩阵完全相同。"""
    assert len(set(ROTATIONS["O"])) == 1


def test_t_piece_states_differ():
    """UT-P-03：T 块的 4 个状态两两不同。"""
    assert len(set(ROTATIONS["T"])) == 4


def test_four_rotations_return_to_start():
    """UT-P-04：连续顺时针旋转 4 次回到原矩阵。"""
    for name in ("I", "T", "S"):
        matrix = SHAPES[name]
        rotated = matrix
        for _ in range(4):
            rotated = _rotate_cw(rotated)
        assert rotated == matrix


def test_kick_table_keys_complete():
    """UT-P-05：两套踢墙表都覆盖 8 个朝向转换。"""
    assert set(KICKS_JLSTZ) == ALL_TRANSITIONS
    assert set(KICKS_I) == ALL_TRANSITIONS


@pytest.mark.parametrize("name", ["J", "L", "S", "T", "Z", "I"])
def test_kick_tables_have_five_offsets(name):
    """UT-P-06/07：JLSTZ 与 I 的每个转换都有 5 个候选，且 (0, 0) 在首位。"""
    for from_rot, to_rot in ALL_TRANSITIONS:
        offsets = kicks_for(name, from_rot, to_rot)
        assert len(offsets) == 5
        assert offsets[0] == (0, 0)


def test_o_piece_has_single_kick():
    """UT-P-08：O 块任意旋转只尝试原位。"""
    assert kicks_for("O", 0, 1) == ((0, 0),)
    assert kicks_for("O", 2, 3) == ((0, 0),)


def test_bag_fairness_over_70_pieces():
    """UT-P-09：连续取 70 个方块，每种恰好 10 次。"""
    bag = SevenBag(random.Random(1))
    types = [bag.next() for _ in range(70)]
    for name in PIECE_TYPES:
        assert types.count(name) == 10


def test_bag_has_no_duplicate_in_one_bag():
    """UT-P-10：任意一袋内的 7 个方块互不重复。"""
    bag = SevenBag(random.Random(7))
    first = [bag.next() for _ in range(7)]
    assert sorted(first) == sorted(PIECE_TYPES)


def test_bag_reproducible_with_seed():
    """UT-P-11：注入相同随机种子时序列一致。"""
    bag1 = SevenBag(random.Random(42))
    seq1 = [bag1.next() for _ in range(14)]
    bag2 = SevenBag(random.Random(42))
    assert seq1 == [bag2.next() for _ in range(14)]


def test_piece_cells_dy_semantics():
    """UT-P-12：dy 向上为正，dy=-1 使所有行号 +1。"""
    piece = Piece("T", x=3, y=5)
    up = piece.cells()
    down = piece.cells(dy=-1)
    assert [(r + 1, c) for r, c in up] == down


def test_piece_cells_absolute_position():
    """坐标语义：O 块在 (x=4, y=2) 时占据 2×2 四格。"""
    assert Piece("O", x=4, y=2).cells() == [(2, 4), (2, 5), (3, 4), (3, 5)]


def test_piece_cells_use_rot_override():
    """试探朝向不改变原方块状态，只影响返回的格子。"""
    piece = Piece("T", x=3, y=3)
    cells_cw = piece.cells(rot=1)
    assert piece.rot == 0
    assert cells_cw == [(3, 4), (4, 4), (4, 5), (5, 4)]


def test_piece_matrix_follows_rotation():
    """matrix 属性返回当前朝向对应的矩阵。"""
    assert Piece("T", rot=2).matrix == ROTATIONS["T"][2]
