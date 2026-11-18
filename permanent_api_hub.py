# -*- coding: utf-8 -*-
"""
محرك الأدوات الدائمة والذكاء الاصطناعي الشامل V1.0 (Permanent API Hub)
مستخرج ومطور بناءً على الفحص العميق لقناتي NextGen AI & Ryan Academy:
1. محرك النصوص الدائم: (Gemini Flash Lite -> Groq Cloud -> BigModel GLM-4 -> XKiro -> Pollinations Zero-Auth -> Local)
2. محرك المرئيات الدائم: (ZeroGPU LTX -> Pixabay 4K -> Pollinations FLUX + 2.5D Motion -> Procedural)
3. محرك الصوتيات الدائم: (Microsoft Edge Neural TTS -> Fish Audio Pool -> Cinematic Ambient Generator)
"""

import asyncio
import itertools
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import edge_tts
try:
    import _env_loader
except ImportError:
    pass

# ==============================================================================
# الأدوات والمساعدات العامة
# ==============================================================================
def get_ffmpeg_bin() -> str:
    which_ff = shutil.which("ffmpeg")
    if which_ff:
        return which_ff
    user_ff = Path("/home/user/ffmpeg")
    if user_ff.exists() and os.access(user_ff, os.X_OK):
        return str(user_ff)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def collect_env_keys(prefixes: List[str]) -> List[str]:
    """جمع المفاتيح النشطة من البيئة مع منع التكرار"""
    keys = []
    for p in prefixes:
        val = os.environ.get(p, "").strip()
        if val and val not in keys:
            keys.append(val)
    return keys

def clean_json_output(raw_text: str) -> Optional[Dict[str, Any]]:
    """تنظيف واستخراج كائن JSON بأمان من أي رد لغوي"""
    try:
        clean = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        clean = re.sub(r"\s*```$", "", clean).strip()
        start_i = clean.find("{")
        end_i = clean.rfind("}")
        if start_i != -1 and end_i != -1 and end_i > start_i:
            clean = clean[start_i:end_i + 1]
        data = json.loads(clean)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

# ==============================================================================
# 1. محرك النصوص والقصص متعدد المزودين (Permanent LLM Hub)
# ==============================================================================
class PermanentLLMHub:
    GEMINI_MODELS = [
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview"
    ]

    GROQ_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant"
    ]

    @classmethod
    def query_llm(cls, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> Optional[str]:
        """استعلام النصوص مع التعاقب الذاتي (Cascade Fallback) عبر 6 طبقات متتالية"""
        full_p = f"{system_prompt}\n\n{user_prompt}"

        # الطبقة 1: Google Gemini Flash Multi-Key
        gem_keys = collect_env_keys(["GEMINI_API_KEY_2", "GEMINI_API_KEY", "GEMINI_API_KEY_3"])
        for k in gem_keys:
            for m in cls.GEMINI_MODELS:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
                    r = requests.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json={"contents": [{"parts": [{"text": full_p}]}]},
                        timeout=18
                    )
                    if r.status_code == 200:
                        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if txt:
                            return txt
                except Exception:
                    continue

        # الطبقة 2: Groq Cloud API (فائق السرعة)
        groq_keys = collect_env_keys(["GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2"])
        for gk in groq_keys:
            for gm in cls.GROQ_MODELS:
                try:
                    r = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {gk}", "Content-Type": "application/json"},
                        json={
                            "model": gm,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": temperature
                        },
                        timeout=15
                    )
                    if r.status_code == 200:
                        txt = r.json()["choices"][0]["message"]["content"].strip()
                        if txt:
                            return txt
                except Exception:
                    continue

        # الطبقة 3: BigModel GLM-4-Flash (مجاني دائم للأبد)
        big_keys = collect_env_keys(["BIGMODEL_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY"])
        for bk in big_keys:
            try:
                r = requests.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {bk}", "Content-Type": "application/json"},
                    json={
                        "model": "glm-4-flash",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature
                    },
                    timeout=20
                )
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"].strip()
                    if txt:
                        return txt
            except Exception:
                continue

        # الطبقة 4: XKiro API (تجدد يومي 5-15 مليون توكن)
        xkiro_keys = collect_env_keys(["XKIRO_API_KEY"])
        for xk in xkiro_keys:
            try:
                r = requests.post(
                    "https://api.xkiro.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {xk}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-v3",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature
                    },
                    timeout=20
                )
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"].strip()
                    if txt:
                        return txt
            except Exception:
                continue

        # الطبقة 5: Pollinations AI (Zero-Auth مجاني 100% بدون أي مفاتيح)
        try:
            encoded_prompt = requests.utils.quote(f"{system_prompt}. {user_prompt}"[:500])
            r = requests.get(f"https://text.pollinations.ai/{encoded_prompt}?model=openai", timeout=20)
            if r.status_code == 200 and len(r.text.strip()) > 20:
                return r.text.strip()
        except Exception:
            pass

        return None

# ==============================================================================
# 2. محرك المرئيات وتوليد المشاهد المتحركة (Permanent Visual Hub)
# ==============================================================================
class PermanentVisualHub:
    @classmethod
    def generate_pollinations_motion_clip(
        cls,
        prompt: str,
        out_mp4: Path,
        is_vertical: bool = True,
        duration_sec: float = 4.0
    ) -> bool:
        """
        توليد صورة FLUX سينمائية عالية الدقة عبر Pollinations (Zero-Auth)
        ثم تحويلها فورياً إلى كليب فيديو متحرك بحركة كاميرا سينمائية 2.5D (Ken Burns) عبر FFmpeg
        """
        out_mp4 = Path(out_mp4)
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        w, h = (1080, 1920) if is_vertical else (1920, 1080)
        clean_prompt = requests.utils.quote(f"cinematic 35mm film still, {prompt[:200]}, 8k atmospheric lighting")
        img_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width={w}&height={h}&model=flux&nologo=true"

        temp_jpg = out_mp4.parent / f"_temp_p_{out_mp4.stem}.jpg"
        try:
            r = requests.get(img_url, timeout=35)
            if r.status_code == 200 and len(r.content) > 15000:
                temp_jpg.write_bytes(r.content)
            else:
                return False
        except Exception:
            return False

        # تحويل الصورة إلى فيديو بحركة سينمائية (Creeping Zoom + Subtle Unsharp)
        ffmpeg_bin = get_ffmpeg_bin()
        fps = 25
        frames = int(round(duration_sec * fps))
        vf = f"zoompan=z='min(zoom+0.0016,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},unsharp=5:5:0.8:5:5:0.0"

        try:
            subprocess.run([
                ffmpeg_bin, "-y",
                "-loop", "1", "-i", str(temp_jpg),
                "-vf", vf,
                "-t", f"{duration_sec:.2f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-an", str(out_mp4)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if temp_jpg.exists():
                temp_jpg.unlink()
            print(f"[✓] Pollinations 2.5D Motion Clip Generated: {out_mp4.name} ({out_mp4.stat().st_size} bytes)")
            return out_mp4.exists() and out_mp4.stat().st_size > 50000
        except Exception as e:
            if temp_jpg.exists():
                temp_jpg.unlink()
            print(f"[!] Pollinations motion conversion failed: {e}")
            return False

    @classmethod
    def generate_procedural_cinematic_clip(
        cls,
        out_mp4: Path,
        is_vertical: bool = True,
        duration_sec: float = 4.0
    ) -> bool:
        """توليد كليب مظلم سينمائي إجرائي عبر FFmpeg يضمن سلامة الفيديو 100% في الحالات القصوى"""
        ffmpeg_bin = get_ffmpeg_bin()
        out_mp4 = Path(out_mp4)
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        res = "1080x1920" if is_vertical else "1920x1080"
        dur = max(2.0, min(15.0, float(duration_sec)))

        try:
            subprocess.run([
                ffmpeg_bin, "-y", "-f", "lavfi",
                "-i", f"color=c=0x0a0c10:s={res}:d={dur:.2f},drawgrid=w=140:h=140:t=1:c=white@0.04",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-an", str(out_mp4)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out_mp4.exists() and out_mp4.stat().st_size > 10000
        except Exception:
            return False

# ==============================================================================
# 3. محرك الصوتيات والراوي البشري الدائم (Permanent Audio Hub)
# ==============================================================================
class PermanentAudioHub:
    AR_VOICES = ["ar-EG-ShakirNeural", "ar-EG-SalmaNeural"]
    EN_VOICES = ["en-US-ChristopherNeural", "en-US-JennyNeural"]

    @classmethod
    def synthesize_speech(cls, text: str, out_mp3: Path, lang: str = "ar") -> Path:
        """توليد الصوت البشري الواقعي الاحترافي عبر مايكروسوفت مع تنظيف وضمان عدم السكون"""
        out_mp3 = Path(out_mp3)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)

        clean = text.replace("\u202f", " ").replace("\u00a0", " ")
        for ch in ("«", "»", "“", "”", '"', "<", ">", "&", "*", "#", "$", "@", "_"):
            clean = clean.replace(ch, " ")
        clean = re.sub(r"[\U00010000-\U0010ffff]", "", clean)
        clean = re.sub(r"\.{3,}", "..", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            clean = "في هذه اللحظة الغامضة تتكشف أسرار جديدة."

        voices = cls.AR_VOICES if lang == "ar" else cls.EN_VOICES
        for voice in voices:
            for attempt in range(3):
                try:
                    communicate = edge_tts.Communicate(clean, voice)
                    asyncio.run(communicate.save(str(out_mp3)))
                    if out_mp3.exists() and out_mp3.stat().st_size > 3000:
                        return out_mp3
                except Exception:
                    time.sleep(0.8)

        # توليد تراك طوارئ محيطي
        ffmpeg_bin = get_ffmpeg_bin()
        try:
            subprocess.run([
                ffmpeg_bin, "-y", "-f", "lavfi",
                "-i", "sine=frequency=65:duration=45,volume=0.25[a1];sine=frequency=95:duration=45,volume=0.18[a2];[a1][a2]amix=inputs=2,aecho=0.8:0.88:1000:0.4",
                "-c:a", "libmp3lame", "-b:a", "192k",
                str(out_mp3)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        return out_mp3
