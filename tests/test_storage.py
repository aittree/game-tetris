# -*- coding: utf-8 -*-
"""storage.py 单元测试：存档容错、原子写、入榜规则与字段校验。

对应用例编号：05 测试计划 §2.4 UT-S-01～UT-S-07，另含两条字段校验补充用例。
全部用例使用 tmp_path，不触碰真实 %APPDATA%。
"""

from __future__ import annotations

import json

import pytest

from src import storage
from src.config import MAX_NAME_LEN
from src.storage import Profile, Record, Settings


@pytest.fixture
def save_file(tmp_path, monkeypatch):
    """把存档路径重定向到临时目录。"""
    monkeypatch.setattr(storage, "APP_DIR", tmp_path)
    target = tmp_path / "save.json"
    monkeypatch.setattr(storage, "SAVE_FILE", target)
    return target


def build_records(scores: list[int]) -> list[Record]:
    return [Record(name=f"P{i}", score=s) for i, s in enumerate(scores)]


def test_missing_file_returns_default_profile(save_file):
    """UT-S-01：存档不存在时返回默认 Profile。"""
    profile = storage.load_profile()

    assert profile == Profile()
    assert profile.settings.music == 70
    assert profile.settings.sfx == 80
    assert profile.settings.ghost is True
    assert profile.settings.fullscreen is False


def test_legacy_best_only_file(save_file):
    """UT-S-02：兼容旧版只含 best 的存档。"""
    save_file.write_text('{"best": 1234}', encoding="utf-8")

    profile = storage.load_profile()

    assert profile.best == 1234
    assert profile.settings == Settings()
    assert profile.leaderboard == []


def test_invalid_json_falls_back_to_default(save_file):
    """UT-S-03：乱码非法 JSON 降级默认且不抛异常。"""
    save_file.write_text("{not valid json", encoding="utf-8")

    assert storage.load_profile() == Profile()


def test_save_then_load_round_trip(save_file):
    """UT-S-04：保存后重新读取，分数、设置与榜单一致，且无残留 tmp 文件。"""
    profile = Profile(
        best=500,
        settings=Settings(fullscreen=True, music=30, sfx=40, ghost=False),
        leaderboard=[Record(name="小明", score=500, level=3, lines=27, time="11-24 21:30")],
    )

    storage.save_profile(profile)
    loaded = storage.load_profile()

    assert loaded == profile
    assert not save_file.with_suffix(".tmp").exists()
    payload = json.loads(save_file.read_text(encoding="utf-8"))
    assert payload["settings"]["music"] == 30


def test_full_board_rejects_lower_score(save_file):
    """UT-S-05：榜单满 10 条时，低于末位的分数不入榜且榜单不变。"""
    profile = Profile(leaderboard=build_records(list(range(100, 20, -8))))   # 100…28，共 10 条
    before = list(profile.leaderboard)

    assert len(profile.leaderboard) == storage.MAX_RECORDS
    assert storage.qualifies(profile, 15) is False
    assert storage.insert_record(profile, " newcomers ", 15, 1, 0) is None
    assert profile.leaderboard == before


def test_zero_score_never_qualifies(save_file):
    """UT-S-06：0 分不入榜。"""
    profile = Profile()

    assert storage.qualifies(profile, 0) is False
    assert storage.insert_record(profile, "甲", 0, 1, 0) is None
    assert profile.leaderboard == []


def test_equal_score_appends_after_existing(save_file):
    """UT-S-07：同分后到者排在先到者之后。"""
    profile = Profile(leaderboard=[Record(name="先", score=90), Record(name="次", score=80)])

    rank = storage.insert_record(profile, "后", 90, 2, 5)

    assert rank == 1
    assert [record.name for record in profile.leaderboard] == ["先", "后", "次"]
    assert profile.leaderboard[1].time != ""


def test_settings_values_are_clamped(save_file):
    """补充：音量越界被夹到 0～100，非法类型回退默认值。"""
    save_file.write_text(json.dumps({
        "settings": {"music": 150, "sfx": -5, "ghost": False, "fullscreen": "yes"},
    }), encoding="utf-8")

    settings = storage.load_profile().settings

    assert settings.music == 100
    assert settings.sfx == 0
    assert settings.ghost is False
    assert settings.fullscreen is False


def test_malformed_records_are_skipped_and_normalized(save_file):
    """补充：非法记录被跳过，超长昵称截断、等级与行数归一到合法范围。"""
    save_file.write_text(json.dumps({
        "leaderboard": [
            {"score": "abc"},
            {"score": -3},
            {"score": 50, "name": "A" * 20, "level": 0, "lines": -1},
        ],
    }), encoding="utf-8")

    records = storage.load_profile().leaderboard

    assert len(records) == 1
    assert records[0].name == "A" * MAX_NAME_LEN
    assert records[0].level == 1
    assert records[0].lines == 0
    assert records[0].time == ""
