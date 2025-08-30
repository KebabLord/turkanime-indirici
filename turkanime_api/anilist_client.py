"""
AniList API Client for TurkAnime GUI
Provides authentication, trending anime, and user tracking features.
"""

import requests
import json
import webbrowser
import http.server
import socketserver
import threading
import time
import os
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import parse_qs, urlparse

class AniListClient:
    """AniList API client with OAuth2 authentication."""

    BASE_URL = "https://graphql.anilist.co"
    AUTH_URL = "https://anilist.co/api/v2/oauth/authorize"
    TOKEN_URL = "https://anilist.co/api/v2/oauth/token"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.user_data = None
        # Try load tokens from disk
        try:
            self._load_tokens()
        except Exception:
            pass
        # Try load persisted OAuth client config if present
        try:
            self._load_config()
        except Exception:
            pass

    def get_auth_url(self, response_type: str = "code", state: Optional[str] = None) -> str:
        """Generate OAuth2 authorization URL.

        response_type:
          - "code"   -> Authorization Code flow (requires client_secret)
          - "token"  -> Implicit flow (no client_secret, access_token in fragment)
        """
        params = [
            ("client_id", self.client_id),
            ("redirect_uri", self.redirect_uri),
            ("response_type", response_type),
        ]
        # Scope code akışında gerekli değildir; implicit (token) akışında eklenebilir.
        if response_type == "token":
            params.append(("scope", "user:read"))
        if state:
            params.append(("state", state))

        # Build URL manually to avoid importing urllib just for urlencode
        query = "&".join([f"{k}={v}" for k, v in params])
        return f"{self.AUTH_URL}?{query}"

    def set_access_token(self, token: str, expires_in: Optional[int] = None):
        """Set access token directly (implicit flow)."""
        self.access_token = token
        # We don't currently track expiry, but could store if needed
        try:
            self._save_tokens()
        except Exception:
            pass

    def exchange_code_for_token(self, code: str) -> bool:
        """Exchange authorization code for access token."""
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': code
        }

        try:
            # AniList token endpoint form-encoded bekler; JSON gönderimi unsupported_grant_type hatası döndürebilir.
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = requests.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            try:
                self._save_tokens()
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Token exchange failed: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            return False

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }

        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = requests.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            try:
                self._save_tokens()
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return False

    def _make_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make authenticated GraphQL request with basic token refresh retry."""
        headers = {'Content-Type': 'application/json'}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'

        data: Dict[str, Any] = {'query': query}
        if variables:
            data['variables'] = variables

        def do_request() -> Optional[requests.Response]:
            try:
                resp = requests.post(self.BASE_URL, headers=headers, json=data)
                return resp
            except Exception as e:
                print(f"API request failed: {e}")
                return None

        response = do_request()
        if response is None:
            return None

        # If unauthorized, try a one-time refresh (when available)
        if response.status_code == 401 and self.refresh_token:
            if self.refresh_access_token():
                # Update header with new token and retry
                if self.access_token:
                    headers['Authorization'] = f'Bearer {self.access_token}'
                response = do_request()
                if response is None:
                    return None

        try:
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Show server-provided error if any
            try:
                print(f"API request failed: {response.status_code} {response.text}")
            except Exception:
                print(f"API request failed: {e}")
            return None

    def get_current_user(self) -> Optional[Dict]:
        """Get current authenticated user information."""
        query = """
        query {
            Viewer {
                id
                name
                avatar {
                    large
                }
                statistics {
                    anime {
                        count
                        meanScore
                        minutesWatched
                    }
                }
            }
        }
        """

        result = self._make_request(query)
        if result and 'data' in result and result['data']['Viewer']:
            self.user_data = result['data']['Viewer']
            return self.user_data
        return None

    def get_trending_anime(self, page: int = 1, per_page: int = 20) -> List[Dict]:
        """Get trending anime list."""
        query = """
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                media(sort: TRENDING_DESC, type: ANIME) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    coverImage {
                        large
                        medium
                    }
                    description
                    episodes
                    duration
                    genres
                    averageScore
                    popularity
                    status
                    season
                    seasonYear
                    studios {
                        nodes {
                            name
                        }
                    }
                }
            }
        }
        """

        variables = {'page': page, 'perPage': per_page}
        result = self._make_request(query, variables)

        if result and 'data' in result and 'Page' in result['data']:
            return result['data']['Page']['media']
        return []

    def search_anime(self, query: str, page: int = 1, per_page: int = 20) -> List[Dict]:
        """Search anime by title."""
        search_query = """
        query ($search: String, $page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                media(search: $search, type: ANIME) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    coverImage {
                        large
                        medium
                    }
                    description
                    episodes
                    duration
                    genres
                    averageScore
                    popularity
                    status
                    season
                    seasonYear
                    studios {
                        nodes {
                            name
                        }
                    }
                }
            }
        }
        """

        variables = {'search': query, 'page': page, 'perPage': per_page}
        result = self._make_request(search_query, variables)

        if result and 'data' in result and 'Page' in result['data']:
            return result['data']['Page']['media']
        return []

    def get_user_anime_list(self, user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user's anime list."""
        list_query = """
        query ($userId: Int, $status: MediaListStatus) {
            MediaListCollection(userId: $userId, type: ANIME, status: $status) {
                lists {
                    name
                    entries {
                        media {
                            id
                            title {
                                romaji
                                english
                                native
                            }
                            coverImage {
                                large
                                medium
                            }
                            episodes
                        }
                        progress
                        score
                        status
                        updatedAt
                    }
                }
            }
        }
        """

        variables: Dict[str, Any] = {'userId': user_id}
        if status:
            variables['status'] = status

        result = self._make_request(list_query, variables)

        if result and 'data' in result and 'MediaListCollection' in result['data']:
            return result['data']['MediaListCollection']['lists']
        return []

    def update_anime_progress(self, media_id: int, progress: int, status: Optional[str] = None) -> bool:
        """Update anime progress in user's list."""
        mutation = """
        mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
            SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status) {
                id
                progress
                status
            }
        }
        """

        variables: Dict[str, Any] = {'mediaId': media_id, 'progress': progress}
        if status:
            variables['status'] = status

        result = self._make_request(mutation, variables)
        return result is not None and 'data' in result and result['data']['SaveMediaListEntry'] is not None

    # --- token persistence ---
    def _tokens_path(self) -> str:
        try:
            import appdirs
            data_dir = appdirs.user_data_dir("TurkAnime", "Barkeser")
        except Exception:
            data_dir = os.path.join(os.path.expanduser("~"), ".turkanime")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "anilist_tokens.json")

    def _save_tokens(self) -> None:
        path = self._tokens_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
            }, f)

    def _load_tokens(self) -> None:
        path = self._tokens_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.access_token = data.get('access_token')
                self.refresh_token = data.get('refresh_token')

    # --- config persistence (client_id, client_secret, redirect_uri) ---
    def _config_path(self) -> str:
        # Reuse tokens directory
        base_dir = os.path.dirname(self._tokens_path())
        return os.path.join(base_dir, "anilist_config.json")

    def _load_config(self) -> None:
        path = self._config_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.client_id = data.get('client_id', self.client_id)
                self.client_secret = data.get('client_secret', self.client_secret)
                self.redirect_uri = data.get('redirect_uri', self.redirect_uri)

    def _save_config(self) -> None:
        path = self._config_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
            }, f)

    def set_oauth_config(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        """Update AniList OAuth client configuration and persist it."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        try:
            self._save_config()
        except Exception:
            pass

    def clear_tokens(self) -> None:
        """Clear saved tokens and in-memory auth."""
        self.access_token = None
        self.refresh_token = None
        # delete tokens file if exists
        try:
            path = self._tokens_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


class AniListAuthServer:
    """Local HTTP server for OAuth2 callback handling."""

    def __init__(self, client: AniListClient):
        self.client = client
        self.auth_code = None
        self.server = None
        self.on_success: Optional[Callable[[], None]] = None  # optional callback when auth succeeds

    def register_on_success(self, cb: Callable[[], None]) -> None:
        """Register a callback to be invoked after successful auth."""
        self.on_success = cb

    def start_server(self, port: int = 9921):
        """Start local server to handle OAuth callback."""

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def __init__(self, *args, anilist_client=None, auth_server=None, **kwargs):
                self.anilist_client = anilist_client
                self._auth_server = auth_server
                super().__init__(*args, **kwargs)

            def do_GET(self):
                parsed_path = urlparse(self.path)
                query_params = parse_qs(parsed_path.query)

                if parsed_path.path.endswith("/anilist-login"):
                    # Authorization Code akışı: code parametresi geldiyse önce bunu işle
                    if 'code' in query_params:
                        code = query_params['code'][0]
                        success = self.anilist_client.exchange_code_for_token(code) if self.anilist_client else False

                        if success:
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b"""
                            <html>
                            <body>
                            <h2>AniList Authentication Successful!</h2>
                            <p>You can close this window and return to the application.</p>
                            <script>
                                window.close();
                            </script>
                            </body>
                            </html>
                            """)
                            try:
                                if self.anilist_client:
                                    self.anilist_client.get_current_user()
                                if self._auth_server and self._auth_server.server:
                                    threading.Thread(target=self._auth_server.server.shutdown, daemon=True).start()
                                if self._auth_server and self._auth_server.on_success:
                                    try:
                                        self._auth_server.on_success()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            return

                    # Implicit akış uyumluluğu: hash'ten access_token yakalayan sayfayı sun
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    # Page reads window.location.hash and forwards to /anilist-token via POST
                    self.wfile.write("""
                        <html><body>
                        <script>
                        (function(){
                            try {
                                var hash = window.location.hash || "";
                                if (hash && hash.startsWith('#')) { hash = hash.substring(1); }
                                var params = new URLSearchParams(hash);
                                var token = params.get('access_token');
                                if (token) {
                                    // Send token to server
                                    fetch('/anilist-token', {
                                        method: 'POST', headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({ access_token: token })
                                     }).then(function(){ window.close(); })
                                         .catch(function(){ window.close(); });
                                 }
                             } catch(e) { /* ignore */ }
                             // Zamanlayıcı: 5 saniye sonra otomatik kapat
                             setTimeout(function(){ window.close(); }, 5000);
                         })();
                         <p>Giriş tamamlandıysa bu pencereyi kapatabilirsiniz.</p>
                         </script>
                         </body></html>
                         """.encode('utf-8'))
                    return
                if parsed_path.path.endswith("/anilist-token") and self.command == 'GET':
                    # For compatibility if someone GETs with query token
                    token = query_params.get('access_token', [None])[0]
                    if token:
                        self._handle_received_token(token)
                        return

                if 'code' in query_params:
                    code = query_params['code'][0]
                    # Use the client from the auth server
                    success = self.anilist_client.exchange_code_for_token(code) if self.anilist_client else False

                    if success:
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <body>
                        <h2>AniList Authentication Successful!</h2>
                        <p>You can close this window and return to the application.</p>
                        <script>
                            window.close();
                        </script>
                        </body>
                        </html>
                        """)
                        # try fetch user and shutdown server
                        try:
                            if self.anilist_client:
                                self.anilist_client.get_current_user()
                            if self._auth_server and self._auth_server.server:
                                # shutdown in a separate thread to avoid deadlock
                                threading.Thread(target=self._auth_server.server.shutdown, daemon=True).start()
                            if self._auth_server and self._auth_server.on_success:
                                try:
                                    self._auth_server.on_success()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <body style='background:#0f0f0f;color:#ff6b6b;font-family:Segoe UI,Arial,sans-serif;'>
                        <h2>Giris Basarisiz</h2>
                        <p>Lutfen tekrar deneyin.</p>
                        <p>Not: Redirect URI uygulama ayarlarindaki ile birebir ayni olmali.</p>
                        </body>
                        </html>
                        """)
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body style='background:#0f0f0f;color:#ff6b6b;font-family:Segoe UI,Arial,sans-serif;'><h2>Gecersiz Istek</h2><p>Parametreler eksik.</p></body></html>")

            def log_message(self, format, *args):
                # Suppress server logs
                pass

            def do_POST(self):
                parsed_path = urlparse(self.path)
                if parsed_path.path.endswith('/anilist-token'):
                    length = int(self.headers.get('Content-Length', '0') or 0)
                    body = self.rfile.read(length) if length > 0 else b""
                    try:
                        payload = json.loads(body.decode('utf-8') or '{}')
                    except Exception:
                        payload = {}
                    token = payload.get('access_token')
                    if token:
                        self._handle_received_token(token)
                        return
                    self.send_response(400)
                    self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def _handle_received_token(self, token: str):
                try:
                    if self.anilist_client:
                        self.anilist_client.set_access_token(token)
                        # Optionally fetch user to validate
                        self.anilist_client.get_current_user()
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body><h2>AniList Auth Success</h2><p>You can close this window.</p><script>window.close();</script></body></html>")
                    # shutdown + callback
                    if self._auth_server and self._auth_server.server:
                        threading.Thread(target=self._auth_server.server.shutdown, daemon=True).start()
                    if self._auth_server and self._auth_server.on_success:
                        try:
                            self._auth_server.on_success()
                        except Exception:
                            pass
                except Exception:
                    self.send_response(500)
                    self.end_headers()

        try:
            # Allow address reuse and threaded handling to reduce port lock issues on Windows
            class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
                allow_reuse_address = True
                daemon_threads = True

            # Create handler with client and auth_server reference
            def handler_factory(*args, **kwargs):
                return CallbackHandler(*args, anilist_client=self.client, auth_server=self, **kwargs)

            self.server = ThreadedTCPServer(("", port), handler_factory)
            print(f"Starting auth server on port {port}")
            self.server.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
# Global AniList client instance
anilist_client = AniListClient(
    client_id="29745",
    client_secret="a6L8mE9xNR2t45kl0KZ15eY0DWYhhBhP2bQpIvku",
    redirect_uri="http://localhost:9921/anilist-login"
)
