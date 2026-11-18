# -*- coding: utf-8 -*-
"""
محرك الأدوات الدائمة ومجمع المفاتيح المتعددة V2.0 (Permanent Multi-Key Enterprise Hub)
تطبيق كامل ومباشر لكل ما تم الاتفاق عليه واستخراجه من قناتي NextGen AI & Ryan Academy:
- نظام تدوير المفاتيح ومجمعات الطاقة (Multi-Key Load Balancer & Round-Robin Key Pools):
  * BigModel GLM-4-Flash (1 إلى 10 مفاتيح - دائم مدى الحياة رسميًا)
  * Groq Cloud (1 إلى 10 مفاتيح - 14,400 طلب/يوم لكل حساب = 144,000 طلب/يوم)
  * XKiro API (1 إلى 10 مفاتيح - 10 مليون توكن/يوم لكل حساب = 100 مليون توكن/يوم)
  * NVIDIA NIM API (1 إلى 10 مفاتيح - 1000 طلب/يوم لكل حساب)
  * YepAPI & LarpRouter & MonkeyCode (مجمعات التوكنز والـ 200 موديل)
  * Google Gemini Flash Lite (حوض مفاتيح 1 إلى 10)
  * Pollinations AI (Zero-Auth مجاني دائم بدون أي مفاتيح)
  * Kling AI & Veo & ZeroGPU (مجمعات الفيديو السينمائي)
  * Microsoft Edge Neural Engine (أصوات مصرية وإنجليزية غير محدودة للأبد)
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

ENV_PATHS = [
    Path(__file__).resolve().parent / ".env",
    Path("/home/user/facebook-empire-autopilot/.env"),
    Path("/home/user/media-empire-autopilot/.env"),
    Path("/home/user/.env")
]

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

def _load_raw_env_file() -> Dict[str, str]:
    mapping = {}
    for ep in ENV_PATHS:
        if ep.exists():
            for line in ep.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    mapping[k.strip()] = v.strip().strip("'\"")
    return mapping

def collect_provider_keys(provider_tag: str) -> List[str]:
    """
    استخراج مصفوفة مفاتيح المنصة (Key Pool) تلقائياً لدعم الحسابات المتعددة (من 1 إلى 20 حساباً)
    يبحث عن:
      - TAG_API_KEY, TAG_KEY, TAG_TOKEN
      - TAG_KEY_1, TAG_KEY_2, ..., TAG_KEY_20
      - TAG_API_KEY_1, TAG_API_KEY_2, ..., TAG_API_KEY_20
    """
    raw_env = _load_raw_env_file()
    keys = []
    tag = provider_tag.upper().strip()

    candidate_patterns = [
        f"{tag}_API_KEY", f"{tag}_KEY", f"{tag}_TOKEN",
        f"{tag}_SECRET", f"{tag}"
    ]
    for i in range(1, 21):
        candidate_patterns.extend([
            f"{tag}_KEY_{i}",
            f"{tag}_API_KEY_{i}",
            f"{tag}_TOKEN_{i}",
            f"{tag}_{i}"
        ])

    for p in candidate_patterns:
        val = os.environ.get(p, "").strip() or raw_env.get(p, "").strip()
        if val and val not in keys and len(val) > 4:
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
# 1. مجمع محركات النصوص والقصص (Multi-Key LLM Load Balancer)
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
        """
        استعلام النصوص مع تدوير المفاتيح (Round-Robin Key Pool) عبر كافة المنصات التي اتفقنا عليها
        الترتيب:
        1. BigModel GLM-4-Flash Pool (دائم مدى الحياة رسميًا)
        2. Groq Cloud Pool (14.4k طلب/يوم لكل حساب)
        3. XKiro API Pool (10M توكن/يوم لكل حساب)
        4. Google Gemini Flash Pool (مفاتيح AI Studio)
        5. NVIDIA NIM API Pool (1000 طلب/يوم لكل حساب)
        6. YepAPI / LarpRouter / MonkeyCode Pool
        7. Pollinations AI (Zero-Auth مجاني 100% بدون أي مفاتيح)
        """
        full_p = f"{system_prompt}\n\n{user_prompt}"

        # 1. حوض مفاتيح BigModel GLM-4-Flash (دائم للأبد)
        big_keys = collect_provider_keys("BIGMODEL") + collect_provider_keys("ZHIPU") + collect_provider_keys("GLM")
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
                    timeout=18
                )
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"].strip()
                    if txt:
                        print("   [PermanentLLMHub] Success via BigModel GLM-4-Flash")
                        return txt
            except Exception:
                continue

        # 2. حوض مفاتيح Groq Cloud (حسابات متعددة: كل حساب 14,400 طلب/يوم)
        groq_keys = collect_provider_keys("GROQ")
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
                        timeout=12
                    )
                    if r.status_code == 200:
                        txt = r.json()["choices"][0]["message"]["content"].strip()
                        if txt:
                            print(f"   [PermanentLLMHub] Success via Groq ({gm})")
                            return txt
                except Exception:
                    continue

        # 3. حوض مفاتيح XKiro API (كل حساب 10 مليون توكن تتجدد يومياً)
        xkiro_keys = collect_provider_keys("XKIRO")
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
                    timeout=18
                )
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"].strip()
                    if txt:
                        print("   [PermanentLLMHub] Success via XKiro (DeepSeek V3)")
                        return txt
            except Exception:
                continue

        # 4. حوض مفاتيح Google Gemini Flash (حسابات متعددة)
        gem_keys = collect_provider_keys("GEMINI")
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
                            print(f"   [PermanentLLMHub] Success via Gemini ({m})")
                            return txt
                except Exception:
                    continue

        # 5. حوض مفاتيح NVIDIA NIM API (1000 طلب/يوم لكل حساب)
        nv_keys = collect_provider_keys("NVIDIA") + collect_provider_keys("NIM")
        for nk in nv_keys:
            try:
                r = requests.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {nk}", "Content-Type": "application/json"},
                    json={
                        "model": "meta/llama-3.3-70b-instruct",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature
                    },
                    timeout=18
                )
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"].strip()
                    if txt:
                        print("   [PermanentLLMHub] Success via NVIDIA NIM")
                        return txt
            except Exception:
                continue

        # 6. حوض مفاتيح YepAPI / LarpRouter / MonkeyCode
        misc_keys = collect_provider_keys("YEPAPI") + collect_provider_keys("LARPROUTER") + collect_provider_keys("MONKEY")
        for mk in misc_keys:
            for ep in ["https://api.yepapi.com/v1/chat/completions", "https://api.larprouter.com/v1/chat/completions"]:
                try:
                    r = requests.post(
                        ep,
                        headers={"Authorization": f"Bearer {mk}", "Content-Type": "application/json"},
                        json={
                            "model": "deepseek-chat",
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
                            print(f"   [PermanentLLMHub] Success via Router ({ep})")
                            return txt
                except Exception:
                    continue

        # 7. شبكة Pollinations AI (Zero-Auth مجاني 100% بدون أي مفاتيح)
        try:
            encoded_prompt = requests.utils.quote(f"{system_prompt}. {user_prompt}"[:500])
            r = requests.get(f"https://text.pollinations.ai/{encoded_prompt}?model=openai", timeout=15)
            if r.status_code == 200 and len(r.text.strip()) > 20:
                print("   [PermanentLLMHub] Success via Pollinations AI (Zero-Auth)")
                return r.text.strip()
        except Exception:
            pass

        return None

# ==============================================================================
# 2. مجمع محركات المرئيات وتوليد الفيديو (Multi-Key Video Load Balancer)
# ==============================================================================
class PermanentVisualHub:
    @classmethod
    def generate_kling_video_clip(
        cls,
        prompt: str,
        out_mp4: Path,
        duration_sec: float = 4.0
    ) -> bool:
        """توليد فيديو سينمائي عبر حوض حسابات Kling AI (66 نقطة تتجدد يومياً لكل حساب)"""
        kling_keys = collect_provider_keys("KLING")
        if not kling_keys:
            return False

        out_mp4 = Path(out_mp4)
        out_mp4.parent.mkdir(parents=True, exist_ok=True)

        for ki, kkey in enumerate(kling_keys):
            try:
                # Kling Open API Dispatch
                headers = {"Authorization": f"Bearer {kkey}", "Content-Type": "application/json"}
                payload = {
                    "model_name": "kling-v1",
                    "prompt": prompt[:250],
                    "cfg_scale": 0.5,
                    "mode": "std",
                    "duration": int(round(duration_sec))
                }
                r = requests.post("https://api.klingai.com/v1/videos/text2video", headers=headers, json=payload, timeout=20)
                if r.status_code == 200:
                    task_id = r.json().get("data", {}).get("task_id")
                    if task_id:
                        for _ in range(12):
                            time.sleep(5)
                            stat_r = requests.get(f"https://api.klingai.com/v1/videos/text2video/{task_id}", headers=headers, timeout=15)
                            if stat_r.status_code == 200:
                                v_res = stat_r.json().get("data", {})
                                if v_res.get("task_status") == "succeed":
                                    v_url = v_res.get("task_result", {}).get("videos", [{}])[0].get("url")
                                    if v_url:
                                        v_bytes = requests.get(v_url, timeout=30).content
                                        if len(v_bytes) > 50000:
                                            out_mp4.write_bytes(v_bytes)
                                            print(f"[✓] Kling AI Video generated via Account #{ki+1} ({len(v_bytes)} bytes)")
                                            return True
            except Exception as e:
                print(f"[!] Kling Account #{ki+1} failed: {e}")
                continue
        return False

    @classmethod
    def generate_pollinations_motion_clip(
        cls,
        prompt: str,
        out_mp4: Path,
        is_vertical: bool = True,
        duration_sec: float = 4.0
    ) -> bool:
        """توليد صورة FLUX سينمائية عالية الدقة عبر Pollinations وتحويلها لفيديو 2.5D Ken-Burns حركي"""
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
# 3. مجمع محركات الصوتيات والراوي البشري (Multi-Key Voice Load Balancer)
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

        # 1. الخط الأساسي الدائم وغير المحدود (Microsoft Edge Neural)
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

        # 2. خط الدفاع الثاني: حوض مفاتيح Fish Audio المتعددة (إذا وفر المستخدم مفاتيح جديدة)
        fish_keys = collect_provider_keys("FISH")
        ref_id = "7f92f8afb8ec43bf81429cc1c9199cb1" if lang == "ar" else "e58eb11e2f18413dbfa1202e2124a91a"
        for fi, fkey in enumerate(fish_keys):
            try:
                r = requests.post(
                    "https://api.fish.audio/v1/tts",
                    headers={"Authorization": f"Bearer {fkey}", "Content-Type": "application/json"},
                    json={"text": clean, "reference_id": ref_id, "format": "mp3", "latency": "normal"},
                    timeout=20
                )
                if r.status_code == 200 and len(r.content) > 3000:
                    out_mp3.write_bytes(r.content)
                    print(f"[✓] Narration generated via Fish Audio Account #{fi+1} ({len(r.content)} bytes)")
                    return out_mp3
            except Exception:
                continue

        # 3. توليد تراك طوارئ محيطي
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
