# -*- coding: utf-8 -*-
"""资源路径解析：源码运行与 exe（onefile/onedir）运行的唯一入口。

分层：基础设施。
允许依赖：标准库。
禁止依赖：pygame 与任何业务模块。

约定：assets/ 下所有文件都必须经 resource_path() 拼接，禁止 "assets/..." 字面量。
"""

from __future__ import annotations

import os
import sys


def resource_path(*parts: str) -> str:
    """返回资源绝对路径；打包后从 sys._MEIPASS 解包目录取，源码运行时从工程根取。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS")
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
