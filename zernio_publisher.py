#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ناشر تيك توك المباشر عبر واجهة Zernio الرسمية (بدون حدود الـ 40 ثانية الخاصة بـ Make.com)
=========================================================================================
يرفع ملف الفيديو MP4 مباشرة من القرص إلى سحابة Zernio (Presigned Upload بنوع video/mp4 صريح)،
ثم يكتشف حساب تيك توك المتصل وإعدادات الخصوصية المسموحة له وينشر الفيديو بمهلة 180 ثانية كاملة.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ZERNIO_BASE = "https://zernio.com/api/v1"


def _zernio_json_request(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
) -> tuple[int, Dict[str, Any]]:
    url = f"{ZERNIO_BASE}{path}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "ThanaweyaPlus-Autopilot/3.1",
    }
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"

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


def find_tiktok_account_id(api_key: str) -> str:
    """يجلب تلقائياً معرّف حساب تيك توك المتصل بحساب Zernio بدون أي إعداد يدوي."""
    status, data = _zernio_json_request("GET", "/accounts", api_key, timeout=30)
    if status != 200:
        raise RuntimeError(f"Zernio GET /accounts failed ({status}): {data}")

    accounts = data.get("accounts") if isinstance(data, dict) else data
    if not isinstance(accounts, list):
        accounts = data.get("data", []) if isinstance(data, dict) else []

    for acc in accounts:
        if str(acc.get("platform", "")).lower() == "tiktok":
            acc_id = acc.get("_id") or acc.get("id") or acc.get("accountId")
            if acc_id:
                return str(acc_id)

    raise RuntimeError(
        "لم يتم العثور على حساب TikTok مربوط داخل Zernio! تأكد من ربط حساب تيك توك في لوحة تحكم zernio.com."
    )


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


def publish_video_to_tiktok_direct(
    video_path: Path,
    caption: str,
    api_key: str,
) -> Dict[str, Any]:
    """يرفع الفيديو وينشره مباشرة على تيك توك عبر Zernio مع معالجة ذكية لكافة الحالات."""
    print("[TikTok Direct] Uploading MP4 directly to Zernio cloud storage (video/mp4)...")
    zernio_public_url = upload_mp4_to_zernio_storage(video_path, api_key)
    print(f"[TikTok Direct] Uploaded to Zernio CDN -> {zernio_public_url}")

    account_id = find_tiktok_account_id(api_key)
    privacy_level = choose_allowed_privacy(account_id, api_key)
    print(f"[TikTok Direct] Found TikTok accountId={account_id} | privacy={privacy_level}")

    post_body: Dict[str, Any] = {
        "content": caption[:2100],
        "mediaItems": [
            {
                "type": "video",
                "url": zernio_public_url,
            }
        ],
        "platforms": [
            {
                "platform": "tiktok",
                "accountId": account_id,
            }
        ],
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

    status, resp = _zernio_json_request("POST", "/posts", api_key, payload=post_body, timeout=180)
    post_obj = resp.get("post", {}) if isinstance(resp, dict) else {}
    post_status = str(post_obj.get("status", ""))

    # في حال إرجاع 207 بسبب امتلاء الحصة المؤقتة لتطبيق المطورين (reached_active_user_cap)، نرسلها لصندوق الوارد في تيك توك كمسودة جاهزة
    if status == 207 or post_status == "failed":
        plat_errs = [
            p.get("errorMessage", "")
            for p in (post_obj.get("platforms") or [])
            if isinstance(p, dict)
        ]
        err_joined = " | ".join(plat_errs) or str(resp)
        print(f"[TikTok Direct] Direct publish returned ({status}): {err_joined}")
        if "capacity" in err_joined.lower() or "active user" in err_joined.lower():
            print("[TikTok Direct] Falling back to TikTok Creator Inbox (draft=True) due to developer lane cap...")
            post_body["tiktokSettings"]["draft"] = True
            s2, r2 = _zernio_json_request("POST", "/posts", api_key, payload=post_body, timeout=180)
            return {"ok": s2 in (200, 201), "mode": "inbox_draft", "zernio_video_url": zernio_public_url, "response": r2}
        return {"ok": False, "error": err_joined, "zernio_video_url": zernio_public_url, "response": resp}

    if status in (200, 201, 202):
        print(f"[TikTok Direct] Published successfully! post_id={post_obj.get('_id')} status={post_status}")
        return {"ok": True, "mode": "direct", "zernio_video_url": zernio_public_url, "response": resp}

    return {"ok": False, "error": f"HTTP {status}: {resp}", "zernio_video_url": zernio_public_url}
