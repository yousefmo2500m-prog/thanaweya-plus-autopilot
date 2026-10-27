#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autopilot.py
العقل المركزي المستقل لمنصة «ثانويتي بلس» (https://thanaweya-ashy.vercel.app)
ينتج 3 نشرات يومية مترابطة وثرية جداً تغطي كل صف وكل شعبة والـ 4 مسارات للبكالوريا المصرية بالوحدة ورقم الدرس والجزء:
  - morning : خطة مذاكرة اليوم التفصيلية (4 بطاقات 1080×1350 + فيديو شورتس 32 ثانية + أول تعليق بالرابط)
  - maghrib : كبسولة الملخص والقوانين وتريكات الامتحان لنفس دروس الصباح (4 بطاقات + فيديو شورتس 32 ثانية + أول تعليق)
  - night   : سهرة تحدي الـ 30 ثانية (فيديو عداد تنازلي 30 ثانية بدون الإجابة + أسئلة السهرة لكل الصفوف والمسارات + أول تعليق)
"""

from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

from curriculum_2026_2027 import get_daily_curriculum_plan
from studio_renderer import (
    render_structured_card,
    render_cards_short_video,
    render_countdown_quiz_video,
)

SITE_URL = "https://thanaweya-ashy.vercel.app"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"


def strip_all_digits_for_fb_video(text: str) -> str:
    """
    مهم لمديول فيسبوك UploadVideo v6 فقط: يرفض أي أرقام (0-9 أو ٠-٩) في حقل الوصف.
    نستبدل الأرقام المستقلة فقط بكلمات عربية ونحذف أي أرقام متبقية بأمان.
    """
    out = text.replace("30", "ثلاثين").replace("٣٠", "ثلاثين")
    out = re.sub(r"(?<![A-Za-z])[1١](?![A-Za-z0-9٠-٩])", "الأول", out)
    out = re.sub(r"(?<![A-Za-z])[2٢](?![A-Za-z0-9٠-٩])", "الثاني", out)
    out = re.sub(r"(?<![A-Za-z])[3٣](?![A-Za-z0-9٠-٩])", "الثالث", out)
    out = re.sub(r"(?<![A-Za-z])[4٤](?![A-Za-z0-9٠-٩])", "الرابع", out)
    out = re.sub(r"[0-9٠-٩۰-۹]+", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def call_groq_json(api_key: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.55,
        "max_completion_tokens": 4096,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ThanaweyaPlus-Autopilot/3.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    content = raw["choices"][0]["message"]["content"]
    return json.loads(content)


def _fmt_item_line(item: Dict[str, str], extra_note: str = "") -> str:
    base = (
        f"• {item['subject']}: {item['unit']} — {item['lesson_num']} "
        f"({item['lesson_title']}) ⬅️ [{item['part']}]"
    )
    if extra_note:
        return f"{base}\n  💡 {extra_note}"
    return base


# ==============================================================================
# 1) نشرة الصباح: خطة مذاكرة اليوم التفصيلية لكل صف ومسار بالوحدة والدرس والجزء
# ==============================================================================
def build_morning_slot(plan: Dict[str, Any], api_key: str, out_dir: Path, cdn_base: str) -> Dict[str, Any]:
    cal = plan["calendar"]
    g1, g2_bac, g2_gen, g3 = plan["g1"], plan["g2_bac"], plan["g2_gen"], plan["g3"]
    is_assess = cal["day_mode"] == "weekly_assessment"

    sys_prompt = (
        "أنت كبير مستشاري المناهج في منصة «ثانويتي بلس» لطلاب المرحلة الثانوية في مصر (الثانوية العامة والبكالوريا المصرية). "
        "ممنوع استخدام مصطلح 'بومودورو' كوحدة قياس غامضة مثل (5 بومودورو). "
        "اكتب نصائح مذاكرة عملية مركزة جداً ومفيدة لكل درس محدد (إزاي يذاكر الجزء ده وإيه أهم فكرة يركز عليها ويحل عليها كام سؤال). "
        "أخرج JSON صالح فقط."
    )
    usr_prompt = f"""
التاريخ: {cal['weekday_ar']} {cal['date_ar']} — {cal['mode_badge']}
أخرج JSON بالمفاتيح التالية (كل قيمة سطر أو سطرين عمليين جداً ومباشرين بدون حشو):
{{
  "intro_hook": "افتتاحية حماسية دافئة لطلاب ثانوي في سطرين تشرح هدف النهاردة",
  "g1_main_tip": "إزاي يذاكر طالب أولى ثانوي درس ({g1['main']['subject']} - {g1['main']['lesson_title']} [{g1['main']['part']}]) بذكاء",
  "g1_sec_tip": "إزاي يلم درس ({g1['secondary']['subject']} - {g1['secondary']['lesson_title']} [{g1['secondary']['part']}]) في نصف ساعة",
  "bac_common_tip": "نصيحة سريعة للمادة المشتركة لثانية بكالوريا ({g2_bac['common']['subject']} - {g2_bac['common']['lesson_title']})",
  "bac_med_tip": "أهم تريكة لمسار الطب وعلوم الحياة اليوم ({g2_bac['tracks']['مسار الطب وعلوم الحياة'][0]['lesson_title']} / {g2_bac['tracks']['مسار الطب وعلوم الحياة'][1]['lesson_title']})",
  "bac_eng_tip": "أهم تريكة لمسار الهندسة وعلوم الحاسب اليوم ({g2_bac['tracks']['مسار الهندسة وعلوم الحاسب'][0]['lesson_title']} / {g2_bac['tracks']['مسار الهندسة وعلوم الحاسب'][1]['lesson_title']})",
  "bac_bus_tip": "أهم تريكة لمسار الأعمال اليوم ({g2_bac['tracks']['مسار الأعمال'][0]['lesson_title']} / {g2_bac['tracks']['مسار الأعمال'][1]['lesson_title']})",
  "bac_art_tip": "أهم تريكة لمسار الآداب والفنون اليوم ({g2_bac['tracks']['مسار الآداب والفنون'][0]['lesson_title']} / {g2_bac['tracks']['مسار الآداب والفنون'][1]['lesson_title']})",
  "g2_gen_sci_tip": "نصيحة عملية لثانية ثانوي عام علمي ({g2_gen['sci']['subject']} - {g2_gen['sci']['lesson_title']})",
  "g2_gen_lit_tip": "نصيحة عملية لثانية ثانوي عام أدبي ({g2_gen['lit']['subject']} - {g2_gen['lit']['lesson_title']})",
  "g3_sci_tip": "نصيحة ذهبية لثالثة ثانوي علمي ({g3['common_sci']['subject']} - {g3['common_sci']['lesson_title']})",
  "g3_bio_tip": "نصيحة ذهبية لثالثة علمي علوم ({g3['bio']['lesson_title']})",
  "g3_math_tip": "نصيحة ذهبية لثالثة علمي رياضة ({g3['math']['lesson_title']})",
  "g3_lit_tip": "نصيحة ذهبية لثالثة أدبي ({g3['lit']['lesson_title']})"
}}
"""
    ai = call_groq_json(api_key, sys_prompt, usr_prompt)

    # ---------------- رسم 4 بطاقات 1080×1350 فائقة الترتيب ----------------
    stamp = f"{cal['date_iso']}_morning"
    c1_sections = [
        {
            "track_label": "المادة الأساسية اليوم",
            "subject": g1["main"]["subject"],
            "unit": g1["main"]["unit"],
            "lesson_num": g1["main"]["lesson_num"],
            "lesson_title": g1["main"]["lesson_title"],
            "part": g1["main"]["part"],
            "detail": f"المطلوب: {g1['main']['focus']}\nالتطبيق: {ai.get('g1_main_tip', '')}",
        },
        {
            "track_label": "المادة الثانية اليوم",
            "subject": g1["secondary"]["subject"],
            "unit": g1["secondary"]["unit"],
            "lesson_num": g1["secondary"]["lesson_num"],
            "lesson_title": g1["secondary"]["lesson_title"],
            "part": g1["secondary"]["part"],
            "detail": f"المطلوب: {g1['secondary']['focus']}\nالتطبيق: {ai.get('g1_sec_tip', '')}",
        },
    ]

    # بطاقة ثانية بكالوريا: المادة المشتركة + المسارات الـ 4 كاملة!
    med0, med1 = g2_bac["tracks"]["مسار الطب وعلوم الحياة"]
    eng0, eng1 = g2_bac["tracks"]["مسار الهندسة وعلوم الحاسب"]
    bus0, bus1 = g2_bac["tracks"]["مسار الأعمال"]
    art0, art1 = g2_bac["tracks"]["مسار الآداب والفنون"]

    c2_sections = [
        {
            "track_label": "مشترك كل المسارات",
            "subject": g2_bac["common"]["subject"],
            "unit": g2_bac["common"]["unit"],
            "lesson_num": g2_bac["common"]["lesson_num"],
            "lesson_title": g2_bac["common"]["lesson_title"],
            "part": g2_bac["common"]["part"],
            "detail": g2_bac["common"]["focus"],
        },
        {
            "track_label": "١) مسار الطب وعلوم الحياة",
            "subject": "فيزياء أو رياضيات",
            "unit": med0["unit"],
            "lesson_num": med0["lesson_num"],
            "lesson_title": f"فيزياء: {med0['lesson_title']}",
            "part": med0["part"],
            "detail": f"أو الرياضيات: {med1['unit']} — {med1['lesson_num']}: {med1['lesson_title']} [{med1['part']}]",
        },
        {
            "track_label": "٢) مسار الهندسة والحاسب",
            "subject": "كيمياء أو برمجة",
            "unit": eng0["unit"],
            "lesson_num": eng0["lesson_num"],
            "lesson_title": f"كيمياء: {eng0['lesson_title']}",
            "part": eng0["part"],
            "detail": f"أو البرمجة والذكاء الاصطناعي: {eng1['unit']} — {eng1['lesson_num']}: {eng1['lesson_title']} [{eng1['part']}]",
        },
        {
            "track_label": "٣) مسار الأعمال",
            "subject": "محاسبة أو إدارة",
            "unit": bus0["unit"],
            "lesson_num": bus0["lesson_num"],
            "lesson_title": f"محاسبة: {bus0['lesson_title']}",
            "part": bus0["part"],
            "detail": f"أو إدارة الأعمال: {bus1['unit']} — {bus1['lesson_num']}: {bus1['lesson_title']} [{bus1['part']}]",
        },
        {
            "track_label": "٤) مسار الآداب والفنون",
            "subject": "علم نفس أو لغة ٢",
            "unit": art0["unit"],
            "lesson_num": art0["lesson_num"],
            "lesson_title": f"علم نفس: {art0['lesson_title']}",
            "part": art0["part"],
            "detail": f"أو اللغة الثانية: {art1['unit']} — {art1['lesson_num']}: {art1['lesson_title']} [{art1['part']}]",
        },
    ]

    c3_sections = [
        {
            "track_label": "شعبة علمي (ثانوية عامة)",
            "subject": g2_gen["sci"]["subject"],
            "unit": g2_gen["sci"]["unit"],
            "lesson_num": g2_gen["sci"]["lesson_num"],
            "lesson_title": g2_gen["sci"]["lesson_title"],
            "part": g2_gen["sci"]["part"],
            "detail": f"المطلوب: {g2_gen['sci']['focus']}\n{ai.get('g2_gen_sci_tip', '')}",
        },
        {
            "track_label": "شعبة أدبي (ثانوية عامة)",
            "subject": g2_gen["lit"]["subject"],
            "unit": g2_gen["lit"]["unit"],
            "lesson_num": g2_gen["lit"]["lesson_num"],
            "lesson_title": g2_gen["lit"]["lesson_title"],
            "part": g2_gen["lit"]["part"],
            "detail": f"المطلوب: {g2_gen['lit']['focus']}\n{ai.get('g2_gen_lit_tip', '')}",
        },
        {
            "track_label": "مادة مشتركة (علمي وأدبي)",
            "subject": g2_bac["common"]["subject"],
            "unit": g2_bac["common"]["unit"],
            "lesson_num": g2_bac["common"]["lesson_num"],
            "lesson_title": g2_bac["common"]["lesson_title"],
            "part": g2_bac["common"]["part"],
            "detail": g2_bac["common"]["focus"],
        },
    ]

    c4_sections = [
        {
            "track_label": "مشترك علمي (علوم + رياضة)",
            "subject": g3["common_sci"]["subject"],
            "unit": g3["common_sci"]["unit"],
            "lesson_num": g3["common_sci"]["lesson_num"],
            "lesson_title": g3["common_sci"]["lesson_title"],
            "part": g3["common_sci"]["part"],
            "detail": g3["common_sci"]["focus"],
        },
        {
            "track_label": "علمي علوم + طب بكالوريا",
            "subject": "الأحياء",
            "unit": g3["bio"]["unit"],
            "lesson_num": g3["bio"]["lesson_num"],
            "lesson_title": g3["bio"]["lesson_title"],
            "part": g3["bio"]["part"],
            "detail": g3["bio"]["focus"],
        },
        {
            "track_label": "علمي رياضة + هندسة بكالوريا",
            "subject": "الرياضيات",
            "unit": g3["math"]["unit"],
            "lesson_num": g3["math"]["lesson_num"],
            "lesson_title": g3["math"]["lesson_title"],
            "part": g3["math"]["part"],
            "detail": g3["math"]["focus"],
        },
        {
            "track_label": "الشعبة الأدبية + أعمال وآداب",
            "subject": g3["lit"]["subject"].split("(")[0].strip(),
            "unit": g3["lit"]["unit"],
            "lesson_num": g3["lit"]["lesson_num"],
            "lesson_title": g3["lit"]["lesson_title"],
            "part": g3["lit"]["part"],
            "detail": g3["lit"]["focus"],
        },
    ]

    all_card_defs = [
        (out_dir / f"{stamp}_c1.jpg", g1["title"], "بطاقة ١/٤", c1_sections),
        (out_dir / f"{stamp}_c2.jpg", g2_bac["title"], "بطاقة ٢/٤", c2_sections),
        (out_dir / f"{stamp}_c3.jpg", g2_gen["title"], "بطاقة ٣/٤", c3_sections),
        (out_dir / f"{stamp}_c4.jpg", g3["title"], "بطاقة ٤/٤", c4_sections),
    ]
    cards: List[Path] = []
    for p, title, sl_lbl, secs in all_card_defs:
        render_structured_card(
            out_path=p,
            slot_type="morning",
            header_badge="ثانويتي بلس • خطة مذاكرة اليوم بالدرس والجزء",
            cohort_title=title,
            date_label=f"{cal['weekday_ar']} {cal['date_ar']}",
            mode_badge=cal["mode_badge"],
            progress_pct=cal["term_progress_pct"],
            slide_label=sl_lbl,
            sections=secs,
            footer_cta="رتّب جدولك وحل أسئلة درس النهاردة مجاناً على ثانويتي بلس!",
        )
        cards.append(p)

    vid_path = out_dir / f"{stamp}_short.mp4"
    render_cards_short_video(
        card_paths=cards,
        out_mp4=vid_path,
        top_title="خطة مذاكرة اليوم — ثانويتي بلس",
        bottom_sub=f"{cal['weekday_ar']} {cal['date_ar']} • {cal['mode_badge']}",
        sec_per_slide=8.0,
    )

    # ---------------- بناء نص البوست الاحترافي المفصّل ----------------
    assess_banner = (
        f"📋 تنبيه التقييم الرسمي: النهاردة مخصص كمان لحل **{cal['mode_badge']}** وتقفيل أي درس متراكم من الأسبوع!\n\n"
        if is_assess else ""
    )

    fb_post = f"""📅 خطة مذاكرة اليوم من «ثانويتي بلس» | {cal['weekday_ar']} {cal['date_ar']} ({cal['mode_badge']}) 🔥
{ai.get('intro_hook', '')}
{assess_banner}علشان تمشي بنظام واضح وتقفل المنهج والتقييمات أول بأول من غير تشتيت، دي خطة النهاردة بالتفصيل لكل صف وشعبة ومسار بالوحدة والدرس والجزء:

━━━━━━━━━━━━━━━━━━
📘 أولاً: الصف الأول الثانوي (عام وبكالوريا مصرية)
{_fmt_item_line(g1['main'], ai.get('g1_main_tip', ''))}
  📌 عناصر الجزء: {g1['main']['focus']}
{_fmt_item_line(g1['secondary'], ai.get('g1_sec_tip', ''))}

━━━━━━━━━━━━━━━━━━
🎓 ثانياً: الصف الثاني الثانوي — البكالوريا المصرية (المسارات الـ ٤)
🔸 المادة المشتركة لجميع المسارات:
{_fmt_item_line(g2_bac['common'], ai.get('bac_common_tip', ''))}

🔸 مادة التخصص حسب مسارك (ذاكر المادة المختارة في مسارك):
🩺 ١) مسار الطب وعلوم الحياة:
• {med0['subject']}: {med0['unit']} — {med0['lesson_num']} ({med0['lesson_title']}) ⬅️ [{med0['part']}]
• أو {med1['subject']}: {med1['unit']} — {med1['lesson_num']} ({med1['lesson_title']}) ⬅️ [{med1['part']}]
  💡 {ai.get('bac_med_tip', '')}

💻 ٢) مسار الهندسة وعلوم الحاسب:
• {eng0['subject']}: {eng0['unit']} — {eng0['lesson_num']} ({eng0['lesson_title']}) ⬅️ [{eng0['part']}]
• أو {eng1['subject']}: {eng1['unit']} — {eng1['lesson_num']} ({eng1['lesson_title']}) ⬅️ [{eng1['part']}]
  💡 {ai.get('bac_eng_tip', '')}

💼 ٣) مسار الأعمال:
• {bus0['subject']}: {bus0['unit']} — {bus0['lesson_num']} ({bus0['lesson_title']}) ⬅️ [{bus0['part']}]
• أو {bus1['subject']}: {bus1['unit']} — {bus1['lesson_num']} ({bus1['lesson_title']}) ⬅️ [{bus1['part']}]
  💡 {ai.get('bac_bus_tip', '')}

🎨 ٤) مسار الآداب والفنون:
• {art0['subject']}: {art0['unit']} — {art0['lesson_num']} ({art0['lesson_title']}) ⬅️ [{art0['part']}]
• أو {art1['subject']}: {art1['unit']} — {art1['lesson_num']} ({art1['lesson_title']}) ⬅️ [{art1['part']}]
  💡 {ai.get('bac_art_tip', '')}

━━━━━━━━━━━━━━━━━━
📐 ثالثاً: الصف الثاني الثانوي العام (علمي وأدبي)
• شعبة علمي — {g2_gen['sci']['subject']}: {g2_gen['sci']['unit']} — {g2_gen['sci']['lesson_num']} ({g2_gen['sci']['lesson_title']}) ⬅️ [{g2_gen['sci']['part']}]
• شعبة أدبي — {g2_gen['lit']['subject']}: {g2_gen['lit']['unit']} — {g2_gen['lit']['lesson_num']} ({g2_gen['lit']['lesson_title']}) ⬅️ [{g2_gen['lit']['part']}]

━━━━━━━━━━━━━━━━━━
🏆 رابعاً: الصف الثالث الثانوي (جميع الشعب والمسارات)
• ⚡ مشترك علمي (علوم + رياضة) — {g3['common_sci']['subject']}: {g3['common_sci']['unit']} — {g3['common_sci']['lesson_num']} ({g3['common_sci']['lesson_title']}) ⬅️ [{g3['common_sci']['part']}]
• 🧬 علمي علوم (وطب بكالوريا) — الأحياء: {g3['bio']['unit']} — {g3['bio']['lesson_num']} ({g3['bio']['lesson_title']}) ⬅️ [{g3['bio']['part']}]
• 📐 علمي رياضة (وهندسة بكالوريا) — الرياضيات: {g3['math']['unit']} — {g3['math']['lesson_num']} ({g3['math']['lesson_title']}) ⬅️ [{g3['math']['part']}]
• 📖 أدبي (وأعمال وآداب بكالوريا) — {g3['lit']['subject']}: {g3['lit']['unit']} — {g3['lit']['lesson_num']} ({g3['lit']['lesson_title']}) ⬅️ [{g3['lit']['part']}]

━━━━━━━━━━━━━━━━━━
⏰ ميعادنا الساعة ٥:٣٠ المغرب مع ملخص القوانين والتريكات لنفس الدروس دي، والساعة ٩:٠٠ بليل تحدي الـ ٣٠ ثانية!
👇 رابط منصة «ثانويتي بلس» (جدول المهام + بنك الأسئلة + دفتر الأخطاء + مصحح التمارين + كروت أنكي + المدرس الذكي) موجود دلوقتي في أول تعليق بالأسفل 👇
اكتب لنا في التعليقات: أنت سنة كام ومسارك أو شعبتك إيه؟ 💪🔥"""

    short_caption = f"""📅 خطة مذاكرة اليوم من «ثانويتي بلس» | {cal['weekday_ar']} {cal['date_ar']} 🔥

📘 أولى ثانوي (عام وبكالوريا):
• {g1['main']['subject']}: {g1['main']['unit']} — {g1['main']['lesson_num']} ({g1['main']['lesson_title']}) [{g1['main']['part']}]
• {g1['secondary']['subject']}: {g1['secondary']['lesson_num']} ({g1['secondary']['lesson_title']}) [{g1['secondary']['part']}]

🎓 ثانية ثانوي — البكالوريا المصرية (المسارات الـ ٤):
• مشترك: {g2_bac['common']['subject']} — {g2_bac['common']['lesson_num']} ({g2_bac['common']['lesson_title']}) [{g2_bac['common']['part']}]
🩺 طب وعلوم حياة: فيزياء ({med0['lesson_title']} [{med0['part']}]) أو رياضيات ({med1['lesson_title']} [{med1['part']}])
💻 هندسة وحاسب: كيمياء ({eng0['lesson_title']} [{eng0['part']}]) أو برمجة ({eng1['lesson_title']} [{eng1['part']}])
💼 أعمال: محاسبة ({bus0['lesson_title']} [{bus0['part']}]) أو إدارة ({bus1['lesson_title']} [{bus1['part']}])
🎨 آداب وفنون: علم نفس ({art0['lesson_title']} [{art0['part']}]) أو لغة ٢ ({art1['lesson_title']} [{art1['part']}])

📐 ثانية عام: علمي ({g2_gen['sci']['subject']}: {g2_gen['sci']['lesson_title']}) | أدبي ({g2_gen['lit']['subject']}: {g2_gen['lit']['lesson_title']})

🏆 ثالثة ثانوي:
• فيزياء/كيمياء علمي: {g3['common_sci']['lesson_num']} ({g3['common_sci']['lesson_title']}) [{g3['common_sci']['part']}]
• علمي علوم: {g3['bio']['lesson_title']} [{g3['bio']['part']}]
• علمي رياضة: {g3['math']['lesson_title']} [{g3['math']['part']}]
• أدبي: {g3['lit']['lesson_title']} [{g3['lit']['part']}]

🚀 افتح منصة ثانويتي بلس ورتّب جدول مهامك وحل بنك الأسئلة مجاناً:
{SITE_URL}
(الرابط المباشر في أول تعليق وفي البايو أعلى الصفحة 👆)
#ثانويتي_بلس #الثانوية_العامة #البكالوريا_المصرية #أولى_ثانوي #تانية_ثانوي #تالتة_ثانوي"""

    first_comment = (
        f"🚀 رابط منصة «ثانويتي بلس» المباشر (مجاناً لكل طلاب أولى وتانية وتالتة ثانوي والبكالوريا المصرية):\n"
        f"{SITE_URL}\n\n"
        f"✅ ادخل دلوقتي اختار صفك ومسارك (أو شعبتك)، ضيف درس النهاردة في «جدول المهام»، وبعد المذاكرة حل عليه من «بنك الأسئلة» وسجّل أي غلطة في «دفتر الأخطاء»!"
    )

    yt_title = f"جدول مذاكرة اليوم بالدرس والجزء | أولى وتانية وتالتة ثانوي والبكالوريا المصرية #shorts"

    return {
        "slot": "morning",
        "date": cal["date_iso"],
        "fb_mode": "album",
        "slide_1_url": f"{cdn_base}/{cards[0].name}",
        "slide_2_url": f"{cdn_base}/{cards[1].name}",
        "slide_3_url": f"{cdn_base}/{cards[2].name}",
        "slide_4_url": f"{cdn_base}/{cards[3].name}",
        "video_url": f"{cdn_base}/{vid_path.name}",
        "facebook_caption": fb_post,
        "instagram_caption": short_caption[:2150],
        "youtube_title": yt_title[:95],
        "youtube_description": f"{fb_post}\n\n🔗 رابط المنصة المباشر: {SITE_URL}\n#shorts #ثانويتي_بلس #الثانوية_العامة #البكالوريا_المصرية"[:4900],
        "tiktok_caption": short_caption[:2100],
        "first_comment": first_comment,
    }


# ==============================================================================
# 2) نشرة المغرب: ملخص القوانين والنقاط الذهبية وتريكات الامتحان لنفس دروس الصباح!
# ==============================================================================
def build_maghrib_slot(plan: Dict[str, Any], api_key: str, out_dir: Path, cdn_base: str) -> Dict[str, Any]:
    cal = plan["calendar"]
    g1, g2_bac, g2_gen, g3 = plan["g1"], plan["g2_bac"], plan["g2_gen"], plan["g3"]
    med0, med1 = g2_bac["tracks"]["مسار الطب وعلوم الحياة"]
    eng0, eng1 = g2_bac["tracks"]["مسار الهندسة وعلوم الحاسب"]
    bus0, bus1 = g2_bac["tracks"]["مسار الأعمال"]
    art0, art1 = g2_bac["tracks"]["مسار الآداب والفنون"]

    sys_prompt = (
        "أنت خبير تلخيص المناهج والقوانين وتريكات الامتحانات في منصة «ثانويتي بلس». "
        "اكتب ملخصاً علمياً دقيقاً جداً ومركزاً يحتوي على القوانين أو القواعد أو الفروق الجوهرية وأشهر فخ امتحاني لكل درس محدد. "
        "تجنب الرموز اليونانية الغريبة واكتب القوانين بوضوح شديد. أخرج JSON صالح فقط."
    )
    usr_prompt = f"""
لخّص القوانين والزتونة العلمية الدقيقة لدروس اليوم ({cal['weekday_ar']} {cal['date_ar']}):
أخرج JSON بالمفاتيح التالية بالظبط (كل مفتاح نص غني ومركز من سطرين إلى 3 أسطر فيها القانون/القاعدة + تريكة الامتحان):
{{
  "g1_main_sum": "ملخص وقوانين ({g1['main']['subject']} — {g1['main']['lesson_num']}: {g1['main']['lesson_title']} [{g1['main']['part']}])",
  "g1_sec_sum": "ملخص وقواعد ({g1['secondary']['subject']} — {g1['secondary']['lesson_num']}: {g1['secondary']['lesson_title']} [{g1['secondary']['part']}])",
  "bac_common_sum": "خلاصة درس المشترك ثانية بكالوريا ({g2_bac['common']['subject']}: {g2_bac['common']['lesson_title']})",
  "bac_med_sum": "قوانين وتريكة مسار الطب ({med0['subject']}: {med0['lesson_title']} + {med1['subject']}: {med1['lesson_title']})",
  "bac_eng_sum": "قواعد وتريكة مسار الهندسة ({eng0['subject']}: {eng0['lesson_title']} + {eng1['subject']}: {eng1['lesson_title']})",
  "bac_bus_sum": "قواعد وتريكة مسار الأعمال ({bus0['subject']}: {bus0['lesson_title']} + {bus1['subject']}: {bus1['lesson_title']})",
  "bac_art_sum": "خلاصة وتريكة مسار الآداب ({art0['subject']}: {art0['lesson_title']} + {art1['subject']}: {art1['lesson_title']})",
  "g2_gen_sci_sum": "قوانين وتريكة ثانية عام علمي ({g2_gen['sci']['subject']}: {g2_gen['sci']['lesson_title']})",
  "g2_gen_lit_sum": "خلاصة وتريكة ثانية عام أدبي ({g2_gen['lit']['subject']}: {g2_gen['lit']['lesson_title']})",
  "g3_sci_sum": "قوانين وتريكات مسائل ثالثة علمي ({g3['common_sci']['subject']}: {g3['common_sci']['lesson_title']})",
  "g3_bio_sum": "زتونة وتريكات أحياء ثالثة علمي علوم ({g3['bio']['lesson_title']})",
  "g3_math_sum": "قوانين وخطوات حل ثالثة علمي رياضة ({g3['math']['lesson_title']})",
  "g3_lit_sum": "استنتاجات ومفاتيح حل ثالثة أدبي ({g3['lit']['subject']}: {g3['lit']['lesson_title']})"
}}
"""
    ai = call_groq_json(api_key, sys_prompt, usr_prompt)

    stamp = f"{cal['date_iso']}_maghrib"
    c1_secs = [
        {
            "track_label": "زتونة وقوانين المادة الأساسية",
            "subject": g1["main"]["subject"],
            "unit": g1["main"]["unit"],
            "lesson_num": g1["main"]["lesson_num"],
            "lesson_title": g1["main"]["lesson_title"],
            "part": g1["main"]["part"],
            "detail": ai.get("g1_main_sum", g1["main"]["focus"]),
        },
        {
            "track_label": "زتونة المادة الثانية",
            "subject": g1["secondary"]["subject"],
            "unit": g1["secondary"]["unit"],
            "lesson_num": g1["secondary"]["lesson_num"],
            "lesson_title": g1["secondary"]["lesson_title"],
            "part": g1["secondary"]["part"],
            "detail": ai.get("g1_sec_sum", g1["secondary"]["focus"]),
        },
    ]
    c2_secs = [
        {
            "track_label": "ملخص المشترك (كل المسارات)",
            "subject": g2_bac["common"]["subject"],
            "unit": g2_bac["common"]["unit"],
            "lesson_num": g2_bac["common"]["lesson_num"],
            "lesson_title": g2_bac["common"]["lesson_title"],
            "part": g2_bac["common"]["part"],
            "detail": ai.get("bac_common_sum", ""),
        },
        {
            "track_label": "١) زتونة مسار الطب وعلوم الحياة",
            "subject": "فيزياء / رياضيات",
            "unit": med0["unit"],
            "lesson_num": med0["lesson_num"],
            "lesson_title": f"{med0['lesson_title']} | {med1['lesson_title']}",
            "part": med0["part"],
            "detail": ai.get("bac_med_sum", ""),
        },
        {
            "track_label": "٢) زتونة مسار الهندسة والحاسب",
            "subject": "كيمياء / برمجة",
            "unit": eng0["unit"],
            "lesson_num": eng0["lesson_num"],
            "lesson_title": f"{eng0['lesson_title']} | {eng1['lesson_title']}",
            "part": eng0["part"],
            "detail": ai.get("bac_eng_sum", ""),
        },
        {
            "track_label": "٣) زتونة مسار الأعمال",
            "subject": "محاسبة / إدارة",
            "unit": bus0["unit"],
            "lesson_num": bus0["lesson_num"],
            "lesson_title": f"{bus0['lesson_title']} | {bus1['lesson_title']}",
            "part": bus0["part"],
            "detail": ai.get("bac_bus_sum", ""),
        },
        {
            "track_label": "٤) زتونة مسار الآداب والفنون",
            "subject": "علم نفس / لغة ٢",
            "unit": art0["unit"],
            "lesson_num": art0["lesson_num"],
            "lesson_title": f"{art0['lesson_title']} | {art1['lesson_title']}",
            "part": art0["part"],
            "detail": ai.get("bac_art_sum", ""),
        },
    ]
    c3_secs = [
        {
            "track_label": "زتونة ثانية عام — علمي",
            "subject": g2_gen["sci"]["subject"],
            "unit": g2_gen["sci"]["unit"],
            "lesson_num": g2_gen["sci"]["lesson_num"],
            "lesson_title": g2_gen["sci"]["lesson_title"],
            "part": g2_gen["sci"]["part"],
            "detail": ai.get("g2_gen_sci_sum", ""),
        },
        {
            "track_label": "زتونة ثانية عام — أدبي",
            "subject": g2_gen["lit"]["subject"],
            "unit": g2_gen["lit"]["unit"],
            "lesson_num": g2_gen["lit"]["lesson_num"],
            "lesson_title": g2_gen["lit"]["lesson_title"],
            "part": g2_gen["lit"]["part"],
            "detail": ai.get("g2_gen_lit_sum", ""),
        },
    ]
    c4_secs = [
        {
            "track_label": "قوانين مشترك علمي (ثالثة ثانوي)",
            "subject": g3["common_sci"]["subject"],
            "unit": g3["common_sci"]["unit"],
            "lesson_num": g3["common_sci"]["lesson_num"],
            "lesson_title": g3["common_sci"]["lesson_title"],
            "part": g3["common_sci"]["part"],
            "detail": ai.get("g3_sci_sum", ""),
        },
        {
            "track_label": "زتونة علمي علوم + طب بكالوريا",
            "subject": "الأحياء",
            "unit": g3["bio"]["unit"],
            "lesson_num": g3["bio"]["lesson_num"],
            "lesson_title": g3["bio"]["lesson_title"],
            "part": g3["bio"]["part"],
            "detail": ai.get("g3_bio_sum", ""),
        },
        {
            "track_label": "قوانين علمي رياضة + هندسة بكالوريا",
            "subject": "الرياضيات",
            "unit": g3["math"]["unit"],
            "lesson_num": g3["math"]["lesson_num"],
            "lesson_title": g3["math"]["lesson_title"],
            "part": g3["math"]["part"],
            "detail": ai.get("g3_math_sum", ""),
        },
        {
            "track_label": "مفاتيح حل الشعبة الأدبية",
            "subject": g3["lit"]["subject"].split("(")[0].strip(),
            "unit": g3["lit"]["unit"],
            "lesson_num": g3["lit"]["lesson_num"],
            "lesson_title": g3["lit"]["lesson_title"],
            "part": g3["lit"]["part"],
            "detail": ai.get("g3_lit_sum", ""),
        },
    ]

    all_card_defs = [
        (out_dir / f"{stamp}_c1.jpg", g1["title"], "ملخص ١/٤", c1_secs),
        (out_dir / f"{stamp}_c2.jpg", g2_bac["title"], "ملخص ٢/٤", c2_secs),
        (out_dir / f"{stamp}_c3.jpg", g2_gen["title"], "ملخص ٣/٤", c3_secs),
        (out_dir / f"{stamp}_c4.jpg", g3["title"], "ملخص ٤/٤", c4_secs),
    ]
    cards: List[Path] = []
    for p, title, sl_lbl, secs in all_card_defs:
        render_structured_card(
            out_path=p,
            slot_type="maghrib",
            header_badge="ثانويتي بلس • كبسولة الملخص والقوانين الذهبية",
            cohort_title=title,
            date_label=f"{cal['weekday_ar']} {cal['date_ar']}",
            mode_badge=cal["mode_badge"],
            progress_pct=cal["term_progress_pct"],
            slide_label=sl_lbl,
            sections=secs,
            footer_cta="ثبّت القوانين بكروت أنكي واسأل المدرس الذكي على ثانويتي بلس!",
        )
        cards.append(p)

    vid_path = out_dir / f"{stamp}_short.mp4"
    render_cards_short_video(
        card_paths=cards,
        out_mp4=vid_path,
        top_title="ملخص القوانين وتريكات الامتحان",
        bottom_sub=f"{cal['weekday_ar']} {cal['date_ar']} • احفظ البوست للمراجعة!",
        sec_per_slide=8.0,
    )

    fb_post = f"""🌇 كبسولة الملخص والقوانين وتريكات الامتحان | {cal['weekday_ar']} {cal['date_ar']} ⚡
ذاكرت جزء النهاردة من جدول الصبح؟ راجع دلوقتي أهم القوانين والمفاتيح الامتحانية اللي بتيجي في التقييمات والامتحانات على نفس دروس النهاردة بالظبط (احفظ البوست عندك للمراجعة 📌):

━━━━━━━━━━━━━━━━━━
📘 أولاً: الصف الأول الثانوي (عام وبكالوريا مصرية)
🔹 {g1['main']['subject']} — {g1['main']['unit']} — {g1['main']['lesson_num']} ({g1['main']['lesson_title']}) [{g1['main']['part']}]:
  ✨ {ai.get('g1_main_sum', '')}
🔹 {g1['secondary']['subject']} — {g1['secondary']['lesson_num']} ({g1['secondary']['lesson_title']}) [{g1['secondary']['part']}]:
  ✨ {ai.get('g1_sec_sum', '')}

━━━━━━━━━━━━━━━━━━
🎓 ثانياً: الصف الثاني الثانوي — البكالوريا المصرية (المسارات الـ ٤)
🔸 المشترك ({g2_bac['common']['subject']} — {g2_bac['common']['lesson_num']}: {g2_bac['common']['lesson_title']}):
  ✨ {ai.get('bac_common_sum', '')}
🩺 ١) مسار الطب وعلوم الحياة ({med0['subject']} / {med1['subject']}):
  ✨ {ai.get('bac_med_sum', '')}
💻 ٢) مسار الهندسة وعلوم الحاسب ({eng0['subject']} / {eng1['subject']}):
  ✨ {ai.get('bac_eng_sum', '')}
💼 ٣) مسار الأعمال ({bus0['subject']} / {bus1['subject']}):
  ✨ {ai.get('bac_bus_sum', '')}
🎨 ٤) مسار الآداب والفنون ({art0['subject']} / {art1['subject']}):
  ✨ {ai.get('bac_art_sum', '')}

━━━━━━━━━━━━━━━━━━
📐 ثالثاً: الصف الثاني الثانوي العام (علمي وأدبي)
• شعبة علمي ({g2_gen['sci']['subject']} — {g2_gen['sci']['lesson_title']}):
  ✨ {ai.get('g2_gen_sci_sum', '')}
• شعبة أدبي ({g2_gen['lit']['subject']} — {g2_gen['lit']['lesson_title']}):
  ✨ {ai.get('g2_gen_lit_sum', '')}

━━━━━━━━━━━━━━━━━━
🏆 رابعاً: الصف الثالث الثانوي (جميع الشعب)
• ⚡ مشترك علمي ({g3['common_sci']['subject']} — {g3['common_sci']['lesson_num']}: {g3['common_sci']['lesson_title']}):
  ✨ {ai.get('g3_sci_sum', '')}
• 🧬 علمي علوم ({g3['bio']['lesson_title']}):
  ✨ {ai.get('g3_bio_sum', '')}
• 📐 علمي رياضة ({g3['math']['lesson_title']}):
  ✨ {ai.get('g3_math_sum', '')}
• 📖 الشعبة الأدبية ({g3['lit']['subject']} — {g3['lit']['lesson_title']}):
  ✨ {ai.get('g3_lit_sum', '')}

━━━━━━━━━━━━━━━━━━
🔔 جهّز نفسك.. الساعة ٩:٠٠ بليل بالظبط هينزل فيديو تحدي الـ ٣٠ ثانية وأسئلة السهرة على الأجزاء دي بدون إجابات!
👇 رابط منصة «ثانويتي بلس» (عشان تراجع القوانين بكروت أنكي وتسأل المدرس الذكي لو أي نقطة وقفت معاك) في أول تعليق بالأسفل 👇"""

    ig_tk_caption = f"""🌇 كبسولة الملخص والقوانين الذهبية | {cal['weekday_ar']} {cal['date_ar']} 📌

📘 أولى ثانوي ({g1['main']['subject']} - {g1['main']['lesson_num']}):
{ai.get('g1_main_sum', '')}

🎓 ثانية بكالوريا (المسارات الـ ٤):
🩺 طب: {ai.get('bac_med_sum', '')}
💻 هندسة: {ai.get('bac_eng_sum', '')}
💼 أعمال: {ai.get('bac_bus_sum', '')}
🎨 آداب: {ai.get('bac_art_sum', '')}

📐 ثانية عام:
• علمي: {ai.get('g2_gen_sci_sum', '')}
• أدبي: {ai.get('g2_gen_lit_sum', '')}

🏆 ثالثة ثانوي:
• علمي: {ai.get('g3_sci_sum', '')}
• أحياء: {ai.get('g3_bio_sum', '')}
• رياضة: {ai.get('g3_math_sum', '')}
• أدبي: {ai.get('g3_lit_sum', '')}

✨ راجع بكروت أنكي واسأل المدرس الذكي مجاناً على ثانويتي بلس:
{SITE_URL}
(الرابط المباشر في أول تعليق وفي البايو 👆)
#ثانويتي_بلس #ملخصات_ثانوي #البكالوريا_المصرية #الثانوية_العامة"""

    first_comment = (
        f"🧠 احفظ قوانين وتريكات النهاردة بكروت المراجعة الذكية (Anki) واسأل «المدرس الذكي» يشرحلك أي جزئية فوراً على منصة «ثانويتي بلس»:\n"
        f"{SITE_URL}\n\n"
        f"⏰ واستنانا الساعة ٩:٠٠ بليل في تحدي الـ ٣٠ ثانية!"
    )

    yt_title = f"ملخص وقوانين درس اليوم وتريكات الامتحان | ثانوي وعام وبكالوريا #shorts"

    return {
        "slot": "maghrib",
        "date": cal["date_iso"],
        "fb_mode": "album",
        "slide_1_url": f"{cdn_base}/{cards[0].name}",
        "slide_2_url": f"{cdn_base}/{cards[1].name}",
        "slide_3_url": f"{cdn_base}/{cards[2].name}",
        "slide_4_url": f"{cdn_base}/{cards[3].name}",
        "video_url": f"{cdn_base}/{vid_path.name}",
        "facebook_caption": fb_post,
        "instagram_caption": ig_tk_caption[:2150],
        "youtube_title": yt_title[:95],
        "youtube_description": f"{fb_post}\n\n🔗 رابط المنصة المباشر: {SITE_URL}\n#shorts #ثانويتي_بلس #الثانوية_العامة #البكالوريا_المصرية"[:4900],
        "tiktok_caption": ig_tk_caption[:2100],
        "first_comment": first_comment,
    }


# ==============================================================================
# 3) نشرة الليل (9:00 م): فيديو عداد تنازلي 30 ثانية + أسئلة السهرة لكل الصفوف والمسارات (بدون الإجابة!)
# ==============================================================================
def build_night_slot(plan: Dict[str, Any], api_key: str, out_dir: Path, cdn_base: str) -> Dict[str, Any]:
    cal = plan["calendar"]
    g1, g2_bac, g2_gen, g3 = plan["g1"], plan["g2_bac"], plan["g2_gen"], plan["g3"]
    spot = plan["spotlight"]
    med0 = g2_bac["tracks"]["مسار الطب وعلوم الحياة"][0]
    eng0 = g2_bac["tracks"]["مسار الهندسة وعلوم الحاسب"][0]
    bus0 = g2_bac["tracks"]["مسار الأعمال"][0]
    art0 = g2_bac["tracks"]["مسار الآداب والفنون"][0]

    sys_prompt = (
        "أنت واضع أسئلة امتحانات وتقييمات وزارة التربية والتعليم في منصة «ثانويتي بلس». "
        "تحذير صارم جداً: ممنوع منعاً باتاً كتابة الإجابة الصحيحة أو التلميح لها في أي حقل من الحقول! "
        "الهدف أن يحل الطلاب الأسئلة بأنفسهم في التعليقات. تجنب الرموز اليونانية الغريبة. أخرج JSON صالح فقط."
    )
    usr_prompt = f"""
ضع أسئلة تحدي السهرة على دروس اليوم ({cal['weekday_ar']} {cal['date_ar']}) بمستوى التقييمات الأسبوعية وامتحانات الوزارة — بدون ذكر أو كشف أي إجابة نهائياً!

1) سؤال الفيديو الرئيسي (عداد 30 ثانية) على:
   الصف/المسار: {spot['cohort']}
   المادة والدرس: {spot['subject']} — {spot['unit']} — {spot['lesson_num']}: {spot['lesson_title']} [{spot['part']}]

2) أسئلة سريعة إضافية في نص البوست لباقي الصفوف والمسارات (كل سؤال مع 4 اختيارات أ، ب، ج، د في سطر واحد مختصر وواضح بدون الإجابة):
   - سؤال أولى ثانوي على: {g1['main']['subject']} ({g1['main']['lesson_title']})
   - سؤال ثانية بكالوريا مسار الطب/علمي على: {med0['subject']} ({med0['lesson_title']})
   - سؤال ثانية بكالوريا مسار الهندسة على: {eng0['subject']} ({eng0['lesson_title']})
   - سؤال ثانية بكالوريا مسار الأعمال/الآداب على: {bus0['subject']} ({bus0['lesson_title']}) أو {art0['subject']} ({art0['lesson_title']})
   - سؤال ثالثة ثانوي علمي على: {g3['common_sci']['subject']} ({g3['common_sci']['lesson_title']}) أو الأحياء ({g3['bio']['lesson_title']})
   - سؤال ثالثة ثانوي أدبي على: {g3['lit']['subject']} ({g3['lit']['lesson_title']})

أخرج JSON بهذا الشكل الدقيق (ممنوع وجود أي مفتاح للإجابة! واكتب أسماء المركبات الكيميائية أو الأرقام بالحروف العربية مثل «كلوريد الباريوم» و«موجب واحد» بدلاً من الرموز الرقمية):
{{
  "video_question": "نص سؤال الفيديو الذكي واضح ومختصر (أقل من 22 كلمة)",
  "video_choices": ["نص الاختيار أ بدون حرف أ", "نص الاختيار ب", "نص الاختيار ج", "نص الاختيار د"],
  "q_g1": "سؤال أولى ثانوي + (أ) ... (ب) ... (ج) ... (د) ...",
  "q_bac_med": "سؤال مسار الطب وثانية علمي + الاختيارات الأربعة",
  "q_bac_eng": "سؤال مسار الهندسة والحاسب + الاختيارات الأربعة",
  "q_bac_bus_art": "سؤال مسار الأعمال والآداب + الاختيارات الأربعة",
  "q_g3_sci": "سؤال ثالثة ثانوي علمي + الاختيارات الأربعة",
  "q_g3_lit": "سؤال ثالثة ثانوي أدبي + الاختيارات الأربعة"
}}
"""
    ai = call_groq_json(api_key, sys_prompt, usr_prompt)

    for k in list(ai.keys()):
        if "answer" in k.lower() or "correct" in k.lower() or "اجاب" in k or "إجاب" in k:
            del ai[k]

    stamp = f"{cal['date_iso']}_night"
    vid_path = out_dir / f"{stamp}_quiz30s.mp4"
    render_countdown_quiz_video(
        out_mp4=vid_path,
        grade_label=spot["cohort"],
        lesson_label=f"{spot['subject']} — {spot['unit']} — {spot['lesson_num']}: {spot['lesson_title']}",
        part_label=spot["part"],
        question_text=ai["video_question"],
        choices=ai["video_choices"][:4],
    )

    full_night_post = f"""⏱️ تحدي الـ ٣٠ ثانية وسهرة الأسئلة من «ثانويتي بلس» | ممنوع الغش نهائياً! 🔥
ذاكرت درس النهاردة وراجعت ملخص المغرب؟ ورّينا شطارتك دلوقتي قبل ما المؤقت يصفر! (مش هنقول الإجابة.. الأبطال هما اللي هيكتبوها بالتفسير في التعليقات 👇)

🎬 سؤال الفيديو الرئيسي ({spot['cohort']} — {spot['subject']} — {spot['lesson_num']}: {spot['lesson_title']}):
شغّل الفيديو واكتب رمز إجابتك الصح ( أ - ب - ج - د ) قبل انتهاء الوقت!

━━━━━━━━━━━━━━━━━━
⚡ أسئلة السهرة لباقي الصفوف والمسارات (اكتب رقم صفك أو مسارك وجاوب سؤالك في التعليقات):

📘 أولى ثانوي ({g1['main']['subject']} — {g1['main']['lesson_num']}):
❓ {ai.get('q_g1', '')}

🩺 ثانية بكالوريا (مسار الطب + ثانية عام علمي — {med0['subject']}):
❓ {ai.get('q_bac_med', '')}

💻 ثانية بكالوريا (مسار الهندسة والحاسب — {eng0['subject']}):
❓ {ai.get('q_bac_eng', '')}

💼🎨 ثانية بكالوريا (مسار الأعمال والآداب):
❓ {ai.get('q_bac_bus_art', '')}

🧬📐 ثالثة ثانوي علمي (علوم ورياضة):
❓ {ai.get('q_g3_sci', '')}

📖 ثالثة ثانوي الشعبة الأدبية:
❓ {ai.get('q_g3_lit', '')}

━━━━━━━━━━━━━━━━━━
📸 تحدي إضافي للأبطال: حل مسألة بالخطوات في كشكولك، وصوّرها لـ «مصحح التمارين والصور» على منصة ثانويتي بلس عشان يصححهالك فوراً ويسجل نقاط ضعفك في دفتر الأخطاء!
👇 رابط منصة «ثانويتي بلس» المباشر مستنيك في أول تعليق تحت الفيديو 👇"""

    # وصف فيديو فيسبوك خالٍ من الأرقام (0-9 / ٠-٩) ومن الروابط لتفادي قيد فيسبوك UploadVideo v6 وزيادة الوصول!
    fb_video_desc = strip_all_digits_for_fb_video(full_night_post)

    ig_tk_night = f"""⏱️ تحدي الـ ٣٠ ثانية من «ثانويتي بلس» — جاوب قبل الجرس بدون غش! 🔥
({spot['cohort']} — {spot['subject']}: {spot['lesson_title']})

واختبر نفسك كمان في سؤال صفك ومسارك في التعليقات 👇:
📘 أولى ثانوي: {ai.get('q_g1', '')}
🩺 طب وعلمي: {ai.get('q_bac_med', '')}
💻 هندسة وحاسب: {ai.get('q_bac_eng', '')}
💼 أعمال وآداب: {ai.get('q_bac_bus_art', '')}
🏆 ثالثة علمي: {ai.get('q_g3_sci', '')}
📖 ثالثة أدبي: {ai.get('q_g3_lit', '')}

📸 صوّر حلك لمصحح التمارين وحل بنك الأسئلة مجاناً على ثانويتي بلس:
{SITE_URL}
(الرابط المباشر في أول تعليق وفي البايو أعلى الصفحة 👆)
#ثانويتي_بلس #تحدي_30_ثانية #الثانوية_العامة #البكالوريا_المصرية"""

    first_comment = (
        f"🎯 خلّصت التحدي؟ ادخل دلوقتي على منصة «ثانويتي بلس» مجاناً:\n"
        f"{SITE_URL}\n\n"
        f"📸 تقدر تصوّر حلك بالموبايل لـ «مصحح التمارين والصور»، وتحل مئات الأسئلة على درس النهاردة في «بنك الأسئلة»، وأي سؤال تغلط فيه بيتحفظ تلقائياً في «دفتر الأخطاء» عشان متغلطش فيه تاني يوم الامتحان!"
    )

    yt_title = f"تحدي 30 ثانية 🔥 تقدر تحل سؤال درس النهاردة قبل الجرس؟ | ثانويتي بلس #shorts"

    return {
        "slot": "night",
        "date": cal["date_iso"],
        "fb_mode": "video",
        "slide_1_url": "",
        "slide_2_url": "",
        "slide_3_url": "",
        "slide_4_url": "",
        "video_url": f"{cdn_base}/{vid_path.name}",
        "facebook_caption": fb_video_desc,
        "instagram_caption": ig_tk_night[:2150],
        "youtube_title": yt_title[:95],
        "youtube_description": f"{full_night_post}\n\n🔗 رابط المنصة المباشر: {SITE_URL}\n#shorts #ثانويتي_بلس #الثانوية_العامة #البكالوريا_المصرية"[:4900],
        "tiktok_caption": ig_tk_night[:2100],
        "first_comment": first_comment,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Thanaweya Plus Daily Autopilot Engine v3")
    parser.add_argument("--slot", choices=["morning", "maghrib", "night", "auto"], default="auto")
    parser.add_argument("--out-dir", default="media/latest")
    parser.add_argument("--cdn-base", default="https://raw.githubusercontent.com/OWNER/REPO/media-cdn/latest")
    parser.add_argument("--date", default="", help="Optional YYYY-MM-DD override for testing")
    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ERROR: GROQ_API_KEY environment variable is required.")

    cairo_tz = datetime.timezone(datetime.timedelta(hours=2))
    if args.date:
        y, m, d = [int(x) for x in args.date.split("-")]
        now = datetime.datetime(y, m, d, 12, 0, tzinfo=cairo_tz)
    else:
        now = datetime.datetime.now(cairo_tz)

    slot = args.slot
    if slot == "auto":
        if now.hour < 13:
            slot = "morning"
        elif now.hour < 19:
            slot = "maghrib"
        else:
            slot = "night"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cdn_base = args.cdn_base.rstrip("/")

    plan = get_daily_curriculum_plan(now)
    print(f"[{now.isoformat()}] Thanaweya Plus v3 | slot={slot} | week={plan['calendar']['week_num']} | mode={plan['calendar']['day_mode']}")

    if slot == "morning":
        payload = build_morning_slot(plan, api_key, out_dir, cdn_base)
    elif slot == "maghrib":
        payload = build_maghrib_slot(plan, api_key, out_dir, cdn_base)
    else:
        payload = build_night_slot(plan, api_key, out_dir, cdn_base)

    # النشر المباشر الاختياري على تيك توك عبر Zernio بدون حدود مهلة Make الـ 40 ثانية
    payload["tiktok_published_direct"] = "false"
    zernio_key = os.environ.get("ZERNIO_API_KEY", "").strip()
    if zernio_key:
        mp4_files = sorted(out_dir.glob("*.mp4"))
        if mp4_files:
            try:
                from zernio_publisher import publish_video_to_tiktok_direct
                tk_res = publish_video_to_tiktok_direct(
                    video_path=mp4_files[0],
                    caption=payload.get("tiktok_caption", ""),
                    api_key=zernio_key,
                )
                if tk_res.get("ok"):
                    payload["tiktok_published_direct"] = "true"
                if tk_res.get("zernio_video_url"):
                    payload["zernio_video_url"] = tk_res["zernio_video_url"]
            except Exception as exc:
                print(f"[TikTok Direct Warning] {exc} — Make.com fallback route will remain active.")

    payload_path = out_dir / "webhook_payload.json"
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Saved payload -> {payload_path}")


if __name__ == "__main__":
    main()
