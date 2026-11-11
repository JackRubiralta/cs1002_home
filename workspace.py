"""Copy starter code and sheets from the StudRes mirror into your own folders.

Ported from cs_lab_start's exercise step: code goes into the folder stacscheck
expects (the tests' srcdir, e.g. W08/W08Exercises/), sheets keep their place so
the HTML still renders, starter zips are unpacked, and **a file that is already
there is never replaced** - your answers are safe, only new files are added.
Tests stay in the mirror; `cs1002 test` points stacscheck at them.
"""

import json
import os
import re
import shutil
import stat
import time
import zipfile

import config
from config import say

WEEK_RE = re.compile(r"^W\d+$")
SKIP_NAMES = {".DS_Store", "__MACOSX", "Thumbs.db"}
DOC_EXT = {".html", ".htm", ".pdf", ".css", ".gif", ".png", ".jpg", ".jpeg", ".svg"}


def read_srcdir(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as f:
            m = re.search(r"^\s*srcdir\s*=\s*(\S+)", f.read(), re.M)
            return m.group(1) if m else None
    except OSError:
        return None


def find_tests(folder):
    """[(tests_dir, srcdir)] for every Tests folder (and Tests/<part>) under folder."""
    out = []
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        if "practical.config" in files and "Tests" in root.split(os.sep):
            srcdir = read_srcdir(os.path.join(root, "practical.config"))
            if srcdir:
                out.append((root, srcdir))
    return out


def top_tests(folder):
    """The Tests folders to run for a week: the outermost ones (W08/Tests, not W08/Tests/Mug)."""
    tests = find_tests(folder)
    tops = []
    for tdir, srcdir in tests:
        if not any(tdir != t and tdir.startswith(t + os.sep) for t, _ in tests):
            tops.append((tdir, srcdir))
    return tops


def _place(rel_parts, srcdirs, here_srcdir, is_doc):
    for i, part in enumerate(rel_parts[:-1]):
        if part in srcdirs:
            return rel_parts[i:]
    if not is_doc and here_srcdir:
        return [here_srcdir, rel_parts[-1]]
    return rel_parts


def plan_folder(src):
    """[(dest_rel_path, kind, source)] for one StudRes week/assignment folder."""
    tests = find_tests(src)
    srcdirs = {s for _, s in tests}
    beside = {}
    for tdir, s in tests:
        parts = tdir.split(os.sep)
        idx = len(parts) - 1 - parts[::-1].index("Tests")
        beside.setdefault(os.sep.join(parts[:idx]), s)

    plan, problems = [], []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d != "Tests" and d not in SKIP_NAMES)
        rel_root = os.path.relpath(root, src)
        rel_parts = [] if rel_root == "." else rel_root.split(os.sep)
        for name in sorted(files):
            if name in SKIP_NAMES or name.startswith("._") or name.endswith(".part"):
                continue
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext == ".zip":
                try:
                    with zipfile.ZipFile(path) as z:
                        for member in z.namelist():
                            mparts = [p for p in member.replace("\\", "/").split("/") if p]
                            if (member.endswith("/") or not mparts
                                    or any(p in SKIP_NAMES or p.startswith("._") or p == ".." for p in mparts)):
                                continue
                            mext = os.path.splitext(mparts[-1])[1].lower()
                            dest = _place(rel_parts + mparts, srcdirs, beside.get(root), mext in DOC_EXT)
                            plan.append((os.path.join(*dest), "zip", (path, member)))
                except (zipfile.BadZipFile, OSError, RuntimeError, ValueError) as e:
                    problems.append("%s (%s)" % (os.path.join(*(rel_parts + [name])), e))
                continue
            dest = _place(rel_parts + [name], srcdirs, beside.get(root), ext in DOC_EXT)
            plan.append((os.path.join(*dest), "file", path))
    plan.sort(key=lambda p: p[1] != "file")   # a loose file beats the same file in a zip
    return plan, tests, problems


def copy_new(kind, source, dest):
    """Copy one file to dest, which must not exist yet (never overwrites)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if kind == "file":
        src = open(source, "rb")
        z = None
    else:
        zpath, member = source
        z = zipfile.ZipFile(zpath)
        src = z.open(member)
    try:
        out = open(dest, "xb")
    except BaseException:
        src.close()
        if z:
            z.close()
        raise
    try:
        with src, out:
            shutil.copyfileobj(src, out)
    except BaseException:
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise
    finally:
        if z:
            z.close()
    try:
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IWUSR | stat.S_IRUSR)
    except OSError:
        pass


def fill(src, dst, label):
    """Add what's new from mirror folder src to your folder dst. Returns (copied, kept, failed)."""
    plan, tests, problems = plan_folder(src)
    copied, kept, failed = [], 0, list(problems)
    for _, srcdir in tests:          # the folder stacscheck looks for, even with no starter code
        d = os.path.join(dst, srcdir)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            copied.append(os.path.join(label, srcdir) + os.sep)
    seen = set()
    for rel, kind, source in plan:
        if rel in seen:
            continue
        seen.add(rel)
        dest = os.path.join(dst, rel)
        if os.path.lexists(dest):
            kept += 1
            continue
        try:
            copy_new(kind, source, dest)
            copied.append(os.path.join(label, rel))
        except FileExistsError:
            kept += 1
        except Exception as e:
            failed.append("%s (%s)" % (os.path.join(label, rel), e))
    return copied, kept, failed


def weeks():
    d = os.path.join(config.MIRROR, "Exercises")
    try:
        return sorted((w for w in os.listdir(d) if WEEK_RE.match(w)), key=lambda w: int(w[1:]))
    except OSError:
        return []


def assignments():
    d = os.path.join(config.MIRROR, "Coursework")
    try:
        return sorted(a for a in os.listdir(d)
                      if os.path.isdir(os.path.join(d, a)) and re.match(r"^Assignment\d+$", a))
    except OSError:
        return []


def update_workspace():
    """Exercises + assignments from the mirror into your folders (never overwrites)."""
    all_copied, all_kept, all_failed = [], 0, []
    for w in weeks():
        c, k, f = fill(os.path.join(config.MIRROR, "Exercises", w), os.path.join(config.EXERCISES, w), w)
        all_copied += c
        all_kept += k
        all_failed += f
    css = os.path.join(config.MIRROR, "Exercises", "css")
    if os.path.isdir(css):
        for name in sorted(os.listdir(css)):
            dest = os.path.join(config.EXERCISES, "css", name)
            if os.path.isfile(os.path.join(css, name)) and not os.path.lexists(dest):
                copy_new("file", os.path.join(css, name), dest)
    for a in assignments():
        c, k, f = fill(os.path.join(config.MIRROR, "Coursework", a), os.path.join(config.COURSEWORK, a), a)
        all_copied += c
        all_kept += k
        all_failed += f
    return all_copied, all_kept, all_failed


# --------------------------------------------------------------------- mock
def mock_zips():
    d = os.path.join(config.MIRROR, "Coursework")
    out = []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.lower().startswith("mocktest") and os.path.isdir(os.path.join(d, name)):
                for f in sorted(os.listdir(os.path.join(d, name))):
                    if f.lower().endswith(".zip"):
                        out.append(os.path.join(d, name, f))
    return out


def new_mock_attempt(zip_path):
    """Unzip a fresh copy of the mock test into MockTest/attempt-N. Returns the folder."""
    os.makedirs(config.MOCK, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(config.MOCK, "attempt-%d" % n)):
        n += 1
    dest = os.path.join(config.MOCK, "attempt-%d" % n)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            parts = [p for p in member.replace("\\", "/").split("/") if p]
            if not parts or any(p == ".." or p in SKIP_NAMES or p.startswith("._") for p in parts):
                continue
            target = os.path.join(dest, *parts)
            if member.endswith("/"):
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(member) as s, open(target, "wb") as o:
                shutil.copyfileobj(s, o)
    return dest


def mock_info(attempt):
    try:
        with open(os.path.join(attempt, ".mock.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_mock_info(attempt, info):
    with open(os.path.join(attempt, ".mock.json"), "w", encoding="utf-8") as f:
        json.dump(info, f)


def latest_mock():
    try:
        tries = sorted((d for d in os.listdir(config.MOCK) if re.match(r"^attempt-\d+$", d)),
                       key=lambda d: int(d.split("-")[1]))
    except OSError:
        return None
    return os.path.join(config.MOCK, tries[-1]) if tries else None


def zip_for_mms(folder, out_path):
    """Zip a code folder for MMS: everything except compiled .class files and our own state."""
    base = os.path.basename(os.path.normpath(folder))
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES and not d.startswith("."))
            for name in sorted(files):
                if name.endswith(".class") or name.startswith(".") or name in SKIP_NAMES:
                    continue
                full = os.path.join(root, name)
                z.write(full, os.path.join(base, os.path.relpath(full, folder)))
                n += 1
    return n
