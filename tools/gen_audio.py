# -*- coding: utf-8 -*-
"""生成俄罗斯方块项目的全部音频素材（原创 8-bit 风格，无版权风险）。

用法：
    python tools/gen_audio.py

输出目录：assets/audio/
    bgm_main.wav      主菜单/游戏循环 BGM（约 30 秒，可循环）
    sfx_move.wav      左右移动
    sfx_rotate.wav    旋转
    sfx_lock.wav      方块锁定
    sfx_clear.wav     消 1～3 行
    sfx_tetris.wav    一次消 4 行
    sfx_levelup.wav   升级
    sfx_gameover.wav  游戏结束
    sfx_menu.wav      菜单点击 / 光标移动
    sfx_pause.wav     暂停 / 继续

全部为 22050 Hz、16 bit、单声道 PCM，pygame.mixer 可直接加载。
"""

import math
import os
import wave

import numpy as np

SR = 22050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "audio")


# ---------------------------------------------------------------- 基础波形
def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def sine(freq: float, dur: float, amp: float = 1.0, phase: float = 0.0) -> np.ndarray:
    return amp * np.sin(2 * math.pi * freq * _t(dur) + phase)


def square(freq: float, dur: float, amp: float = 1.0) -> np.ndarray:
    """简单的带限处理：方波 + 少量三次谐波，听感比裸方波柔和。"""
    t = _t(dur)
    s = np.sign(np.sin(2 * math.pi * freq * t))
    return amp * (0.8 * s + 0.2 * np.sin(2 * math.pi * freq * 3 * t))


def triangle(freq: float, dur: float, amp: float = 1.0) -> np.ndarray:
    t = _t(dur)
    return amp * (2 / math.pi) * np.arcsin(np.sin(2 * math.pi * freq * t))


def noise(dur: float, amp: float = 1.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return amp * rng.uniform(-1.0, 1.0, int(SR * dur))


def lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    """一阶 IIR 低通，alpha 越小越闷。"""
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def env(n: int, attack: float = 0.004, release: float = 0.6, curve: float = 2.0) -> np.ndarray:
    """攻击-衰减包络，attack/release 为占比。"""
    a = max(1, int(n * attack))
    r = max(1, int(n * release))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    tail = np.linspace(1, 0, r) ** curve
    e[-r:] = np.minimum(e[-r:], tail)
    return e


def place(buf: np.ndarray, signal: np.ndarray, start: float, amp: float = 1.0) -> None:
    i = int(start * SR)
    n = min(len(signal), len(buf) - i)
    if n > 0:
        buf[i:i + n] += signal[:n] * amp


def midi(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def write(name: str, data: np.ndarray) -> None:
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767).astype(np.int16)
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"{name}: {len(data) / SR:.2f}s  {os.path.getsize(path) / 1024:.0f} KB")


# ---------------------------------------------------------------- 音效
def sfx_move() -> np.ndarray:
    n = int(SR * 0.06)
    buf = np.zeros(n)
    dur = 0.05
    s = lowpass(noise(dur, 1.0, seed=1), 0.45) * env(int(SR * dur), release=0.8)
    place(buf, s, 0.0, 0.35)
    place(buf, sine(950, dur, 1.0) * env(int(SR * dur), release=0.85), 0.0, 0.18)
    return buf


def sfx_rotate() -> np.ndarray:
    n = int(SR * 0.1)
    buf = np.zeros(n)
    dur = 0.045
    e = env(int(SR * dur), release=0.9)
    place(buf, sine(720, dur) * e, 0.00, 0.30)
    place(buf, sine(1080, dur) * e, 0.04, 0.22)
    return buf


def sfx_lock() -> np.ndarray:
    n = int(SR * 0.14)
    buf = np.zeros(n)
    dur = 0.13
    e = env(int(SR * dur), release=0.75, curve=2.5)
    place(buf, sine(150, dur, 0.8) * e, 0.0, 0.55)
    place(buf, lowpass(noise(dur, 1.0, seed=2), 0.20) * e, 0.0, 0.35)
    return buf


def _arp(notes: list, step: float, wave_fn=square, amp: float = 0.5, tail: float = 0.25) -> np.ndarray:
    total = step * len(notes) + tail
    buf = np.zeros(int(SR * total))
    for i, note in enumerate(notes):
        dur = min(step * 1.5, total - i * step)
        e = env(int(SR * dur), release=0.7)
        place(buf, wave_fn(midi(note), dur) * e, i * step, amp)
    return buf


def sfx_clear() -> np.ndarray:
    return _arp([72, 76, 79, 84], 0.055, amp=0.45, tail=0.12)


def sfx_tetris() -> np.ndarray:
    buf = _arp([72, 76, 79, 84, 88], 0.06, amp=0.45, tail=0.3)
    # 叠加一层高频闪烁，强调「四行」
    sparkle = sine(1760, 0.5) * env(int(SR * 0.5), release=0.9)
    place(buf, sparkle, 0.22, 0.12)
    return buf


def sfx_levelup() -> np.ndarray:
    return _arp([67, 72, 76, 79, 84], 0.07, amp=0.5, tail=0.2)


def sfx_gameover() -> np.ndarray:
    total = 1.6
    buf = np.zeros(int(SR * total))
    for i, note in enumerate([72, 67, 64, 60]):
        dur = 0.5
        e = env(int(SR * dur), attack=0.02, release=0.85, curve=1.6)
        place(buf, triangle(midi(note), dur) * e, i * 0.36, 0.42)
    place(buf, sine(midi(48), 1.2) * env(int(SR * 1.2), release=0.9), 0.4, 0.22)
    return buf


def sfx_menu() -> np.ndarray:
    dur = 0.05
    n = int(SR * dur)
    return sine(1200, dur) * env(n, release=0.9) * 0.25


def sfx_pause() -> np.ndarray:
    buf = np.zeros(int(SR * 0.3))
    e = env(int(SR * 0.09), release=0.8)
    place(buf, sine(680, 0.09) * e, 0.0, 0.25)
    place(buf, sine(460, 0.09) * e, 0.1, 0.25)
    return buf


# ---------------------------------------------------------------- BGM
def bgm_main() -> np.ndarray:
    """8 小节一循环、重复 5 次的原创芯片音乐。

    和声进行 Am - F - C - G；旋律为 A 小调五声音阶的分解音型；
    低音用三角波，鼓组用噪声与短正弦合成。
    """
    bpm = 160
    beat = 60 / bpm
    bar = beat * 4
    bars = 20
    total = bars * bar
    buf = np.zeros(int(SR * total) + SR)

    prog = [
        (57, [57, 60, 64, 67]),   # Am
        (53, [53, 57, 60, 64]),   # F
        (48, [48, 52, 55, 60]),   # C
        (55, [55, 59, 62, 67]),   # G
    ]
    melody = [
        [69, 72, 76, 72, 79, 76, 72, 69],
        [69, 72, 77, 72, 81, 77, 72, 69],
        [72, 76, 79, 76, 84, 79, 76, 72],
        [71, 74, 79, 74, 83, 79, 74, 71],
    ]

    for b in range(bars):
        chord_root, chord = prog[b % 4]
        mel = melody[b % 4]
        t0 = b * bar

        # 鼓：底鼓（第 1、3 拍）+ 军鼓（第 2、4 拍）+ 踩镲（反拍）
        for k in range(4):
            if k % 2 == 0:
                kick = sine(60, 0.12) * env(int(SR * 0.12), release=0.7) * 0.5
                place(buf, lowpass(noise(0.02, 1.0, seed=10 + b), 0.3), t0 + k * beat, 0.15)
                place(buf, kick, t0 + k * beat, 0.35)
            else:
                sn = noise(0.06, 1.0, seed=20 + b + k) * env(int(SR * 0.06), release=0.85) * 0.25
                place(buf, sn, t0 + k * beat, 0.30)
            hat = noise(0.02, 1.0, seed=30 + b) * env(int(SR * 0.02), release=0.9)
            place(buf, hat, t0 + k * beat + beat / 2, 0.12)

        # 低音：每拍一个根音，第 3 拍换到五度
        for k in range(4):
            root = chord_root if k != 2 else chord_root + 7
            place(buf, triangle(midi(root), beat * 0.9) *
                  env(int(SR * beat * 0.9), release=0.8), t0 + k * beat, 0.20)

        # 旋律：8 个八分音符，高八度叠加轻音
        step = beat / 2
        for i, note in enumerate(mel):
            dur = step * 1.1
            e = env(int(SR * dur), attack=0.01, release=0.75)
            place(buf, square(midi(note), dur) * e, t0 + i * step, 0.22)
            place(buf, sine(midi(note), dur) * e, t0 + i * step, 0.06)

        # 和声铺底：每小节一个和弦的三音
        for note in chord[1:]:
            place(buf, sine(midi(note), bar * 0.9) *
                  env(int(SR * bar * 0.9), attack=0.1, release=0.9), t0, 0.035)

    # 首尾各 0.3 秒淡入淡出，循环时不会出现「咔哒」声
    fade = int(SR * 0.3)
    buf[:fade] *= np.linspace(0, 1, fade)
    buf[-fade:] *= np.linspace(1, 0, fade)
    buf *= 0.9 / max(1e-6, np.abs(buf).max())
    return buf


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write("bgm_main.wav", bgm_main())
    write("sfx_move.wav", sfx_move())
    write("sfx_rotate.wav", sfx_rotate())
    write("sfx_lock.wav", sfx_lock())
    write("sfx_clear.wav", sfx_clear())
    write("sfx_tetris.wav", sfx_tetris())
    write("sfx_levelup.wav", sfx_levelup())
    write("sfx_gameover.wav", sfx_gameover())
    write("sfx_menu.wav", sfx_menu())
    write("sfx_pause.wav", sfx_pause())
