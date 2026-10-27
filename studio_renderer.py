# -*- coding: utf-8 -*-
"""
studio_renderer.py
الاستوديو البصري والصوتي المحلي لمنصة «ثانويتي بلس» (https://thanaweya-ashy.vercel.app)
مصمم بنفس هوية وألوان وشعار موقع «ثانويتي بلس» الأصلي (#0b1020 + #2dd4bf + #8b5cf6 + #fbbf24):
- بطاقات 1080×1350 فائقة الوضوح تغطي كل صف وكل شعبة والـ 4 مسارات للبكالوريا المصرية بالوحدة ورقم الدرس والجزء.
- ريلز/شورتس 1080×1920 متحرك لجميع البطاقات بالصوت.
- فيديو تحدي السهرة 30 ثانية (1080×1920) بمؤقت نيون تنازلي حيّ وتكتكة وجرس نهاية بدون كشف الإجابة.
"""

from __future__ import annotations
import math
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT_PATH = HERE / "fonts" / "Cairo-Variable.ttf"
LOGO_PATH = HERE / "assets" / "logo.png"

# ألوان الهوية الأصلية لموقع «ثانويتي بلس» (theme.css)
BG_DARK = (11, 16, 32)         # --bg: #0b1020
BG_CARD = (17, 25, 46)         # --bg2: #0f172a
BG_INNER = (23, 34, 60)
TEAL = (45, 212, 191)          # --pri: #2dd4bf
TEAL_DARK = (13, 148, 136)     # --pri2: #0d9488
VIOLET = (139, 92, 246)        # --vio: #8b5cf6
GOLD = (251, 191, 36)          # --acc: #fbbf24
GOLD_DARK = (245, 158, 11)     # --acc2: #f59e0b
GREEN = (74, 222, 128)         # --grn: #4ade80
BLUE = (96, 165, 250)          # --blu: #60a5fa
PINK = (244, 114, 182)         # --pink: #f472b6
RED_NEON = (248, 113, 113)     # --red: #f87171
WHITE = (238, 242, 255)        # --txt: #eef2ff
MUTED = (165, 180, 207)        # --txt2: #a5b4cf
NAVY_TEXT = (4, 33, 28)

SECTION_ACCENTS = [TEAL, GOLD, VIOLET, BLUE, GREEN, PINK]


def get_ffmpeg() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size=size)
    try:
        font.set_variation_by_name(weight)
    except Exception:
        pass
    return font


def sanitize_for_cairo(text: str) -> str:
    """استبدال الرموز الرياضية اليونانية والمحارف الخاصة غير المدعومة في خط Cairo بمكافئاتها العربية/اللاتينية."""
    replacements = {
        "Σ": "مجموع ",
        "∑": "مجموع ",
        "Δ": "دلتا ",
        "∆": "دلتا ",
        "θ": "ثيتا",
        "φ": "فاي",
        "π": "باي",
        "Ω": "أوم",
        "μ": "ميو",
        "λ": "لمدا",
        "α": "ألفا",
        "β": "بيتا",
        "η": "إيتا",
        "τ": "تاو",
        "γ": "جاما",
        "ρ": "رو",
        "ν": "نيو",
        "→": "<-",
        "←": "<-",
        "↔": "<->",
        "⇌": "<->",
        "≈": "=",
        "≠": "!=",
        "≤": "<=",
        "≥": ">=",
        "×": "x",
        "÷": "/",
        "⁄": "/",
        "∕": "/",
        "\u202f": " ",
        "\u00a0": " ",
        "\u2009": " ",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": " - ",
        "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
        "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
        "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
        "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
        "•": " - ",
    }
    out = str(text or "")
    for k, v in replacements.items():
        out = out.replace(k, v)
    # إزالة أي رمز نادر خارج نطاق العربية واللاتينية وعلامات الترقيم القياسية لمنع ظهور مربعات فارغة
    cleaned = []
    for ch in out:
        cp = ord(ch)
        if (
            ch in ("\n", "\t")
            or (0x20 <= cp <= 0x7E)
            or (0x0600 <= cp <= 0x06FF)
            or (0x0750 <= cp <= 0x077F)
            or (0xFB50 <= cp <= 0xFDFF)
            or (0xFE70 <= cp <= 0xFEFF)
        ):
            cleaned.append(ch)
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split(" "))


def wrap_arabic_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    text = sanitize_for_cairo((text or "").replace("\r", "").strip())
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    lines: List[str] = []
    for para in paragraphs:
        words = para.split()
        cur = ""
        for w in words:
            cand = f"{cur} {w}".strip() if cur else w
            bbox = draw.textbbox((0, 0), cand, font=font, direction="rtl", language="ar")
            if (bbox[2] - bbox[0]) <= max_width or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def draw_centered_rtl(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
) -> int:
    text = sanitize_for_cairo(text)
    bbox = draw.textbbox((0, 0), text, font=font, direction="rtl", language="ar")
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((cx - w // 2, y), text, font=font, fill=fill, direction="rtl", language="ar")
    return h


def draw_right_rtl(
    draw: ImageDraw.ImageDraw,
    text: str,
    right_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
) -> Tuple[int, int]:
    text = sanitize_for_cairo(text)
    bbox = draw.textbbox((0, 0), text, font=font, direction="rtl", language="ar")
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((right_x - w, y), text, font=font, fill=fill, direction="rtl", language="ar")
    return w, h


def make_brand_background(w: int, h: int) -> Image.Image:
    """خلفية متطابقة مع هوية موقع ثانويتي بلس (Teal + Violet glow on Deep Navy #0b1020)."""
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    g_violet = np.exp(-(((xx - 0.85) ** 2) / 0.14 + ((yy - 0.08) ** 2) / 0.12))
    g_teal = np.exp(-(((xx - 0.15) ** 2) / 0.16 + ((yy - 0.90) ** 2) / 0.16))

    r = np.clip(11 + 36 * g_violet + 6 * g_teal, 0, 255)
    g = np.clip(16 + 18 * g_violet + 38 * g_teal, 0, 255)
    b = np.clip(32 + 65 * g_violet + 36 * g_teal, 0, 255)
    arr = np.stack([r, g, b], axis=-1).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    draw = ImageDraw.Draw(img)
    for x in range(0, w, 64):
        draw.line([(x, 0), (x, h)], fill=(20, 30, 54), width=1)
    for y in range(0, h, 64):
        draw.line([(0, y), (w, y)], fill=(20, 30, 54), width=1)
    return img


def paste_logo(img: Image.Image, x: int, y: int, size: int = 86) -> None:
    if not LOGO_PATH.exists():
        return
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((size, size), Image.Resampling.LANCZOS)
        # توهج خفيف خلف الشعار
        base_rgba = img.convert("RGBA")
        base_rgba.alpha_composite(logo, dest=(x, y))
        img.paste(base_rgba.convert("RGB"), (0, 0))
    except Exception:
        pass


def render_structured_card(
    out_path: Path,
    slot_type: str,  # "morning" or "maghrib"
    header_badge: str,
    cohort_title: str,
    date_label: str,
    mode_badge: str,
    progress_pct: int,
    slide_label: str,
    sections: List[Dict[str, str]],
    footer_cta: str,
) -> Path:
    """
    يرسم بطاقة 1080×1350 غنية ومرتبة لأقسام متعددة (مثلاً المسارات الـ 4 للبكالوريا أو شعب ثالثة ثانوي)،
    بحيث يظهر لكل قسم: اسم المسار/الشعبة + المادة + الوحدة + رقم الدرس وعنوانه + الجزء الكام + التفاصيل!
    """
    W, H = 1080, 1350
    img = make_brand_background(W, H)
    draw = ImageDraw.Draw(img)

    main_accent = TEAL if slot_type == "morning" else GOLD

    # ---------------- 1) ترويسة المنصة والصف + الشعار الرسمي ----------------
    draw.rounded_rectangle([38, 28, W - 38, 232], radius=28, fill=BG_CARD, outline=main_accent, width=3)
    paste_logo(img, W - 152, 46, size=92)
    draw = ImageDraw.Draw(img)

    # شارة النشرة في أعلى يسار/منتصف الهيدر
    f_badge = load_font(22, "Bold")
    draw.rounded_rectangle([62, 44, 886, 86], radius=16, fill=(22, 42, 62), outline=TEAL_DARK, width=1)
    draw_centered_rtl(draw, f"{header_badge}  |  {slide_label}", 474, 48, f_badge, GOLD)

    # اسم الصف / النظام (تحجيم تلقائي ذكي حتى لا يلمس الإطار الأيسر أبداً)
    for c_sz in (31, 28, 25, 22):
        f_cohort = load_font(c_sz, "Black")
        cb = draw.textbbox((0, 0), sanitize_for_cairo(cohort_title), font=f_cohort, direction="rtl", language="ar")
        if (cb[2] - cb[0]) <= 825:
            break
    draw_right_rtl(draw, cohort_title, 905, 98, f_cohort, WHITE)

    # الأسبوع / التقييم + التاريخ
    f_sub = load_font(21, "Bold")
    draw_right_rtl(draw, f"{mode_badge}  |  {date_label}", 905, 148, f_sub, TEAL)

    # شريط التقدم في المنهج
    bar_x1, bar_x2 = 64, 680
    draw.rounded_rectangle([bar_x1, 194, bar_x2, 212], radius=9, fill=(28, 40, 68))
    fill_w = max(28, int((bar_x2 - bar_x1) * (progress_pct / 100.0)))
    draw.rounded_rectangle([bar_x2 - fill_w, 194, bar_x2, 212], radius=9, fill=TEAL)
    f_pct = load_font(19, "Bold")
    draw_right_rtl(draw, f"إنجاز المنهج: {progress_pct}%", 905, 187, f_pct, MUTED)

    # ---------------- 2) منطقة الأقسام / المسارات / الدروس ----------------
    top_area = 250
    bottom_area = 1196
    avail_h = bottom_area - top_area
    n = max(1, len(sections))
    gap = 12 if n >= 4 else 16
    box_h = (avail_h - gap * (n - 1)) // n

    # أحجام الخطوط حسب عدد الأقسام في البطاقة (٢ أو ٣ أو ٤ أو ٥ أقسام)
    if n >= 5:
        f_tag = load_font(20, "ExtraBold")
        f_part = load_font(19, "Bold")
        f_lesson = load_font(22, "Bold")
        f_detail = load_font(19, "SemiBold")
        max_detail_lines = 2
    elif n == 4:
        f_tag = load_font(22, "ExtraBold")
        f_part = load_font(20, "Bold")
        f_lesson = load_font(24, "Bold")
        f_detail = load_font(21, "SemiBold")
        max_detail_lines = 2
    elif n == 3:
        f_tag = load_font(24, "ExtraBold")
        f_part = load_font(21, "Bold")
        f_lesson = load_font(26, "Bold")
        f_detail = load_font(22, "SemiBold")
        max_detail_lines = 3
    else:
        f_tag = load_font(26, "ExtraBold")
        f_part = load_font(22, "Bold")
        f_lesson = load_font(29, "Bold")
        f_detail = load_font(24, "SemiBold")
        max_detail_lines = 4

    cur_y = top_area
    for idx, sec in enumerate(sections):
        acc = SECTION_ACCENTS[idx % len(SECTION_ACCENTS)]
        draw.rounded_rectangle([38, cur_y, W - 38, cur_y + box_h], radius=22, fill=BG_CARD, outline=acc, width=2)
        # شريط جانبي ملون على اليمين
        draw.rounded_rectangle([W - 50, cur_y + 12, W - 40, cur_y + box_h - 12], radius=5, fill=acc)

        # شارة الجزء الكام في أقصى اليسار العلوي
        part_txt = sanitize_for_cairo(sec.get("part", "الدرس كامل"))
        pb = draw.textbbox((0, 0), part_txt, font=f_part, direction="rtl", language="ar")
        pw = (pb[2] - pb[0]) + 28
        ph = 36 if n >= 4 else 40
        draw.rounded_rectangle([58, cur_y + 12, 58 + pw, cur_y + 12 + ph], radius=12, fill=(28, 43, 74), outline=acc, width=1)
        draw_centered_rtl(draw, part_txt, 58 + pw // 2, cur_y + 13, f_part, acc)

        # عنوان المسار / الشعبة + المادة على اليمين
        track_hdr = f"{sec.get('track_label', '')}  |  {sec.get('subject', '')}".strip(" |")
        draw_right_rtl(draw, track_hdr, W - 64, cur_y + 10, f_tag, acc)

        # الوحدة + رقم الدرس + عنوان الدرس
        lesson_full = f"{sec.get('unit', '')} — {sec.get('lesson_num', '')}: {sec.get('lesson_title', '')}".strip(" —:")
        l_lines = wrap_arabic_lines(draw, lesson_full, f_lesson, max_width=W - 130)[:2]
        ly = cur_y + (46 if n >= 5 else 52)
        for ln in l_lines:
            draw_right_rtl(draw, ln, W - 64, ly, f_lesson, WHITE)
            ly += (29 if n >= 5 else 34)

        # التفاصيل (المطلوب مذاكرته الصبح أو القوانين والملخص المغرب)
        detail_txt = sec.get("detail", "")
        d_lines = wrap_arabic_lines(draw, detail_txt, f_detail, max_width=W - 130)[:max_detail_lines]
        dy = ly + 4
        for dl in d_lines:
            if dy + 26 > cur_y + box_h - 8:
                break
            draw_right_rtl(draw, f"• {dl}", W - 64, dy, f_detail, MUTED)
            dy += (26 if n >= 5 else 31)

        cur_y += box_h + gap

    # ---------------- 3) الفوتر التحفيزي + التوجيه لأول تعليق ----------------
    footer_fill = TEAL if slot_type == "morning" else GOLD
    draw.rounded_rectangle([38, 1212, W - 38, 1322], radius=24, fill=footer_fill)
    f_cta1 = load_font(25, "Black")
    f_cta2 = load_font(22, "ExtraBold")
    draw_centered_rtl(draw, footer_cta, W // 2, 1222, f_cta1, NAVY_TEXT)
    draw_centered_rtl(draw, "منصة ثانويتي بلس: thanaweya-ashy.vercel.app  (الرابط المباشر في أول تعليق)", W // 2, 1268, f_cta2, NAVY_TEXT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), format="JPEG", quality=94, optimize=True)
    return out_path


def _generate_chime_audio(wav_path: Path, duration_sec: float) -> None:
    sr = 44100
    n = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    audio = np.zeros_like(t)
    freqs = [523.25, 659.25, 783.99, 1046.50]
    for idx, f in enumerate(freqs):
        start = idx * 0.11
        mask = (t >= start) & (t < start + 1.1)
        tt = t[mask] - start
        audio[mask] += 0.16 * np.sin(2 * np.pi * f * tt) * np.exp(-3.0 * tt)

    for beat in range(2, int(duration_sec)):
        if beat % 8 == 0:
            for idx, f in enumerate([587.33, 880.0]):
                st = beat + idx * 0.08
                mask = (t >= st) & (t < st + 0.55)
                tt = t[mask] - st
                audio[mask] += 0.10 * np.sin(2 * np.pi * f * tt) * np.exp(-4.5 * tt)
        else:
            mask = (t >= beat) & (t < beat + 0.04)
            tt = t[mask] - beat
            audio[mask] += 0.03 * np.sin(2 * np.pi * 880.0 * tt) * np.exp(-45.0 * tt)

    stereo = np.clip(np.column_stack([audio, audio]), -0.95, 0.95)
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def render_cards_short_video(
    card_paths: List[Path],
    out_mp4: Path,
    top_title: str,
    bottom_sub: str,
    sec_per_slide: float = 7.0,
) -> Path:
    """يحوّل البطاقات الأربعة إلى فيديو ريلز/شورتس عمودي 1080×1920 احترافي بالصوت وبذاكرة منخفضة جداً."""
    W, H = 1080, 1920
    fps = 12
    frames_per_slide = int(sec_per_slide * fps)
    fade_frames = max(2, int(0.35 * fps))
    total_dur = len(card_paths) * sec_per_slide
    ffmpeg = get_ffmpeg()

    slide_arrays: List[np.ndarray] = []
    for idx, cp in enumerate(card_paths):
        bg = make_brand_background(W, H)
        paste_logo(bg, W - 148, 56, size=94)
        draw = ImageDraw.Draw(bg)
        f_top = load_font(36, "Black")
        f_sub = load_font(25, "Bold")
        draw_right_rtl(draw, top_title, W - 165, 62, f_top, TEAL)
        draw_right_rtl(draw, f"{bottom_sub}  •  بطاقة ({idx + 1} من {len(card_paths)})", W - 165, 116, f_sub, GOLD)

        card_img = Image.open(cp).convert("RGB").resize((1000, 1250), Image.Resampling.LANCZOS)
        bg.paste(card_img, (40, 210))

        dot_total_w = len(card_paths) * 34
        start_x = (W - dot_total_w) // 2
        for d_i in range(len(card_paths)):
            cx = start_x + d_i * 34
            col = TEAL if d_i == idx else (55, 72, 108)
            draw.ellipse([cx, 1500, cx + 18, 1518], fill=col)

        draw.rounded_rectangle([54, 1554, W - 54, 1796], radius=28, fill=BG_CARD, outline=TEAL, width=2)
        f_b1 = load_font(30, "ExtraBold")
        f_b2 = load_font(25, "Bold")
        draw_centered_rtl(draw, "ثبّت الفيديو وادخل دلوقتي على منصة ثانويتي بلس!", W // 2, 1580, f_b1, WHITE)
        draw_centered_rtl(draw, "جدول مهام • بنك أسئلة • مصحح تمارين • كروت أنكي • مدرس ذكي", W // 2, 1642, f_b2, GOLD)
        draw_centered_rtl(draw, "الرابط المباشر في أول تعليق وفي البايو أعلى الحساب", W // 2, 1706, f_b2, TEAL)

        slide_arrays.append(np.asarray(bg, dtype=np.uint8))

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "chime.wav"
        _generate_chime_audio(wav_path, total_dur)

        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(fps),
            "-i", "-",
            "-i", str(wav_path),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-threads", "2",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(out_mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        for arr in slide_arrays:
            raw_full = arr.tobytes()
            for fi in range(frames_per_slide):
                if fi < fade_frames:
                    alpha = (fi + 1) / float(fade_frames)
                    proc.stdin.write((arr.astype(np.float32) * alpha).astype(np.uint8).tobytes())
                elif fi >= frames_per_slide - fade_frames:
                    alpha = (frames_per_slide - fi) / float(fade_frames)
                    proc.stdin.write((arr.astype(np.float32) * alpha).astype(np.uint8).tobytes())
                else:
                    proc.stdin.write(raw_full)

        proc.stdin.close()
        stderr_out = proc.stderr.read() if proc.stderr else b""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg short failed ({ret}): {stderr_out.decode('utf-8', errors='ignore')[-400:]}")
    return out_mp4


def _generate_countdown_30s_wav(wav_path: Path) -> None:
    sr = 44100
    dur = 30.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    audio = np.zeros_like(t)

    for idx, f in enumerate([523.25, 659.25, 783.99]):
        st = idx * 0.08
        m = (t >= st) & (t < st + 0.5)
        tt = t[m] - st
        audio[m] += 0.18 * np.sin(2 * np.pi * f * tt) * np.exp(-5.0 * tt)

    for sec in range(1, 30):
        urgent = sec >= 25
        freq = 1320.0 if urgent else (980.0 if sec % 2 == 0 else 820.0)
        amp = 0.22 if urgent else 0.11
        m = (t >= sec) & (t < sec + 0.06)
        tt = t[m] - sec
        audio[m] += amp * np.sin(2 * np.pi * freq * tt) * np.exp(-42.0 * tt)
        if urgent:
            m2 = (t >= sec + 0.5) & (t < sec + 0.55)
            tt2 = t[m2] - (sec + 0.5)
            audio[m2] += 0.14 * np.sin(2 * np.pi * 1560.0 * tt2) * np.exp(-45.0 * tt2)

    m_end = t >= 29.25
    tt_end = t[m_end] - 29.25
    audio[m_end] += (
        0.25 * np.sin(2 * np.pi * 880.0 * tt_end)
        + 0.18 * np.sin(2 * np.pi * 1318.5 * tt_end)
    ) * np.exp(-3.2 * tt_end)

    stereo = np.clip(np.column_stack([audio, audio]), -0.95, 0.95)
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def render_countdown_quiz_video(
    out_mp4: Path,
    grade_label: str,
    lesson_label: str,
    part_label: str,
    question_text: str,
    choices: List[str],
) -> Path:
    """
    ينتج فيديو تحدي السهرة 30 ثانية (1080×1920) بالهوية والشعار الرسمي لثانويتي بلس:
    - مكتوب عليه بوضوح: الصف/المسار + المادة والوحدة ورقم الدرس + الجزء الكام + السؤال والـ 4 اختيارات
    - مؤقت نيون حيّ يعد تنازلياً من 30 إلى 0 بالصوت وجرس النهاية
    - بدون كشف الإجابة نهائياً!
    """
    W, H = 1080, 1920
    fps = 15
    total_frames = 30 * fps
    ffmpeg = get_ffmpeg()

    base = make_brand_background(W, H)
    draw = ImageDraw.Draw(base)

    # 1) بطاقة الهيدر (المنصة + الصف والمسار + الدرس والجزء + الشعار الرسمي)
    draw.rounded_rectangle([38, 36, W - 38, 326], radius=28, fill=BG_CARD, outline=TEAL, width=3)
    paste_logo(base, W - 144, 52, size=88)
    draw = ImageDraw.Draw(base)
    f_top = load_font(22, "Bold")
    draw.rounded_rectangle([62, 52, 886, 96], radius=16, fill=(22, 42, 62), outline=GOLD_DARK, width=1)
    draw_centered_rtl(draw, f"سهرة تحدي الـ ٣٠ ثانية  |  {part_label}", 474, 56, f_top, GOLD)

    for g_sz in (29, 26, 23):
        f_grade = load_font(g_sz, "Black")
        gb = draw.textbbox((0, 0), sanitize_for_cairo(grade_label), font=f_grade, direction="rtl", language="ar")
        if (gb[2] - gb[0]) <= 825:
            break
    draw_right_rtl(draw, grade_label, 895, 108, f_grade, TEAL)

    f_lesson = load_font(25, "Bold")
    l_lines = wrap_arabic_lines(draw, lesson_label, f_lesson, max_width=W - 140)[:2]
    ly = 166
    for ln in l_lines:
        draw_centered_rtl(draw, ln, W // 2, ly, f_lesson, WHITE)
        ly += 38

    # شارات تحفيزية يمين ويسار العداد
    f_side = load_font(23, "Bold")
    draw.rounded_rectangle([54, 456, 356, 526], radius=18, fill=BG_CARD, outline=VIOLET, width=2)
    draw_centered_rtl(draw, "تحدي ٣٠ ثانية", 205, 468, f_side, WHITE)
    draw.rounded_rectangle([W - 356, 456, W - 54, 526], radius=18, fill=BG_CARD, outline=GOLD, width=2)
    draw_centered_rtl(draw, "جاوب بنفسك!", W - 205, 468, f_side, GOLD)

    # 2) صندوق السؤال
    draw.rounded_rectangle([42, 666, W - 42, 1042], radius=30, fill=BG_CARD, outline=GOLD, width=3)
    draw.rounded_rectangle([240, 642, W - 240, 704], radius=18, fill=GOLD)
    f_qhdr = load_font(26, "Black")
    draw_centered_rtl(draw, "سؤال الليلة — جاوب قبل الجرس!", W // 2, 650, f_qhdr, NAVY_TEXT)

    for q_size in (35, 31, 28, 25):
        f_q = load_font(q_size, "ExtraBold")
        q_lines = wrap_arabic_lines(draw, question_text, f_q, max_width=W - 150)
        if len(q_lines) <= 4:
            break
    q_lines = q_lines[:4]
    total_qh = len(q_lines) * (q_size + 18)
    qy = 720 + max(0, (300 - total_qh) // 2)
    for ln in q_lines:
        draw_centered_rtl(draw, ln, W // 2, qy, f_q, WHITE)
        qy += q_size + 18

    # 3) صناديق الاختيارات الأربعة (أ - ب - ج - د) بدون تظليل أي إجابة
    labels_ar = ["أ", "ب", "ج", "د"]
    opt_y = 1072
    f_badge = load_font(32, "Black")
    for idx in range(4):
        raw_c = choices[idx] if idx < len(choices) else ""
        for pfx in ("أ)", "ب)", "ج)", "د)", "أ-", "ب-", "ج-", "د-", "أ :", "ب :", "ج :", "د :"):
            if raw_c.strip().startswith(pfx):
                raw_c = raw_c.strip()[len(pfx):].strip()
        box_top = opt_y + idx * 144
        box_bot = box_top + 126
        draw.rounded_rectangle([54, box_top, W - 54, box_bot], radius=24, fill=BG_CARD, outline=(48, 86, 128), width=2)
        draw.rounded_rectangle([W - 166, box_top + 18, W - 76, box_bot - 18], radius=18, fill=(22, 46, 68), outline=TEAL, width=2)
        draw_centered_rtl(draw, labels_ar[idx], W - 121, box_top + 32, f_badge, TEAL)

        for c_size in (29, 25, 22):
            f_c = load_font(c_size, "Bold")
            c_lines = wrap_arabic_lines(draw, raw_c, f_c, max_width=W - 260)
            if len(c_lines) <= 2:
                break
        c_lines = c_lines[:2]
        cy = box_top + (38 if len(c_lines) == 1 else 18)
        for cl in c_lines:
            draw_centered_rtl(draw, cl, (W - 120) // 2, cy, f_c, WHITE)
            cy += c_size + 10

    # 4) الفوتر التحفيزي + الإشارة لأول تعليق
    draw.rounded_rectangle([42, 1672, W - 42, 1872], radius=28, fill=TEAL)
    f_cta1 = load_font(29, "Black")
    f_cta2 = load_font(24, "ExtraBold")
    draw_centered_rtl(draw, "اكتب رمز إجابتك الصح ( أ - ب - ج - د ) واسم شعبتك في التعليقات!", W // 2, 1692, f_cta1, NAVY_TEXT)
    draw_centered_rtl(draw, "وصوّر حلك لمصحح التمارين على ثانويتي بلس (الرابط في أول تعليق)", W // 2, 1768, f_cta2, NAVY_TEXT)

    f_num = load_font(86, "Black")
    f_sec_lbl = load_font(24, "Bold")
    cx, cy_ring = W // 2, 490
    ring_r = 122

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "timer30.wav"
        _generate_countdown_30s_wav(wav_path)

        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(fps),
            "-i", "-",
            "-i", str(wav_path),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(out_mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        for frame_idx in range(total_frames):
            t_elapsed = frame_idx / float(fps)
            rem = max(0.0, 30.0 - t_elapsed)
            sec_int = int(math.ceil(rem)) if rem > 0.05 else 0
            frac = rem / 30.0

            frame = base.copy()
            fd = ImageDraw.Draw(frame)

            urgent = sec_int <= 5
            ring_color = RED_NEON if urgent else (GOLD if sec_int <= 10 else TEAL)

            fd.ellipse([cx - ring_r - 12, cy_ring - ring_r - 12, cx + ring_r + 12, cy_ring + ring_r + 12], fill=(15, 24, 44), outline=(36, 56, 88), width=3)
            bbox_arc = [cx - ring_r, cy_ring - ring_r, cx + ring_r, cy_ring + ring_r]
            fd.arc(bbox_arc, start=0, end=360, fill=(32, 46, 74), width=16)
            if frac > 0.002:
                end_angle = -90 + 360.0 * frac
                fd.arc(bbox_arc, start=-90, end=end_angle, fill=ring_color, width=16)

            num_str = str(sec_int)
            nb = fd.textbbox((0, 0), num_str, font=f_num)
            nw = nb[2] - nb[0]
            fd.text((cx - nw // 2, cy_ring - 68), num_str, font=f_num, fill=(RED_NEON if urgent else WHITE))
            draw_centered_rtl(fd, "انتهى الوقت!" if sec_int == 0 else "ثانية", cx, cy_ring + 36, f_sec_lbl, ring_color)

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        stderr_out = proc.stderr.read() if proc.stderr else b""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg failed ({ret}): {stderr_out.decode('utf-8', errors='ignore')[-500:]}")

    return out_mp4
