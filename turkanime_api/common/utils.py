# -*- coding: utf-8 -*-
"""
turkanime_api için ortak yardımcı fonksiyonlar.
"""
import platform
import re
import subprocess as sp
import importlib
from typing import Optional, Dict, Any

def get_platform() -> str:
    """Mevcut platformu tespit et."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "macos"
    elif system == "android":
        return "android"
    else:
        return "unknown"

def get_arch() -> str:
    """Mevcut mimariyi tespit et."""
    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        return "x64"
    elif machine in ["i386", "i686"]:
        return "x32"
    elif machine in ["arm64", "aarch64"]:
        return "arm64"
    else:
        return "x64"  # Bilinmeyen mimariler için varsayılan

def get_ydl_opts(logger=None, impersonate_target: Optional[str] = None) -> Dict[str, Any]:
    """yt-dlp için temel seçenekleri döndürür."""
    opts = {
        'logger': logger,
        'quiet': True,
        'ignoreerrors': 'only_download',
        'retries': 5,
        'fragment_retries': 10,
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'concurrent_fragment_downloads': 5,
    }
    if impersonate_target:
        try:
            mod = None
            for path in ("yt_dlp.impersonate", "yt_dlp.networking.impersonate"):
                try:
                    mod = importlib.import_module(path)
                    break
                except Exception:
                    continue
            if mod and hasattr(mod, "ImpersonateTarget"):
                ImpersonateTarget = getattr(mod, "ImpersonateTarget")
                opts['impersonate'] = ImpersonateTarget(impersonate_target)
        except (ImportError, TypeError, AttributeError):
            # yt-dlp sürümü desteklemiyor olabilir veya hedef geçersiz olabilir
            pass
    return opts
    return opts

def get_video_resolution_mpv(url: str) -> Optional[int]:
    """mpv kullanarak bir video URL'sinin çözünürlüğünü (yüksekliğini) alır."""
    try:
        cmd = [
            "mpv", "--no-config", "--no-audio", "--no-video",
            "--frames=1", "--really-quiet",
            "--term-playing-msg=${video-params/w}x${video-params/h}",
            url,
        ]
        res = sp.run(cmd, text=True, stdout=sp.PIPE, stderr=sp.PIPE, timeout=10)
        out = (res.stdout or "") + (res.stderr or "")
        mm = re.findall(r"(\d{3,4})x(\d{3,4})", out)
        if mm:
            return int(mm[-1][1])
    except (FileNotFoundError, sp.TimeoutExpired, Exception):
        # mpv yüklü değil, zaman aşımı veya başka bir hata
        pass
    return None
