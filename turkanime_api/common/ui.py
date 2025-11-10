"""
UI bileşenleri için modül.
Accordion tarzı bölüm listesi ve diğer UI yardımcıları.
"""

import customtkinter as ctk
from typing import List, Dict, Any, Callable, Optional
import threading
from .adapters import AniListAdapter, TurkAnimeAdapter, AnimeciXAdapter, AnizleAdapter




class AccordionSourceEpisodeList:
    """Kaynakları accordion içinde gösteren gelişmiş bölüm listesi."""

    def __init__(self, parent, sources_data: Dict[str, List[Dict[str, Any]]],
                 max_episodes_per_source: int = 50,
                 on_play: Optional[Callable] = None, on_download: Optional[Callable] = None,
                 on_match: Optional[Callable] = None, db_matches: Optional[Dict[str, Dict]] = None,
                 user_id: Optional[str] = None, anime_name: Optional[str] = None):
        self.parent = parent
        self.sources_data = sources_data  # {"AniList": [...], "TürkAnime": [...], "AnimeciX": [...]}
        self.max_episodes_per_source = max_episodes_per_source
        self.on_play = on_play
        self.on_download = on_download
        self.on_match = on_match
        self.db_matches = db_matches or {}  # DB'den çekilen önceki eşleşmeler
        self.expanded_frames = {}
        self.selected_episodes = set()
        self.source_matches = {}  # Kaynak eşleşmeleri için
        self.user_id = user_id  # Kullanıcı kimliği
        self.anime_name = anime_name or "unknown"  # Anime adı

        # Arama ve yükleme durumu
        self.search_queries = {}  # {source_name: search_query}
        self.loaded_episodes_count = {}  # {source_name: loaded_count}
        self.all_episodes_data = sources_data.copy()  # Orijinal veriler

        # Arama progress için
        self.search_in_progress = {}  # {source_name: bool}
        self.search_results = {}  # {source_name: filtered_episodes}

        # Bölüm durumlarını takip et (izlendi/indirildi)
        self.episode_status = {}  # {episode_id: {'watched': bool, 'downloaded': bool}}

        # Kullanıcının episode status'lerini API'den yükle
        if self.user_id:
            self._load_user_episode_status()

        # Adapter instance'ları
        self.adapters = {
            "AniList": AniListAdapter(),
            "TürkAnime": TurkAnimeAdapter(),
            "AnimeciX": AnimeciXAdapter(),
            "Anizle": AnizleAdapter()
        }

        # Ana frame
        self.main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        # Başlık ve toplu aksiyonlar
        self._create_header()

        # Kaynak accordion'ları
        self._create_source_accordions()

    def _load_user_episode_status(self):
        """Kullanıcının episode status'lerini API'den yükler."""
        if not self.user_id:
            return

        try:
            from .db import api_manager
            status_data = api_manager.get_user_episode_status(self.user_id)
            if status_data:
                self.episode_status = status_data
                print(f"Episode status'ler yüklendi: {len(status_data)} bölüm")
        except Exception as e:
            print(f"Episode status yükleme hatası: {e}")

    def _create_header(self):
        """Başlık ve toplu aksiyon butonları."""
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        title_label = ctk.CTkLabel(header_frame, text="🎯 Kaynaklar ve Bölümler",
                                 font=ctk.CTkFont(size=16, weight="bold"),
                                 text_color="#ffffff")
        title_label.pack(side="left")

        # Eşleştirme butonu
        if self.on_match:
            self.match_btn = ctk.CTkButton(header_frame, text="🔗 Eşleştir",
                                         width=100, height=30,
                                         fg_color="#4ecdc4", hover_color="#45b7aa",
                                         command=self._show_match_dialog)
            self.match_btn.pack(side="right")

    def _create_source_accordions(self):
        """Her kaynak için ayrı accordion oluştur."""
        sources_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        sources_frame.pack(fill="both", expand=False)

        for source_name, episodes in self.sources_data.items():
            if not episodes:
                continue

            # Kaynak rengi
            source_color = self._get_source_color(source_name)

            # Başlangıçta yüklenen bölüm sayısı
            initial_load = min(50, len(episodes))
            self.loaded_episodes_count[source_name] = initial_load

            # Kaynak accordion'u
            source_frame = CollapsibleFrame(sources_frame,
                                          title=f"{source_name} ({len(episodes)} bölüm)",
                                          fg_color="#2a2a2a")
            source_frame.pack(fill="x", pady=2)

            # Arama ve kontrol frame'i
            control_frame = ctk.CTkFrame(source_frame.content_frame, fg_color="transparent")
            control_frame.pack(fill="x", pady=(0, 10))

            # Arama kutusu
            search_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
            search_frame.pack(side="left", fill="x", expand=True)

            search_entry = ctk.CTkEntry(search_frame, placeholder_text="Bölüm ara...",
                                      width=200, height=30)
            search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

            # Arama butonu
            search_btn = ctk.CTkButton(search_frame, text="🔍", width=40, height=30,
                                     command=lambda src=source_name, entry=search_entry: self._search_episodes(src, entry))
            search_btn.pack(side="left")

            # Temizle butonu
            clear_btn = ctk.CTkButton(search_frame, text="❌", width=40, height=30,
                                    fg_color="#666666", hover_color="#555555",
                                    command=lambda src=source_name: self._clear_search(src))
            clear_btn.pack(side="left", padx=(5, 0))

            # Daha fazla yükle butonu (eğer 50'den fazla bölüm varsa)
            if len(episodes) > 50:
                load_more_btn = ctk.CTkButton(control_frame, text=f"📥 Daha Fazla Yükle ({len(episodes) - 50} bölüm)",
                                            height=30, fg_color="#4ecdc4", hover_color="#45b7aa",
                                            command=lambda src=source_name, sf=source_frame: self._load_more_episodes(src, sf))
                load_more_btn.pack(side="right", padx=(10, 0))

            # Kaynak içindeki bölümler (ilk 50 tanesi)
            initial_episodes = episodes[:initial_load]
            self._create_source_episodes(source_frame.content_frame, initial_episodes, source_name)

    def _create_source_episodes(self, parent_frame, episodes: List[Dict[str, Any]], source_name: str):
        """Kaynak içindeki bölümleri oluştur."""
        # Bölümleri 50'li gruplara ayır
        group_size = 50
        for i in range(0, len(episodes), group_size):
            group_episodes = episodes[i:i + group_size]
            group_start = i + 1
            group_end = min(i + group_size, len(episodes))

            # Grup başlığı
            group_title = f"Bölüm {group_start}-{group_end}"
            if len(episodes) <= group_size:
                group_title = "Tüm Bölümler"

            # Grup frame
            group_frame = CollapsibleFrame(parent_frame, title=group_title,
                                         fg_color="#1a1a1a")
            group_frame.pack(fill="x", pady=1, padx=5)

            # Grup içindeki bölümler
            self._create_group_episodes(group_frame.content_frame, group_episodes, group_start, source_name)

    def _create_group_episodes(self, parent_frame, episodes: List[Dict[str, Any]],
                             start_number: int, source_name: str):
        """Grup içindeki bölümleri oluştur."""
        for idx, episode in enumerate(episodes):
            episode_number = start_number + idx

            # Bölüm frame'i - hafif border ile
            episode_frame = ctk.CTkFrame(parent_frame, fg_color="#1a1a1a",
                                       border_width=1, border_color="#333333",
                                       corner_radius=5)
            episode_frame.pack(fill="x", pady=1, padx=5)

            # Sol taraf - durum ikonları
            status_frame = ctk.CTkFrame(episode_frame, fg_color="transparent")
            status_frame.pack(side="left", padx=(5, 0))

            # Bölüm ID'si oluştur - {KAYNAK_İSMİ}_{ANİMEİSMİ}_{BÖLÜMİSMİ} formatında
            # Anime adını güvenli hale getir (boşlukları kaldır, özel karakterleri temizle)
            safe_anime_name = self.anime_name.replace(' ', '').replace('-', '').replace('_', '').replace(':', '').replace(';', '').replace(',', '').replace('.', '').replace('!', '').replace('?', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('{', '').replace('}', '').replace('/', '').replace('\\', '').replace('|', '').replace('*', '').replace('<', '').replace('>', '').replace('"', '').replace("'", '')
            episode_title = episode.get('title', 'unknown').replace(' ', '').replace('-', '').replace('_', '').replace(':', '').replace(';', '').replace(',', '').replace('.', '').replace('!', '').replace('?', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('{', '').replace('}', '').replace('/', '').replace('\\', '').replace('|', '').replace('*', '').replace('<', '').replace('>', '').replace('"', '').replace("'", '')
            episode_id = f"{source_name}_{safe_anime_name}_{episode_title}"

            # İzlenme durumu ikonu
            watched_status = self.episode_status.get(episode_id, {}).get('watched', False)
            watched_icon = "👁️" if watched_status else "○"
            watched_color = "#4ecdc4" if watched_status else "#666666"

            watched_label = ctk.CTkLabel(status_frame, text=watched_icon,
                                       font=ctk.CTkFont(size=12),
                                       text_color=watched_color)
            watched_label.pack(side="left", padx=(0, 3))

            # İndirme durumu ikonu
            downloaded_status = self.episode_status.get(episode_id, {}).get('downloaded', False)
            downloaded_icon = "💾" if downloaded_status else "○"
            downloaded_color = "#ff6b6b" if downloaded_status else "#666666"

            downloaded_label = ctk.CTkLabel(status_frame, text=downloaded_icon,
                                          font=ctk.CTkFont(size=12),
                                          text_color=downloaded_color)
            downloaded_label.pack(side="left", padx=(0, 5))

            # Checkbox
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(episode_frame,
                                     text=f"{episode_number:02d} - {episode['title']}",
                                     variable=var,
                                     command=lambda v=var, ep=episode, src=source_name: self._on_episode_toggle(v, ep, src))
            checkbox.pack(side="left", fill="x", expand=True, padx=(0, 5))

            # Aksiyon butonları
            actions_frame = ctk.CTkFrame(episode_frame, fg_color="transparent")
            actions_frame.pack(side="right", padx=(0, 5))

            # İzlenme durumunu değiştir butonu
            toggle_watched_btn = ctk.CTkButton(actions_frame, text="✓", width=25, height=25,
                                             fg_color="transparent", text_color="#4ecdc4",
                                             command=lambda eid=episode_id, wl=watched_label: self._toggle_watched(eid, wl))
            toggle_watched_btn.pack(side="left", padx=(0, 2))

            # İndirme durumunu değiştir butonu
            toggle_downloaded_btn = ctk.CTkButton(actions_frame, text="⬇️", width=25, height=25,
                                                fg_color="transparent", text_color="#ff6b6b",
                                                command=lambda eid=episode_id, dl=downloaded_label: self._toggle_downloaded(eid, dl))
            toggle_downloaded_btn.pack(side="left", padx=(0, 2))

            # Oynat butonu
            if self.on_play:
                play_btn = ctk.CTkButton(actions_frame, text="▶️", width=30, height=25,
                                       command=lambda ep=episode: self._safe_call(self.on_play, ep['obj']))
                play_btn.pack(side="left", padx=(0, 2))

            # İndir butonu
            if self.on_download:
                download_btn = ctk.CTkButton(actions_frame, text="⬇️", width=30, height=25,
                                           fg_color="#ff6b6b", hover_color="#ff5252",
                                           command=lambda ep=episode: self._safe_call(self.on_download, ep['obj']))
                download_btn.pack(side="left")

    def _on_episode_toggle(self, var: ctk.BooleanVar, episode: Dict[str, Any], source_name: str):
        """Bölüm seçildiğinde çağrılır."""
        episode_key = f"{source_name}:{episode['title']}"
        if var.get():
            self.selected_episodes.add(episode_key)
        else:
            self.selected_episodes.discard(episode_key)

    def _get_source_color(self, source_name: str) -> str:
        """Kaynak için renk kodu döndür."""
        colors = {
            "AniList": "#4ecdc4",  # Turkuaz
            "TürkAnime": "#ffd93d",  # Sarı
            "AnimeciX": "#ff6b6b",  # Kırmızı
            "Anizle": "#9b59b6"  # Mor
        }
        return colors.get(source_name, "#666666")

    def _search_source_anime(self, source_name, search_entry, combo_box, selected_anime):
        """Kaynakta anime ara."""
        if not combo_box:
            return

        query = search_entry.get().strip()
        if not query:
            return

        try:
            # Arama butonunu devre dışı bırak
            search_entry.configure(state="disabled")

            # Arama sonuçlarını getir
            results = self._perform_source_search(source_name, query)

            if results:
                combo_box.configure(values=results)
                combo_box.set(results[0])
                # Arama sonucu seçildiğinde selected_anime'yi güncelle
                selected_anime[source_name] = results[0]
            else:
                combo_box.configure(values=["Sonuç bulunamadı"])
                combo_box.set("Sonuç bulunamadı")
                selected_anime[source_name] = "Sonuç bulunamadı"

        except Exception as e:
            print(f"Arama hatası ({source_name}): {e}")
            combo_box.configure(values=["Arama hatası"])
            combo_box.set("Arama hatası")
            selected_anime[source_name] = "Arama hatası"
        finally:
            # Arama girişini tekrar etkinleştir
            search_entry.configure(state="normal")

    def _perform_source_search(self, source_name, query):
        """Kaynakta arama yap."""
        try:
            adapter = self.adapters.get(source_name)
            if not adapter:
                return [f"{source_name} adaptörü bulunamadı"]

            # Adapter ile arama yap
            results = adapter.search_anime(query, limit=10)

            if results:
                # Sadece başlıkları döndür
                return [title for _, title in results]
            else:
                return ["Sonuç bulunamadı"]

        except Exception as e:
            print(f"Arama hatası ({source_name}): {e}")
            return ["Arama hatası"]

    def _show_match_dialog(self):
        """Eşleştirme dialog'unu göster."""
        if not self.on_match:
            return

        # Dialog penceresi
        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("🎯 Anime Eşleştirme")
        dialog.geometry("700x600")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Başlık
        title_label = ctk.CTkLabel(dialog, text="2 Kaynaktan 1'er Anime Seçin",
                                 font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=10)

        # Kaynak seçim frame'leri
        selections_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        selections_frame.pack(fill="both", expand=True, padx=20, pady=10)

        selected_anime = {}
        search_entries = {}
        search_buttons = {}
        combo_boxes = {}

        # Sadece eşleştirme için kullanılacak kaynaklar
        matching_sources = {k: v for k, v in self.sources_data.items() if k in ["TürkAnime", "AnimeciX"]}

        for source_name, episodes in matching_sources.items():
            if not episodes:
                continue

            # Kaynak frame
            source_frame = ctk.CTkFrame(selections_frame, fg_color="#2a2a2a")
            source_frame.pack(fill="x", pady=5)

            source_label = ctk.CTkLabel(source_frame, text=f"{source_name}",
                                      font=ctk.CTkFont(size=14, weight="bold"))
            source_label.pack(pady=5)

            # Arama kutusu ve butonu
            search_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
            search_frame.pack(fill="x", padx=10, pady=5)

            search_entry = ctk.CTkEntry(search_frame, placeholder_text=f"{source_name}'ta ara...",
                                      width=200)
            search_entry.pack(side="left", padx=(0, 10))

            search_btn = ctk.CTkButton(search_frame, text="🔍 Ara", width=80,
                                     command=lambda src=source_name, entry=search_entry: self._search_source_anime(src, entry, combo_boxes.get(src), selected_anime))
            search_btn.pack(side="left")

            # Mevcut bölümlerden anime seçenekleri
            current_options = list(set([ep.get('anime_title', ep['title']) for ep in episodes]))

            # DB'den önceki eşleşmeleri de ekle
            if source_name in self.db_matches:
                db_anime_title = self.db_matches[source_name].get('anime_title', '')
                if db_anime_title and db_anime_title not in current_options:
                    current_options.insert(0, f"📚 {db_anime_title}")  # DB'den gelenleri başa ekle

            # Anime seçimi için combobox
            combo = ctk.CTkComboBox(source_frame, values=current_options if current_options else ["Arama yapın..."],
                                  command=lambda value, src=source_name: selected_anime.update({src: value}))
            combo.pack(pady=5)

            if current_options:
                # DB'den gelen eşleşmeyi varsayılan olarak seç
                if source_name in self.db_matches:
                    db_anime_title = self.db_matches[source_name].get('anime_title', '')
                    if db_anime_title in current_options:
                        combo.set(f"📚 {db_anime_title}")
                        selected_anime[source_name] = f"📚 {db_anime_title}"
                    else:
                        combo.set(current_options[0])
                        selected_anime[source_name] = current_options[0]
                else:
                    combo.set(current_options[0])
                    selected_anime[source_name] = current_options[0]
            else:
                combo.set("Arama yapın...")
                # Varsayılan değer ata ki seçim zorunlu olmasın
                selected_anime[source_name] = "Arama yapın..."

            # Referansları sakla
            search_entries[source_name] = search_entry
            search_buttons[source_name] = search_btn
            combo_boxes[source_name] = combo

        # Butonlar
        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=10)

        def on_confirm():
            try:
                print("DEBUG: on_confirm başladı")
                # Geçerli seçimleri kontrol et
                valid_selections = {}
                for source, anime_title in selected_anime.items():
                    if anime_title and anime_title not in ["Arama yapın...", "Sonuç bulunamadı", "Arama hatası"]:
                        # DB'den gelen eşleşmeler için prefix'i kaldır
                        clean_title = anime_title.replace("📚 ", "") if anime_title.startswith("📚 ") else anime_title
                        valid_selections[source] = clean_title

                print(f"DEBUG: selected_anime = {selected_anime}")
                print(f"DEBUG: valid_selections = {valid_selections}")
                print(f"DEBUG: len(valid_selections) = {len(valid_selections)}")

                if len(valid_selections) >= 2:
                    print("DEBUG: on_match çağrılıyor")
                    self._safe_call(self.on_match, valid_selections)
                    print("DEBUG: dialog kapatılıyor")
                    dialog.destroy()
                else:
                    # Hata mesajı
                    error_label = ctk.CTkLabel(buttons_frame, text="❌ Tüm kaynaklardan geçerli anime seçmelisiniz!",
                                             text_color="#ff6b6b")
                    error_label.pack(pady=5)
            except Exception as e:
                print(f"DEBUG: on_confirm exception: {e}")
                import traceback
                traceback.print_exc()

        confirm_btn = ctk.CTkButton(buttons_frame, text="✅ Eşleştir", command=on_confirm)
        confirm_btn.pack(side="right", padx=10)

        cancel_btn = ctk.CTkButton(buttons_frame, text="❌ İptal", command=dialog.destroy)
        cancel_btn.pack(side="right")

    def _safe_call(self, func, *args):
        """Güvenli fonksiyon çağrısı."""
        if func:
            try:
                func(*args)
            except Exception as e:
                print(f"Fonksiyon çağrısı hatası: {e}")

    def destroy(self):
        """Accordion listesini temizle."""
        if hasattr(self, 'main_frame'):
            self.main_frame.destroy()

    def _toggle_watched(self, episode_id, label):
        """Bölüm izlenme durumunu değiştir."""
        current_status = self.episode_status.get(episode_id, {}).get('watched', False)
        new_status = not current_status

        # Durumu güncelle
        if episode_id not in self.episode_status:
            self.episode_status[episode_id] = {'watched': False, 'downloaded': False}
        self.episode_status[episode_id]['watched'] = new_status

        # İkonu güncelle
        if new_status:
            label.configure(text="👁️", text_color="#4ecdc4")
        else:
            label.configure(text="○", text_color="#666666")

        # API'ye kaydet
        if self.user_id:
            try:
                from .db import api_manager
                api_manager.save_user_episode_status(
                    self.user_id, episode_id, new_status,
                    self.episode_status[episode_id].get('downloaded', False)
                )
            except Exception as e:
                print(f"Episode status API kaydetme hatası: {e}")

    def _toggle_downloaded(self, episode_id, label):
        """Bölüm indirme durumunu değiştir."""
        current_status = self.episode_status.get(episode_id, {}).get('downloaded', False)
        new_status = not current_status

        # Durumu güncelle
        if episode_id not in self.episode_status:
            self.episode_status[episode_id] = {'watched': False, 'downloaded': False}
        self.episode_status[episode_id]['downloaded'] = new_status

        # İkonu güncelle
        if new_status:
            label.configure(text="💾", text_color="#ff6b6b")
        else:
            label.configure(text="○", text_color="#666666")

        # API'ye kaydet
        if self.user_id:
            try:
                from .db import api_manager
                api_manager.save_user_episode_status(
                    self.user_id, episode_id,
                    self.episode_status[episode_id].get('watched', False), new_status
                )
            except Exception as e:
                print(f"Episode status API kaydetme hatası: {e}")

    def _search_episodes(self, source_name: str, search_entry):
        """Kaynaktaki bölümleri ara."""
        query = search_entry.get().strip().lower()
        self.search_queries[source_name] = query

        # Eğer zaten arama yapılıyorsa iptal et
        if self.search_in_progress.get(source_name, False):
            return

        # Arama durumunu ayarla ve UI'ı devre dışı bırak
        self.search_in_progress[source_name] = True
        search_entry.configure(state="disabled", placeholder_text="Aranıyor...")

        def do_search():
            try:
                # Tüm bölümleri al
                all_episodes = self.all_episodes_data.get(source_name, [])

                if query:
                    # Arama varsa tüm bölümleri yükle ve filtrele
                    filtered_episodes = [
                        ep for ep in all_episodes
                        if query in ep.get('title', '').lower()
                    ]
                    self.loaded_episodes_count[source_name] = len(all_episodes)  # Tüm bölümler yüklenmiş sayılır
                else:
                    # Arama yoksa ilk 50 bölümü göster
                    filtered_episodes = all_episodes[:50]
                    self.loaded_episodes_count[source_name] = min(50, len(all_episodes))

                # Sonuçları sakla
                self.search_results[source_name] = filtered_episodes

                # UI güncellemesini main thread'de yap
                self.parent.after(0, lambda: self._update_search_results(source_name, search_entry, query))

            except Exception as e:
                print(f"Arama hatası: {e}")
                self.search_in_progress[source_name] = False

        # Aramayı arka planda yap
        import threading
        search_thread = threading.Thread(target=do_search, daemon=True)
        search_thread.start()

    def _update_search_results(self, source_name: str, search_entry, query: str):
        """Arama sonuçlarını UI'da güncelle."""
        try:
            # Arama durumunu sıfırla
            self.search_in_progress[source_name] = False

            # Sonuçları al
            filtered_episodes = self.search_results.get(source_name, [])

            # Bölümleri yeniden oluştur
            self._refresh_source_display(source_name, filtered_episodes)

            # Placeholder'ı güncelle
            if query:
                search_entry.configure(placeholder_text=f"{len(filtered_episodes)} sonuç bulundu")
            else:
                search_entry.configure(placeholder_text="Bölüm ara...")

            # Arama kutusunu tekrar etkinleştir
            search_entry.configure(state="normal")

        except Exception as e:
            print(f"Arama sonucu güncelleme hatası: {e}")
            search_entry.configure(state="normal")

    def _clear_search(self, source_name: str):
        """Kaynaktaki arama filtresini temizle."""
        # Eğer arama yapılıyorsa bekle
        if self.search_in_progress.get(source_name, False):
            return

        self.search_queries[source_name] = ""

        # İlk 50 bölümü göster
        all_episodes = self.all_episodes_data.get(source_name, [])
        initial_episodes = all_episodes[:50]
        self.loaded_episodes_count[source_name] = min(50, len(all_episodes))

        # Bölümleri yeniden oluştur
        self._refresh_source_display(source_name, initial_episodes)

        # Arama kutusunun placeholder'ını sıfırla
        # Tüm search entry'leri bul ve placeholder'ı sıfırla
        for widget in self.main_frame.winfo_children():
            if hasattr(widget, 'winfo_children'):
                for child in widget.winfo_children():
                    if hasattr(child, 'winfo_children'):
                        for grandchild in child.winfo_children():
                            if hasattr(grandchild, 'winfo_children'):
                                for ggchild in grandchild.winfo_children():
                                    if hasattr(ggchild, 'configure') and hasattr(ggchild, 'get'):
                                        try:
                                            ggchild.configure(placeholder_text="Bölüm ara...", state="normal")
                                        except:
                                            pass

    def _load_more_episodes(self, source_name: str, source_frame):
        """Kaynak için daha fazla bölüm yükle."""
        try:
            all_episodes = self.all_episodes_data.get(source_name, [])
            current_loaded = self.loaded_episodes_count[source_name]

            if current_loaded >= len(all_episodes):
                return  # Zaten tüm bölümler yüklenmiş

            # Kalan tüm bölümleri yükle
            remaining_episodes = all_episodes[current_loaded:]
            self.loaded_episodes_count[source_name] = len(all_episodes)

            # Yeni bölümleri ekle
            self._create_source_episodes(source_frame.content_frame, remaining_episodes, source_name)

            # Daha fazla yükle butonunu kaldır/gizle
            self.parent.after(10, lambda: self._safe_hide_load_button(source_frame))

        except Exception as e:
            print(f"Daha fazla yükleme hatası: {e}")

    def _safe_hide_load_button(self, source_frame):
        """Daha fazla yükle butonunu güvenli şekilde gizle."""
        try:
            for widget in source_frame.content_frame.winfo_children():
                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        if hasattr(child, 'cget'):
                            try:
                                text = child.cget('text')
                                if 'Daha Fazla Yükle' in text:
                                    child.pack_forget()
                                    break
                            except:
                                continue
        except Exception as e:
            print(f"Buton gizleme hatası: {e}")

    def _refresh_source_display(self, source_name: str, episodes: List[Dict[str, Any]]):
        """Kaynak display'ini yenile."""
        try:
            # Tüm kaynak frame'lerini bul
            sources_frame = None
            source_frame = None

            for widget in self.main_frame.winfo_children():
                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        if hasattr(child, 'title_button') and hasattr(child.title_button, 'cget'):
                            try:
                                title_text = child.title_button.cget('text')
                                if source_name in title_text:
                                    source_frame = child
                                    sources_frame = widget
                                    break
                            except:
                                continue
                    if source_frame:
                        break

            if not source_frame:
                return

            # Mevcut bölüm widget'lerini güvenli şekilde temizle
            children_to_remove = []
            for widget in source_frame.content_frame.winfo_children():
                # Kontrol frame'i (arama kutusu olan) hariç hepsini kaldır
                if hasattr(widget, 'winfo_children'):
                    has_search = False
                    for child in widget.winfo_children():
                        if hasattr(child, 'winfo_children'):
                            for grandchild in child.winfo_children():
                                if hasattr(grandchild, 'get'):  # Entry widget
                                    has_search = True
                                    break
                            if has_search:
                                break
                    if not has_search:
                        children_to_remove.append(widget)

            # Widget'ları güvenli şekilde destroy et
            for widget in children_to_remove:
                try:
                    widget.destroy()
                except:
                    pass  # Zaten destroy edilmiş olabilir

            # Kısa bir delay ekle ki UI kendini toparlasın
            self.parent.after(10, lambda: self._safe_create_episodes(source_name, source_frame, episodes))

        except Exception as e:
            print(f"Display yenileme hatası: {e}")

    def _safe_create_episodes(self, source_name: str, source_frame, episodes: List[Dict[str, Any]]):
        """Güvenli şekilde bölümleri oluştur."""
        try:
            if episodes:
                self._create_source_episodes(source_frame.content_frame, episodes, source_name)
        except Exception as e:
            print(f"Bölüm oluşturma hatası: {e}")


class CollapsibleFrame(ctk.CTkFrame):
    """Daraltılabilir/expand edilebilir frame."""

    def __init__(self, parent, title="", **kwargs):
        super().__init__(parent, **kwargs)

        self.is_expanded = True

        # Başlık butonu
        self.title_button = ctk.CTkButton(self, text=f"▶️ {title}",
                                        command=self.toggle,
                                        fg_color="transparent",
                                        text_color="#ffffff",
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        anchor="w", height=35)
        self.title_button.pack(fill="x", padx=10, pady=5)

        # İçerik frame'i
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="x", padx=10, pady=(0, 10))

    def toggle(self):
        """Frame'i aç/kapat."""
        current_text = self.title_button.cget("text")
        if self.is_expanded:
            # Kapat
            self.content_frame.pack_forget()
            self.title_button.configure(text=current_text.replace("🔽", "▶️"))
            self.is_expanded = False
        else:
            # Aç
            self.content_frame.pack(fill="x", padx=10, pady=(0, 10))
            self.title_button.configure(text=current_text.replace("▶️", "🔽"))
            self.is_expanded = True