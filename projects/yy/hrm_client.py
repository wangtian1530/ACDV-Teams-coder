"""Client HRM VFR: login OAuth2+PKCE, refresh token, gọi API tăng ca.

Tự phục hồi session: nếu request timeout >60s hoặc mất kết nối / HTTP 401
→ tự động logout, xoá token, login lại và retry request (1 lần).

Toàn bộ HTTP request/response được log DEBUG vào ./logs/hrm_client.log.
Logger name: "hrm-client" — cấu hình tại logger_setup.py.
"""
import base64
import hashlib
import itertools
import json
import logging
import os
import threading
import time
from urllib.parse import parse_qs

from bs4 import BeautifulSoup
import requests

# ================== CONFIG ==================
APP_REQ = "APP_PORTAL_776c4d48-af67-4d10-a6c2-e0866f0202d8"
UUID_ONLY = "776c4d48-af67-4d10-a6c2-e0866f0202d8"
OPENID_URL = "https://hrm.vfr.net.vn:9026/.well-known/openid-configuration"
API_BASE = "https://hrm.vfr.net.vn:9025"
LOGOUT_BASE = "https://hrm.vfr.net.vn:9023"

# Timeout & retry
REQUEST_TIMEOUT = 60           # giây — user yêu cầu 60s
LOGOUT_TIMEOUT = 15            # logout nhanh gọn
MAX_RELOGIN_RETRIES = 1        # sau khi relogin, retry request 1 lần nữa

log = logging.getLogger("hrm-client")

MAX_BODY_LOG = 8000
_REQ_SEQ = itertools.count(1)

# Các exception mạng → kích hoạt auto-recovery
RETRYABLE_EXC = (
    requests.exceptions.Timeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)

CANDIDATE_SECRETS = [
    None, "", APP_REQ, UUID_ONLY,
    "hrm10_portal_app", "secret", "misa", "MISA", "Misa@2024", "misa@2025",
    "hrm10_portal_app_secret", "portal4hrm", "portal4hrm_secret", "APP_PORTAL",
]

SENSITIVE_KEYS = {
    "password", "Password",
    "TwoFactorCode", "Input.TwoFactorCode", "Code", "Input.Code", "otp",
    "authorization", "Authorization",
    "tokenportalapp", "refreshtoken", "idtoken",
    "access_token", "refresh_token", "id_token",
    "client_secret",
}


# ================== HELPERS ==================
def _mask(v, keep_head=6, keep_tail=4):
    if v is None:
        return None
    s = str(v)
    if len(s) <= keep_head + keep_tail:
        return "*" * len(s)
    return f"{s[:keep_head]}…{'*'*6}…{s[-keep_tail:]}"


def _sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in SENSITIVE_KEYS and v:
                out[k] = _mask(v)
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    return obj


def _dump(obj, limit=MAX_BODY_LOG):
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        s = repr(obj)
    if len(s) > limit:
        s = s[:limit] + f"\n… [truncated, total {len(s)} chars]"
    return s


# ================== EXCEPTIONS ==================
class Hrm2FARequired(Exception):
    """Cần OTP 2FA. Caller phải gọi lại login() với otp_provider."""


class TokenExpired(Exception):
    pass


# ================== CLIENT ==================
class HrmClient:
    def __init__(self, telegram_id=None, on_tokens_update=None, debug=False,
                 username=None, password=None, otp_provider=None):
        self.session = requests.Session()
        self.session.headers.update({
            "application-request": APP_REQ,
            "accept": "application/json",
            "user-agent": "okhttp/4.12.0",
        })
        self.openid_config = None
        self.tokens = None
        self.telegram_id = telegram_id
        self.on_tokens_update = on_tokens_update
        self.debug = debug
        self._current_rid = None

        # Credentials để auto-recovery
        self.username = username
        self.password = password
        self.otp_provider = otp_provider
        self._relogin_lock = threading.Lock()

    # ---------- HTTP logging wrappers ----------
    def _req_tag(self):
        return f"[TG:{self.telegram_id}]" if self.telegram_id else "[TG:?]"

    def _log_request(self, method, url, headers=None, params=None,
                     data=None, json_body=None, auth=None):
        rid = next(_REQ_SEQ)
        self._current_rid = rid
        h = _sanitize(dict(headers or {}))
        if auth:
            h["_auth"] = _mask(f"{auth[0]}:{auth[1] or ''}", keep_head=8, keep_tail=0)
        lines = [
            f"────────────── REQ #{rid} ──────────────",
            f"→ {method} {url}",
            f"  headers: {_dump(h, 4000)}",
        ]
        if params:
            lines.append(f"  params: {_dump(_sanitize(params), 2000)}")
        if data is not None:
            lines.append(f"  form: {_dump(_sanitize(data))}")
        if json_body is not None:
            lines.append(f"  json: {_dump(_sanitize(json_body))}")
        log.debug("%s %s", self._req_tag(), "\n".join(lines))

    def _log_response(self, r, elapsed_ms=None):
        rid = getattr(self, "_current_rid", "?")
        status = r.status_code
        body = r.content.decode("utf-8-sig", errors="replace") if r.content else ""
        try:
            parsed = json.loads(body) if body else None
            body_log = _dump(_sanitize(parsed)) if parsed is not None else body
        except Exception:
            body_log = body
        if len(body_log) > MAX_BODY_LOG:
            body_log = body_log[:MAX_BODY_LOG] + f"\n… [truncated, total {len(body_log)} chars]"
        extra = f" ({elapsed_ms:.0f}ms)" if elapsed_ms is not None else ""
        lines = [
            f"← RSP #{rid} ──── HTTP {status}{extra}",
            f"  url: {r.url}",
            f"  headers: {_dump(_sanitize(dict(r.headers)), 3000)}",
            f"  body: {body_log}",
        ]
        if status >= 400:
            log.warning("%s %s", self._req_tag(), "\n".join(lines))
        else:
            log.debug("%s %s", self._req_tag(), "\n".join(lines))

    def _post(self, url, headers=None, data=None, json_body=None,
              auth=None, allow_redirects=True, timeout=REQUEST_TIMEOUT):
        t0 = time.time()
        self._log_request("POST", url, headers=headers, data=data,
                          json_body=json_body, auth=auth)
        try:
            r = self.session.post(url, headers=headers, data=data,
                                  json=json_body, auth=auth,
                                  allow_redirects=allow_redirects,
                                  timeout=timeout)
        except Exception as e:
            log.error("%s × POST %s THẤT BẠI (timeout=%ss): %s: %s",
                      self._req_tag(), url, timeout, type(e).__name__, e,
                      exc_info=True)
            raise
        self._log_response(r, (time.time() - t0) * 1000)
        return r

    def _get(self, url, headers=None, params=None, allow_redirects=True,
             timeout=REQUEST_TIMEOUT):
        t0 = time.time()
        self._log_request("GET", url, headers=headers, params=params)
        try:
            r = self.session.get(url, headers=headers, params=params,
                                 allow_redirects=allow_redirects,
                                 timeout=timeout)
        except Exception as e:
            log.error("%s × GET %s THẤT BẠI (timeout=%ss): %s: %s",
                      self._req_tag(), url, timeout, type(e).__name__, e,
                      exc_info=True)
            raise
        self._log_response(r, (time.time() - t0) * 1000)
        return r

    # ================= AUTO-RECOVERY =================
    def logout(self):
        """Gọi API logout (port 9023) để hủy session, sau đó xoá token.

        Best-effort: mọi lỗi đều bị nuốt (đã log ERROR), miễn là token bị xoá.
        """
        old_tokens = self.tokens
        self.tokens = None  # clear ngay để tránh dùng lại token cũ

        if old_tokens:
            try:
                at = old_tokens.get("access_token", "")
                p = self.decode_jwt(at)
                url = f"{LOGOUT_BASE}/Por_GetData/LogoutAppMobile"
                headers = {
                    "Host": "hrm.vfr.net.vn:9023",
                    "profileidapp": p.get("hrm_profile_id", ""),
                    "sysuserid":    p.get("hrm_user_id", ""),
                    "userid":       p.get("hrm_user_id", ""),
                    "userlogin":    p.get("hrm_username", ""),
                    "languagecode": "VN",
                    "isportalapp":  "true",
                    "tokenportalapp": at,
                    "refreshtoken": old_tokens.get("refresh_token", ""),
                    "idtoken":      old_tokens.get("id_token", ""),
                    "application-request": APP_REQ,
                    "accept": "application/json",
                    "authorization": f"Bearer {at}",
                    "content-type": "application/json",
                    "user-agent": "okhttp/4.12.0",
                }
                payload = {
                    "userID": p.get("hrm_user_id", ""),
                    "deviceToken": "",
                }
                r = self._post(url, json_body=payload, headers=headers,
                               timeout=LOGOUT_TIMEOUT)
                log.info("%s [logout] HTTP %s body=%r",
                         self._req_tag(), r.status_code, r.text[:200])
            except Exception as e:
                log.error("%s [logout] thất bại (bỏ qua, vẫn xoá token): %s: %s",
                          self._req_tag(), type(e).__name__, e, exc_info=True)

        # Xoá token trong DB (ghi {})
        if self.on_tokens_update:
            try:
                self.on_tokens_update({})
            except Exception:
                log.exception("%s [logout] on_tokens_update lỗi", self._req_tag())

        log.warning("%s [logout] đã xoá token & session", self._req_tag())

    def _relogin(self):
        """Logout session cũ → login lại bằng credentials đã lưu. Thread-safe."""
        with self._relogin_lock:
            if not self.username or not self.password:
                raise Exception("Không có username/password để login lại "
                                "(client chưa được cấu hình credentials)")
            log.warning("%s [recovery] ▶ Bắt đầu logout + login lại user=%s",
                        self._req_tag(), self.username)
            try:
                self.logout()
            except Exception:
                log.exception("%s [recovery] logout lỗi (bỏ qua)", self._req_tag())

            try:
                tokens = self.login(self.username, self.password,
                                    otp_provider=self.otp_provider)
                log.warning("%s [recovery] ✔ Login lại THÀNH CÔNG user=%s",
                            self._req_tag(), self.username)
                return tokens
            except Exception:
                log.exception("%s [recovery] ✘ Login lại THẤT BẠI user=%s",
                              self._req_tag(), self.username)
                raise

    def _with_recovery(self, op_name, func):
        """Chạy func(). Nếu timeout/mất kết nối/401 → logout + login lại + retry.

        Retry tối đa MAX_RELOGIN_RETRIES lần sau khi relogin.
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                return func()

            except RETRYABLE_EXC as e:
                log.error(
                    "%s [recovery] ✖ %s lỗi mạng lần %d/%d: %s: %s",
                    self._req_tag(), op_name, attempts,
                    MAX_RELOGIN_RETRIES + 1, type(e).__name__, e,
                    exc_info=True,
                )
                if attempts > MAX_RELOGIN_RETRIES:
                    log.error("%s [recovery] ✖ %s BỎ CUỘC sau %d lần thử",
                              self._req_tag(), op_name, attempts)
                    raise
                try:
                    self._relogin()
                except Exception:
                    log.exception("%s [recovery] Không thể login lại, dừng retry",
                                  self._req_tag())
                    raise
                log.warning("%s [recovery] ↻ Retry %s (lần %d)...",
                            self._req_tag(), op_name, attempts + 1)

            except TokenExpired as e:
                log.error(
                    "%s [recovery] ✖ %s TokenExpired lần %d/%d: %s",
                    self._req_tag(), op_name, attempts,
                    MAX_RELOGIN_RETRIES + 1, e,
                )
                if attempts > MAX_RELOGIN_RETRIES:
                    log.error("%s [recovery] ✖ %s BỎ CUỘC sau %d lần thử",
                              self._req_tag(), op_name, attempts)
                    raise
                try:
                    self._relogin()
                except Exception:
                    log.exception("%s [recovery] Không thể login lại, dừng retry",
                                  self._req_tag())
                    raise
                log.warning("%s [recovery] ↻ Retry %s (lần %d)...",
                            self._req_tag(), op_name, attempts + 1)

    # ================= OpenID =================
    def _fetch_openid(self):
        if self.openid_config:
            return self.openid_config
        log.info("%s [openid] fetch %s", self._req_tag(), OPENID_URL)
        r = self._get(OPENID_URL)
        r.raise_for_status()
        self.openid_config = r.json()
        log.info("%s [openid] OK endpoint token=%s issuer=%s",
                 self._req_tag(), self.openid_config.get("token_endpoint"),
                 self.openid_config.get("issuer"))
        return self.openid_config

    @staticmethod
    def _pkce():
        v = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip("=")
        return v, c

    @staticmethod
    def decode_jwt(token: str):
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return {}
            b = parts[1] + "=" * (-len(parts[1]) % 4)
            return json.loads(base64.urlsafe_b64decode(b).decode())
        except Exception:
            return {}

    @staticmethod
    def _extract_code(loc: str):
        if not loc or "code=" not in loc:
            return None
        return parse_qs(loc.split("?", 1)[1]).get("code", [None])[0]

    def _follow_http_redirects(self, res, browser_headers, identity_url, max_hops=10):
        for _ in range(max_hops):
            if res.status_code not in (301, 302, 303, 307, 308):
                return res
            loc = res.headers.get("Location", "")
            if not loc:
                return res
            if loc.startswith("/"):
                loc = f"{identity_url}{loc}"
            if not loc.startswith(("http://", "https://")):
                return res
            res = self._get(loc, headers=browser_headers, allow_redirects=False)
            log.debug("%s REDIRECT HOP -> %s | HTTP %s",
                      self._req_tag(), loc, res.status_code)
        return res

    # ================= LOGIN =================
    def login(self, username, password, otp_provider=None):
        log.info("%s [login] ─── BẮT ĐẦU login user=%s ───",
                 self._req_tag(), username)
        cfg = self._fetch_openid()
        token_endpoint = cfg["token_endpoint"]
        issuer = cfg.get("issuer", "https://hrm.vfr.net.vn:9026").rstrip("/")
        login_endpoint = f"{issuer}/Account/Login"
        log.debug("%s [login] token_endpoint=%s login_endpoint=%s",
                  self._req_tag(), token_endpoint, login_endpoint)

        code_verifier, code_challenge = self._pkce()
        return_url = (
            "/connect/authorize/callback?"
            "client_id=hrm10_portal_app&response_type=code&"
            "redirect_uri=portal4hrm%3A%2FHome&"
            "scope=openid%20profile%20api%20offline_access%20IdentityServerApi&"
            f"code_challenge={code_challenge}&code_challenge_method=S256"
        )
        br = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}

        log.debug("%s [login] STEP1 GET login page", self._req_tag())
        r = self._get(login_endpoint, params={"ReturnUrl": return_url}, headers=br)
        soup = BeautifulSoup(r.text, "html.parser")
        tok = soup.find("input", {"name": "__RequestVerificationToken"})
        if not tok:
            log.error("%s [login] STEP1 KHÔNG có __RequestVerificationToken (HTTP %s)",
                      self._req_tag(), r.status_code)
            raise Exception("Không tìm thấy __RequestVerificationToken (sai endpoint?)")

        log.debug("%s [login] STEP2 POST credentials user=%s", self._req_tag(), username)
        r = self._post(login_endpoint, headers=br, allow_redirects=True, data={
            "ReturnUrl": return_url, "Username": username, "Password": password,
            "button": "login", "LanguageCode": "VN",
            "__RequestVerificationToken": tok["value"], "RememberLogin": "false",
        })
        soup = BeautifulSoup(r.text, "html.parser")
        cb = None
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta and "url=" in (meta.get("content") or ""):
            cb = meta["content"].split("url=")[1]
        if not cb:
            m = soup.find("meta", attrs={"data-url": True})
            if m:
                cb = m["data-url"]
        if not cb:
            log.warning("%s [login] STEP2 không có callback → sai user/pass (user=%s)",
                        self._req_tag(), username)
            raise Exception("Đăng nhập thất bại: sai user/pass")

        full_cb = cb if cb.startswith(("http://", "https://")) else f"{issuer}{cb}"
        log.debug("%s [login] STEP2.5 GET callback %s", self._req_tag(), full_cb)
        r = self._get(full_cb, headers=br, allow_redirects=False)
        loc = r.headers.get("Location", "")

        # STEP 2.6: 2FA
        if "/Account/LoginWith2Fa" in loc:
            log.info("%s [login] STEP2.6 server yêu cầu 2FA (user=%s)",
                     self._req_tag(), username)
            full_2fa = loc if loc.startswith("http") else f"{issuer}{loc}"
            r2 = self._get(full_2fa, headers=br, allow_redirects=False)
            r2 = self._follow_http_redirects(r2, br, issuer)
            final_loc = r2.headers.get("Location", "")

            if "code=" in final_loc:
                log.info("%s [login] STEP2.6 2FA auto-passed (trusted device)",
                         self._req_tag())
                loc = final_loc
            else:
                if otp_provider is None:
                    log.warning("%s [login] STEP2.6 cần OTP nhưng không có provider",
                                self._req_tag())
                    raise Hrm2FARequired(full_2fa)
                otp = otp_provider()
                log.info("%s [login] STEP2.6 đã nhận OTP từ user, POST xác thực (user=%s)",
                         self._req_tag(), username)
                soup2 = BeautifulSoup(r2.text, "html.parser")
                vt = soup2.find("input", {"name": "__RequestVerificationToken"})
                ru = soup2.find("input", {"name": "ReturnUrl"})
                post_url = r2.url.split("?")[0]
                r3 = self._post(post_url, headers=br, allow_redirects=False, data={
                    "ReturnUrl": (ru["value"] if ru else ""),
                    "TwoFactorCode": otp, "Input.TwoFactorCode": otp,
                    "Code": otp, "Input.Code": otp, "otp": otp,
                    "RememberLogin": "false", "button": "login",
                    "__RequestVerificationToken": (vt["value"] if vt else ""),
                })
                loc = r3.headers.get("Location", "")
                for _ in range(10):
                    if "code=" in loc:
                        break
                    if not loc:
                        break
                    if loc.startswith("/"):
                        loc = f"{issuer}{loc}"
                    r3 = self._get(loc, headers=br, allow_redirects=False)
                    if r3.status_code not in (301, 302, 303, 307, 308):
                        break
                    loc = r3.headers.get("Location", "")
                if "code=" not in loc and r3.text:
                    soup3 = BeautifulSoup(r3.text, "html.parser")
                    m3 = soup3.find("meta", attrs={"http-equiv": "refresh"})
                    if m3 and "url=" in (m3.get("content") or ""):
                        cb3 = m3["content"].split("url=")[1]
                        if cb3.startswith("/"):
                            cb3 = f"{issuer}{cb3}"
                        r4 = self._get(cb3, headers=br, allow_redirects=False)
                        loc = r4.headers.get("Location", loc)

        code = self._extract_code(loc)
        if not code:
            log.warning("%s [login] không lấy được code loc=%r", self._req_tag(), loc)
            raise Exception(f"Không lấy được code (loc={loc!r})")
        log.debug("%s [login] nhận được authorization code (len=%d)",
                  self._req_tag(), len(code))
        self.tokens = self._exchange_code(token_endpoint, code, code_verifier)
        self._save_tokens()
        # Lưu credentials để auto-recovery có thể dùng lại sau này
        self.username = username
        self.password = password
        if otp_provider is not None:
            self.otp_provider = otp_provider
        log.info("%s [login] ─── THÀNH CÔNG user=%s ───", self._req_tag(), username)
        return self.tokens

    def _exchange_code(self, token_endpoint, code, code_verifier):
        base = {
            "client_id": "hrm10_portal_app",
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "portal4hrm:/Home",
            "code_verifier": code_verifier,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "application-request": APP_REQ,
            "user-agent": "okhttp/4.12.0",
        }

        last_status = None
        last_text = ""
        for secret in CANDIDATE_SECRETS:
            for mode in ("post", "basic"):
                if mode == "post":
                    payload = dict(base)
                    auth = None
                    if secret is not None:
                        payload["client_secret"] = secret
                else:
                    payload = dict(base)
                    auth = ("hrm10_portal_app", secret or "")

                try:
                    r = self._post(token_endpoint, data=payload,
                                   headers=headers, auth=auth)
                except RETRYABLE_EXC as e:
                    log.warning("%s [exchange] timeout/mất kết nối (secret=%r mode=%s): %s",
                                self._req_tag(), secret, mode, e, exc_info=True)
                    # Bơm ra ngoài để _with_recovery (nếu có) xử lý
                    raise
                except Exception as e:
                    log.warning("%s [exchange] exception (secret=%r mode=%s): %s",
                                self._req_tag(), secret, mode, e, exc_info=True)
                    continue

                if r.status_code == 200:
                    log.info("%s [exchange] THÀNH CÔNG (secret=%r mode=%s)",
                             self._req_tag(), secret, mode)
                    return r.json()

                last_status = r.status_code
                last_text = r.text[:300]

        log.error("%s [exchange] THẤT BẠI last_status=%s body=%r",
                  self._req_tag(), last_status, last_text)
        raise Exception(
            f"Đổi code lấy token thất bại (last={last_status} body={last_text!r})"
        )

    # ================= TOKEN =================
    def set_tokens(self, tokens):
        self.tokens = tokens

    def _save_tokens(self):
        if self.on_tokens_update and self.tokens:
            try:
                self.on_tokens_update(self.tokens)
            except Exception:
                log.exception("%s [token] on_tokens_update lỗi", self._req_tag())

    def _is_expired(self, token):
        p = self.decode_jwt(token)
        return p.get("exp", 0) < (time.time() + 60)

    def ensure_token(self):
        if not self.tokens or not self.tokens.get("access_token"):
            raise TokenExpired("Chưa có access_token")
        if not self._is_expired(self.tokens["access_token"]):
            return False
        rt = self.tokens.get("refresh_token")
        if not rt:
            raise TokenExpired("Không có refresh_token")
        log.info("%s [token] access_token hết hạn, thử refresh...", self._req_tag())
        new_tokens = self._refresh(rt)
        if not new_tokens:
            log.warning("%s [token] refresh THẤT BẠI", self._req_tag())
            raise TokenExpired("Refresh token thất bại")
        if "id_token" not in new_tokens and self.tokens.get("id_token"):
            new_tokens["id_token"] = self.tokens["id_token"]
        self.tokens = new_tokens
        self._save_tokens()
        log.info("%s [token] refresh THÀNH CÔNG", self._req_tag())
        return True

    def _refresh(self, refresh_token):
        cfg = self._fetch_openid()
        ep = cfg["token_endpoint"]
        data = {
            "client_id": "hrm10_portal_app",
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "application-request": APP_REQ,
            "user-agent": "okhttp/4.12.0",
        }
        for secret in (None, APP_REQ, UUID_ONLY):
            payload = dict(data)
            if secret:
                payload["client_secret"] = secret
            try:
                r = self._post(ep, data=payload, headers=headers)
            except RETRYABLE_EXC:
                raise
            if r.status_code == 200:
                return r.json()
        return None

    # ================= AUTH HEADERS =================
    def _auth_headers(self):
        self.ensure_token()
        t = self.tokens
        at = t["access_token"]
        p = self.decode_jwt(at)
        return {
            "Host": "hrm.vfr.net.vn:9025",
            "profileidapp": p.get("hrm_profile_id", ""),
            "sysuserid":    p.get("hrm_user_id", ""),
            "userid":       p.get("hrm_user_id", ""),
            "userlogin":    p.get("hrm_username", ""),
            "languagecode": "VN",
            "isportalapp": "true",
            "tokenportalapp": at,
            "refreshtoken": t.get("refresh_token", ""),
            "idtoken":      t.get("id_token", ""),
            "application-request": APP_REQ,
            "accept": "application/json",
            "authorization": f"Bearer {at}",
            "content-type": "application/json",
            "user-agent": "okhttp/4.12.0",
        }

    # ================= API (wrapped với auto-recovery) =================
    def list_overtime(self, page_size=50):
        return self._with_recovery(
            "list_overtime",
            lambda: self._list_overtime_impl(page_size),
        )

    def _list_overtime_impl(self, page_size=50):
        url = f"{API_BASE}/api/Att_OvertimePlan/New_PlanOvertimeByFilterHandle_App"
        headers = self._auth_headers()
        all_items, page = [], 1
        while True:
            payload = {
                "IsPortalNew": True, "page": page, "pageSize": page_size,
                "take": page_size, "skip": (page - 1) * page_size, "group": [],
                "dataSourceRequestString": f"page={page}&pageSize={page_size}",
                "ValueFields": "ID,Status,ApproveHours,RegisterHours,ConfirmHours,WorkDateRoot,"
                               "InTime,OutTime,Rate,RequestCancelStatus,itemStatusCancel,StatusView,"
                               "WarningViolation,ReasonOT,DateCreate,DateApprove,ApprovalDate,DateUpdate,"
                               "DateReject,DateCancel,ProfileName,E_COMPANY,E_BRANCH,E_UNIT,E_DIVISION,"
                               "E_DEPARTMENT,E_TEAM,E_SECTION,JobTitleName,PositionName,MethodPaymentView,"
                               "WorkDate,DurationTypeView,OvertimeTypeName,OrgStructureTransName,"
                               "StrConfirmHours,StrRegisterHours,TimeFrom,FileAttachment,IsUnitAssistant,"
                               "IsSignUpToEat,IsRequestForBenefit,IsRequestEntryExitGate,BusinessUnitTypeView,"
                               "BusinessUnitView,SendToView,OvertimeArea",
                "Status": None, "keyQuery": "E_PRIMARY_DATA",
                "isCompare": True, "dataChange": True,
            }
            log.debug("%s [list_overtime] page=%d pageSize=%d",
                      self._req_tag(), page, page_size)
            r = self._post(url, json_body=payload, headers=headers)
            if r.status_code == 401:
                log.warning("%s [list_overtime] HTTP 401 → token hết hạn", self._req_tag())
                raise TokenExpired("HTTP 401")
            if r.status_code != 200:
                log.warning("%s [list_overtime] HTTP %s page=%s",
                            self._req_tag(), r.status_code, page)
                break
            try:
                data = json.loads(r.content.decode("utf-8-sig"))
            except Exception as e:
                log.warning("%s [list_overtime] parse JSON lỗi: %s",
                            self._req_tag(), e, exc_info=True)
                break
            items = data if isinstance(data, list) else (
                data.get("Data") or data.get("Result") or data.get("Items") or []
            )
            if not items:
                break
            all_items.extend(items)
            if len(items) < page_size:
                break
            page += 1
        log.info("%s [list_overtime] Tổng %d bản ghi", self._req_tag(), len(all_items))
        return all_items

    def get_cutoff_duration_by_profile(self):
        return self._with_recovery(
            "get_cutoff_duration_by_profile",
            self._get_cutoff_duration_by_profile_impl,
        )

    def _get_cutoff_duration_by_profile_impl(self):
        url = f"{API_BASE}/api/Att_GetData/GetCutOffDurationByProfile"
        headers = self._auth_headers()
        r = self._get(url, headers=headers)
        if r.status_code == 401:
            log.warning("%s [cutoff] HTTP 401 → token hết hạn", self._req_tag())
            raise TokenExpired("HTTP 401")
        try:
            res = json.loads(r.content.decode("utf-8-sig"))
            log.info("%s [cutoff] OK status=%s, %d kỳ",
                     self._req_tag(), res.get("Status"),
                     len(res.get("Data") or []) if isinstance(res.get("Data"), list) else 0)
            return res
        except Exception as e:
            log.warning("%s [cutoff] parse JSON lỗi: %s",
                        self._req_tag(), e, exc_info=True)
            return {"Status": "ERROR", "Message": r.text[:300], "HttpCode": r.status_code}

    def get_workday_detail(self, cutoff_duration_id, profile_id=None):
        """Lấy bảng công chi tiết theo kỳ chốt công."""
        return self._with_recovery(
            "get_workday_detail",
            lambda: self._get_workday_detail_impl(cutoff_duration_id, profile_id),
        )

    def _get_workday_detail_impl(self, cutoff_duration_id, profile_id=None):
        url = f"{API_BASE}/api/Att_Workday/GetListDataWorkdayForProfile"
        headers = self._auth_headers()
        p = self.decode_jwt(self.tokens["access_token"])
        payload = {
            "ProfileID": profile_id or p.get("hrm_profile_id", ""),
            "CutOffDurationID": cutoff_duration_id,
        }
        log.info("%s [workday] lấy bảng công chi tiết cutoff=%s",
                 self._req_tag(), cutoff_duration_id)
        r = self._post(url, json_body=payload, headers=headers)
        if r.status_code == 401:
            log.warning("%s [workday] HTTP 401 → token hết hạn", self._req_tag())
            raise TokenExpired("HTTP 401")
        try:
            res = json.loads(r.content.decode("utf-8-sig"))
            data = res.get("Data") or []
            log.info("%s [workday] OK status=%s, %d profile",
                     self._req_tag(), res.get("Status"),
                     len(data) if isinstance(data, list) else 0)
            return res
        except Exception as e:
            log.warning("%s [workday] parse JSON lỗi: %s",
                        self._req_tag(), e, exc_info=True)
            return {"Status": "ERROR", "Message": r.text[:300], "HttpCode": r.status_code}

    def submit_overtime(self, record_ids):
        return self._with_recovery(
            "submit_overtime",
            lambda: self._submit_overtime_impl(record_ids),
        )

    def _submit_overtime_impl(self, record_ids):
        if not record_ids:
            log.info("%s [submit] không có ID nào để gửi", self._req_tag())
            return {"Status": "SKIP", "Message": "Không có ID nào"}
        url = f"{API_BASE}/api/Att_OvertimePlan/ProcessingSendMailAndValidateOvertimePlan"
        headers = self._auth_headers()
        p = self.decode_jwt(self.tokens["access_token"])
        payload = {
            "ListRecordID": list(record_ids),
            "UserLogin": p.get("hrm_username", ""),
            "UserProcessID": p.get("hrm_user_id", ""),
            "Host": "https://hrm.vfr.net.vn:9022/",
            "ProfileRemoveIDs": None,
            "IsRemoveAndContinue": None,
            "CacheID": None,
            "IsContinueSave": False,
            "IsReloadUserApprove": False,
        }
        log.info("%s [submit] gửi %d ID: %s",
                 self._req_tag(), len(record_ids), [i[:8] for i in record_ids][:10])
        r = self._post(url, json_body=payload, headers=headers)
        if r.status_code == 401:
            log.warning("%s [submit] HTTP 401 → token hết hạn", self._req_tag())
            raise TokenExpired("HTTP 401")
        try:
            res = json.loads(r.content.decode("utf-8-sig"))
            log.info("%s [submit] kết quả status=%s", self._req_tag(), res.get("Status"))
            return res
        except Exception as e:
            log.warning("%s [submit] parse JSON lỗi: %s",
                        self._req_tag(), e, exc_info=True)
            return {"Status": "ERROR", "Message": r.text[:300], "HttpCode": r.status_code}