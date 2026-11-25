# -*- coding: utf-8 -*-
"""存档读写：最高分、设置与前 10 排行榜。

分层：基础设施。
允许依赖：标准库、config。
禁止依赖：pygame、ui、game。

存档位置：%APPDATA%\\TetrisDesktop\\save.json（禁止写入 exe 所在目录）。
实现依据：03 详细设计 §5.1。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import MAX_NAME_LEN, SAVE_DIR_NAME

MAX_RECORDS = 10
DEFAULT_NAME = "玩家"
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / SAVE_DIR_NAME
SAVE_FILE = APP_DIR / "save.json"


@dataclass
class Settings:
    fullscreen: bool = False
    music: int = 70
    sfx: int = 80
    ghost: bool = True


@dataclass
class Record:
    name: str
    score: int
    level: int = 1
    lines: int = 0
    time: str = ""                  # MM-DD HH:MM，缺失显示「—」


@dataclass
class Profile:
    best: int = 0
    settings: Settings = field(default_factory=Settings)
    leaderboard: list[Record] = field(default_factory=list)


def load_profile() -> Profile:
    """读取存档；文件缺失、解析失败或字段类型错误一律降级为默认 Profile。"""
    try:
        raw = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Profile()
    if not isinstance(raw, dict):
        return Profile()

    try:
        best = max(0, int(raw.get("best", 0)))
        settings = _parse_settings(raw.get("settings"))
        leaderboard = _parse_records(raw.get("leaderboard"))
    except (TypeError, ValueError):
        return Profile()
    return Profile(best=best, settings=settings, leaderboard=leaderboard)


def save_profile(profile: Profile) -> None:
    """原子写入存档（save.tmp + os.replace）；失败只降级不抛出。"""
    payload = {
        "best": int(profile.best),
        "settings": {
            "fullscreen": bool(profile.settings.fullscreen),
            "music": int(profile.settings.music),
            "sfx": int(profile.settings.sfx),
            "ghost": bool(profile.settings.ghost),
        },
        "leaderboard": [
            {"name": r.name, "score": int(r.score), "level": int(r.level),
             "lines": int(r.lines), "time": r.time}
            for r in profile.leaderboard[:MAX_RECORDS]
        ],
    }
    tmp = SAVE_FILE.with_suffix(".tmp")
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, SAVE_FILE)
    except OSError:
        pass                        # 磁盘只读/权限不足时不影响游戏继续


def qualifies(profile: Profile, score: int) -> bool:
    """判断该分数是否可进入前 10：0 分不入榜，满榜时须严格高于末位。"""
    if score <= 0:
        return False
    if len(profile.leaderboard) < MAX_RECORDS:
        return True
    return score > profile.leaderboard[-1].score


def insert_record(profile: Profile, name: str, score: int, level: int, lines: int) -> int | None:
    """插入一条成绩，返回 0 起名次；未入榜返回 None。同分先到先得（稳定）。"""
    if not qualifies(profile, score):
        return None

    index = len(profile.leaderboard)
    for i, record in enumerate(profile.leaderboard):
        if score > record.score:            # 严格大于才前置，同分排在已有记录之后
            index = i
            break
    if index >= MAX_RECORDS:
        return None

    clean_name = name.strip()[:MAX_NAME_LEN] or DEFAULT_NAME
    record = Record(
        name=clean_name,
        score=score,
        level=max(1, level),
        lines=max(0, lines),
        time=datetime.now().strftime("%m-%d %H:%M"),
    )
    profile.leaderboard.insert(index, record)
    del profile.leaderboard[MAX_RECORDS:]
    return index


# —— 反序列化辅助 ——
def _clamp_int(value: object, default: int, low: int, high: int) -> int:
    try:
        number = int(value)             # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _parse_settings(raw: object) -> Settings:
    if not isinstance(raw, dict):
        return Settings()
    return Settings(
        fullscreen=raw.get("fullscreen") is True,
        music=_clamp_int(raw.get("music"), 70, 0, 100),
        sfx=_clamp_int(raw.get("sfx"), 80, 0, 100),
        ghost=raw.get("ghost") is not False,
    )


def _parse_records(raw: object) -> list[Record]:
    if not isinstance(raw, list):
        return []
    records: list[Record] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            score = int(item.get("score", 0))
        except (TypeError, ValueError):
            continue
        if score <= 0:
            continue
        name = item.get("name")
        name = (name.strip() if isinstance(name, str) else DEFAULT_NAME)[:MAX_NAME_LEN] or DEFAULT_NAME
        records.append(Record(
            name=name,
            score=score,
            level=max(1, _clamp_int(item.get("level"), 1, 1, 99)),
            lines=max(0, _clamp_int(item.get("lines"), 0, 0, 10 ** 6)),
            time=item["time"] if isinstance(item.get("time"), str) else "",
        ))
    return records[:MAX_RECORDS]
