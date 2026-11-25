# -*- coding: utf-8 -*-
"""程序入口：初始化、事件分发、主循环、界面流转与退出存档。

实现依据：03 详细设计 §7。界面状态机：
    screen: menu / game / settings / ranking / entry
    dialog: None / pause / restart / exit
约束：只有 window 关闭（QUIT）、Alt+F4 与主菜单「退出」会离开游戏；
      P / ESC 只负责暂停与继续；退出前必定 save_profile()。
"""

from __future__ import annotations

import ctypes
import sys
import traceback

import pygame

from src import storage
from src.audio import Audio
from src.config import (APP_NAME, ARR_MS, DAS_MS, FPS, MAX_NAME_LEN, SOFT_DROP_MS)
from src.game import Action, Game, GameEvent, GameState
from src.resource import resource_path
from src.ui.display import Display
from src.ui.effects import Effects
from src.ui.renderer import Renderer
from src.ui.theme import ENTRY_NAME_BOX

KEY_ACTIONS = {
    pygame.K_LEFT: Action.MOVE_LEFT, pygame.K_a: Action.MOVE_LEFT,
    pygame.K_RIGHT: Action.MOVE_RIGHT, pygame.K_d: Action.MOVE_RIGHT,
    pygame.K_DOWN: Action.SOFT_DROP, pygame.K_s: Action.SOFT_DROP,
    pygame.K_SPACE: Action.HARD_DROP,
    pygame.K_x: Action.ROTATE_CW, pygame.K_UP: Action.ROTATE_CW,
    pygame.K_z: Action.ROTATE_CCW,
    pygame.K_c: Action.HOLD,
    pygame.K_p: Action.PAUSE,
    pygame.K_r: Action.RESTART,       # 仅 GAME_OVER 状态生效：再来一局
}

LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)

SOUND_EVENTS = ("move", "rotate", "lock", "clear", "tetris", "levelup", "gameover")


def enable_dpi_awareness() -> None:
    """在 pygame.init() 之前声明 DPI 感知；失败静默（Win7 用旧 API 兜底）。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class App:
    """把主循环、界面流转与输入分发收在一起，避免在函数间传十几个参数。"""

    def __init__(self) -> None:
        enable_dpi_awareness()
        pygame.init()
        pygame.display.set_caption(APP_NAME)
        try:
            pygame.display.set_icon(pygame.image.load(
                resource_path("assets", "icon.png")))
        except (pygame.error, FileNotFoundError):
            pass

        self.profile = storage.load_profile()
        self.display = Display(self.profile.settings.fullscreen)
        self.renderer = Renderer(resource_path("assets", "fonts", "msyh.ttc"))
        self.audio = Audio(self.profile.settings.music, self.profile.settings.sfx)
        self.audio.play_music()

        self.game = Game(best=self.profile.best)
        self.effects = Effects()
        self.clock = pygame.time.Clock()

        self.screen = "menu"
        self.dialog: str | None = None          # None / pause / restart / exit
        self.dialog_back: str | None = None     # 取消确认弹窗后回到的浮层
        self.entry_back = "game"                # 昵称登记完成后的去向
        self.entry_exit = False                 # 登记是否为退出前的最后一步
        self.recorded = False                   # 本局是否已登记成绩
        self.name = ""
        self.preedit = ""

        self.held = {"left": False, "right": False, "down": False}
        self.das_timer = {"left": 0.0, "right": 0.0}
        self.arr_timer = {"left": 0.0, "right": 0.0}
        self.soft_timer = 0.0

    # —— 主循环 ——
    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                self._process_event(event)
            self._update(dt)
            self._draw()

    def _update(self, dt: float) -> None:
        if (self.screen == "game" and self.dialog is None
                and self.game.state is GameState.PLAYING):
            for direction in ("left", "right"):
                if not self.held[direction]:
                    continue
                self.das_timer[direction] += dt
                if self.das_timer[direction] >= DAS_MS:
                    self.arr_timer[direction] += dt
                    while self.arr_timer[direction] >= ARR_MS:
                        self.arr_timer[direction] -= ARR_MS
                        self.game.handle(Action.MOVE_LEFT if direction == "left"
                                         else Action.MOVE_RIGHT)
            if self.held["down"]:
                self.soft_timer += dt
                while self.soft_timer >= SOFT_DROP_MS:
                    self.soft_timer -= SOFT_DROP_MS
                    self.game.handle(Action.SOFT_DROP)
            self.game.update(dt)

        self.effects.update(dt)
        for game_event in self.game.take_events():
            self._handle_game_event(game_event)

    def _draw(self) -> None:
        canvas = self.display.canvas
        snapshot = self.game.snapshot()
        if self.screen == "menu":
            self.renderer.draw_menu(canvas, self.profile.best)
        elif self.screen == "game":
            self.renderer.draw_game(canvas, snapshot, self.effects, self.profile.settings)
            if self.dialog == "pause":
                self.renderer.draw_pause(canvas)
            elif self.dialog is None and self.game.state is GameState.GAME_OVER:
                self.renderer.draw_gameover(canvas, snapshot, self._can_record())
        elif self.screen == "settings":
            self.renderer.draw_settings(canvas, self.profile.settings)
        elif self.screen == "ranking":
            self.renderer.draw_ranking(canvas, self.profile.leaderboard)
        elif self.screen == "entry":
            self.renderer.draw_entry(canvas, self.game.score, self.game.level,
                                     self.game.lines, self.name, self.preedit)

        if self.dialog == "restart":
            self.renderer.draw_confirm(canvas, "重新开始？", "当前进度会丢失",
                                       "重新开始", "取消")
        elif self.dialog == "exit":
            self.renderer.draw_confirm(canvas, "退出游戏？", "进度与设置将自动保存",
                                       "退出", "取消")
        self.display.present()

    # —— 事件分发 ——
    def _process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self._request_exit("pause" if self.game.state is GameState.PAUSED else None)
        elif event.type == pygame.KEYDOWN:
            self._on_keydown(event)
        elif event.type == pygame.KEYUP:
            self._on_keyup(event)
        elif event.type == pygame.TEXTINPUT and self.screen == "entry" and self.dialog is None:
            text = "".join(ch for ch in event.text
                           if ch.isprintable() and ch not in "\r\n\t")
            room = MAX_NAME_LEN - len(self.name)
            if room > 0:
                self.name += text[:room]
        elif event.type == pygame.TEXTEDITING and self.screen == "entry" and self.dialog is None:
            self.preedit = event.text
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.display.to_canvas(event.pos)
            if pos is not None:
                self._on_click(pos)

    def _on_keydown(self, event: pygame.event.Event) -> None:
        key = event.key
        if key == pygame.K_F11:
            self._toggle_fullscreen()
            return
        if key == pygame.K_ESCAPE:
            self._on_escape()
            return
        if self.screen == "entry":
            if self.dialog is None:
                if key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._finish_entry(True)
            return

        action = KEY_ACTIONS.get(key)
        if action is None:
            return
        if action is Action.PAUSE:
            if self.dialog in (None, "pause"):
                self._toggle_pause()
            return
        if self.screen != "game" or self.dialog is not None:
            return
        if action is Action.RESTART:
            if self.game.state is GameState.GAME_OVER:
                self._start_game()
            return
        if self.game.state is not GameState.PLAYING:
            return

        self.game.handle(action)
        if key in LEFT_KEYS:
            self._press("left")
        elif key in RIGHT_KEYS:
            self._press("right")
        elif key in DOWN_KEYS:
            self.held["down"] = True
            self.soft_timer = 0.0

    def _on_keyup(self, event: pygame.event.Event) -> None:
        if event.key in LEFT_KEYS:
            self.held["left"] = False
        elif event.key in RIGHT_KEYS:
            self.held["right"] = False
        elif event.key in DOWN_KEYS:
            self.held["down"] = False

    def _on_escape(self) -> None:
        if self.dialog in ("restart", "exit"):
            self.dialog = self.dialog_back
            return
        if self.dialog == "pause":
            self._toggle_pause()
            return
        if self.screen == "game":
            if self.game.state in (GameState.PLAYING, GameState.PAUSED):
                self._toggle_pause()
        elif self.screen in ("settings", "ranking"):
            self.screen = "menu"
        elif self.screen == "entry":
            self._finish_entry(False)

    def _on_click(self, pos: tuple[int, int]) -> None:
        if self.dialog == "pause":
            self._click_pause(self.renderer.hit_overlay(pos))
        elif self.dialog in ("restart", "exit"):
            self._click_confirm(self.renderer.hit_confirm(pos))
        elif self.screen == "menu":
            self._click_menu(self.renderer.hit_menu(pos))
        elif self.screen == "game" and self.game.state is GameState.GAME_OVER:
            self._click_gameover(self.renderer.hit_overlay(pos))
        elif self.screen == "settings":
            self._click_settings(self.renderer.hit_settings(pos))
        elif self.screen == "ranking" and self.renderer.hit_back(pos):
            self.audio.play("menu")
            self.screen = "menu"

    def _click_menu(self, hit: str | None) -> None:
        if hit is None:
            return
        self.audio.play("menu")
        if hit == "start":
            self._start_game()
        elif hit == "ranking":
            self.screen = "ranking"
        elif hit == "settings":
            self.screen = "settings"
        elif hit == "exit":
            self._request_exit(None)

    def _click_pause(self, hit: str | None) -> None:
        if hit is None:
            return
        self.audio.play("menu")
        if hit == "resume":
            self._toggle_pause()
        elif hit == "restart":
            self.dialog = "restart"
            self.dialog_back = "pause"
        elif hit == "menu":
            self._leave_to_menu()

    def _click_gameover(self, hit: str | None) -> None:
        if hit is None:
            return
        self.audio.play("menu")
        if hit == "restart":
            self._start_game()
        elif hit == "record":
            self._start_entry("game")
        elif hit == "menu":
            self._leave_to_menu()

    def _click_confirm(self, hit: str | None) -> None:
        if hit == "cancel":
            self.dialog = self.dialog_back
            self.audio.play("menu")
        elif hit == "confirm":
            if self.dialog == "restart":
                self._start_game()
            else:
                if self._pending_record():
                    self._start_entry("game", exit_after=True)
                else:
                    self._quit()

    def _click_settings(self, hit: str | None) -> None:
        if hit is None:
            return
        self.audio.play("menu")
        settings = self.profile.settings
        if hit == "back":
            self.screen = "menu"
        elif hit == "ghost":
            settings.ghost = not settings.ghost
        elif hit == "display":
            self._toggle_fullscreen()
        elif hit.startswith("music"):
            settings.music = self._step_volume(settings.music, hit.endswith("inc"))
            self.audio.set_music_volume(settings.music)
        elif hit.startswith("sfx"):
            settings.sfx = self._step_volume(settings.sfx, hit.endswith("inc"))
            self.audio.set_sfx_volume(settings.sfx)

    # —— 状态切换 ——
    def _start_game(self) -> None:
        self.game.reset()
        self.effects = Effects()
        self.recorded = False
        self.screen = "game"
        self.dialog = None
        self._reset_repeat()
        self.audio.resume()

    def _toggle_pause(self) -> None:
        if self.screen != "game" or self.game.state is GameState.GAME_OVER:
            return
        if self.game.state is GameState.PLAYING:
            self.game.handle(Action.PAUSE)
            self.dialog = "pause"
            self.audio.pause()
            self._reset_repeat()
        elif self.game.state is GameState.PAUSED:
            self.game.handle(Action.PAUSE)
            self.dialog = None
            self.audio.resume()

    def _leave_to_menu(self) -> None:
        """中途返回主菜单：可进榜且未登记时先登记。"""
        if self._pending_record():
            self._start_entry("menu")
            return
        self.profile.best = max(self.profile.best, self.game.best, self.game.score)
        self.screen = "menu"
        self.dialog = None
        self._reset_repeat()
        self.audio.resume()

    def _start_entry(self, back: str, exit_after: bool = False) -> None:
        self.entry_back = back
        self.entry_exit = exit_after
        self.screen = "entry"
        self.dialog = None
        self.name = ""
        self.preedit = ""
        self._reset_repeat()
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(
            self.display.canvas_rect_to_screen(ENTRY_NAME_BOX))

    def _finish_entry(self, save: bool) -> None:
        pygame.key.stop_text_input()
        if save:
            storage.insert_record(self.profile, self.name, self.game.score,
                                  self.game.level, self.game.lines)
            self.recorded = True
            self.profile.best = max(self.profile.best, self.game.score)
            storage.save_profile(self.profile)
            self.audio.play("clear")
        self.preedit = ""
        if self.entry_exit:
            self._quit()
            return
        self.screen = "menu" if self.entry_back == "menu" else "game"
        self.dialog = None
        if self.screen == "menu":
            self.profile.best = max(self.profile.best, self.game.best, self.game.score)
            self.audio.resume()

    def _request_exit(self, back: str | None) -> None:
        self.dialog_back = back
        self.dialog = "exit"
        self._reset_repeat()

    def _quit(self) -> None:
        self.profile.best = max(self.profile.best, self.game.best, self.game.score)
        storage.save_profile(self.profile)
        pygame.quit()
        sys.exit(0)

    # —— 辅助 ——
    def _can_record(self) -> bool:
        return not self.recorded and storage.qualifies(self.profile, self.game.score)

    def _pending_record(self) -> bool:
        return self.screen == "game" and self._can_record()

    def _press(self, direction: str) -> None:
        self.held[direction] = True
        self.das_timer[direction] = 0.0
        self.arr_timer[direction] = 0.0

    def _reset_repeat(self) -> None:
        self.held = {"left": False, "right": False, "down": False}
        self.das_timer = {"left": 0.0, "right": 0.0}
        self.arr_timer = {"left": 0.0, "right": 0.0}
        self.soft_timer = 0.0

    def _toggle_fullscreen(self) -> None:
        self.display.apply_mode(not self.display.fullscreen)
        self.profile.settings.fullscreen = self.display.fullscreen
        if self.screen == "entry":
            pygame.key.set_text_input_rect(
                self.display.canvas_rect_to_screen(ENTRY_NAME_BOX))

    @staticmethod
    def _step_volume(value: int, increase: bool) -> int:
        return max(0, min(100, value + (5 if increase else -5)))

    def _handle_game_event(self, event: GameEvent) -> None:
        """模型事件 → 音效与特效的唯一入口。"""
        if event.kind in SOUND_EVENTS:
            self.audio.play(event.kind)
        if event.kind in ("clear", "tetris") and event.data:
            self.effects.on_clear(event.data["rows"], event.data["count"])
        elif event.kind == "harddrop" and event.data:
            self.effects.on_land(event.data["cells"])


def _write_crash_log(exc: BaseException) -> None:
    """未捕获异常写入 %APPDATA%\\TetrisDesktop\\crash.log，不依赖 stdout。"""
    try:
        storage.APP_DIR.mkdir(parents=True, exist_ok=True)
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        (storage.APP_DIR / "crash.log").write_text(text, encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    try:
        App().run()
    except SystemExit:
        raise
    except Exception as exc:                    # noqa: BLE001 - 兜底写日志后继续抛出
        _write_crash_log(exc)
        raise


if __name__ == "__main__":
    main()
