# -*- coding: utf-8 -*-
"""一局游戏的状态机：重力、锁定延迟、计分、暂存/预览、结束判定。

分层：应用层。
允许依赖：pieces、board、config。
禁止依赖：pygame、ui、audio、storage（音效由 main.py 消费事件后播放）。

实现依据：03 详细设计 §4。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .board import Board
from .config import (HARD_DROP_PER_CELL, HIDDEN_ROWS, LINE_SCORES, LOCK_DELAY_MS,
                    LOCK_RESET_MAX, NEXT_COUNT, SOFT_DROP_PER_CELL, gravity_ms,
                    level_from_lines)
from .pieces import SPAWN_X, SPAWN_Y, Piece, SevenBag, kicks_for

if TYPE_CHECKING:
    from random import Random


class GameState(Enum):
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class Action(Enum):
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    SOFT_DROP = auto()
    HARD_DROP = auto()
    ROTATE_CW = auto()
    ROTATE_CCW = auto()
    HOLD = auto()
    PAUSE = auto()
    RESTART = auto()                # 仅 GAME_OVER 状态生效，对应 R 键


@dataclass
class GameEvent:
    """模型层事件，由 main.py 取走并翻译成音效与特效，不参与规则计算。"""

    kind: str                       # move/rotate/reject/lock/clear/tetris/levelup/hold/harddrop/gameover
    data: dict | None = None


@dataclass(frozen=True)
class Snapshot:
    """渲染层只读快照；grid 为深拷贝，表现层无法反向改坏模型。"""

    grid: list
    score: int
    best: int
    level: int
    lines: int
    state: GameState
    piece_type: str | None
    piece_rot: int
    piece_x: int
    piece_y: int
    piece_cells: tuple
    ghost_cells: tuple
    next_types: tuple
    hold_type: str | None
    hold_used: bool


class Game:
    """一局对战的全部可变状态。"""

    def __init__(self, best: int = 0, rng: Random | None = None) -> None:
        self.board = Board()
        self.bag = SevenBag(rng)
        self.best = best
        self.events: list[GameEvent] = []
        # 全部实例属性先在 __init__ 中声明，reset() 只负责重置取值
        self.next_queue: list[str] = []
        self.hold_type: str | None = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.state = GameState.PLAYING
        self.gravity_acc = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lock_active = False
        self.piece: Piece | None = None
        self.reset()

    def reset(self) -> None:
        """重置对局（保留最高分）。"""
        self.board.reset()
        self.next_queue: list[str] = [self.bag.next() for _ in range(NEXT_COUNT)]
        self.hold_type: str | None = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.state = GameState.PLAYING
        self.gravity_acc = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lock_active = False
        self.piece: Piece | None = None
        self.spawn_next()

    # —— 主循环推进 ——
    def update(self, dt_ms: float) -> None:
        """按毫秒推进重力与锁定倒计时；掉帧不改变总下落速度。"""
        if self.state is not GameState.PLAYING or self.piece is None:
            return

        # 重力：按毫秒累计
        self.gravity_acc += dt_ms
        interval = gravity_ms(self.level)
        while self.gravity_acc >= interval:
            self.gravity_acc -= interval
            if not self._try_down():
                break

        # 锁定倒计时（只在贴底时运行）
        if self.lock_active:
            self.lock_timer += dt_ms
            if self.lock_timer >= LOCK_DELAY_MS:
                self._lock()

    def handle(self, action: Action) -> None:
        """处理一个抽象动作（不接收 pygame 键值）。"""
        if action is Action.PAUSE:
            self.state = (GameState.PAUSED if self.state is GameState.PLAYING
                          else GameState.PLAYING if self.state is GameState.PAUSED
                          else self.state)
            return
        if action is Action.RESTART:
            if self.state is GameState.GAME_OVER:
                self.reset()
            return
        if self.state is not GameState.PLAYING or self.piece is None:
            return

        if action is Action.MOVE_LEFT:
            self._shift(-1)
        elif action is Action.MOVE_RIGHT:
            self._shift(1)
        elif action is Action.SOFT_DROP:
            if not self.board.collides(self.piece.cells(dy=-1)):
                self.piece.y += 1
                self.score += SOFT_DROP_PER_CELL
                self.gravity_acc = 0.0
                self._touch_lock()
                self.events.append(GameEvent("move"))
        elif action is Action.HARD_DROP:
            self._hard_drop()
        elif action in (Action.ROTATE_CW, Action.ROTATE_CCW):
            self._rotate(1 if action is Action.ROTATE_CW else -1)
        elif action is Action.HOLD:
            self._hold()

    def take_events(self) -> list[GameEvent]:
        """取走并清空事件队列；main.py 每帧调用一次，用于播放音效与特效。"""
        events, self.events = self.events, []
        return events

    # —— 生成与结束判定 ——
    def spawn_next(self) -> None:
        """从预览队列取块，并补充队尾。"""
        piece_type = self.next_queue.pop(0)
        self.next_queue.append(self.bag.next())
        self.spawn(piece_type)

    def spawn(self, piece_type: str) -> None:
        """以生成态放置方块并检测顶出；顶出即结束。"""
        piece = Piece(piece_type, rot=0, x=SPAWN_X[piece_type], y=SPAWN_Y)
        self.piece = piece
        self.gravity_acc = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lock_active = False
        if self.board.collides(piece.cells()):
            self.piece = None
            self.state = GameState.GAME_OVER
            self.events.append(GameEvent("gameover"))

    def snapshot(self) -> Snapshot:
        """导出只读快照，供渲染层绘制。"""
        ghost: tuple[tuple[int, int], ...] = ()
        if self.piece is not None:
            drop = 0
            while not self.board.collides(self.piece.cells(dy=-(drop + 1))):
                drop += 1
            ghost = tuple((r + drop, c) for r, c in self.piece.cells())
        return Snapshot(
            grid=[row[:] for row in self.board.grid],
            score=self.score, best=self.best, level=self.level, lines=self.lines,
            state=self.state,
            piece_type=None if self.piece is None else self.piece.type,
            piece_rot=0 if self.piece is None else self.piece.rot,
            piece_x=0 if self.piece is None else self.piece.x,
            piece_y=0 if self.piece is None else self.piece.y,
            piece_cells=() if self.piece is None else tuple(self.piece.cells()),
            ghost_cells=ghost,
            next_types=tuple(self.next_queue), hold_type=self.hold_type,
            hold_used=self.hold_used,
        )

    # —— 内部规则 ——
    def _try_down(self) -> bool:
        """尝试下落一格；贴底时进入锁定倒计时。"""
        if self.piece is None or self.board.collides(self.piece.cells(dy=-1)):
            self.lock_active = True
            return False
        self.piece.y += 1
        self.gravity_acc = 0.0          # 向下移动后重置累计，避免攒够格数一次掉多格
        self.lock_active = False
        self.lock_resets = 0            # 方块重新获得下落后，重置次数清零
        return True

    def _touch_lock(self) -> None:
        """成功移动/旋转后重置锁定计时，但有次数上限。"""
        if self.lock_active and self.lock_resets < LOCK_RESET_MAX:
            self.lock_timer = 0.0
            self.lock_resets += 1

    def _shift(self, dx: int) -> None:
        if self.piece is None:
            return
        if self.board.collides(self.piece.cells(dx=dx)):
            self.events.append(GameEvent("reject"))
            return
        self.piece.x += dx
        self._touch_lock()
        self.events.append(GameEvent("move"))

    def _rotate(self, direction: int) -> None:
        """按 SRS 踢墙表尝试旋转；全部候选均冲突时拒绝。"""
        if self.piece is None:
            return
        from_rot = self.piece.rot
        to_rot = (from_rot + direction) % 4
        for dx, dy in kicks_for(self.piece.type, from_rot, to_rot):
            if not self.board.collides(self.piece.cells(dx=dx, dy=dy, rot=to_rot)):
                self.piece.x += dx
                self.piece.y -= dy               # 偏移量的 dy 向上为正
                self.piece.rot = to_rot
                self._touch_lock()
                self.events.append(GameEvent("rotate"))
                return
        self.events.append(GameEvent("reject"))

    def _hard_drop(self) -> None:
        if self.piece is None:
            return
        dist = 0
        while not self.board.collides(self.piece.cells(dy=-1)):
            self.piece.y += 1
            dist += 1
        self.score += dist * HARD_DROP_PER_CELL
        self.best = max(self.best, self.score)
        self.lock_active = False
        self.events.append(GameEvent("harddrop", {"dist": dist, "cells": self.piece.cells()}))
        self._lock()

    def _lock(self) -> None:
        """锁定当前方块 → 消行计分 → 升级 → 生成下一块。"""
        piece = self.piece
        if piece is None:
            return
        cells = piece.cells()
        self.board.lock(piece)

        # 锁出：整块仍处于隐藏缓冲区
        if all(r < HIDDEN_ROWS for r, _ in cells):
            self.piece = None
            self.state = GameState.GAME_OVER
            self.events.append(GameEvent("gameover"))
            return

        self.events.append(GameEvent("lock"))
        rows = self.board.full_rows()
        if rows:
            count = len(rows)
            self.score += LINE_SCORES[count] * self.level
            self.best = max(self.best, self.score)
            self.lines += count
            self.board.clear_rows(rows)
            self.events.append(GameEvent("tetris" if count == 4 else "clear",
                                         {"rows": rows, "count": count}))
            new_level = level_from_lines(self.lines)
            if new_level > self.level:
                self.level = new_level
                self.events.append(GameEvent("levelup", {"level": new_level}))

        self.hold_used = False
        self.spawn_next()               # 内部会检测顶出

    def _hold(self) -> None:
        """暂存/交换当前方块；每次落地前只能使用一次。"""
        if self.hold_used or self.piece is None:
            return
        current = self.piece.type
        if self.hold_type is None:
            self.hold_type = current
            self.spawn_next()                # 首次暂存：取队首新块，队尾补 bag
        else:
            swap = self.hold_type
            self.hold_type = current
            self.spawn(swap)                 # 交换：槽内方块从生成位置重新落下
        self.hold_used = True
        self.events.append(GameEvent("hold"))
