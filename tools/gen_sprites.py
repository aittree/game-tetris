# -*- coding: utf-8 -*-
"""生成俄罗斯方块项目所需的图片素材（背景、方块贴图、Logo 与图标）。

用法：
    python tools/gen_sprites.py

输入：
    _src/bg_game_src.png   游戏背景原图（AI 生成）
    _src/bg_menu_src.png   主菜单背景原图（AI 生成）
    _src/logo_src.png      Logo 原图（白底）
输出：
    assets/images/bg_game.png    720×800
    assets/images/bg_menu.png    720×800
    assets/images/logo.png       512×512 透明底
    assets/images/blocks.png     8×1 方块贴图带（每格 64px）
    assets/icon.png              256×256 透明底
    assets/icon.ico              16/24/32/48/64/128/256 多尺寸
"""

import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_src")
IMG = os.path.join(ROOT, "assets", "images")

CANVAS = (720, 800)
CELL = 64                      # 贴图单格 64px，渲染时缩放到 30px，兼顾高分屏

# 与 docs/03 主题配色保持一致：I J L O S T Z + 幽灵
BLOCK_COLORS = [
    (0, 229, 255),     # I 青
    (61, 90, 254),     # J 蓝
    (255, 159, 28),    # L 橙
    (255, 214, 10),    # O 黄
    (46, 230, 168),    # S 绿
    (177, 78, 255),    # T 紫
    (255, 77, 109),    # Z 红
    (120, 130, 160),   # 幽灵灰
]


def prepare_background(src_name: str, dst_name: str, crop: float = 0.045, darken: float = 1.0) -> None:
    """裁掉原图四周的装饰边框，再等比铺满 720×800 画布。

    crop: 四边各裁掉的比例。bg_game 原图带圆角外框，需要裁得更深（0.085）。
    """
    im = Image.open(os.path.join(SRC, src_name)).convert("RGB")
    w, h = im.size
    margin_x, margin_y = int(w * crop), int(h * crop)
    im = im.crop((margin_x, margin_y, w - margin_x, h - margin_y))

    tw, th = CANVAS
    ratio = max(tw / im.width, th / im.height)
    im = im.resize((int(im.width * ratio + 1), int(im.height * ratio + 1)), Image.LANCZOS)
    left = (im.width - tw) // 2
    top = (im.height - th) // 2
    im = im.crop((left, top, left + tw, top + th))

    if darken != 1.0:
        im = Image.eval(im, lambda v: int(v * darken))
    im.save(os.path.join(IMG, dst_name), optimize=True)
    print(f"{dst_name}: {im.size}")


def build_logo() -> None:
    """白底 Logo 抠成透明底，并输出窗口图标与 exe 图标。"""
    im = Image.open(os.path.join(SRC, "logo_src.png")).convert("RGBA")
    px = im.load()
    corners = [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]
    for corner in corners:
        ImageDraw.floodfill(im, corner, (0, 0, 0, 0), thresh=40)

    # 半透明白边清理：亮度很高且饱和度很低的像素直接透明，避免残留白晕
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and r > 235 and g > 235 and b > 235:
                px[x, y] = (0, 0, 0, 0)

    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)

    logo = canvas.resize((512, 512), Image.LANCZOS)
    logo.save(os.path.join(IMG, "logo.png"), optimize=True)
    print("logo.png: 512x512")

    canvas.resize((256, 256), Image.LANCZOS).save(os.path.join(ROOT, "assets", "icon.png"), optimize=True)
    canvas.save(
        os.path.join(ROOT, "assets", "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("icon.png / icon.ico ok")


def build_blocks() -> None:
    """绘制 8 格方块贴图带：圆角、上高光、下暗边、外发光。"""
    pad = 4
    sheet = Image.new("RGBA", (CELL * len(BLOCK_COLORS), CELL), (0, 0, 0, 0))

    for i, color in enumerate(BLOCK_COLORS):
        tile = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        glow = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        d = ImageDraw.Draw(glow)
        d.rounded_rectangle((pad + 2, pad + 2, CELL - pad - 3, CELL - pad - 3),
                            radius=9, fill=color + (110,))
        glow = glow.filter(ImageFilter.GaussianBlur(3))
        tile.alpha_composite(glow)

        d = ImageDraw.Draw(tile)
        body = (pad, pad, CELL - pad - 1, CELL - pad - 1)
        d.rounded_rectangle(body, radius=9, fill=color + (255,))
        # 上部高光：白色半透明横向渐变
        hi = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        dh = ImageDraw.Draw(hi)
        for k in range(CELL // 2):
            alpha = int(95 * (1 - k / (CELL // 2)))
            dh.line([(pad + 3, pad + 3 + k), (CELL - pad - 4, pad + 3 + k)], fill=(255, 255, 255, alpha))
        tile.alpha_composite(hi)
        # 底部内阴影，让方块有厚度
        lo = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lo)
        for k in range(CELL // 3):
            alpha = int(70 * (1 - k / (CELL // 3)))
            dl.line([(pad + 3, CELL - pad - 4 - k), (CELL - pad - 4, CELL - pad - 4 - k)],
                    fill=(0, 0, 0, alpha))
        tile.alpha_composite(lo)
        # 内描边
        d.rounded_rectangle(body, radius=9, outline=(255, 255, 255, 120), width=2)
        sheet.paste(tile, (i * CELL, 0), tile)

    sheet.save(os.path.join(IMG, "blocks.png"), optimize=True)
    print(f"blocks.png: {sheet.size}")


if __name__ == "__main__":
    os.makedirs(IMG, exist_ok=True)
    prepare_background("bg_game_src.png", "bg_game.png", crop=0.085, darken=0.9)
    prepare_background("bg_menu_src.png", "bg_menu.png", darken=0.95)
    build_logo()
    build_blocks()

