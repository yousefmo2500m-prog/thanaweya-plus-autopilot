#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ناشر Zernio المباشر (تيك توك + أول تعليق مثبت + دعم يوتيوب/إنستجرام بأول تعليق تلقائي)
=======================================================================================
يرفع ملف الفيديو MP4 مباشرة إلى سحابة Zernio (Presigned Upload بنوع video/mp4 صريح)،
وينشر على تيك توك ثم يكتب أول تعليق بالرابط ويثبّته (Pin) عبر واجهة Zernio Inbox API،
كما يكتشف تلقائياً لو تم ربط قناة يوتيوب (الحساب المجاني الثاني في Zernio) فينشر الـ Short
ويضع أول تعليق ومثبت على يوتيوب تلقائياً بدون استهلاك نقاط Make!
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ZERNIO_BASE = "https://zernio.com/api/v1"


def _zernio_json_request(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
    extra_headers: Optional[Dict[str, str]] = None,
) -> tuple[int, Dict[str, Any]]:
    url = f"{ZERNIO_BASE}{path}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "ThanaweyaPlus-Autopilot/3.3",
    }
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", errors="replace")
            return status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw_error": raw[:500]}
        return e.code, parsed


def upload_mp4_to_zernio_storage(video_path: Path, api_key: str) -> str:
    """يرفع ملف MP4 مباشرة إلى تخزين Zernio السحابي ويعيد رابط publicUrl بنوع video/mp4 مضمون 100%."""
    file_bytes = video_path.read_bytes()
    status, presign = _zernio_json_request(
        "POST",
        "/media/presign",
        api_key,
        payload={
            "filename": video_path.name,
            "contentType": "video/mp4",
            "size": len(file_bytes),
        },
        timeout=45,
    )
    if status not in (200, 201) or "uploadUrl" not in presign or "publicUrl" not in presign:
        raise RuntimeError(f"Zernio presign failed ({status}): {presign}")

    put_req = urllib.request.Request(
        presign["uploadUrl"],
        data=file_bytes,
        headers={"Content-Type": "video/mp4"},
        method="PUT",
    )
    with urllib.request.urlopen(put_req, timeout=180) as put_resp:
        if put_resp.getcode() not in (200, 201, 204):
            raise RuntimeError(f"Zernio R2 PUT failed with HTTP {put_resp.getcode()}")

    return str(presign["publicUrl"])


def list_connected_accounts(api_key: str) -> Dict[str, str]:
    """يجلب كافة الحسابات المتصلة في Zernio ويعيد خريطة {platform: account_id}."""
    status, data = _zernio_json_request("GET", "/accounts", api_key, timeout=30)
    if status != 200:
        raise RuntimeError(f"Zernio GET /accounts failed ({status}): {data}")

    accounts = data.get("accounts") if isinstance(data, dict) else data
    if not isinstance(accounts, list):
        accounts = data.get("data", []) if isinstance(data, dict) else []

    found: Dict[str, str] = {}
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        plat = str(acc.get("platform", "")).lower().strip()
        acc_id = acc.get("_id") or acc.get("id") or acc.get("accountId")
        if plat and acc_id and plat not in found:
            found[plat] = str(acc_id)
    return found


def choose_allowed_privacy(account_id: str, api_key: str) -> str:
    """يفحص إعدادات منشئ المحتوى على تيك توك لاختيار مستوى الخصوصية العام المسموح للحساب."""
    status, info = _zernio_json_request("GET", f"/accounts/{account_id}/tiktok/creator-info", api_key, timeout=30)
    if status == 200 and isinstance(info, dict):
        levels = info.get("privacyLevels") or []
        vals = [lv.get("value") if isinstance(lv, dict) else str(lv) for lv in levels]
        if "PUBLIC_TO_EVERYONE" in vals:
            return "PUBLIC_TO_EVERYONE"
        if vals:
            return str(vals[0])
    return "PUBLIC_TO_EVERYONE"


def _get_recent_platform_post_ids(account_id: str, api_key: str) -> List[str]:
    """يجلب أحدث معرفات المنشورات الرقمية الحية مباشرة من المنصة عبر GET /v1/accounts/{accountId}/posts."""
    status, data = _zernio_json_request("GET", f"/accounts/{account_id}/posts", api_key, timeout=30)
    if status != 200 or not isinstance(data, dict):
        return []
    posts = data.get("posts") or []
    out: List[str] = []
    for p in posts:
        if isinstance(p, dict) and p.get("id"):
            out.append(str(p["id"]).strip())
    return out


def _post_and_pin_tiktok_first_comment(
    account_id: str,
    before_ids: Set[str],
    native_publish_id: str,
    first_comment: str,
    api_key: str,
) -> Dict[str, Any]:
    """ينتظر ظهور المعرّف الرقمي الحقيقي لفيديو تيك توك (int VideoId) ثم ينشر أول تعليق ويثبّته (Pin)."""
    if not first_comment.strip():
        return {"commented": False}

    candidate_numeric_ids: List[str] = []

    # 1) استطلاع أحدث منشور حي على حساب تيك توك للحصول على المعرّف الرقمي الفعلي للفيديو بعد الفهرسة
    for poll_idx in range(5):
        time.sleep(7)
        live_ids = _get_recent_platform_post_ids(account_id, api_key)
        for lid in live_ids:
            if lid not in before_ids and lid.isdigit():
                candidate_numeric_ids.append(lid)
                break
        if candidate_numeric_ids:
            print(f"[TikTok First Comment] Resolved live numeric VideoId={candidate_numeric_ids[0]} on poll #{poll_idx + 1}")
            break

    # 2) استخراج الرقم الطويل الاحتياطي من v_pub_url~v2.<digits> إن لم يظهر بعد في القائمة
    for num_match in re.findall(r"\d{15,22}", native_publish_id or ""):
        if num_match not in candidate_numeric_ids:
            candidate_numeric_ids.append(num_match)

    # 3) كحل أخير نجرّب أحدث منشور رقمي في الحساب إن كان مطابقاً زمنياً
    if not candidate_numeric_ids:
        live_ids = _get_recent_platform_post_ids(account_id, api_key)
        if live_ids and live_ids[0].isdigit():
            candidate_numeric_ids.append(live_ids[0])

    for vid_id in candidate_numeric_ids:
        idem_key = f"tk-comment-{vid_id}-{uuid.uuid4().hex[:8]}"
        c_status, c_resp = _zernio_json_request(
            "POST",
            f"/inbox/comments/{vid_id}",
            api_key,
            payload={
                "accountId": account_id,
                "message": first_comment[:1400],
            },
            timeout=45,
            extra_headers={"Idempotency-Key": idem_key},
        )
        if c_status in (200, 201):
            c_data = c_resp.get("data", {}) if isinstance(c_resp, dict) else {}
            comment_id = str(c_data.get("commentId") or c_resp.get("commentId") or "")
            print(f"[TikTok First Comment] Posted successfully on VideoId={vid_id}! commentId={comment_id}")
            pinned = False
            if comment_id:
                time.sleep(2)
                p_status, p_resp = _zernio_json_request(
                    "POST",
                    f"/inbox/comments/{vid_id}/{comment_id}/pin",
                    api_key,
                    payload={"accountId": account_id},
                    timeout=30,
                )
                pinned = p_status in (200, 201)
                print(f"[TikTok Pin Comment] Pin status={p_status} pinned={pinned} resp={p_resp}")
            return {"commented": True, "pinned": pinned, "commentId": comment_id, "videoId": vid_id}

        print(f"[TikTok First Comment] Attempt on numeric VideoId={vid_id} returned ({c_status}): {c_resp}")
        if c_status in (400, 403) and "PLATFORM_LIMITATION" in str(c_resp):
            return {"commented": False, "reason": "tiktok_reconnect_needed_for_comments"}

    return {"commented": False}


def publish_direct_via_zernio(
    video_path: Path,
    tiktok_caption: str,
    youtube_title: str,
    youtube_description: str,
    instagram_caption: str,
    first_comment: str,
    api_key: str,
) -> Dict[str, Any]:
    """
    ينشر الفيديو عبر Zernio على:
    1) تيك توك + يكتب أول تعليق ويثبته (Pin).
    2) يوتيوب Shorts (إن كانت القناة مربوطة كحساب ثانٍ مجاني في Zernio) + يكتب ويثبت أول تعليق تلقائياً عبر firstComment!
    3) إنستجرام Reels (إن كان مربوطاً في Zernio) + أول تعليق تلقائي عبر firstComment!
    """
    result: Dict[str, Any] = {
        "tiktok_ok": False,
        "youtube_ok": False,
        "instagram_ok": False,
        "zernio_video_url": "",
    }

    print("[Zernio Direct] Uploading MP4 directly to Zernio cloud storage (video/mp4)...")
    zernio_public_url = upload_mp4_to_zernio_storage(video_path, api_key)
    result["zernio_video_url"] = zernio_public_url
    print(f"[Zernio Direct] Uploaded to Zernio CDN -> {zernio_public_url}")

    accounts = list_connected_accounts(api_key)
    print(f"[Zernio Direct] Connected platforms detected: {list(accounts.keys())}")

    # 1) النشر على تيك توك + أول تعليق مثبت
    if "tiktok" in accounts:
        tk_acc = accounts["tiktok"]
        before_tk_ids = set(_get_recent_platform_post_ids(tk_acc, api_key))
        privacy_level = choose_allowed_privacy(tk_acc, api_key)
        tk_body: Dict[str, Any] = {
            "content": tiktok_caption[:2100],
            "mediaItems": [{"type": "video", "url": zernio_public_url}],
            "platforms": [{"platform": "tiktok", "accountId": tk_acc}],
            "tiktokSettings": {
                "privacy_level": privacy_level,
                "allow_comment": True,
                "allow_duet": True,
                "allow_stitch": True,
                "video_cover_timestamp_ms": 1500,
                "content_preview_confirmed": True,
                "express_consent_given": True,
            },
            "publishNow": True,
        }
        status, resp = _zernio_json_request("POST", "/posts", api_key, payload=tk_body, timeout=180)
        post_obj = resp.get("post", {}) if isinstance(resp, dict) else {}
        post_status = str(post_obj.get("status", ""))

        if status == 207 or post_status == "failed":
            plat_errs = [
                p.get("errorMessage", "")
                for p in (post_obj.get("platforms") or [])
                if isinstance(p, dict)
            ]
            err_joined = " | ".join(plat_errs) or str(resp)
            print(f"[TikTok Direct] Direct publish returned ({status}): {err_joined}")
            if "capacity" in err_joined.lower() or "active user" in err_joined.lower():
                tk_body["tiktokSettings"]["draft"] = True
                s2, _ = _zernio_json_request("POST", "/posts", api_key, payload=tk_body, timeout=180)
                result["tiktok_ok"] = s2 in (200, 201)
        elif status in (200, 201, 202):
            zernio_post_id = str(post_obj.get("_id") or "")
            plat_entries = post_obj.get("platforms") or []
            native_tk_id = ""
            for pe in plat_entries:
                if isinstance(pe, dict) and pe.get("platform") == "tiktok":
                    native_tk_id = str(pe.get("platformPostId") or pe.get("postId") or "")
            print(f"[TikTok Direct] Published successfully! post_id={zernio_post_id} native_id={native_tk_id}")
            result["tiktok_ok"] = True
            try:
                c_info = _post_and_pin_tiktok_first_comment(
                    account_id=tk_acc,
                    before_ids=before_tk_ids,
                    native_publish_id=native_tk_id,
                    first_comment=first_comment,
                    api_key=api_key,
                )
                result["tiktok_comment"] = c_info
            except Exception as ce:
                print(f"[TikTok First Comment Warning] {ce}")

    # 2) النشر على يوتيوب Shorts + أول تعليق مثبت تلقائياً عبر Zernio (إن كانت القناة مربوطة في Zernio)
    if "youtube" in accounts:
        yt_acc = accounts["youtube"]
        yt_body: Dict[str, Any] = {
            "content": youtube_description[:4800],
            "tags": ["ثانويتي بلس", "الثانوية العامة", "البكالوريا المصرية", "اولى ثانوي", "تانية ثانوي", "تالتة ثانوي"],
            "mediaItems": [{"type": "video", "url": zernio_public_url}],
            "platforms": [
                {
                    "platform": "youtube",
                    "accountId": yt_acc,
                    "platformSpecificData": {
                        "title": youtube_title[:95],
                        "visibility": "public",
                        "categoryId": "27",
                        "madeForKids": False,
                        "containsSyntheticMedia": False,
                        "firstComment": first_comment[:2000],
                    },
                }
            ],
            "publishNow": True,
        }
        ys, yresp = _zernio_json_request("POST", "/posts", api_key, payload=yt_body, timeout=180)
        ypost = yresp.get("post", {}) if isinstance(yresp, dict) else {}
        if ys in (200, 201, 202) and str(ypost.get("status", "")) != "failed":
            print(f"[YouTube Direct + FirstComment] Published successfully! post_id={ypost.get('_id')}")
            result["youtube_ok"] = True
        else:
            print(f"[YouTube Direct Warning] ({ys}): {yresp}")

    # 3) النشر على إنستجرام Reels + أول تعليق تلقائي عبر Zernio (إن كان مربوطاً في Zernio)
    if "instagram" in accounts:
        ig_acc = accounts["instagram"]
        ig_body: Dict[str, Any] = {
            "content": instagram_caption[:2100],
            "mediaItems": [{"type": "video", "url": zernio_public_url}],
            "platforms": [
                {
                    "platform": "instagram",
                    "accountId": ig_acc,
                    "platformSpecificData": {
                        "shareToFeed": True,
                        "firstComment": first_comment[:2000],
                    },
                }
            ],
            "publishNow": True,
        }
        igs, igresp = _zernio_json_request("POST", "/posts", api_key, payload=ig_body, timeout=180)
        igpost = igresp.get("post", {}) if isinstance(igresp, dict) else {}
        if igs in (200, 201, 202) and str(igpost.get("status", "")) != "failed":
            print(f"[Instagram Direct + FirstComment] Published successfully! post_id={igpost.get('_id')}")
            result["instagram_ok"] = True
        else:
            print(f"[Instagram Direct Warning] ({igs}): {igresp}")

    return result


# توافق خلفي في حال استدعاء الدالة القديمة
def publish_video_to_tiktok_direct(video_path: Path, caption: str, api_key: str) -> Dict[str, Any]:
    r = publish_direct_via_zernio(
        video_path=video_path,
        tiktok_caption=caption,
        youtube_title="ثانويتي بلس",
        youtube_description=caption,
        instagram_caption=caption,
        first_comment="",
        api_key=api_key,
    )
    return {"ok": r.get("tiktok_ok", False), "zernio_video_url": r.get("zernio_video_url", "")}
