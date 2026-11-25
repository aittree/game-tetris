# -*- coding: utf-8 -*-
"""俄罗斯方块（Tetris）桌面版 —— 源码包。

分层（依赖方向严格单向向下，详见 02 概要设计 §2）：

- 模型层：config.py、pieces.py、board.py
- 应用层：game.py
- 表现层：ui/（theme、renderer、effects、display）
- 基础设施：storage.py、resource.py、audio.py

模型层与应用层不得导入 pygame。
"""
