#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
EMOJI_ANIMATED = ROOT / "emojis" / "animated"
EMOJI_STATIC = ROOT / "emojis" / "static"
README_DIR = ASSETS / "readme"
WALLPAPERS_DESKTOP = ROOT / "wallpapers" / "desktop"
WALLPAPERS_PHONE = ROOT / "wallpapers" / "phone"
SPRITESHEET = ROOT / "codex-pet" / "fren-bot" / "spritesheet.webp"
MAGICK = "magick"
DISCORD_LIMIT = 256 * 1024
ATLAS_CELL = (192, 208)
ATLAS_ROWS = [
    ("idle", 6),
    ("running-right", 8),
    ("running-left", 8),
    ("waving", 4),
    ("jumping", 5),
    ("failed", 8),
    ("waiting", 6),
    ("running", 6),
    ("review", 6),
]


PALETTE = {
    "cream": "#FFF1DE",
    "cream_shadow": "#FADFC8",
    "lavender": "#D8B3FF",
    "lavender_dark": "#6A3FB0",
    "lavender_mid": "#A46DE9",
    "pink": "#FFB4C6",
    "pink_dark": "#F47DA3",
    "night": "#1F163D",
    "night_mid": "#3B2E70",
    "sky": "#F3E8FF",
    "white": "#FFFFFF",
}


@dataclass
class SequenceSpec:
    name: str
    kind: str
    source: str
    frames: int | None = None
    duration_ms: int = 120


def ensure_dirs() -> None:
    for path in [
        EMOJI_ANIMATED,
        EMOJI_STATIC,
        README_DIR,
        WALLPAPERS_DESKTOP,
        WALLPAPERS_PHONE,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(hex_color)
    return (r, g, b, alpha)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(color_a: tuple[int, int, int], color_b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(lerp(color_a[0], color_b[0], t)),
        int(lerp(color_a[1], color_b[1], t)),
        int(lerp(color_a[2], color_b[2], t)),
    )


def gradient_canvas(size: tuple[int, int], top_hex: str, bottom_hex: str, horizontal: bool = False) -> Image.Image:
    width, height = size
    top = ImageColor.getrgb(top_hex)
    bottom = ImageColor.getrgb(bottom_hex)
    img = Image.new("RGBA", size)
    px = img.load()
    denom = max((width if horizontal else height) - 1, 1)
    for y in range(height):
        for x in range(width):
            t = (x if horizontal else y) / denom
            px[x, y] = (*lerp_color(top, bottom, t), 255)
    return img


def radial_glow(size: tuple[int, int], center: tuple[float, float], radius: float, color_hex: str, alpha: int) -> Image.Image:
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = center
    color = rgba(color_hex, alpha)
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.ellipse(box, fill=color)
    return overlay.filter(ImageFilter.GaussianBlur(radius / 3))


def add_sparkles(base: Image.Image, seed: int, count: int) -> None:
    rng = random.Random(seed)
    draw = ImageDraw.Draw(base)
    width, height = base.size
    for _ in range(count):
        x = rng.randint(40, width - 40)
        y = rng.randint(40, height - 40)
        size = rng.randint(max(10, width // 160), max(24, width // 80))
        color = rgba(PALETTE["white"], rng.randint(110, 220))
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=color)
        draw.polygon(
            [(x, y - size), (x + size * 0.25, y), (x, y + size), (x - size * 0.25, y)],
            fill=color,
        )
        draw.polygon(
            [(x - size, y), (x, y - size * 0.25), (x + size, y), (x, y + size * 0.25)],
            fill=color,
        )


def add_bokeh(base: Image.Image, seed: int, count: int, palette: list[str]) -> None:
    rng = random.Random(seed)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    for _ in range(count):
        radius = rng.randint(max(32, width // 50), max(96, width // 18))
        x = rng.randint(-radius, width + radius)
        y = rng.randint(-radius, height + radius)
        color = rgba(rng.choice(palette), rng.randint(35, 90))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    base.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(max(8, width // 120))))


def add_code_glyphs(base: Image.Image, seed: int, count: int, fill_hex: str, alpha: int, size_factor: float = 1.0) -> None:
    rng = random.Random(seed)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    glyphs = ["</>", "{ }", "< >", "[ ]", "//", ";;"]
    font = load_font(int(width * 0.032 * size_factor))
    for _ in range(count):
        glyph = rng.choice(glyphs)
        x = rng.randint(-40, width - 40)
        y = rng.randint(-40, height - 40)
        draw.text((x, y), glyph, font=font, fill=rgba(fill_hex, alpha))
    base.alpha_composite(overlay)


def add_paw_prints(base: Image.Image, seed: int, count: int, fill_hex: str, alpha: int) -> None:
    rng = random.Random(seed)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    for _ in range(count):
        x = rng.randint(60, width - 60)
        y = rng.randint(60, height - 60)
        size = rng.randint(max(18, width // 120), max(42, width // 64))
        color = rgba(fill_hex, alpha)
        draw.ellipse((x - size * 0.6, y, x + size * 0.6, y + size * 0.8), fill=color)
        for dx, dy in [(-0.5, -0.55), (-0.15, -0.85), (0.2, -0.85), (0.55, -0.55)]:
            tx = x + dx * size
            ty = y + dy * size
            r = size * 0.26
            draw.ellipse((tx - r, ty - r, tx + r, ty + r), fill=color)
    base.alpha_composite(overlay)


def add_glass_card(base: Image.Image, box: tuple[int, int, int, int], fill_alpha: int = 88) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(box, radius=42, fill=rgba(PALETTE["white"], fill_alpha), outline=rgba(PALETTE["white"], 150), width=4)
    highlight = (
        box[0] + 18,
        box[1] + 18,
        box[2] - 18,
        box[1] + max(64, (box[3] - box[1]) // 3),
    )
    draw.rounded_rectangle(highlight, radius=34, fill=rgba(PALETTE["white"], 36))
    base.alpha_composite(overlay)


def alpha_bbox(img: Image.Image, threshold: int = 16) -> tuple[int, int, int, int] | None:
    alpha = img.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > threshold else 0).getbbox()
    return bbox


def crop_with_padding(img: Image.Image, bbox: tuple[int, int, int, int], padding: int = 8) -> Image.Image:
    x0, y0, x1, y1 = bbox
    return img.crop((max(0, x0 - padding), max(0, y0 - padding), min(img.width, x1 + padding), min(img.height, y1 + padding)))


def clean_dark_matte(img: Image.Image, threshold: int = 18) -> Image.Image:
    src = img.convert("RGBA")
    px = src.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = px[x, y]
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (r, g, b, 0)
    return src


def open_asset(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    if "badge" in path.name:
        img = clean_dark_matte(img)
    return img


def chroma_key(img: Image.Image) -> Image.Image:
    src = img.convert("RGBA")
    px = src.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = px[x, y]
            green_score = g - max(r, b)
            if g > 160 and green_score > 70:
                if green_score > 140 and r < 80 and b < 80:
                    alpha = 0
                else:
                    alpha = max(0, min(255, int((green_score - 70) * 2.8)))
                    alpha = 255 - alpha
                if alpha < 255:
                    g = int((g + max(r, b)) / 2)
                px[x, y] = (r, g, b, alpha)
    return src


def split_strip_frames(path: Path) -> list[Image.Image]:
    keyed = chroma_key(Image.open(path))
    alpha = keyed.getchannel("A")
    column_ranges: list[tuple[int, int]] = []
    start = None
    for x in range(alpha.width):
        has_pixel = alpha.crop((x, 0, x + 1, alpha.height)).getbbox() is not None
        if has_pixel and start is None:
            start = x
        elif not has_pixel and start is not None:
            if x - start > 24:
                column_ranges.append((start, x))
            start = None
    if start is not None:
        column_ranges.append((start, alpha.width))
    frames: list[Image.Image] = []
    local_boxes: list[tuple[int, int, int, int]] = []
    frame_crops: list[Image.Image] = []
    for x0, x1 in column_ranges:
        segment = keyed.crop((x0, 0, x1, keyed.height))
        bbox = alpha_bbox(segment)
        if bbox is None:
            continue
        local_boxes.append(bbox)
        frame_crops.append(segment.crop(bbox))
    if not frame_crops:
        return frames
    ux0 = min(box[0] for box in local_boxes)
    uy0 = min(box[1] for box in local_boxes)
    ux1 = max(box[2] for box in local_boxes)
    uy1 = max(box[3] for box in local_boxes)
    pad = 10
    canvas_w = ux1 - ux0 + pad * 2
    canvas_h = uy1 - uy0 + pad * 2
    for crop, box in zip(frame_crops, local_boxes, strict=False):
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        offset = (pad + box[0] - ux0, pad + box[1] - uy0)
        canvas.paste(crop, offset, crop)
        frames.append(canvas)
    return frames


def atlas_frames(state: str) -> list[Image.Image]:
    atlas = open_asset(SPRITESHEET)
    cell_w, cell_h = ATLAS_CELL
    row_index = next(index for index, (name, _) in enumerate(ATLAS_ROWS) if name == state)
    frame_count = next(count for name, count in ATLAS_ROWS if name == state)
    frames = []
    for frame_index in range(frame_count):
        x0 = frame_index * cell_w
        y0 = row_index * cell_h
        frame = atlas.crop((x0, y0, x0 + cell_w, y0 + cell_h))
        frames.append(frame)
    return normalize_sequence(frames)


def normalize_sequence(frames: list[Image.Image]) -> list[Image.Image]:
    boxes = [alpha_bbox(frame) for frame in frames]
    valid = [box for box in boxes if box is not None]
    if not valid:
        return frames
    ux0 = min(box[0] for box in valid)
    uy0 = min(box[1] for box in valid)
    ux1 = max(box[2] for box in valid)
    uy1 = max(box[3] for box in valid)
    pad = 8
    canvas_w = ux1 - ux0 + pad * 2
    canvas_h = uy1 - uy0 + pad * 2
    normalized = []
    for frame, box in zip(frames, boxes, strict=False):
        if box is None:
            normalized.append(Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0)))
            continue
        crop = frame.crop(box)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        offset = (pad + box[0] - ux0, pad + box[1] - uy0)
        canvas.paste(crop, offset, crop)
        normalized.append(canvas)
    return normalized


def load_sequence(spec: SequenceSpec) -> list[Image.Image]:
    if spec.kind == "atlas":
        return atlas_frames(spec.source)
    if spec.kind == "strip":
        return split_strip_frames(ROOT / spec.source)
    raise ValueError(f"Unknown sequence kind: {spec.kind}")


def fit_on_canvas(img: Image.Image, canvas_size: int) -> Image.Image:
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    max_w = canvas_size - 12
    max_h = canvas_size - 12
    frame = img.copy()
    ratio = min(max_w / frame.width, max_h / frame.height, 1.0)
    new_size = (max(1, int(frame.width * ratio)), max(1, int(frame.height * ratio)))
    frame = frame.resize(new_size, Image.Resampling.LANCZOS)
    x = (canvas_size - frame.width) // 2
    y = (canvas_size - frame.height) // 2
    canvas.paste(frame, (x, y), frame)
    return canvas


def save_gif(frames: list[Image.Image], out_path: Path, duration_ms: int) -> int:
    size_steps = [128, 120, 112, 104, 96, 88, 80]
    best_size = None
    for canvas_size in size_steps:
        rendered = [fit_on_canvas(frame, canvas_size) for frame in frames]
        paletted: list[Image.Image] = []
        for frame in rendered:
            palette_frame = frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=48, dither=Image.Dither.NONE)
            paletted.append(palette_frame)
        paletted[0].save(
            out_path,
            save_all=True,
            append_images=paletted[1:],
            duration=duration_ms,
            loop=0,
            disposal=2,
            optimize=False,
            transparency=0,
        )
        if shutil_which(MAGICK):
            optimize_gif(out_path)
        file_size = out_path.stat().st_size
        best_size = file_size
        if file_size <= DISCORD_LIMIT:
            return file_size
    return best_size or out_path.stat().st_size


def shutil_which(name: str) -> bool:
    try:
        subprocess.run(["/usr/bin/env", "which", name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def optimize_gif(path: Path) -> None:
    with TemporaryDirectory() as tmp_dir:
        optimized = Path(tmp_dir) / path.name
        subprocess.run(
            [
                MAGICK,
                str(path),
                "-layers",
                "OptimizeTransparency",
                str(optimized),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        optimized.replace(path)


def save_static_png(src_path: Path, out_path: Path) -> int:
    img = open_asset(src_path)
    bbox = alpha_bbox(img)
    if bbox is not None:
        img = crop_with_padding(img, bbox, 16)
    img = fit_on_canvas(img, 128)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path.stat().st_size


def build_emojis() -> dict[str, dict[str, int | str]]:
    animated_specs = [
        SequenceSpec("fren_idle", "atlas", "idle", duration_ms=160),
        SequenceSpec("fren_run", "atlas", "running-right", duration_ms=90),
        SequenceSpec("fren_wave", "atlas", "waving", duration_ms=150),
        SequenceSpec("fren_jump", "atlas", "jumping", duration_ms=125),
        SequenceSpec("fren_wait", "atlas", "waiting", duration_ms=140),
        SequenceSpec("fren_review", "atlas", "review", duration_ms=140),
        SequenceSpec("fren_sad", "atlas", "failed", duration_ms=130),
        SequenceSpec("fren_tailwag", "strip", "assets/emoji-source/fren-tailwag-strip-v2.png", duration_ms=140),
        SequenceSpec("fren_hop", "strip", "assets/emoji-source/fren-hop-strip-v1.png", duration_ms=115),
    ]
    static_specs = [
        ("fren_sit", ASSETS / "fren-pet-final.png"),
        ("fren_badge", ASSETS / "fren-pet-badge-final.png"),
        ("fren_stand", ASSETS / "fren-pet-standing.png"),
    ]
    manifest: dict[str, dict[str, int | str]] = {}
    for spec in animated_specs:
        frames = load_sequence(spec)
        out_path = EMOJI_ANIMATED / f"{spec.name}.gif"
        size_bytes = save_gif(frames, out_path, spec.duration_ms)
        manifest[spec.name] = {
            "type": "animated",
            "path": str(out_path.relative_to(ROOT)),
            "frames": len(frames),
            "bytes": size_bytes,
        }
    for name, path in static_specs:
        out_path = EMOJI_STATIC / f"{name}.png"
        size_bytes = save_static_png(path, out_path)
        manifest[name] = {
            "type": "static",
            "path": str(out_path.relative_to(ROOT)),
            "frames": 1,
            "bytes": size_bytes,
        }
    (ROOT / "emojis" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def resized_pet(path: Path, target_height: int) -> Image.Image:
    img = open_asset(path)
    ratio = target_height / img.height
    size = (int(img.width * ratio), int(img.height * ratio))
    return img.resize(size, Image.Resampling.LANCZOS)


def paste_with_glow(base: Image.Image, sticker: Image.Image, position: tuple[int, int], glow_hex: str, blur: int, alpha: int = 170) -> None:
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_sprite = Image.new("RGBA", sticker.size, rgba(glow_hex, alpha))
    glow_sprite.putalpha(sticker.getchannel("A"))
    glow.paste(glow_sprite, position, glow_sprite)
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(blur)))
    base.alpha_composite(sticker, position)


def draw_wallpaper_label(base: Image.Image, title: str, subtitle: str, anchor: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(base)
    title_font = load_font(max(42, base.width // 34), bold=True)
    subtitle_font = load_font(max(24, base.width // 58))
    x, y = anchor
    draw.text((x, y), title, font=title_font, fill=rgba(PALETTE["white"], 245))
    draw.text((x, y + title_font.size + 8), subtitle, font=subtitle_font, fill=rgba(PALETTE["white"], 180))


def wallpaper_dream(size: tuple[int, int], phone: bool) -> Image.Image:
    bg = gradient_canvas(size, "#FFF4F8", "#B48BFF")
    add_bokeh(bg, seed=11 if phone else 7, count=28, palette=["#FFFFFF", "#FFD7E8", "#E2CCFF"])
    bg.alpha_composite(radial_glow(size, (size[0] * 0.68, size[1] * 0.38), min(size) * 0.22, "#FFFFFF", 150))
    bg.alpha_composite(radial_glow(size, (size[0] * 0.28, size[1] * 0.16), min(size) * 0.18, "#FFBBD1", 100))
    add_sparkles(bg, seed=13 if phone else 17, count=18 if phone else 24)
    add_code_glyphs(bg, seed=23, count=10 if phone else 14, fill_hex="#FFFFFF", alpha=60, size_factor=0.75)
    pet = resized_pet(ASSETS / "fren-pet-final.png", int(size[1] * (0.44 if phone else 0.62)))
    badge = resized_pet(ASSETS / "fren-pet-badge-final.png", int(size[1] * (0.11 if phone else 0.14)))
    if phone:
        add_glass_card(bg, (180, int(size[1] * 0.18), size[0] - 180, int(size[1] * 0.86)), 70)
        paste_with_glow(bg, pet, ((size[0] - pet.width) // 2, int(size[1] * 0.36)), "#F9D2FF", 56)
        bg.alpha_composite(badge, ((size[0] - badge.width) // 2, int(size[1] * 0.12)))
        draw_wallpaper_label(bg, "Fren Bot", "dream mode", (180, int(size[1] * 0.075)))
    else:
        add_glass_card(bg, (210, 220, size[0] - 210, size[1] - 210), 62)
        paste_with_glow(bg, pet, (int(size[0] * 0.55), int(size[1] * 0.28)), "#FFD9F6", 64)
        bg.alpha_composite(badge, (int(size[0] * 0.14), int(size[1] * 0.2)))
        draw_wallpaper_label(bg, "Fren Bot", "soft focus coding buddy", (240, int(size[1] * 0.62)))
    return bg


def wallpaper_runner(size: tuple[int, int], phone: bool) -> Image.Image:
    bg = gradient_canvas(size, "#FFE7D5", "#A77BFF")
    add_bokeh(bg, seed=29, count=22, palette=["#FFE4BC", "#FFD2E5", "#FFFFFF"])
    add_paw_prints(bg, seed=31 if phone else 37, count=12 if phone else 18, fill_hex="#FFFFFF", alpha=58)
    add_code_glyphs(bg, seed=41, count=8 if phone else 12, fill_hex="#FFEED8", alpha=72, size_factor=0.8)
    runner_frames = atlas_frames("running-right")
    runner = runner_frames[2].resize(
        (
            int(runner_frames[2].width * (size[1] * (0.0042 if phone else 0.0048))),
            int(runner_frames[2].height * (size[1] * (0.0042 if phone else 0.0048))),
        ),
        Image.Resampling.LANCZOS,
    )
    standing = resized_pet(ASSETS / "fren-pet-standing.png", int(size[1] * (0.34 if phone else 0.48)))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    trail_positions = (
        [(260, 620), (620, 880), (980, 1140), (1340, 1400)] if phone else [(320, 1240), (860, 1060), (1420, 900), (1980, 760), (2540, 660)]
    )
    for idx, pos in enumerate(trail_positions):
        faded = runner.copy()
        faded.putalpha(faded.getchannel("A").point(lambda value, i=idx: int(value * (0.20 + i * 0.12))))
        overlay.alpha_composite(faded, pos)
    bg.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(2)))
    if phone:
        paste_with_glow(bg, standing, (int(size[0] * 0.46), int(size[1] * 0.58)), "#FFD8A6", 52)
        draw_wallpaper_label(bg, "Fren Sprint", "tiny paws, high velocity", (170, 200))
    else:
        paste_with_glow(bg, standing, (int(size[0] * 0.68), int(size[1] * 0.42)), "#FFD39A", 56)
        draw_wallpaper_label(bg, "Fren Sprint", "chasing the next compile", (260, 300))
    return bg


def wallpaper_night(size: tuple[int, int], phone: bool) -> Image.Image:
    bg = gradient_canvas(size, "#24184D", "#0C1027")
    add_bokeh(bg, seed=53, count=18, palette=["#8E75FF", "#D9BEFF", "#FFFFFF"])
    bg.alpha_composite(radial_glow(size, (size[0] * 0.74, size[1] * 0.22), min(size) * 0.24, "#9275FF", 125))
    bg.alpha_composite(radial_glow(size, (size[0] * 0.2, size[1] * 0.74), min(size) * 0.16, "#FFB5D6", 85))
    add_sparkles(bg, seed=59 if phone else 61, count=20 if phone else 28)
    add_code_glyphs(bg, seed=67, count=12 if phone else 16, fill_hex="#DCC5FF", alpha=80, size_factor=0.95)
    add_glass_card(bg, (140 if phone else 220, 180 if phone else 240, size[0] - (140 if phone else 220), size[1] - (180 if phone else 240)), 58)
    pet = resized_pet(ASSETS / "fren-pet-standing.png", int(size[1] * (0.4 if phone else 0.58)))
    badge = resized_pet(ASSETS / "fren-pet-badge-final.png", int(size[1] * (0.12 if phone else 0.15)))
    if phone:
        paste_with_glow(bg, pet, ((size[0] - pet.width) // 2, int(size[1] * 0.34)), "#8E75FF", 68)
        bg.alpha_composite(badge, (int(size[0] * 0.12), int(size[1] * 0.18)))
        draw_wallpaper_label(bg, "Night Shift Fren", "quiet keys, glowing paws", (170, int(size[1] * 0.78)))
    else:
        paste_with_glow(bg, pet, (int(size[0] * 0.56), int(size[1] * 0.24)), "#8E75FF", 72)
        bg.alpha_composite(badge, (int(size[0] * 0.14), int(size[1] * 0.18)))
        draw_wallpaper_label(bg, "Night Shift Fren", "warm headphones, cool terminal", (260, int(size[1] * 0.7)))
    return bg


def build_wallpapers() -> dict[str, str]:
    manifest: dict[str, str] = {}
    specs = [
        ("fren-dream-desktop-4k.png", WALLPAPERS_DESKTOP, (3840, 2160), wallpaper_dream, False),
        ("fren-sprint-desktop-4k.png", WALLPAPERS_DESKTOP, (3840, 2160), wallpaper_runner, False),
        ("fren-night-desktop-4k.png", WALLPAPERS_DESKTOP, (3840, 2160), wallpaper_night, False),
        ("fren-dream-phone-4k.png", WALLPAPERS_PHONE, (2160, 3840), wallpaper_dream, True),
        ("fren-sprint-phone-4k.png", WALLPAPERS_PHONE, (2160, 3840), wallpaper_runner, True),
        ("fren-night-phone-4k.png", WALLPAPERS_PHONE, (2160, 3840), wallpaper_night, True),
    ]
    for filename, folder, size, factory, phone in specs:
        image = factory(size, phone)
        path = folder / filename
        image.save(path)
        manifest[filename] = str(path.relative_to(ROOT))
    return manifest


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return (right - left, bottom - top)


def build_readme_graphics(emoji_manifest: dict[str, dict[str, int | str]]) -> None:
    hero = gradient_canvas((1600, 900), "#FFF5EC", "#B58BFF")
    add_bokeh(hero, seed=73, count=18, palette=["#FFFFFF", "#F9D4E7", "#E0D0FF"])
    add_sparkles(hero, seed=79, count=18)
    add_glass_card(hero, (90, 90, 1510, 810), 72)
    seated = resized_pet(ASSETS / "fren-pet-final.png", 420)
    standing = resized_pet(ASSETS / "fren-pet-standing.png", 330)
    badge = resized_pet(ASSETS / "fren-pet-badge-final.png", 140)
    paste_with_glow(hero, seated, (1085, 345), "#FFD8EF", 44)
    hero.alpha_composite(standing, (930, 390))
    hero.alpha_composite(badge, (140, 120))
    draw = ImageDraw.Draw(hero)
    title_font = load_font(84, bold=True)
    body_font = load_font(34)
    pill_font = load_font(28)
    draw.text((320, 170), "Fren Bot", font=title_font, fill=rgba(PALETTE["night"], 255))
    draw.text((320, 276), "Codex pet, Discord emojis,", font=body_font, fill=rgba(PALETTE["night_mid"], 230))
    draw.text((320, 322), "and 4K wallpapers.", font=body_font, fill=rgba(PALETTE["night_mid"], 230))
    chips = ["custom Codex pet", "9 animated emojis", "6 wallpapers"]
    chip_x = 320
    for chip in chips:
        w, h = text_size(draw, chip, pill_font)
        box = (chip_x, 392, chip_x + w + 40, 392 + h + 24)
        draw.rounded_rectangle(box, radius=24, fill=rgba(PALETTE["white"], 190))
        draw.text((chip_x + 20, 404), chip, font=pill_font, fill=rgba(PALETTE["lavender_dark"], 255))
        chip_x = box[2] + 20
    draw.text((320, 500), "Cute, clean, and already sized for Discord limits.", font=body_font, fill=rgba(PALETTE["night_mid"], 200))
    hero.save(README_DIR / "fren-hero.png")

    showcase = gradient_canvas((1600, 900), "#F6EDFF", "#FFF5F1")
    add_bokeh(showcase, seed=83, count=12, palette=["#FFFFFF", "#ECD7FF", "#FFD3DE"])
    draw = ImageDraw.Draw(showcase)
    title_font = load_font(56, bold=True)
    label_font = load_font(26)
    draw.text((88, 72), "Emoji Pack", font=title_font, fill=rgba(PALETTE["night"], 255))
    preview_names = [
        "fren_idle",
        "fren_run",
        "fren_wave",
        "fren_jump",
        "fren_sad",
        "fren_tailwag",
        "fren_hop",
        "fren_sit",
        "fren_badge",
    ]
    card_w = 420
    card_h = 220
    x_positions = [88, 510, 932]
    y_positions = [180, 420, 660]
    for index, name in enumerate(preview_names):
        card_x = x_positions[index % 3]
        card_y = y_positions[index // 3]
        draw.rounded_rectangle((card_x, card_y, card_x + card_w, card_y + card_h), radius=34, fill=rgba(PALETTE["white"], 178), outline=rgba(PALETTE["lavender"], 160), width=3)
        meta = emoji_manifest[name]
        asset = ROOT / str(meta["path"])
        if asset.suffix == ".gif":
            frame = Image.open(asset)
            preview = frame.convert("RGBA")
        else:
            preview = open_asset(asset)
        preview = fit_on_canvas(preview, 124)
        showcase.alpha_composite(preview, (card_x + 26, card_y + 48))
        draw.text((card_x + 170, card_y + 74), name.replace("fren_", "fren "), font=label_font, fill=rgba(PALETTE["night"], 235))
        badge_text = f'{meta["bytes"] // 1024} KB'
        draw.text((card_x + 170, card_y + 116), badge_text, font=label_font, fill=rgba(PALETTE["lavender_dark"], 205))
    showcase.save(README_DIR / "emoji-showcase.png")

    wallpaper_grid = gradient_canvas((1600, 950), "#F4EBFF", "#FFF7EF")
    draw = ImageDraw.Draw(wallpaper_grid)
    draw.text((88, 72), "Wallpaper Set", font=title_font, fill=rgba(PALETTE["night"], 255))
    wallpaper_files = [
        WALLPAPERS_DESKTOP / "fren-dream-desktop-4k.png",
        WALLPAPERS_DESKTOP / "fren-sprint-desktop-4k.png",
        WALLPAPERS_DESKTOP / "fren-night-desktop-4k.png",
        WALLPAPERS_PHONE / "fren-dream-phone-4k.png",
        WALLPAPERS_PHONE / "fren-sprint-phone-4k.png",
        WALLPAPERS_PHONE / "fren-night-phone-4k.png",
    ]
    desktop_slots = [(88, 180), (574, 180), (1060, 180)]
    phone_slots = [(210, 520), (650, 520), (1090, 520)]
    for path, (x, y) in zip(wallpaper_files[:3], desktop_slots, strict=False):
        thumb = Image.open(path).convert("RGBA")
        thumb.thumbnail((420, 236), Image.Resampling.LANCZOS)
        card = Image.new("RGBA", (452, 268), rgba(PALETTE["white"], 176))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, 451, 267), radius=28, fill=rgba(PALETTE["white"], 176), outline=rgba(PALETTE["lavender"], 140), width=3)
        card.alpha_composite(thumb, ((452 - thumb.width) // 2, (268 - thumb.height) // 2))
        wallpaper_grid.alpha_composite(card, (x, y))
    for path, (x, y) in zip(wallpaper_files[3:], phone_slots, strict=False):
        thumb = Image.open(path).convert("RGBA")
        thumb.thumbnail((220, 390), Image.Resampling.LANCZOS)
        card = Image.new("RGBA", (252, 422), rgba(PALETTE["white"], 176))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, 251, 421), radius=28, fill=rgba(PALETTE["white"], 176), outline=rgba(PALETTE["lavender"], 140), width=3)
        card.alpha_composite(thumb, ((252 - thumb.width) // 2, (422 - thumb.height) // 2))
        wallpaper_grid.alpha_composite(card, (x, y))
    wallpaper_grid.save(README_DIR / "wallpaper-showcase.png")


def main() -> None:
    ensure_dirs()
    emoji_manifest = build_emojis()
    build_wallpapers()
    build_readme_graphics(emoji_manifest)


if __name__ == "__main__":
    main()
