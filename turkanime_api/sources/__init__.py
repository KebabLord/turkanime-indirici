"""Kaynaklar (TürkAnime, AnimeciX, Anizle) için facade.

Ek sağlayıcılar bu modülden dışa aktarılır ve `register_provider`
yardımıyla sisteme kaydedilebilir.
"""

from .animecix import CixAnime, search_animecix  # noqa: F401
from .anizle import AnizleAnime, search_anizle  # noqa: F401

# Mevcut sağlayıcılar
PROVIDERS = {
    "animecix": {
        "name": "AnimeciX",
        "adapter": None,  # Eski sistem kullanılıyor
        "enabled": True,
        "priority": 1
    },
    "anizle": {
        "name": "Anizle",
        "adapter": None,
        "enabled": True,
        "priority": 2
    }
}

def register_provider(name: str, adapter_class, enabled: bool = True, priority: int = 5):
    """Yeni bir anime sağlayıcısı kaydet."""
    PROVIDERS[name] = {
        "name": name,
        "adapter": adapter_class,
        "enabled": enabled,
        "priority": priority
    }

def get_enabled_providers():
    """Etkin sağlayıcıları döndür."""
    return {name: data for name, data in PROVIDERS.items() if data["enabled"]}

def get_provider_by_priority():
    """Öncelik sırasına göre sağlayıcıları döndür."""
    enabled = get_enabled_providers()
    return sorted(enabled.items(), key=lambda x: x[1]["priority"])
