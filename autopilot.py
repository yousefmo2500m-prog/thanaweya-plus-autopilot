#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
المحرك الذاتي الكامل لمنصة "ثانويتي بلس" (https://thanaweya-ashy.vercel.app)
يعمل تلقائياً 3 مرات يومياً طوال العام الدراسي والسنوات القادمة مجاناً ($0):
- الصباح (morning): جدول ومهام المذاكرة اليومية لكل الصفوف (أولى، ثانية، ثالثة - عام وبكالوريا)
- المغرب (maghrib): كبسولة ملخص الدرس والقوانين الذهبية لنفس دروس الصباح
- المساء (night): فيديو تحدي الـ 30 ثانية بالعداد التنازلي + أسئلة السهرة على ما تمت مذاكرته (بدون كشف الإجابة نهائياً!)
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from curriculum_2026_2027 import get_academic_context, CAIRO_TZ
from studio_renderer import render_slides_and_short, render_night_countdown_video

SITE_URL = "https://thanaweya-ashy.vercel.app"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def call_groq_json(api_key: str, system_prompt: str, user_prompt: str, retries: int = 3) -> dict:
    body = json.dumps({
        "model": DEFAULT_GROQ_MODEL,
        "temperature": 0.65,
        "max_completion_tokens": 3800,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }).encode("utf-8")

    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "ThanaweyaPlus-Autopilot/2.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Groq API failed after {retries} attempts: {last_err}")


def strip_digits_for_fb_video(text: str) -> str:
    """
    حماية رسمية لموديول Facebook Upload a Video في Make.com الذي يرفض الأرقام العددية في الوصف:
    نحوّل الأرقام الشائعة لكلمات عربية مع الحفاظ التام على رابط الموقع الخالي أصلاً من الأرقام.
    """
    replacements = [
        ("30", "ثلاثين"), ("٣٠", "ثلاثين"),
        ("25", "خمسة وعشرين"), ("٢٥", "خمسة وعشرين"),
        ("100%", "مئة بالمئة"), ("100", "مئة"),
        ("1", "الأول"), ("١", "الأول"),
        ("2", "الثاني"), ("٢", "الثاني"),
        ("3", "الثالث"), ("٣", "الثالث"),
    ]
    out = text
    for k, v in replacements:
        out = out.replace(k, v)
    out = re.sub(r"[0-9٠-٩]+", "", out)
    return out


def generate_morning_content(api_key: str, ctx: dict) -> dict:
    g1, g2, g3 = ctx["grades"]
    sys_p = (
        "أنت الخبير الأكاديمي لمنصة ثانويتي بلس المصرية (https://thanaweya-ashy.vercel.app) لطلاب أولى وثانية وثالثة ثانوي "
        "(الثانوية العامة والبكالوريا المصرية). مهمتك إعداد خطة المذاكرة الصباحية اليومية للطلاب بالعامية المصرية المشجعة والمنظمة. "
        "أخرج JSON صالح فقط يحتوي على الحقول التالية: "
        "g1_points (مصفوفة من 3 خطوات عملية قصيرة لمذاكرة درس أولى ثانوي اليوم، كل خطوة أقل من 65 حرفاً)، "
        "g2_points (مصفوفة من 3 خطوات عملية قصيرة لمذاكرة درس ثانية ثانوي اليوم، كل خطوة أقل من 65 حرفاً)، "
        "g3_points (مصفوفة من 3 خطوات عملية قصيرة لمذاكرة درس ثالثة ثانوي اليوم، كل خطوة أقل من 65 حرفاً)، "
        "facebook_caption (بوست فيسبوك صباحي حماسي يعرض جدول اليوم للصفوف الثلاثة ويوجّه الطلاب لفتح جدول المهام وتايمر البومودورو على https://thanaweya-ashy.vercel.app)، "
        "instagram_caption (كابشن ريلز إنستجرام صباحي منظم + هاشتاجات + رابط الموقع)، "
        "youtube_title (عنوان جذاب أقل من 85 حرفاً ينتهي بـ #Shorts)، "
        "youtube_description (وصف يوتيوب شورتس لجدول اليوم + رابط https://thanaweya-ashy.vercel.app)، "
        "tiktok_caption (كابشن تيك توك صباحي سريع يحفز الطلاب يكتبوا تم لما يبدأوا المذاكرة + رابط الموقع)."
    )
    usr_p = (
        f"اليوم: {ctx['date_str']} | الحالة: {ctx['mode_badge']} | نسبة إنجاز الخطة: {ctx['progress_pct']}%\n"
        f"- أولى ثانوي (عام وبكالوريا): {g1['subject']} — {g1['unit']} — {g1['lesson']} ({g1['type']}، {g1['pomodoros']} بومودورو)\n"
        f"- ثانية ثانوي (عام وبكالوريا): {g2['subject']} — {g2['unit']} — {g2['lesson']} ({g2['type']}، {g2['pomodoros']} بومودورو)\n"
        f"- ثالثة ثانوي (عام وبكالوريا): {g3['subject']} — {g3['unit']} — {g3['lesson']} ({g3['type']}، {g3['pomodoros']} بومودورو)\n"
        "اجعل الخطوات عملية جداً ومرتبطة بطبيعة الدرس نفسه (قوانين، رسومات بيانية، حل تدريبات، تقييم أسبوعي لو اليوم خميس/جمعة)."
    )
    return call_groq_json(api_key, sys_p, usr_p)


def generate_maghrib_content(api_key: str, ctx: dict) -> dict:
    g1, g2, g3 = ctx["grades"]
    sys_p = (
        "أنت كبير معلمي الثانوية العامة والبكالوريا المصرية على منصة ثانويتي بلس (https://thanaweya-ashy.vercel.app). "
        "مهمتك في فترة المغرب تلخيص نفس الدروس التي ذاكرها الطلاب صباح اليوم في كبسولة قوانين وتريكات امتحانات ذهبية مركزة ودقيقة علمياً 100%. "
        "أخرج JSON صالح فقط يحتوي على الحقول التالية: "
        "g1_points (مصفوفة من 4 نقاط تلخص أهم قوانين ومفاهيم وتريكة امتحان درس أولى ثانوي اليوم، كل نقطة أقل من 68 حرفاً)، "
        "g2_points (مصفوفة من 4 نقاط تلخص أهم قوانين ومفاهيم وتريكة امتحان درس ثانية ثانوي اليوم، كل نقطة أقل من 68 حرفاً)، "
        "g3_points (مصفوفة من 4 نقاط تلخص أهم قوانين ومفاهيم وتريكة امتحان درس ثالثة ثانوي اليوم، كل نقطة أقل من 68 حرفاً)، "
        "facebook_caption (بوست ملخص المغرب الشامل للصفوف الثلاثة مع أهم تريكات الدرس ودعوة لحفظ القوانين على كروت أنكي وسؤال المدرس الذكي على https://thanaweya-ashy.vercel.app)، "
        "instagram_caption (كابشن ريلز ملخص القوانين + دعوة لحفظ البوست للمراجعة + رابط الموقع)، "
        "youtube_title (عنوان أقل من 85 حرفاً عن ملخص وقوانين اليوم ينتهي بـ #Shorts)، "
        "youtube_description (ملخص الدروس ورابط https://thanaweya-ashy.vercel.app)، "
        "tiktok_caption (كابشن تيك توك مركز يشجع الطلاب يحفظوا الفيديو قبل سهرة الأسئلة بالليل + رابط الموقع)."
    )
    usr_p = (
        f"اليوم: {ctx['date_str']} | {ctx['mode_badge']}\n"
        f"لخّص بدقة علمية أهم القوانين والعلاقات وتريكات الامتحانات للدروس التالية التي يذاكرها الطلاب اليوم:\n"
        f"1) أولى ثانوي: {g1['subject']} | {g1['unit']} | {g1['lesson']}\n"
        f"2) ثانية ثانوي: {g2['subject']} | {g2['unit']} | {g2['lesson']}\n"
        f"3) ثالثة ثانوي: {g3['subject']} | {g3['unit']} | {g3['lesson']}"
    )
    return call_groq_json(api_key, sys_p, usr_p)


def generate_night_content(api_key: str, ctx: dict) -> dict:
    g1, g2, g3 = ctx["grades"]
    spot = ctx["night_spotlight"]
    sys_p = (
        "أنت واضع أسئلة امتحانات وتقييمات وزارة التربية والتعليم المصرية (الثانوية العامة والبكالوريا المصرية) لمنصة ثانويتي بلس (https://thanaweya-ashy.vercel.app). "
        "قواعد صارمة لا يمكن مخالفتها مطلقاً: "
        "1- ممنوع منعاً باتاً كتابة الإجابة الصحيحة أو التلميح إليها في أي حقل من الحقول لأن الطلاب هم من سيكتبون الإجابات في التعليقات! "
        "2- التزم حرفياً بالدروس المحددة لليوم فقط ولا تسأل أي سؤال خارجها أو من دروس متأخرة في المنهج! "
        "3- اكتب سؤال الفيديو الرئيسي (question_text) واضحاً ومشوقاً (أقل من 115 حرفاً) مع 4 اختيارات دقيقة (choice_a, choice_b, choice_c, choice_d بدون حروف أ/ب قبلها، كل اختيار أقل من 32 حرفاً). "
        "4- داخل نصوص البوستات (facebook_caption, instagram_caption, youtube_description) ضع بالإضافة لتحدي الفيديو سؤالاً سريعاً لكل صف من الصفوف الثلاثة على درس اليوم (بدون ذكر أي إجابة!) ليشارك طلاب أولى وثانية وثالثة ثانوي جميعاً في التعليقات، مع توجيههم لتصوير خطوات حلهم لمصحح التمارين وتسجيل أخطائهم في دفتر الأخطاء على https://thanaweya-ashy.vercel.app. "
        "أخرج JSON صالح فقط بالحقول التالية حصراً: "
        "grade_label, lesson_label, question_text, choice_a, choice_b, choice_c, choice_d, facebook_caption, instagram_caption, youtube_title, youtube_description, tiktok_caption."
    )
    assessment_note = (
        f"اليوم هو ({ctx['mode_badge']}): اجعل الأسئلة بأسلوب التقييم الأسبوعي الرسمي لوزارة التربية والتعليم المصرية على دروس هذا الأسبوع!"
        if ctx["day_mode"] == "weekly_assessment"
        else "اجعل الأسئلة من صميم درس اليوم الذي ذاكره الطلاب صباحاً وراجعوا ملخصه المغرب!"
    )
    usr_p = (
        f"{assessment_note}\n"
        f"الصف الرئيسي لبطاقة فيديو المؤقت التنازلي (30 ثانية) الليلة:\n"
        f"- الصف: {spot['grade_title']}\n"
        f"- المادة والوحدة والدرس: {spot['subject']} • {spot['unit']} • {spot['lesson']}\n\n"
        f"ودروس الصفوف الثلاثة اليوم لوضع أسئلة السهرة الإضافية في نص البوست (بدون إجابات نهائياً!):\n"
        f"- أولى ثانوي: {g1['subject']} ({g1['lesson']})\n"
        f"- ثانية ثانوي: {g2['subject']} ({g2['lesson']})\n"
        f"- ثالثة ثانوي: {g3['subject']} ({g3['lesson']})\n"
        "تذكر: youtube_title أقل من 85 حرفاً وينتهي بـ #Shorts، وممنوع كشف أي إجابة!"
    )
    return call_groq_json(api_key, sys_p, usr_p)


def detect_slot(now_dt: datetime) -> str:
    h = now_dt.hour
    if h < 13:
        return "morning"
    elif h < 19:
        return "maghrib"
    return "night"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "morning", "maghrib", "night"], default="auto")
    parser.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "media"))
    parser.add_argument("--cdn-base-url", default=os.environ.get("CDN_BASE_URL", ""))
    parser.add_argument("--send-webhook", action="store_true")
    args = parser.parse_args()

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise SystemExit("ERROR: GROQ_API_KEY environment variable is required.")

    now_dt = datetime.now(CAIRO_TZ)
    slot = detect_slot(now_dt) if args.slot == "auto" else args.slot
    ctx = get_academic_context(now_dt)
    tag = now_dt.strftime("%Y%m%d_%H%M")

    print(f"[{now_dt.isoformat()}] Running Thanaweya Plus Autopilot | slot={slot} | week={ctx['week_num']} | mode={ctx['day_mode']}")

    os.makedirs(args.out_dir, exist_ok=True)
    cdn = args.cdn_base_url.rstrip("/")

    if slot in ("morning", "maghrib"):
        ai = generate_morning_content(groq_key, ctx) if slot == "morning" else generate_maghrib_content(groq_key, ctx)
        cards = [
            {"points": ai.get("g1_points", [])},
            {"points": ai.get("g2_points", [])},
            {"points": ai.get("g3_points", [])},
        ]
        rendered = render_slides_and_short(slot, ctx, cards, args.out_dir, tag)
        s1, s2, s3 = [os.path.basename(p) for p in rendered["jpg_paths"]]
        v_name = os.path.basename(rendered["mp4_path"])

        payload = {
            "slot": slot,
            "date": ctx["date_str"],
            "fb_mode": "album",
            "slide_1_url": f"{cdn}/{s1}" if cdn else rendered["jpg_paths"][0],
            "slide_2_url": f"{cdn}/{s2}" if cdn else rendered["jpg_paths"][1],
            "slide_3_url": f"{cdn}/{s3}" if cdn else rendered["jpg_paths"][2],
            "video_url": f"{cdn}/{v_name}" if cdn else rendered["mp4_path"],
            "facebook_caption": ai["facebook_caption"],
            "instagram_caption": ai["instagram_caption"],
            "youtube_title": ai["youtube_title"][:95],
            "youtube_description": ai["youtube_description"],
            "tiktok_caption": ai["tiktok_caption"],
        }
    else:
        ai = generate_night_content(groq_key, ctx)
        spot = ctx["night_spotlight"]
        # فرض العنوان الرسمي الدقيق للصف والنظام والوحدة والدرس دائماً على بطاقة الفيديو
        ai["grade_label"] = spot["grade_title"]
        ai["lesson_label"] = f"{spot['subject']} • {spot['unit']} — {spot['lesson']}"
        mp4_path = render_night_countdown_video(ctx, ai, args.out_dir, tag)
        v_name = os.path.basename(mp4_path)

        payload = {
            "slot": "night",
            "date": ctx["date_str"],
            "fb_mode": "video",
            "slide_1_url": "",
            "slide_2_url": "",
            "slide_3_url": "",
            "video_url": f"{cdn}/{v_name}" if cdn else mp4_path,
            "facebook_caption": strip_digits_for_fb_video(ai["facebook_caption"]),
            "instagram_caption": ai["instagram_caption"],
            "youtube_title": ai["youtube_title"][:95],
            "youtube_description": ai["youtube_description"],
            "tiktok_caption": ai["tiktok_caption"],
        }

    payload_path = os.path.join(args.out_dir, "webhook_payload.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("Saved payload:", payload_path)

    webhook_url = os.environ.get("MAKE_WEBHOOK_URL", "").strip()
    if args.send_webhook and webhook_url:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("Make Webhook response:", resp.status, resp.read().decode("utf-8", errors="ignore"))


if __name__ == "__main__":
    main()
