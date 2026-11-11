"""Sign in to StudRes and mirror CS1002 to this computer.

StudRes (https://studres.cs.st-andrews.ac.uk/CS1002/) sits behind the
University's Microsoft sign-in, so plain HTTP gets nothing. We keep our own
browser profile (Playwright, ~/.cs1002_home/browser): you sign in there once,
Microsoft's "Stay signed in" cookie keeps it, and every later sync signs in by
itself without showing a window. Files are fetched with that browser's
cookies (Playwright's request API), so nothing is clicked or rendered.

The sign-in steps are the same ones cs_lab_start uses on the lab PCs: it can
type the email and password from .env, presses "Yes" on "Stay signed in?",
picks Authenticator, and prints the number you type on your phone.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
from email.utils import parsedate_to_datetime

import config
from config import say

STUDRES_ROOT = "https://studres.cs.st-andrews.ac.uk/CS1002/"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com",
               "login.st-andrews.ac.uk", "idp.st-andrews.ac.uk")
LOGIN_TIMEOUT = 300          # seconds, long enough to find your phone

# Folders mirrored by `sync` (relative to /CS1002/). 0-General (JavaDoc, ~10k files) is left out.
DEFAULT_FOLDERS = ["Exercises", "Coursework", "Tutorials", "Examples", "Lectures"]
BIG_EXT = {".pptx", ".ppt", ".mp4", ".mov", ".mkv", ".m4v", ".webm"}
SKIP_RE = re.compile(r"(Zone\.Identifier|\.DS_Store|Thumbs\.db)$|(^|/)__MACOSX(/|$)|(^|/)\._")


class NotSignedIn(Exception):
    pass


class SignInFailed(Exception):
    pass


# ------------------------------------------------------------------ browser
def _channels():
    """Browsers to try, best first. Edge is on every Windows PC, so Windows needs no
    browser download; elsewhere Playwright's own Chromium, then Chrome."""
    saved = config.load_state().get("browser_channel")
    order = ["msedge", "chrome", "chromium"] if os.name == "nt" else ["chromium", "chrome", "msedge"]
    if saved in order:
        order.remove(saved)
        order.insert(0, saved)
    return order


class Browser:
    """A Playwright persistent context on our own profile. Use as a context manager."""

    def __init__(self, headless=True):
        self.headless = headless
        self.pw = None
        self.ctx = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise SystemExit("Playwright isn't installed. Run the installer again "
                             "(./install.sh or install.ps1), or: python -m pip install playwright")
        self.pw = sync_playwright().start()
        errors = []
        os.makedirs(config.PROFILE_DIR, exist_ok=True)
        for channel in _channels():
            kw = dict(user_data_dir=config.PROFILE_DIR, headless=self.headless,
                      accept_downloads=False, viewport=None if not self.headless else {"width": 1200, "height": 900},
                      args=["--no-first-run", "--no-default-browser-check"])
            if channel != "chromium":
                kw["channel"] = channel
            try:
                self.ctx = self.pw.chromium.launch_persistent_context(**kw)
                st = config.load_state()
                if st.get("browser_channel") != channel:
                    st["browser_channel"] = channel
                    config.save_state(st)
                return self
            except Exception as e:     # not installed / profile from another browser
                errors.append("%s: %s" % (channel, str(e).splitlines()[0][:160]))
        self.pw.stop()
        raise SystemExit("Couldn't start a browser:\n  " + "\n  ".join(errors) +
                         "\nRun:  python -m playwright install chromium   (or `cs1002 setup`)")

    def __exit__(self, *exc):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self.pw:
                self.pw.stop()

    # -------------------------------------------------------------- requests
    def get(self, url, timeout=60):
        """GET with the browser's cookies. Raises NotSignedIn if StudRes bounced us to SSO."""
        r = self.ctx.request.get(url, timeout=timeout * 1000, max_redirects=0, fail_on_status_code=False)
        host = urllib.parse.urlparse(r.headers.get("location", "")).netloc
        if r.status in (301, 302, 303, 307, 308) and (host in LOGIN_HOSTS or "Shibboleth" in r.headers.get("location", "")):
            raise NotSignedIn()
        if r.status in (301, 302, 303, 307, 308):          # e.g. folder without trailing slash
            return self.get(urllib.parse.urljoin(url, r.headers["location"]), timeout)
        if r.status in (401, 403, 500) and "studres" in url:
            # StudRes answers 500 (Shibboleth) when there is no session at all
            raise NotSignedIn()
        return r

    def signed_in(self):
        try:
            r = self.get(STUDRES_ROOT, timeout=30)
        except NotSignedIn:
            return False
        return r.status == 200 and "Index of /CS1002" in r.text()

    # --------------------------------------------------------------- sign-in
    def sign_in(self, email=None, password=None, timeout=LOGIN_TIMEOUT):
        """Open StudRes in a page and drive the Microsoft login until StudRes shows.
        Headless: succeeds only if Microsoft remembers us (no typing needed)."""
        page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        try:
            page.goto(STUDRES_ROOT, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass
        state = {}
        deadline = time.time() + timeout
        last = (None, 0.0)
        while time.time() < deadline:
            try:
                info = page.evaluate(DETECT_JS)
            except Exception:
                time.sleep(0.5)          # mid-navigation
                continue
            url = info.get("url", "")
            host = urllib.parse.urlparse(url).netloc
            if host.startswith("studres.") and "Index of /CS1002" in info.get("page", ""):
                return True
            if host not in LOGIN_HOSTS and not host.endswith(".microsoftonline.com"):
                time.sleep(0.5)          # a redirect hop on the way
                continue
            kind = info.get("kind")
            if self.headless and kind in ("email", "password", "number", "approve", "method", "picker", "error"):
                raise NotSignedIn()      # needs a person: caller opens a window
            key = (kind, info.get("number"))
            if key == last[0] and time.time() - last[1] < 6:
                time.sleep(0.5)
                continue
            last = (key, time.time())
            try:
                _act(page, info, kind, email, password, state)
            except SignInFailed:
                raise
            except Exception:
                pass                     # page changed under us; look again
            time.sleep(0.7)
        raise SignInFailed("timed out after %d s waiting for StudRes" % timeout)


# Same detector as cs_lab_start (lab_start.py DETECT_JS), as a function for Playwright.
DETECT_JS = r"""() => {
const vis = e => {
  if (!e || e.offsetWidth === 0 || e.offsetHeight === 0 || e.closest('.moveOffScreen')) return false;
  const cs = getComputedStyle(e), r = e.getBoundingClientRect();
  return cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0' &&
    !(e.tagName === 'INPUT' && e.tabIndex < 0) && r.right > 0 && r.bottom > 0 &&
    r.left < innerWidth && r.top < innerHeight;
};
const q = s => [...document.querySelectorAll(s)].find(vis) || null;
const text = (document.body && document.body.innerText) || '';
const out = {url: location.href, ready: document.readyState, kind: 'wait',
             page: (document.title + ' | ' + text.slice(0, 600))};
const err = q('#usernameError, #passwordError, #errorText, [data-testid="error"], .alert-error, #idTD_Error');
if (err && err.innerText.trim()) { out.kind = 'error'; out.error = err.innerText.trim().slice(0, 200); return out; }
const pw = q('input[name="passwd"], input[type="password"]');
if (pw) { out.kind = 'password'; out.filled = !!pw.value; return out; }
if (q('input[name="loginfmt"]')) { out.kind = 'email'; out.filled = !!q('input[name="loginfmt"]').value; return out; }
let num = q('#idRichContext_DisplaySign, #displaySign, [data-testid="displaySign"]');
if (!num && /Authenticator|Approve sign.?in/i.test(text))
  num = [...document.querySelectorAll('div,span,p')].find(e => vis(e) && /^\s*\d{2,3}\s*$/.test(e.innerText || ''));
if (num) { out.kind = 'number'; out.number = num.innerText.trim(); return out; }
if (/Approve sign.?in request|Check your Authenticator|open your Authenticator/i.test(text)) { out.kind = 'approve'; return out; }
if (/We didn.t hear from you|request (was )?denied|denied the request|You.ve hit our limit/i.test(text)) {
  out.kind = 'error'; out.error = 'Authenticator: ' + (text.match(/We didn.t hear from you|request (was )?denied|denied the request|You.ve hit our limit[^.]*/i) || [''])[0]; return out; }
if (/Stay signed in\?/i.test(text)) { out.kind = 'kmsi'; return out; }
if (/Pick an account/i.test(text)) { out.kind = 'picker'; return out; }
if (/Verify your identity/i.test(text)) { out.kind = 'method'; return out; }
return out;
}"""

CLICK_TEXT_JS = r"""(want) => {
want = want.toLowerCase();
const vis = e => !!e && e.offsetWidth > 0 && e.offsetHeight > 0;
const els = [...document.querySelectorAll('[role="button"], [role="link"], button, a, div[data-value], div.table, small')];
const hit = els.filter(vis).find(e => (e.innerText || '').toLowerCase().includes(want));
if (hit) { hit.click(); return true; }
return false;
}"""


def _submit(page):
    for sel in ("#idSIButton9", 'input[type="submit"]', 'button[type="submit"]'):
        loc = page.locator(sel + ":visible")
        if loc.count():
            loc.first.click(timeout=5000)
            return


def _act(page, info, kind, email, password, state):
    if kind == "error":
        raise SignInFailed(info.get("error", "sign-in error"))
    if kind == "email":
        if not email:
            if not state.get("told_email"):
                state["told_email"] = True
                say("  type your University email in the browser window")
            return
        if not info.get("filled"):
            page.locator('input[name="loginfmt"]:visible').first.fill(email)
        _submit(page)
        say("  email entered")
    elif kind == "password":
        if not password:
            if not state.get("told_pw"):
                state["told_pw"] = True
                say("  type your password in the browser window")
            return
        if state.get("password_tries", 0) >= 1:
            raise SignInFailed("the password page came back - check PASSWORD in .env "
                               "(stopped so your account doesn't get locked)")
        state["password_tries"] = state.get("password_tries", 0) + 1
        page.locator('input[name="passwd"]:visible, input[type="password"]:visible').first.fill(password)
        _submit(page)
        say("  password entered")
    elif kind == "number":
        if state.get("shown") != info["number"]:
            state["shown"] = info["number"]
            show_number(info["number"])
    elif kind == "approve":
        if state.get("shown") != "approve":
            state["shown"] = "approve"
            say("  approve the sign-in on your phone (Microsoft Authenticator)...")
    elif kind == "kmsi":
        _submit(page)                     # "Stay signed in?" -> Yes, so later syncs need no window
        say("  'Stay signed in?' -> Yes")
    elif kind == "picker":
        if email and page.evaluate(CLICK_TEXT_JS, email):
            say("  picked account " + email)
    elif kind == "method":
        for label in ("Approve a request on my Microsoft Authenticator",
                      "Microsoft Authenticator", "Authenticator app"):
            if page.evaluate(CLICK_TEXT_JS, label):
                say("  chose Microsoft Authenticator")
                break


def show_number(number):
    say("")
    say("  +------------------------------------------+")
    say("  |  Type  %-4s into Microsoft Authenticator  |" % number)
    say("  +------------------------------------------+")
    say("")


def login(force_window=False):
    """Make sure the profile is signed in. Tries silently first, then opens a window."""
    email, password = config.load_env()
    if not force_window:
        with Browser(headless=True) as b:
            if b.signed_in():
                return True
            try:
                if b.sign_in(timeout=40) and b.signed_in():
                    return True
            except (NotSignedIn, SignInFailed):
                pass
    say("Signing in to StudRes - a browser window opens.")
    if not (email and password):
        say("  (put EMAIL= and PASSWORD= in %s to have it typed for you)" % config.ENV_FILE)
    with Browser(headless=False) as b:
        b.sign_in(email, password)
        ok = b.signed_in()
    if ok:
        say("Signed in. Later syncs reuse this sign-in without a window.")
    return ok


# ------------------------------------------------------------------- listing
ROW_RE = re.compile(
    r'<tr><td[^>]*><img[^>]*alt="\[([^\]]*)\]"[^>]*></td><td><a href="([^"]+)">.*?</a></td>'
    r'<td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td>', re.S)


def parse_listing(text):
    """Apache 'Index of' page -> [(name, is_dir, mtime 'YYYY-MM-DD HH:MM', size str)]."""
    out = []
    for alt, href, mtime, size in ROW_RE.findall(text):
        if alt == "PARENTDIR" or href.startswith(("/", "?", "http")):
            continue
        name = urllib.parse.unquote(html.unescape(href))
        is_dir = name.endswith("/")
        out.append((name.rstrip("/"), is_dir, mtime.strip(), size.strip()))
    return out


def size_bytes(s):
    m = re.match(r"^([\d.]+)([KMG]?)$", s.strip())
    if not m:
        return 0
    return int(float(m.group(1)) * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[m.group(2)])


def crawl(b, rel):
    """Every file under /CS1002/<rel>/ -> [(relpath, mtime, size_str)]."""
    files, todo = [], [rel.strip("/")]
    while todo:
        folder = todo.pop()
        url = STUDRES_ROOT + urllib.parse.quote(folder + "/")
        r = b.get(url)
        if r.status == 404:
            continue
        text = r.text()
        if "Index of /CS1002" not in text:
            if "javadoc" in folder.lower():
                continue
            raise NotSignedIn()
        for name, is_dir, mtime, size in parse_listing(text):
            path = folder + "/" + name
            if SKIP_RE.search(path):
                continue
            if is_dir:
                todo.append(path)
            else:
                files.append((path, mtime, size))
    return sorted(files)


# ---------------------------------------------------------------------- sync
def sync(folders=None, max_mb=60, include_big=False, dry_run=False, quiet=False):
    """Mirror StudRes folders into <home>/studres/CS1002/. Re-downloads a file only when
    StudRes shows a newer time; never deletes anything local. Returns (new, updated, skipped)."""
    folders = folders or DEFAULT_FOLDERS
    manifest = config.load_manifest()
    new, updated, skipped, failed = [], [], [], []
    for attempt in (1, 2):
        try:
            with Browser(headless=True) as b:
                if not b.signed_in():
                    try:
                        b.sign_in(timeout=40)     # Microsoft still remembers us
                    except (NotSignedIn, SignInFailed):
                        raise NotSignedIn()
                for folder in folders:
                    if not quiet:
                        say("  checking %s/ ..." % folder)
                    for path, mtime, size in crawl(b, folder):
                        dest = os.path.join(config.MIRROR, *path.split("/"))
                        ext = os.path.splitext(path)[1].lower()
                        if (not include_big) and (ext in BIG_EXT or size_bytes(size) > max_mb * 1024 ** 2):
                            if not os.path.exists(dest):
                                skipped.append("%s (%s)" % (path, size))
                            continue
                        known = manifest.get(path)
                        if os.path.exists(dest) and known == mtime:
                            continue
                        (updated if os.path.exists(dest) else new).append(path)
                        if dry_run:
                            continue
                        try:
                            _download(b, path, dest)
                            manifest[path] = mtime
                        except NotSignedIn:
                            raise
                        except Exception as e:
                            failed.append("%s (%s)" % (path, str(e).splitlines()[0][:100]))
                        if len(new) + len(updated) and (len(new) + len(updated)) % 25 == 0:
                            config.save_manifest(manifest)
            break
        except NotSignedIn:
            config.save_manifest(manifest)
            if attempt == 2 or dry_run:
                raise SystemExit("Not signed in to StudRes. Run:  cs1002 login")
            say("StudRes wants you to sign in again.")
            if not login(force_window=True):
                raise SystemExit("Sign-in didn't finish - run  cs1002 login  and try again.")
    config.save_manifest(manifest)
    return new, updated, skipped, failed


def _download(b, path, dest):
    r = b.get(STUDRES_ROOT + urllib.parse.quote(path), timeout=300)
    if r.status != 200:
        raise IOError("HTTP %d" % r.status)
    body = r.body()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)
    lm = r.headers.get("last-modified")
    if lm:
        try:
            t = parsedate_to_datetime(lm).timestamp()
            os.utime(dest, (t, t))
        except (TypeError, ValueError, OSError):
            pass
    if dest.endswith(".sh") and os.name != "nt":
        os.chmod(dest, 0o755)       # stacscheck runs them with bash, but keep them executable like the lab
