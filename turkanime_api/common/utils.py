# -*- coding: utf-8 -*-
"""
turkanime_api için ortak yardımcı fonksiyonlar.
"""
import platform
import re
import subprocess as sp
import importlib
import sysconfig
import sys
from typing import Optional, Dict, Any
from yt_dlp import YoutubeDL

def get_platform() -> str:
    """Return a string with current platform (system and machine architecture).

    This attempts to improve upon `sysconfig.get_platform` by fixing some
    issues when running a Python interpreter with a different architecture than
    that of the system (e.g. 32bit on 64bit system, or a multiarch build),
    which should return the machine architecture of the currently running
    interpreter rather than that of the system (which didn't seem to work
    properly). The reported machine architectures follow platform-specific
    naming conventions (e.g. "x86_64" on Linux, but "x64" on Windows).

    Example output strings for common platforms:

        darwin_(ppc|ppc64|i386|x86_64|arm64)
        linux_(i686|x86_64|armv7l|aarch64)
        windows_(x86|x64|arm32|arm64)
        android_(armv7l|aarch64)

    """
    system = platform.system().lower()
    machine = sysconfig.get_platform().split("-")[-1].lower()
    is_64bit = sys.maxsize > 2 ** 32

    if system == "darwin":  # get machine architecture of multiarch binaries
        if any([x in machine for x in ("fat", "intel", "universal")]):
            machine = platform.machine().lower()

    elif system == "linux":  # fix running 32bit interpreter on 64bit system
        if not is_64bit and machine == "x86_64":
            machine = "i686"
        elif not is_64bit and machine == "aarch64":
            machine = "armv7l"

    elif system == "windows":  # return more precise machine architecture names
        if machine == "amd64":
            machine = "x64"
        elif machine == "win32":
            if is_64bit:
                machine = platform.machine().lower()
            else:
                machine = "x86"

    # some more fixes based on examples in https://en.wikipedia.org/wiki/Uname
    if not is_64bit and machine in ("x86_64", "amd64"):
        if any([x in system for x in ("cygwin", "mingw", "msys")]):
            machine = "i686"
        else:
            machine = "i386"

    return f"{system}_{machine}"

def get_arch() -> str:
    """Mevcut mimariyi tespit et."""
    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        return "x64"
    elif machine in ["i386", "i686"]:
        return "x32"
    elif machine in ["arm64", "aarch64"]:
        return "arm64"
    elif machine in ["armv7l"]:
        return "armv7l"
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


def extract_video_info(url: str, ydl_opts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """YoutubeDL kullanarak video bilgilerini çıkarır."""
    try:
        with YoutubeDL(ydl_opts) as ydl:
            raw_info = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(raw_info)
        if info and isinstance(info, dict):
            return info
        return {}
    except Exception:
        return {}
