# -*- coding: utf-8 -*-
"""board.py 单元测试：碰撞边界、锁定、消行与快照一致性。

对应用例编号：05 测试计划 §2.2 UT-B-01～UT-B-11。
"""

from __future__ import annotations

from src.board import EMPTY, Board
from src.config import COLS, HIDDEN_ROWS, ROWS
from src.pieces import Piece


def make_empty_rows() -> list[str]:
    """构造 22 行空地形字符画。"""
    return ["." * COLS for _ in range(ROWS)]


def test_empty_board_never_collides():
    """UT-B-01：空棋盘场内任意格均不冲突。"""
    board = Board()
    assert board.collides([(0, 0), (21, 9), (10, 5)]) is False


def test_horizontal_out_of_bounds_collides():
    """UT-B-02：列 -1 与列 10 越界。"""
    board = Board()
    assert board.collides([(10, -1)]) is True
    assert board.collides([(10, 10)]) is True


def test_below_bottom_collides():
    """UT-B-03：行 22 超出底部。"""
    assert Board().collides([(22, 3)]) is True


def test_above_top_is_free():
    """UT-B-04：行 -1 视为画面自由空间，允许踢墙顶出。"""
    assert Board().collides([(-1, 3), (-2, 4)]) is False


def test_occupied_cell_collides():
    """UT-B-05：已有地形格冲突。"""
    board = Board()
    board.grid[5][3] = "L"
    assert board.collides([(5, 3)]) is True
    assert board.collides([(5, 4)]) is False


def test_lock_writes_piece_type():
    """UT-B-06：锁定后对应格写入方块类型字母。"""
    board = Board()
    board.lock(Piece("O", x=4, y=2))
    assert board.grid[2][4] == "O"
    assert board.grid[2][5] == "O"
    assert board.grid[3][4] == "O"
    assert board.grid[3][5] == "O"
    assert board.grid[2][3] == EMPTY


def test_full_rows_reports_completed_rows():
    """UT-B-07：只返回已填满的行号。"""
    rows = make_empty_rows()
    rows[20] = "IIIIIIIIII"
    rows[21] = "IIIIIIIII."
    board = Board()
    board.load_from(rows)
    assert board.full_rows() == [20]


def test_clear_two_rows_shifts_down_and_pads_top():
    """UT-B-08：一次消 2 行后总行数不变、顶部补 2 空行、其余顺序不变。"""
    rows = make_empty_rows()
    rows[19] = "IIIIIIIII."
    rows[20] = "IIIIIIIIII"
    rows[21] = "IIIIIIIIII"
    board = Board()
    board.load_from(rows)

    board.clear_rows([20, 21])

    assert len(board.grid) == ROWS
    assert all(cell == EMPTY for row in board.grid[:2] for cell in row)
    assert board.grid[21][0] == "I"
    assert board.grid[21][9] == EMPTY
    assert board.grid[20][0] == EMPTY


def test_rows_are_contiguous_after_clear():
    """UT-B-09：消行后再次锁定，行号连续且无空洞。"""
    rows = make_empty_rows()
    rows[21] = "IIIIIIIIII"
    board = Board()
    board.load_from(rows)
    board.clear_rows([21])

    piece = Piece("O", x=4, y=20)
    assert board.collides(piece.cells()) is False
    board.lock(piece)

    assert len(board.grid) == ROWS
    assert board.grid[20][4] == "O"
    assert board.grid[21][4] == "O"
    assert board.grid[19][4] == EMPTY


def test_visible_count_ignores_hidden_rows():
    """UT-B-10：visible_count 只统计可见区（行 2～21）。"""
    board = Board()
    board.grid[0][0] = "T"
    board.grid[HIDDEN_ROWS - 1][1] = "T"
    assert board.visible_count() == 0

    board.grid[HIDDEN_ROWS][2] = "T"
    assert board.visible_count() == 1


def test_dump_matches_grid():
    """UT-B-11：dump 输出与 grid 内容一致。"""
    board = Board()
    board.grid[0][0] = "T"
    board.grid[21][9] = "I"

    lines = board.dump().splitlines()

    assert len(lines) == ROWS
    assert all(len(line) == COLS for line in lines)
    assert lines[0][0] == "T"
    assert lines[21][9] == "I"
    assert lines[10][9] == "."
    assert lines[0][1:] == "." * (COLS - 1)
