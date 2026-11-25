# -*- coding: utf-8 -*-
"""渲染器：棋盘、面板、菜单、设置、排行榜、昵称与浮层绘制，以及按钮命中检测。

分层：表现层。
允许依赖：pygame、config、resource、pieces（形状预览）、theme、game 的只读快照。
禁止依赖：修改 board / game 内部状态。

实现依据：03 详细设计 §6.2、§6.5；布局依据 01 需求规格 §5.1。
"""

from __future__ import annotations

import pygame

from ..config import (ACCENT, BG_COLOR, BOARD_BG, BORDER_COLOR, CARD_BG, CELL, COLS,
                      GRID_COLOR, HIDDEN_ROWS, ROWS, TEXT_MAIN, TEXT_SUB)
from ..pieces import ROTATIONS
from ..resource import resource_path
from .effects import FLASH_MS, LAND_MS
from .theme import (CARD_RECTS, CONFIRM_CANCEL, CONFIRM_CARD, CONFIRM_OK, ENTRY_CARD,
                    ENTRY_NAME_BOX, FONT_SIZES, HINT_COL_XS, HINT_ITEMS, HINT_ROW_YS,
                    HOLD_BOX, HOLD_CENTER, MENU_BUTTON_LABELS, MENU_BUTTON_RECTS, NEXT_BOX,
                    NEXT_FIRST_CENTER, NEXT_STEP, OVERLAY_BUTTON_RECTS, OVERLAY_CARD,
                    OVERLAY_OVER_LABELS, OVERLAY_PAUSE_LABELS, RANKING_BACK,
                    RANKING_FIRST_Y, RANKING_HEADER_Y, RANKING_ROW_H, SETTINGS_BACK,
                    SETTINGS_MINUS_X, SETTINGS_PLUS_X, SETTINGS_ROW_H, SETTINGS_ROW_YS,
                    board_rect, cell_rect, piece_rgb)

_SPRITE_ORDER = ("I", "J", "L", "O", "S", "T", "Z", "ghost")


class Renderer:
    """全部界面绘制入口；字体、背景与贴图在构造时加载并缓存。"""

    def __init__(self, font_path: str) -> None:
        self.font_path = font_path
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._mini: dict[tuple[str, int], pygame.Surface] = {}
        self.bg_game = self._load_bg("bg_game.png")
        self.bg_menu = self._load_bg("bg_menu.png")
        self.blocks = self._load_blocks()
        self.logo = self._load_logo()
        # 浮层命中检测依赖最近一次绘制的浮层类型
        self.overlay_mode: str | None = None
        self.can_record = False

    # —— 资源与字体 ——
    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            try:
                loaded = pygame.font.Font(self.font_path, size)
            except (pygame.error, FileNotFoundError):
                loaded = pygame.font.SysFont("microsoftyahei", size)
            loaded.set_bold(bold)
            self._fonts[key] = loaded
        return self._fonts[key]

    @staticmethod
    def _load_bg(name: str) -> pygame.Surface:
        try:
            image = pygame.image.load(resource_path("assets", "images", name)).convert()
        except (pygame.error, FileNotFoundError):
            image = pygame.Surface((720, 800))
            image.fill(BG_COLOR)
        if image.get_size() != (720, 800):
            image = pygame.transform.smoothscale(image, (720, 800))
        return image

    @staticmethod
    def _load_logo() -> pygame.Surface | None:
        try:
            image = pygame.image.load(resource_path("assets", "images", "logo.png")).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None
        return pygame.transform.smoothscale(image, (140, 140))

    @staticmethod
    def _load_blocks() -> dict[str, pygame.Surface]:
        """贴图带按 8 格切分并缩放到 CELL；资源缺失时退回纯色块。"""
        frames: dict[str, pygame.Surface] = {}
        try:
            sheet = pygame.image.load(
                resource_path("assets", "images", "blocks.png")).convert_alpha()
            for i, key in enumerate(_SPRITE_ORDER):
                sub = sheet.subsurface((i * 64, 0, 64, 64))
                frame = pygame.transform.smoothscale(sub, (CELL, CELL))
                if key == "ghost":
                    frame.set_alpha(90)
                frames[key] = frame
        except (pygame.error, FileNotFoundError, ValueError):
            for key in _SPRITE_ORDER:
                frame = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                color = (120, 130, 160, 90) if key == "ghost" else (*piece_rgb(key), 255)
                pygame.draw.rect(frame, color, (0, 0, CELL, CELL), border_radius=6)
                frames[key] = frame
        return frames

    def _mini_block(self, kind: str, size: int) -> pygame.Surface:
        key = (kind, size)
        if key not in self._mini:
            self._mini[key] = pygame.transform.smoothscale(self.blocks[kind], (size, size))
        return self._mini[key]

    # —— 基础绘制 ——
    def _text(self, surf: pygame.Surface, text: str, size: int, color: tuple[int, int, int],
              pos: tuple[int, int], anchor: str = "topleft", bold: bool = False) -> None:
        image = self.font(size, bold).render(text, True, color)
        rect = image.get_rect(**{anchor: pos})
        surf.blit(image, rect)

    def _text_fit(self, surf: pygame.Surface, text: str, size: int,
                  color: tuple[int, int, int], center: tuple[int, int],
                  max_width: int, bold: bool = True) -> None:
        """按卡片宽度自动降字号，避免大分数溢出。"""
        while size > 12 and self.font(size, bold).size(text)[0] > max_width:
            size -= 2
        self._text(surf, text, size, color, center, anchor="center", bold=bold)

    @staticmethod
    def _card(surf: pygame.Surface, rect: tuple[int, int, int, int], radius: int = 14,
              fill: tuple[int, int, int] = CARD_BG, alpha: int = 190,
              border: tuple[int, int, int] = BORDER_COLOR, border_alpha: int = 110,
              width: int = 2) -> None:
        layer = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*fill, alpha), layer.get_rect(), border_radius=radius)
        pygame.draw.rect(layer, (*border, border_alpha), layer.get_rect(),
                         width=width, border_radius=radius)
        surf.blit(layer, (rect[0], rect[1]))

    def _button(self, surf: pygame.Surface, rect: tuple[int, int, int, int], label: str) -> None:
        self._card(surf, rect, radius=12, alpha=210, border_alpha=170)
        self._text(surf, label, FONT_SIZES["button"], TEXT_MAIN,
                   (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2), anchor="center")

    def draw_block(self, surf: pygame.Surface, row: int, col: int, kind: str,
                   offset: tuple[int, int] = (0, 0)) -> None:
        """绘制单格；完全落在棋盘之外的隐藏行直接跳过。"""
        x, y, w, h = cell_rect(row, col)
        rect = pygame.Rect(x + offset[0], y + offset[1], w, h)
        board = pygame.Rect(board_rect())
        if not rect.colliderect(board):
            return
        surf.blit(self.blocks[kind], rect)

    # —— 游戏界面 ——
    def draw_game(self, surf: pygame.Surface, snap, effects, settings) -> None:
        """绘制游戏界面：背景 → 棋盘 → 方块 → HUD → 面板 → 提示。"""
        surf.blit(self.bg_game, (0, 0))
        shake = effects.offset() if effects is not None else (0, 0)
        self._draw_board_panel(surf)
        self._draw_locked(surf, snap, shake)
        self._draw_ghost(surf, snap, settings, shake)
        self._draw_piece(surf, snap, shake)
        self._draw_flashes(surf, effects, shake)
        self._draw_land_marks(surf, effects, shake)
        self._draw_header(surf, snap)
        self._draw_panel(surf, snap)

    def _draw_board_panel(self, surf: pygame.Surface) -> None:
        rect = board_rect()
        self._card(surf, rect, radius=16, fill=BOARD_BG, alpha=190, border_alpha=150, width=2)
        inner = pygame.Rect(rect)
        for c in range(1, COLS):
            x = inner.x + c * CELL
            pygame.draw.line(surf, GRID_COLOR, (x, inner.y), (x, inner.bottom - 1))
        for r in range(1, 20):
            y = inner.y + r * CELL
            pygame.draw.line(surf, GRID_COLOR, (inner.x, y), (inner.right - 1, y))

    def _draw_locked(self, surf: pygame.Surface, snap, shake: tuple[int, int]) -> None:
        for r in range(HIDDEN_ROWS, ROWS):
            for c, kind in enumerate(snap.grid[r]):
                if kind:
                    self.draw_block(surf, r, c, str(kind), shake)

    def _draw_ghost(self, surf: pygame.Surface, snap, settings, shake: tuple[int, int]) -> None:
        if not settings.ghost or not snap.ghost_cells or not snap.piece_cells:
            return
        current = set(snap.piece_cells)
        for r, c in snap.ghost_cells:
            if (r, c) not in current:
                self.draw_block(surf, r, c, "ghost", shake)

    def _draw_piece(self, surf: pygame.Surface, snap, shake: tuple[int, int]) -> None:
        if snap.piece_type is None:
            return
        for r, c in snap.piece_cells:
            if r >= HIDDEN_ROWS:
                self.draw_block(surf, r, c, snap.piece_type, shake)

    @staticmethod
    def _draw_flashes(surf: pygame.Surface, effects, shake: tuple[int, int]) -> None:
        if effects is None:
            return
        board = pygame.Rect(board_rect())
        for rows, elapsed in effects.flashes:
            alpha = int(170 * max(0.0, 1.0 - elapsed / FLASH_MS))
            if alpha <= 0:
                continue
            layer = pygame.Surface((COLS * CELL, CELL), pygame.SRCALPHA)
            layer.fill((255, 255, 255, alpha))
            for row in rows:
                top = board.y + (row - HIDDEN_ROWS) * CELL
                surf.blit(layer, (board.x + shake[0], top + shake[1]))

    @staticmethod
    def _draw_land_marks(surf: pygame.Surface, effects, shake: tuple[int, int]) -> None:
        if effects is None:
            return
        for cells, elapsed in effects.land_rects:
            alpha = int(200 * max(0.0, 1.0 - elapsed / LAND_MS))
            if alpha <= 0:
                continue
            layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.rect(layer, (*ACCENT, alpha), layer.get_rect(), width=2)
            for r, c in cells:
                if r < HIDDEN_ROWS:
                    continue
                x, y, _, _ = cell_rect(r, c)
                surf.blit(layer, (x + shake[0], y + shake[1]))

    def _draw_header(self, surf: pygame.Surface, snap) -> None:
        self._text(surf, "俄罗斯方块", FONT_SIZES["title"], TEXT_MAIN, (56, 26), bold=True)
        self._text(surf, "TETRIS  ·  CLASSIC", FONT_SIZES["small"], ACCENT, (58, 78))
        labels = ("分数", "等级", "行数")
        values = (str(snap.score), str(snap.level), str(snap.lines))
        for rect, label, value in zip(CARD_RECTS, labels, values):
            self._card(surf, rect, radius=12, alpha=200)
            self._text(surf, label, FONT_SIZES["card_label"], TEXT_SUB,
                       (rect[0] + rect[2] // 2, rect[1] + 12), anchor="midtop")
            self._text_fit(surf, value, FONT_SIZES["value"], TEXT_MAIN,
                           (rect[0] + rect[2] // 2, rect[1] + 46), rect[2] - 12)

    def _draw_panel(self, surf: pygame.Surface, snap) -> None:
        panel = (384, 136, 280, 600)
        self._card(surf, panel, radius=16, alpha=190, border_alpha=110)
        self._text(surf, "暂存", FONT_SIZES["panel_title"], ACCENT, (404, 150), bold=True)
        if snap.hold_type:
            self._draw_preview(surf, snap.hold_type, HOLD_CENTER, 22,
                               dim=snap.hold_used)
        else:
            self._text(surf, "—", FONT_SIZES["panel_value"], TEXT_SUB, HOLD_CENTER,
                       anchor="center")

        pygame.draw.line(surf, GRID_COLOR, (404, HOLD_BOX[1] + HOLD_BOX[3] + 2),
                         (644, HOLD_BOX[1] + HOLD_BOX[3] + 2))
        self._text(surf, "下一个", FONT_SIZES["panel_title"], ACCENT, (404, 316), bold=True)
        for i, piece_type in enumerate(snap.next_types):
            center = (NEXT_FIRST_CENTER[0], NEXT_FIRST_CENTER[1] + i * NEXT_STEP)
            self._draw_preview(surf, piece_type, center, 32)

        pygame.draw.line(surf, GRID_COLOR, (404, NEXT_BOX[1] + NEXT_BOX[3] + 2),
                         (644, NEXT_BOX[1] + NEXT_BOX[3] + 2))
        self._text(surf, "操作提示", FONT_SIZES["panel_title"], ACCENT, (404, 490), bold=True)
        for row, y in enumerate(HINT_ROW_YS):
            for col, (key, desc) in enumerate(HINT_ITEMS[row]):
                self._draw_key_hint(surf, key, desc, HINT_COL_XS[col], y)

    def _draw_key_hint(self, surf: pygame.Surface, key: str, desc: str,
                       x: int, y: int) -> None:
        """按键胶囊 + 中文说明，用于右侧操作提示的两列网格。"""
        key_surface = self.font(FONT_SIZES["small"], True).render(key, True, ACCENT)
        chip = pygame.Surface((key_surface.get_width() + 14, 22), pygame.SRCALPHA)
        chip_rect = chip.get_rect()
        pygame.draw.rect(chip, (12, 34, 50, 200), chip_rect, border_radius=6)
        pygame.draw.rect(chip, (0, 229, 255, 70), chip_rect, width=1, border_radius=6)
        surf.blit(chip, (x, y))
        surf.blit(key_surface, (x + 7, y + (22 - key_surface.get_height()) // 2))
        self._text(surf, desc, FONT_SIZES["small"], TEXT_SUB,
                   (x + chip.get_width() + 8, y + 4))

    def _draw_preview(self, surf: pygame.Surface, piece_type: str,
                      center: tuple[int, int], cell: int,
                      dim: bool = False, alpha: int = 255) -> None:
        matrix = ROTATIONS[piece_type][0]
        cells = [(r, c) for r, row in enumerate(matrix)
                 for c, value in enumerate(row) if value]
        min_r = min(r for r, _ in cells)
        max_r = max(r for r, _ in cells)
        min_c = min(c for _, c in cells)
        max_c = max(c for _, c in cells)
        origin_x = center[0] - (max_c - min_c + 1) * cell // 2 - min_c * cell
        origin_y = center[1] - (max_r - min_r + 1) * cell // 2 - min_r * cell

        frame = self._mini_block(piece_type, cell)
        if dim or alpha < 255:
            frame = frame.copy()
            frame.set_alpha(110 if dim else alpha)
        for r, c in cells:
            surf.blit(frame, (origin_x + c * cell, origin_y + r * cell))

    # —— 整屏页面 ——
    def draw_menu(self, surf: pygame.Surface, best: int) -> None:
        surf.blit(self.bg_menu, (0, 0))
        if self.logo is not None:
            surf.blit(self.logo, self.logo.get_rect(center=(360, 140)))
        self._text(surf, "俄罗斯方块", FONT_SIZES["logo"], TEXT_MAIN, (360, 222),
                   anchor="center", bold=True)
        self._text(surf, "T E T R I S", FONT_SIZES["card_label"], ACCENT, (360, 272),
                   anchor="center")
        self._text(surf, f"最高分   {best}", FONT_SIZES["panel_value"], TEXT_MAIN,
                   (360, 318), anchor="center")
        for rect, label in zip(MENU_BUTTON_RECTS, MENU_BUTTON_LABELS):
            self._button(surf, rect, label)
        self._text(surf, "F11 全屏切换   ·   成绩自动保存至本机", FONT_SIZES["small"],
                   TEXT_SUB, (360, 730), anchor="midtop")

    @staticmethod
    def _dim(surf: pygame.Surface, alpha: int = 90) -> None:
        """压暗背景图，保证文字在星空贴图上仍有足够对比度。"""
        layer = pygame.Surface((720, 800), pygame.SRCALPHA)
        layer.fill((0, 0, 0, alpha))
        surf.blit(layer, (0, 0))

    def draw_settings(self, surf: pygame.Surface, settings) -> None:
        surf.blit(self.bg_menu, (0, 0))
        self._dim(surf)
        self._text(surf, "设置", FONT_SIZES["title"], TEXT_MAIN, (56, 44), bold=True)
        self._text(surf, "ESC 返回主菜单", FONT_SIZES["small"], TEXT_SUB, (58, 96))

        rows = (
            ("音乐音量", str(settings.music)),
            ("音效音量", str(settings.sfx)),
            ("幽灵方块", "开" if settings.ghost else "关"),
            ("显示模式", "全屏" if settings.fullscreen else "窗口"),
        )
        for i, (label, value) in enumerate(rows):
            y = SETTINGS_ROW_YS[i]
            self._card(surf, (56, y, 608, SETTINGS_ROW_H), radius=12, alpha=190)
            self._text(surf, label, FONT_SIZES["panel_value"], TEXT_MAIN, (84, y + 20))
            if i < 2:
                self._volume_button(surf, (SETTINGS_MINUS_X, y + 12, 40, 40), "−")
                self._volume_button(surf, (SETTINGS_PLUS_X, y + 12, 40, 40), "+")
                self._text(surf, value, FONT_SIZES["panel_value"], ACCENT,
                           (555, y + SETTINGS_ROW_H // 2), anchor="center")
            else:
                self._text(surf, value, FONT_SIZES["panel_value"], ACCENT,
                           (636, y + SETTINGS_ROW_H // 2), anchor="midright")
        self._button(surf, SETTINGS_BACK, "返回主菜单")

    def _volume_button(self, surf: pygame.Surface, rect: tuple[int, int, int, int],
                       label: str) -> None:
        self._card(surf, rect, radius=8, alpha=230, border_alpha=190, width=1)
        self._text(surf, label, FONT_SIZES["panel_value"], TEXT_MAIN,
                   (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2), anchor="center")

    def draw_ranking(self, surf: pygame.Surface, records: list) -> None:
        surf.blit(self.bg_menu, (0, 0))
        self._dim(surf)
        self._text(surf, "排行榜", FONT_SIZES["title"], TEXT_MAIN, (56, 44), bold=True)
        self._text(surf, "本机前 10 名   ·   同分先到先得", FONT_SIZES["small"],
                   TEXT_SUB, (58, 96))
        self._card(surf, (56, 124, 608, 524), radius=16, alpha=215, border_alpha=110)

        headers = (("名次", 90), ("昵称", 130), ("分数", 390), ("等级", 455),
                   ("行数", 535), ("日期", 615))
        for text, x in headers:
            anchor = "midleft" if text == "昵称" else "center"
            self._text(surf, text, FONT_SIZES["card_label"], TEXT_SUB,
                       (x, RANKING_HEADER_Y), anchor=anchor)

        if not records:
            self._text(surf, "暂无记录", FONT_SIZES["logo"], TEXT_SUB, (360, 380),
                       anchor="center")
        for i, record in enumerate(records[:10]):
            y = RANKING_FIRST_Y + i * RANKING_ROW_H
            if i % 2 == 0:
                layer = pygame.Surface((608, RANKING_ROW_H - 6), pygame.SRCALPHA)
                layer.fill((*CARD_BG, 130))
                surf.blit(layer, (56, y))
            mid = y + (RANKING_ROW_H - 6) // 2
            name = record.name if len(record.name) <= 8 else record.name[:8] + "…"
            self._text(surf, str(i + 1), FONT_SIZES["panel_value"], ACCENT, (90, mid),
                       anchor="center")
            self._text(surf, name, FONT_SIZES["panel_value"], TEXT_MAIN, (130, mid),
                       anchor="midleft")
            self._text(surf, str(record.score), FONT_SIZES["panel_value"], TEXT_MAIN,
                       (390, mid), anchor="center")
            self._text(surf, str(record.level), FONT_SIZES["card_label"], TEXT_SUB,
                       (455, mid), anchor="center")
            self._text(surf, str(record.lines), FONT_SIZES["card_label"], TEXT_SUB,
                       (535, mid), anchor="center")
            self._text(surf, record.time or "—", FONT_SIZES["card_label"], TEXT_SUB,
                       (615, mid), anchor="center")

        self._button(surf, RANKING_BACK, "返回主菜单")

    def draw_entry(self, surf: pygame.Surface, score: int, level: int, lines: int,
                   name: str, preedit: str = "") -> None:
        surf.blit(self.bg_game, (0, 0))
        scrim = pygame.Surface((720, 800), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 180))
        surf.blit(scrim, (0, 0))

        self._card(surf, ENTRY_CARD, radius=18, alpha=225, border_alpha=190)
        self._text(surf, "登记成绩", FONT_SIZES["overlay_title"], TEXT_MAIN, (360, 238),
                   anchor="midtop", bold=True)
        self._text(surf, f"分数 {score}      等级 {level}      行数 {lines}",
                   FONT_SIZES["panel_value"], TEXT_SUB, (360, 304), anchor="center")
        self._text(surf, "昵称", FONT_SIZES["card_label"], TEXT_SUB,
                   (ENTRY_NAME_BOX[0], 342))
        self._card(surf, ENTRY_NAME_BOX, radius=10, alpha=235, border_alpha=200, width=2)
        self._text(surf, name, FONT_SIZES["panel_value"], TEXT_MAIN,
                   (ENTRY_NAME_BOX[0] + 16, ENTRY_NAME_BOX[1] + 18))

        if preedit:
            name_width = self.font(FONT_SIZES["panel_value"], False).size(name)[0]
            x = ENTRY_NAME_BOX[0] + 16 + name_width + 4
            self._text(surf, preedit, FONT_SIZES["panel_value"], ACCENT, (x, 388))
            preedit_width = self.font(FONT_SIZES["panel_value"], False).size(preedit)[0]
            pygame.draw.line(surf, ACCENT, (x, 414), (x + preedit_width, 414), 2)

        self._text(surf, "Enter 保存     ESC 跳过     Backspace 删除", FONT_SIZES["small"],
                   TEXT_SUB, (360, 520), anchor="midtop")

    # —— 浮层 ——
    def draw_pause(self, surf: pygame.Surface) -> None:
        self.overlay_mode = "pause"
        self.can_record = False
        self._draw_overlay_frame(surf, "已暂停", "按 P 或 ESC 继续游戏")

    def draw_gameover(self, surf: pygame.Surface, snap, can_record: bool) -> None:
        self.overlay_mode = "gameover"
        self.can_record = can_record
        self._draw_overlay_frame(surf, "游戏结束",
                                 f"分数 {snap.score}   等级 {snap.level}   行数 {snap.lines}")

    def _draw_overlay_frame(self, surf: pygame.Surface, title: str, subtitle: str) -> None:
        scrim = pygame.Surface((720, 800), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 190))
        surf.blit(scrim, (0, 0))
        self._card(surf, OVERLAY_CARD, radius=18, alpha=235, border_alpha=190)
        self._text(surf, title, FONT_SIZES["overlay_title"], TEXT_MAIN,
                   (360, OVERLAY_CARD[1] + 46), anchor="midtop", bold=True)
        self._text(surf, subtitle, FONT_SIZES["card_label"], TEXT_SUB, (360, 340),
                   anchor="center")

        if self.overlay_mode == "pause":
            labels = OVERLAY_PAUSE_LABELS
        else:
            labels = OVERLAY_OVER_LABELS
        for i, (rect, label) in enumerate(zip(OVERLAY_BUTTON_RECTS, labels)):
            if self.overlay_mode == "gameover" and i == 1 and not self.can_record:
                continue
            self._button(surf, rect, label)

    def draw_confirm(self, surf: pygame.Surface, title: str, message: str,
                     ok_label: str = "确定", cancel_label: str = "取消") -> None:
        """二次确认弹窗：退出与重开共用。"""
        scrim = pygame.Surface((720, 800), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 190))
        surf.blit(scrim, (0, 0))
        self._card(surf, CONFIRM_CARD, radius=18, alpha=235, border_alpha=190)
        self._text(surf, title, FONT_SIZES["overlay_title"], TEXT_MAIN, (360, 296),
                   anchor="midtop", bold=True)
        self._text(surf, message, FONT_SIZES["card_label"], TEXT_SUB, (360, 368),
                   anchor="center")
        self._button(surf, CONFIRM_CANCEL, cancel_label)
        self._button(surf, CONFIRM_OK, ok_label)

    # —— 命中检测 ——
    @staticmethod
    def hit_menu(pos: tuple[int, int]) -> str | None:
        """返回 start / ranking / settings / exit；未命中返回 None。"""
        labels = ("start", "ranking", "settings", "exit")
        for rect, label in zip(MENU_BUTTON_RECTS, labels):
            if pygame.Rect(rect).collidepoint(pos):
                return label
        return None

    @staticmethod
    def hit_settings(pos: tuple[int, int]) -> str | None:
        """返回 music_inc/music_dec/sfx_inc/sfx_dec/ghost/display/back。"""
        if pygame.Rect(SETTINGS_BACK).collidepoint(pos):
            return "back"
        for i, y in enumerate(SETTINGS_ROW_YS):
            if not pygame.Rect(56, y, 608, SETTINGS_ROW_H).collidepoint(pos):
                continue
            if i < 2:
                prefix = "music" if i == 0 else "sfx"
                if pygame.Rect(SETTINGS_MINUS_X, y + 12, 40, 40).collidepoint(pos):
                    return f"{prefix}_dec"
                if pygame.Rect(SETTINGS_PLUS_X, y + 12, 40, 40).collidepoint(pos):
                    return f"{prefix}_inc"
                return None
            return "ghost" if i == 2 else "display"
        return None

    def hit_overlay(self, pos: tuple[int, int]) -> str | None:
        """返回 resume/restart/menu/record；未命中返回 None。"""
        if self.overlay_mode == "pause":
            labels = ("resume", "restart", "menu")
        else:
            labels = ("restart", "record", "menu")
        for rect, label in zip(OVERLAY_BUTTON_RECTS, labels):
            if label == "record" and not self.can_record:
                continue
            if pygame.Rect(rect).collidepoint(pos):
                return label
        return None

    @staticmethod
    def hit_confirm(pos: tuple[int, int]) -> str | None:
        """返回 confirm / cancel；二次确认弹窗专用。"""
        if pygame.Rect(CONFIRM_CANCEL).collidepoint(pos):
            return "cancel"
        if pygame.Rect(CONFIRM_OK).collidepoint(pos):
            return "confirm"
        return None

    @staticmethod
    def hit_back(pos: tuple[int, int]) -> bool:
        """排行榜「返回」按钮命中检测。"""
        return pygame.Rect(RANKING_BACK).collidepoint(pos)
