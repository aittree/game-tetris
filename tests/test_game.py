# -*- coding: utf-8 -*-
"""game.py 单元测试：重力、锁定延迟、消行计分、暂存与结束判定。

对应用例编号：05 测试计划 §2.3 UT-G-01～UT-G-13。
全部用例不依赖 pygame。
"""

from __future__ import annotations

import random

from src.config import COLS, LOCK_RESET_MAX
from src.game import Action, Game, GameState
from src.pieces import SPAWN_X, Piece


def new_game(seed: int = 1) -> Game:
    """创建带固定种子的对局，保证预览队列可复现。"""
    return Game(best=0, rng=random.Random(seed))


def bottom_game() -> Game:
    """构造一个已贴底、正在锁定倒计时的 O 块对局。"""
    game = new_game()
    game.piece = Piece("O", x=SPAWN_X["O"], y=20)
    game.lock_active = True
    return game


def kinds(game: Game) -> list[str]:
    return [event.kind for event in game.events]


def test_gravity_drops_one_cell_per_800ms():
    """UT-G-01：1 级重力 800 ms 恰好下落 1 格。"""
    game = new_game()
    piece = game.piece
    assert piece is not None
    y0 = piece.y
    game.update(800)
    assert game.piece is not None and game.piece.y == y0 + 1


def test_gravity_accumulates_without_multi_drop():
    """UT-G-02：分 40 次推进共 4000 ms，合计下落 5 格。"""
    game = new_game()
    piece = game.piece
    assert piece is not None
    y0 = piece.y
    for _ in range(40):
        game.update(100)
    assert game.piece is not None and game.piece.y == y0 + 5


def test_lock_after_500ms_at_bottom():
    """UT-G-03：贴底 500 ms 后锁定并生成下一块。"""
    game = bottom_game()
    game.update(500)

    assert "lock" in kinds(game)
    assert game.piece is not None
    assert game.state is GameState.PLAYING
    assert game.board.visible_count() == 4


def test_move_resets_lock_timer():
    """UT-G-04：贴底后移动会重置锁定计时，时长从移动后重算。"""
    game = bottom_game()
    game.update(400)
    timer_before = game.lock_timer
    game.handle(Action.MOVE_LEFT)
    timer_after_move = game.lock_timer
    resets_after_move = game.lock_resets
    game.update(500)

    # 合并为单个断言：避免 IDE 依据前一条断言判定后续代码不可达
    result = (timer_before, timer_after_move, resets_after_move,
              "lock" in kinds(game))
    assert result == (400, 0, 1, True)


def test_lock_reset_is_capped():
    """UT-G-05：贴底后连续移动，锁定延迟重置不超过 15 次。"""
    game = bottom_game()
    max_resets = 0
    locked_at = None

    for i in range(200):
        game.update(30)
        max_resets = max(max_resets, game.lock_resets)
        if "lock" in kinds(game):
            locked_at = i
            break
        game.handle(Action.MOVE_LEFT if i % 2 == 0 else Action.MOVE_RIGHT)

    assert max_resets == LOCK_RESET_MAX
    assert locked_at is not None and locked_at < 100


def test_single_line_clear_and_score():
    """UT-G-06：填满 1 行后硬降，lines 与得分均正确。"""
    game = new_game()
    game.board.load_from(["." * COLS] * 21 + ["IIIIIIIII."])
    game.piece = Piece("I", rot=1, x=7, y=0)

    game.handle(Action.HARD_DROP)

    assert game.lines == 1
    assert game.score == 18 * 2 + 100     # 硬降 18 格 ×2 + 单行 100×1 级


def test_tetris_clear_scores_800():
    """UT-G-07：同列缺口填满 4 行，触发 tetris 事件并计 800 分。"""
    game = new_game()
    game.board.load_from(["." * COLS] * 18 + ["IIIIIIIII."] * 4)
    game.piece = Piece("I", rot=1, x=7, y=0)

    game.handle(Action.HARD_DROP)

    assert game.lines == 4
    assert game.score == 18 * 2 + 800
    assert "tetris" in kinds(game)


def test_level_up_after_ten_lines():
    """UT-G-08：累计 9 行后再消 1 行升到 2 级并触发 levelup。"""
    game = new_game()
    game.lines = 9
    game.board.load_from(["." * COLS] * 21 + ["IIIIIIIII."])
    game.piece = Piece("I", rot=1, x=7, y=0)

    game.handle(Action.HARD_DROP)

    assert game.lines == 10
    assert game.level == 2
    assert "levelup" in kinds(game)


def test_first_hold_takes_next_piece():
    """UT-G-09：首次暂存后槽内为原方块，并从队首取新块。"""
    game = new_game()
    piece = game.piece
    assert piece is not None
    first = piece.type
    queue_head = game.next_queue[0]

    game.handle(Action.HOLD)

    assert game.hold_type == first
    assert game.hold_used is True
    assert game.piece is not None and game.piece.type == queue_head


def test_second_hold_without_lock_has_no_effect():
    """UT-G-10：未落定再次暂存无效，方块与槽位都不变。"""
    game = new_game()
    game.handle(Action.HOLD)
    held = game.hold_type
    piece = game.piece
    assert piece is not None
    current = piece.type
    game.handle(Action.HOLD)

    assert game.hold_type == held
    assert game.piece is not None and game.piece.type == current
    assert kinds(game).count("hold") == 1


def test_hold_resets_after_lock():
    """UT-G-11：锁定后 hold_used 复位，可再次暂存并交换。"""
    game = new_game()
    piece = game.piece
    assert piece is not None
    first = piece.type
    game.handle(Action.HOLD)

    game.handle(Action.HARD_DROP)
    assert game.hold_used is False
    assert game.piece is not None
    spawned = game.piece.type

    game.handle(Action.HOLD)

    assert game.hold_type == spawned
    assert game.piece is not None and game.piece.type == first


def test_spawn_blocked_ends_game():
    """UT-G-12：生成位置被占时立即 GAME_OVER 且清空当前方块。"""
    game = new_game()
    game.board.load_from(["IIIIIIIIII"] + ["." * COLS] * 21)

    game.spawn("T")

    assert game.state is GameState.GAME_OVER
    assert game.piece is None
    assert "gameover" in kinds(game)


def test_lock_out_ends_game():
    """UT-G-13：方块整体锁定在隐藏行时判定锁出。"""
    game = new_game()
    game.piece = Piece("O", x=SPAWN_X["O"], y=0)

    game._lock()

    assert game.state is GameState.GAME_OVER
    assert game.piece is None
    assert game.board.visible_count() == 0
