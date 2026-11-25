# -*- coding: utf-8 -*-
"""音频：9 个短音效与循环 BGM，支持音量分组与无设备降级。

分层：基础设施（表现层使用）。
允许依赖：pygame、resource。
禁止依赖：game / board / storage / ui。

实现依据：03 详细设计 §5.3。
约定：必须在 pygame.display 初始化之前构造，避免先占用 44.1 kHz 立体声设备。
"""

from __future__ import annotations

import pygame

from .resource import resource_path

SFX_FILES: dict[str, str] = {
    "move": "sfx_move.wav",
    "rotate": "sfx_rotate.wav",
    "lock": "sfx_lock.wav",
    "clear": "sfx_clear.wav",
    "tetris": "sfx_tetris.wav",
    "levelup": "sfx_levelup.wav",
    "gameover": "sfx_gameover.wav",
    "menu": "sfx_menu.wav",
    "pause": "sfx_pause.wav",
}


class Audio:
    """音效与 BGM 的统一入口；任何设备/资源异常都降级为静音，不向上抛出。"""

    def __init__(self, music_volume: int = 70, sfx_volume: int = 80) -> None:
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_volume = max(0, min(100, music_volume))
        self.sfx_volume = max(0, min(100, sfx_volume))

        try:
            # pygame.init() 可能已用默认 44.1 kHz 立体声初始化 mixer；
            # 先退出再按低延迟参数重建，确保设备参数符合设计
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
            # 单声道 22.05 kHz、512 缓冲：延迟低，且避免与显示初始化抢占设备
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.available = True
        except pygame.error:
            return                                  # 无声卡：后续调用全部空操作

        for name, filename in SFX_FILES.items():
            try:
                self.sounds[name] = pygame.mixer.Sound(
                    resource_path("assets", "audio", filename))
            except (pygame.error, FileNotFoundError):
                continue                            # 单个音效缺失不影响其他

        try:
            pygame.mixer.music.load(resource_path("assets", "audio", "bgm_main.wav"))
        except (pygame.error, FileNotFoundError):
            self.music_volume = 0                   # BGM 缺失时视为音乐关闭
        pygame.mixer.music.set_volume(self.music_volume / 100)

    def play(self, name: str) -> None:
        """播放一次短音效；通道占满时静默丢弃（不排队）。"""
        if not self.available:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        sound.set_volume(self.sfx_volume / 100)
        sound.play()

    def play_music(self) -> None:
        """无限循环 BGM；音乐音量为 0 时不启动。"""
        if self.available and self.music_volume > 0:
            pygame.mixer.music.play(-1)

    def set_music_volume(self, volume: int) -> None:
        """调整 BGM 音量并立即生效；归零时暂停，恢复时继续。"""
        self.music_volume = max(0, min(100, volume))
        if not self.available:
            return
        pygame.mixer.music.set_volume(self.music_volume / 100)
        if self.music_volume == 0:
            pygame.mixer.music.pause()
        else:
            pygame.mixer.music.unpause()

    def set_sfx_volume(self, volume: int) -> None:
        """调整音效音量；下一次 play() 时应用。"""
        self.sfx_volume = max(0, min(100, volume))

    def pause(self) -> None:
        """暂停 BGM（短音效自然结束）。"""
        if self.available:
            pygame.mixer.music.pause()

    def resume(self) -> None:
        """恢复 BGM；音量为 0 时保持静音。"""
        if self.available and self.music_volume > 0:
            pygame.mixer.music.unpause()
