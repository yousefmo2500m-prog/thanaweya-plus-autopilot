# -*- coding: utf-8 -*-
"""
محرك التصميم والمونتاج المحلي (صفر تكلفة - بدون أي مواقع خارجية)
يرسم بطاقات 1080x1350 وفيديوهات 1080x1920 بالخط العربي الأصلي (Cairo) ومؤثرات صوتية احترافية.
"""

import os
import math
import wave
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "fonts", "Cairo-Variable.ttf")


def get_ffmpeg() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_cairo(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_FILE, size)
    try:
        f.set_variation_by_name(weight.encode("utf-8") if isinstance(weight, str) else weight)
    except Exception:
        pass
    return f


def sanitize_math_for_cairo(text: str) -> str:
    """استبدال الرموز اليونانية غير الموجودة في خط Cairo بمرادفاتها العربية الواضحة."""
    if not text:
        return ""
    swaps = [
        ("∑", "مجموع "), ("Σ", "مجموع "),
        ("Δ", "دلتا "), ("∆", "دلتا "),
        ("θ", "سيتا"), ("π", "ط"),
        ("Ω", " أوم"), ("μ", "ميكرو "),
        ("→", " ← "), ("↔", " = "),
        ("≈", "="), ("≠", " لا يساوي "),
        ("≤", " أقل أو يساوي "), ("≥", " أكبر أو يساوي "),
    ]
    out = text
    for k, v in swaps:
        out = out.replace(k, v)
    return out


def wrap_arabic(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 3) -> list[str]:
    """تقسيم النص العربي بذكاء حسب العرض الفعلي بالبيكسل لمنع أي خروج للنص خارج الإطار."""
    words = sanitize_math_for_cairo(text or "").replace("\n", " ").split()
    if not words:
        return [""]
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        kept = lines[:max_lines - 1]
        tail = " ".join(lines[max_lines - 1:])
        while len(tail) > 10:
            bbox = draw.textbbox((0, 0), tail + "…", font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
            tail = " ".join(tail.split()[:-1])
        kept.append(tail + ("…" if tail != lines[max_lines - 1] else ""))
        return kept
    return lines


def draw_centered_multiline(draw: ImageDraw.ImageDraw, lines: list[str], cx: int, cy: int, font: ImageFont.FreeTypeFont, fill: tuple, line_gap: int = 12):
    heights = []
    for ln in lines:
        bb = draw.textbbox((0, 0), ln or " ", font=font)
        heights.append(bb[3] - bb[1])
    total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = cy - total_h // 2
    for ln, h in zip(lines, heights):
        draw.text((cx, y + h // 2), ln, font=font, fill=fill, anchor="mm")
        y += h + line_gap


def make_studio_bg(w: int, h: int, accent_rgb: tuple = (56, 189, 248), glow_y: float = 0.35) -> Image.Image:
    y_idx = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    x_idx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[:, :, 0] = 7 + 9 * np.sin(np.pi * y_idx)
    arr[:, :, 1] = 12 + 15 * np.sin(np.pi * y_idx)
    arr[:, :, 2] = 26 + 26 * np.sin(np.pi * y_idx)

    dist2 = ((x_idx * w - w * 0.5) ** 2 + (y_idx * h - h * glow_y) ** 2) / ((w * 0.42) ** 2)
    glow = np.exp(-dist2)
    arr[:, :, 0] += accent_rgb[0] * 0.16 * glow
    arr[:, :, 1] += accent_rgb[1] * 0.16 * glow
    arr[:, :, 2] += accent_rgb[2] * 0.18 * glow

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for gx in range(60, w, 120):
        d.line([(gx, 0), (gx, h)], fill=accent_rgb + (12,), width=1)
    for gy in range(60, h, 120):
        d.line([(0, gy), (w, gy)], fill=accent_rgb + (12,), width=1)
    return img


def build_chime_wav(wav_path: str, duration_s: int, style: str = "morning"):
    sr = 44100
    total = sr * duration_s
    audio = np.zeros(total, dtype=np.float32)

    def note(t0, dur, freqs, amp=0.22, decay=6.0):
        i0 = int(t0 * sr)
        n = min(int(dur * sr), total - i0)
        if n <= 0:
            return
        t = np.arange(n, dtype=np.float32) / sr
        env = np.exp(-decay * t) * (1.0 - np.exp(-250.0 * t))
        sig = sum(w * np.sin(2.0 * np.pi * f * t) for f, w in freqs)
        audio[i0:i0 + n] += amp * sig * env

    if style == "morning":
        # نغمة صباحية مشرقة عند بداية كل شريحة صف دراسي + نبضة هادئة
        chords = [0.05, 8.0, 16.0]
        for c in chords:
            if c < duration_s:
                note(c, 0.7, [(523.25, 0.5), (659.25, 0.35), (783.99, 0.3)], amp=0.28, decay=4.5)
                note(c + 0.18, 0.7, [(659.25, 0.45), (1046.5, 0.35)], amp=0.24, decay=4.5)
        for s in range(duration_s):
            note(s, 0.07, [(440.0 if s % 2 == 0 else 554.37, 0.6)], amp=0.07, decay=28.0)
    elif style == "maghrib":
        chords = [0.05, 9.0, 18.0]
        for c in chords:
            if c < duration_s:
                note(c, 0.8, [(440.0, 0.5), (523.25, 0.35), (659.25, 0.3)], amp=0.26, decay=4.0)
        for s in range(duration_s):
            note(s, 0.08, [(392.0 if s % 2 == 0 else 493.88, 0.6)], amp=0.07, decay=26.0)
    else:
        # مؤقت الـ 30 ثانية التنافسي بالتكتكة والعد السريع في آخر 5 ثوانٍ وجرس النهاية
        for sec in range(duration_s):
            rem = duration_s - sec
            if rem > 10:
                f_m = 880.0 if sec % 2 == 0 else 660.0
                note(sec, 0.09, [(f_m, 0.7), (f_m * 2, 0.3)], amp=0.24, decay=35.0)
            elif rem > 5:
                f_m = 987.77 if sec % 2 == 0 else 783.99
                note(sec, 0.11, [(f_m, 0.7), (f_m * 2, 0.3)], amp=0.30, decay=30.0)
            else:
                note(sec, 0.14, [(1046.5, 0.65), (2093.0, 0.25), (523.25, 0.3)], amp=0.38, decay=22.0)
                if sec < duration_s - 1:
                    note(sec + 0.5, 0.09, [(783.99, 0.7), (1567.98, 0.3)], amp=0.24, decay=32.0)
        note(duration_s - 0.55, 0.54, [(523.25, 0.45), (659.25, 0.35), (783.99, 0.35), (1046.5, 0.25)], amp=0.45, decay=5.5)

    pcm = (np.clip(audio, -0.95, 0.95) * 32767.0).astype(np.int16)
    stereo = np.column_stack([pcm, pcm]).ravel()
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo.tobytes())


def _draw_study_or_summary_card(
    w: int, h: int,
    slot_type: str,  # "morning" or "maghrib"
    grade_info: dict,
    ai_card: dict,
    ctx: dict,
    slide_idx: int = 0
) -> Image.Image:
    is_morning = (slot_type == "morning")
    accent = (56, 189, 248) if is_morning else (251, 191, 36)
    accent2 = (16, 185, 129) if is_morning else (56, 189, 248)

    img = make_studio_bg(w, h, accent_rgb=accent, glow_y=0.32)
    d = ImageDraw.Draw(img, "RGBA")

    f_badge = load_cairo(26 if h < 1500 else 28, "ExtraBold")
    f_grade = load_cairo(32 if h < 1500 else 36, "Black")
    f_sub = load_cairo(25 if h < 1500 else 28, "Bold")
    f_lesson = load_cairo(27 if h < 1500 else 30, "ExtraBold")
    f_item = load_cairo(25 if h < 1500 else 28, "Bold")
    f_cta = load_cairo(24 if h < 1500 else 27, "ExtraBold")
    f_small = load_cairo(21 if h < 1500 else 23, "Bold")

    top_y = 42 if h < 1500 else 95
    # 1. Header Card
    hdr_h = 260 if h < 1500 else 300
    d.rounded_rectangle([48, top_y, w - 48, top_y + hdr_h], radius=28, fill=(15, 23, 42, 240), outline=accent + (220,), width=3)

    pill_txt = "ثانويتي بلس  •  جدول ومهمة اليوم الصباحية" if is_morning else "ثانويتي بلس  •  كبسولة الملخص والقوانين الذهبية"
    d.rounded_rectangle([180, top_y + 18, w - 180, top_y + 68], radius=18, fill=accent + (38,), outline=accent + (180,), width=2)
    d.text((w // 2, top_y + 43), pill_txt, font=f_badge, fill=accent + (255,), anchor="mm")

    d.text((w // 2, top_y + 112), grade_info["grade_title"], font=f_grade, fill=(255, 255, 255, 255), anchor="mm")
    d.text((w // 2, top_y + 162), ctx["mode_badge"], font=f_small, fill=accent2 + (245,), anchor="mm")

    # Progress bar inside header
    pct = ctx["progress_pct"]
    bar_x1, bar_x2 = 110, w - 110
    bar_y = top_y + hdr_h - 46
    d.rounded_rectangle([bar_x1, bar_y, bar_x2, bar_y + 22], radius=11, fill=(30, 41, 59, 255))
    fill_w = max(24, int((bar_x2 - bar_x1) * (pct / 100.0)))
    d.rounded_rectangle([bar_x2 - fill_w, bar_y, bar_x2, bar_y + 22], radius=11, fill=accent2 + (255,))
    d.text((w // 2, bar_y - 18), f"نسبة إنجاز خطة التقفيل: {pct}%  |  التاريخ: {ctx['date_str']}", font=f_small, fill=(203, 213, 225, 240), anchor="mm")

    # 2. Lesson Banner Card
    les_y = top_y + hdr_h + (24 if h < 1500 else 36)
    les_h = 205 if h < 1500 else 235
    d.rounded_rectangle([48, les_y, w - 48, les_y + les_h], radius=26, fill=(30, 41, 59, 238), outline=accent2 + (190,), width=2)
    subj_line = f"{grade_info['subject']}  •  {grade_info['unit']}"
    subj_wrapped = wrap_arabic(d, subj_line, f_sub, w - 150, max_lines=1)
    d.text((w // 2, les_y + 42), subj_wrapped[0], font=f_sub, fill=accent + (255,), anchor="mm")

    les_lines = wrap_arabic(d, grade_info["lesson"], f_lesson, w - 150, max_lines=2)
    draw_centered_multiline(d, les_lines, w // 2, les_y + 112, f_lesson, (255, 255, 255, 255), line_gap=8)

    meta_pill = f"نوع المهمة: {grade_info['type']}   |   المقترح: {grade_info['pomodoros']} جلسات بومودورو" if is_morning else f"ملخص مركز وقوانين وتريكات الامتحان  •  شريحة ({slide_idx + 1}/3)"
    d.rounded_rectangle([130, les_y + les_h - 48, w - 130, les_y + les_h - 12], radius=12, fill=(15, 23, 42, 220))
    d.text((w // 2, les_y + les_h - 30), meta_pill, font=f_small, fill=(251, 191, 36, 255), anchor="mm")

    # 3. Three / Four Action or Law Points
    pts = ai_card.get("points", [])[:4]
    pts_y = les_y + les_h + (24 if h < 1500 else 36)
    avail_bottom = h - (185 if h < 1500 else 255)
    n_pts = max(1, len(pts))
    gap = 16 if h < 1500 else 22
    box_h = (avail_bottom - pts_y - gap * (n_pts - 1)) // n_pts

    for i, pt in enumerate(pts):
        by1 = pts_y + i * (box_h + gap)
        by2 = by1 + box_h
        d.rounded_rectangle([56, by1, w - 56, by2], radius=22, fill=(15, 23, 42, 235), outline=(56, 189, 248, 120) if i % 2 == 0 else (251, 191, 36, 130), width=2)
        # Number badge on the right (RTL)
        d.ellipse([w - 136, (by1 + by2) // 2 - 28, w - 80, (by1 + by2) // 2 + 28], fill=accent + (245,))
        d.text((w - 108, (by1 + by2) // 2), str(i + 1), font=f_sub, fill=(15, 23, 42, 255), anchor="mm")

        lines = wrap_arabic(d, pt, f_item, w - 230, max_lines=2)
        draw_centered_multiline(d, lines, (w - 90) // 2, (by1 + by2) // 2, f_item, (248, 250, 252, 255), line_gap=6)

    # 4. Bottom CTA Banner
    cta_y1 = h - (158 if h < 1500 else 215)
    cta_y2 = h - (36 if h < 1500 else 75)
    d.rounded_rectangle([48, cta_y1, w - 48, cta_y2], radius=24, fill=(251, 191, 36, 255), outline=(245, 158, 11, 255), width=3)
    cta_line1 = "ابدأ جلسات البومودورو وسجّل مهامك الآن مجاناً!" if is_morning else "احفظ القوانين على كروت أنكي واسأل المدرس الذكي مجاناً!"
    cta_line2 = "ادخل الآن على موقعنا:   thanaweya-ashy.vercel.app"
    d.text((w // 2, cta_y1 + (cta_y2 - cta_y1) * 0.34), cta_line1, font=f_cta, fill=(15, 23, 42, 255), anchor="mm")
    d.text((w // 2, cta_y1 + (cta_y2 - cta_y1) * 0.72), cta_line2, font=f_cta, fill=(15, 23, 42, 255), anchor="mm")

    return img


def render_slides_and_short(slot_type: str, ctx: dict, ai_cards: list[dict], out_dir: str, tag: str) -> dict:
    """يرسم 3 صور ألبوم (1080x1350) + فيديو ريلز/شورتس متحرك (1080x1920) يجمع الصفوف الثلاثة."""
    os.makedirs(out_dir, exist_ok=True)
    jpg_paths = []
    vert_slides = []

    for idx, g_info in enumerate(ctx["grades"]):
        card_data = ai_cards[idx] if idx < len(ai_cards) else {"points": []}
        # 1. Album card 1080x1350
        img_album = _draw_study_or_summary_card(1080, 1350, slot_type, g_info, card_data, ctx, idx)
        p_jpg = os.path.join(out_dir, f"{slot_type}_{tag}_g{idx + 1}.jpg")
        img_album.save(p_jpg, "JPEG", quality=93, optimize=True)
        jpg_paths.append(p_jpg)

        # 2. Vertical video slide 1080x1920
        img_vert = _draw_study_or_summary_card(1080, 1920, slot_type, g_info, card_data, ctx, idx)
        vert_slides.append(img_vert)

    # Render animated 1080x1920 MP4 (8s per slide morning = 24s, 9s per slide maghrib = 27s)
    sec_per_slide = 8 if slot_type == "morning" else 9
    total_dur = sec_per_slide * 3
    fps = 30
    total_frames = total_dur * fps

    wav_path = f"/tmp/{slot_type}_{tag}.wav"
    build_chime_wav(wav_path, total_dur, style=slot_type)

    mp4_path = os.path.join(out_dir, f"{slot_type}_{tag}_short.mp4")
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", "1080x1920", "-pix_fmt", "rgb24", "-r", str(fps),
        "-i", "-",
        "-i", wav_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        mp4_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    f_tab = load_cairo(22, "ExtraBold")
    tab_labels = ["١ ث", "٢ ث", "٣ ث"]

    for f_i in range(total_frames):
        t = f_i / fps
        s_idx = min(2, int(t // sec_per_slide))
        local_t = t - s_idx * sec_per_slide
        local_frac = local_t / sec_per_slide

        frame = vert_slides[s_idx].copy()
        d = ImageDraw.Draw(frame, "RGBA")

        # Top story-style progress bars for the 3 grades!
        for k in range(3):
            bx1 = 60 + k * 326
            bx2 = bx1 + 308
            d.rounded_rectangle([bx1, 36, bx2, 50], radius=7, fill=(30, 41, 59, 220))
            if k < s_idx:
                d.rounded_rectangle([bx1, 36, bx2, 50], radius=7, fill=(56, 189, 248, 255))
            elif k == s_idx:
                pw = max(14, int(308 * local_frac))
                d.rounded_rectangle([bx2 - pw, 36, bx2, 50], radius=7, fill=(251, 191, 36, 255))
            d.text(((bx1 + bx2) // 2, 68), tab_labels[k], font=f_tab, fill=(251, 191, 36, 255) if k == s_idx else (148, 163, 184, 200), anchor="mm")

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return {"jpg_paths": jpg_paths, "mp4_path": mp4_path}


def render_night_countdown_video(ctx: dict, quiz_data: dict, out_dir: str, tag: str) -> str:
    """
    ينشئ فيديو تحدي الـ 30 ثانية الاحترافي (1080x1920 - 30fps - عداد تنازلي نيون حي + صوت تكتكة وجرس)
    مع كتابة الصف والنظام (الثانوية العامة والبكالوريا) واسم الدرس والسؤال والاختيارات بدون الإجابة نهائياً!
    """
    os.makedirs(out_dir, exist_ok=True)
    w, h = 1080, 1920
    fps = 30
    duration = 30
    total_frames = fps * duration

    # 1. Pre-render static base frame (everything except the animated timer band y=330..650)
    base = make_studio_bg(w, h, accent_rgb=(56, 189, 248), glow_y=0.255)
    d = ImageDraw.Draw(base, "RGBA")

    f_brand = load_cairo(25, "ExtraBold")
    f_grade = load_cairo(29, "Black")
    f_lesson = load_cairo(25, "Bold")
    f_qbadge = load_cairo(24, "ExtraBold")
    f_q = load_cairo(35, "ExtraBold")
    f_opt = load_cairo(32, "Bold")
    f_cta = load_cairo(27, "ExtraBold")

    # Header Card (y: 38..315)
    d.rounded_rectangle([44, 38, w - 44, 315], radius=28, fill=(15, 23, 42, 242), outline=(56, 189, 248, 235), width=3)
    hdr_pill = "ثانويتي بلس  •  تحدي التقييم الأسبوعي (٣٠ ثانية)" if ctx["day_mode"] == "weekly_assessment" else "منصة ثانويتي بلس  •  تحدي السهرة (٣٠ ثانية)"
    d.rounded_rectangle([185, 54, w - 185, 104], radius=16, fill=(251, 191, 36, 40), outline=(251, 191, 36, 200), width=2)
    d.text((w // 2, 79), hdr_pill, font=f_brand, fill=(251, 191, 36, 255), anchor="mm")

    d.rounded_rectangle([72, 116, w - 72, 196], radius=16, fill=(56, 189, 248, 35), outline=(56, 189, 248, 120), width=2)
    d.text((w // 2, 156), quiz_data["grade_label"], font=f_grade, fill=(56, 189, 248, 255), anchor="mm")

    les_lines = wrap_arabic(d, quiz_data["lesson_label"], f_lesson, w - 150, max_lines=2)
    draw_centered_multiline(d, les_lines, w // 2, 254, f_lesson, (241, 245, 249, 255), line_gap=4)

    # Question Card (y: 662..1030)
    d.rounded_rectangle([44, 662, w - 44, 1030], radius=28, fill=(15, 23, 42, 244), outline=(251, 191, 36, 235), width=3)
    d.rounded_rectangle([260, 662, w - 260, 726], radius=16, fill=(251, 191, 36, 255))
    d.text((w // 2, 694), "سؤال التحدي — جاوب قبل انتهاء الوقت!", font=f_qbadge, fill=(15, 23, 42, 255), anchor="mm")

    q_lines = wrap_arabic(d, quiz_data["question_text"], f_q, w - 160, max_lines=3)
    draw_centered_multiline(d, q_lines, w // 2, 875, f_q, (255, 255, 255, 255), line_gap=10)

    # 4 Option Buttons (y: 1064..1640)
    letters = ["أ", "ب", "ج", "د"]
    choices = [quiz_data["choice_a"], quiz_data["choice_b"], quiz_data["choice_c"], quiz_data["choice_d"]]
    for idx_opt, (ltr, ch_txt) in enumerate(zip(letters, choices)):
        oy1 = 1064 + idx_opt * 146
        oy2 = oy1 + 124
        d.rounded_rectangle([54, oy1, w - 54, oy2], radius=22, fill=(30, 41, 59, 242), outline=(56, 189, 248, 195), width=2)
        # Right letter pill
        d.rounded_rectangle([w - 166, oy1 + 18, w - 76, oy2 - 18], radius=16, fill=(56, 189, 248, 45), outline=(56, 189, 248, 180), width=2)
        d.text((w - 121, (oy1 + oy2) // 2), ltr, font=f_opt, fill=(56, 189, 248, 255), anchor="mm")

        ch_lines = wrap_arabic(d, ch_txt, f_opt, w - 280, max_lines=1)
        d.text(((w - 120) // 2, (oy1 + oy2) // 2), ch_lines[0], font=f_opt, fill=(248, 250, 252, 255), anchor="mm")

    # Bottom Gold CTA Banner (y: 1680..1850)
    d.rounded_rectangle([44, 1680, w - 44, 1852], radius=26, fill=(251, 191, 36, 255), outline=(245, 158, 11, 255), width=3)
    d.text((w // 2, 1734), "اكتب رمز إجابتك الصح ( أ - ب - ج - د ) في التعليقات!", font=f_cta, fill=(15, 23, 42, 255), anchor="mm")
    d.text((w // 2, 1798), "صوّر حلك لمصحح التمارين مجاناً:  thanaweya-ashy.vercel.app", font=f_cta, fill=(15, 23, 42, 255), anchor="mm")

    # 2. Audio + 900-frame live timer render (we only copy & draw on the timer band y=320..658 for blazing speed!)
    wav_path = f"/tmp/night_quiz_{tag}.wav"
    build_chime_wav(wav_path, duration, style="countdown")

    mp4_path = os.path.join(out_dir, f"night_{tag}_quiz30s.mp4")
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{w}x{h}", "-pix_fmt", "rgb24", "-r", str(fps),
        "-i", "-",
        "-i", wav_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        mp4_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    f_num = load_cairo(92, "Black")
    f_sec = load_cairo(25, "ExtraBold")
    f_hud = load_cairo(23, "Bold")
    cx, cy = 540, 488

    # Crop clean timer strip for super fast per-frame compositing
    strip_top, strip_bot = 318, 658
    clean_strip = base.crop((0, strip_top, w, strip_bot))

    frame = base.copy()
    for f_i in range(total_frames):
        t = f_i / fps
        rem_exact = max(0.0, duration - t)
        disp_num = 0 if t >= 29.5 else int(math.ceil(rem_exact))
        frac = rem_exact / duration

        if disp_num > 10:
            ring_col = (56, 189, 248)
            glow_col = (56, 189, 248, 55)
        elif disp_num > 5:
            ring_col = (251, 191, 36)
            glow_col = (251, 191, 36, 65)
        else:
            ring_col = (239, 68, 68)
            glow_col = (239, 68, 68, 85)

        beat = t - math.floor(t)
        pulse = math.exp(-6.0 * beat) if disp_num <= 5 else 0.4 * math.exp(-7.0 * beat)
        r_outer = int(130 + 6 * pulse)

        strip = clean_strip.copy()
        sd = ImageDraw.Draw(strip, "RGBA")
        scy = cy - strip_top

        # Left & Right HUD Bars
        sd.rounded_rectangle([60, scy - 32, 365, scy + 32], radius=15, fill=(15, 23, 42, 225), outline=ring_col + (130,), width=2)
        bar_w = int(275 * frac)
        sd.rounded_rectangle([75, scy + 12, 350, scy + 20], radius=4, fill=(30, 41, 59, 220))
        if bar_w > 6:
            sd.rounded_rectangle([75, scy + 12, 75 + bar_w, scy + 20], radius=4, fill=ring_col + (245,))
        sd.text((212, scy - 9), "تحدي ٣٠ ثانية", font=f_hud, fill=(241, 245, 249, 250), anchor="mm")

        sd.rounded_rectangle([715, scy - 32, 1020, scy + 32], radius=15, fill=(15, 23, 42, 225), outline=ring_col + (130,), width=2)
        sd.rounded_rectangle([730, scy + 12, 1005, scy + 20], radius=4, fill=(30, 41, 59, 220))
        if bar_w > 6:
            sd.rounded_rectangle([1005 - bar_w, scy + 12, 1005, scy + 20], radius=4, fill=ring_col + (245,))
        sd.text((867, scy - 9), "بدون غش!", font=f_hud, fill=(241, 245, 249, 250), anchor="mm")

        # Center Neon Timer Ring
        sd.ellipse([cx - r_outer - 12, scy - r_outer - 12, cx + r_outer + 12, scy + r_outer + 12], fill=glow_col)
        sd.ellipse([cx - 130, scy - 130, cx + 130, scy + 130], fill=(15, 23, 42, 248), outline=(30, 41, 59, 255), width=4)
        r_arc = 110
        sd.ellipse([cx - r_arc, scy - r_arc, cx + r_arc, scy + r_arc], outline=(30, 41, 59, 255), width=14)

        if frac > 0.003:
            end_ang = -90.0 + 360.0 * frac
            sd.arc([cx - r_arc, scy - r_arc, cx + r_arc, scy + r_arc], start=-90.0, end=end_ang, fill=ring_col + (255,), width=14)
            rad = math.radians(end_ang)
            tx = cx + r_arc * math.cos(rad)
            ty = scy + r_arc * math.sin(rad)
            sd.ellipse([tx - 9, ty - 9, tx + 9, ty + 9], fill=(255, 255, 255, 255))

        num_col = (255, 255, 255, 255) if disp_num > 5 else (254, 202, 202, 255)
        sd.text((cx, scy - 14), f"{disp_num:02d}", font=f_num, fill=num_col, anchor="mm")
        sub_txt = "انتهى الوقت!" if disp_num == 0 else "ثانية"
        sub_col = (251, 191, 36, 255) if disp_num == 0 else ring_col + (245,)
        sd.text((cx, scy + 52), sub_txt, font=f_sec, fill=sub_col, anchor="mm")

        frame.paste(strip, (0, strip_top))
        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return mp4_path
