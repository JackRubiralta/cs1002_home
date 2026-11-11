#!/usr/bin/env python3
"""cs1002 - do CS1002 exercises, assignments and the mock test on your own computer.

  cs1002 setup            check Java, Git Bash (Windows), VS Code, the browser
  cs1002 login            sign in to StudRes once (a browser window opens)
  cs1002 sync             download everything new from StudRes + add new starter code
  cs1002 test [WHAT]      run stacscheck: W08, 8, a2, mock, or nothing = the folder you're in
  cs1002 mock             start a timed mock test (fresh copy, timer, spec + VS Code)
  cs1002 code [WHAT]      open VS Code on a week / assignment
  cs1002 zip [WHAT]       zip your code for the MMS upload (no .class files)
  cs1002 status           what you have, newest week, sign-in state
  cs1002 stacscheck ARGS  the School's stacscheck itself, e.g. cs1002 stacscheck <Tests folder>
  cs1002 update           get the newest version of this program
"""

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config                                    # noqa: E402
import workspace                                 # noqa: E402
from config import say                           # noqa: E402

RUNNER = os.path.join(HERE, "run_stacscheck.py")


# ------------------------------------------------------------------- helpers
def head(title):
    say("")
    say("== " + title + " " + "=" * max(3, 60 - len(title)))


def find_code():
    for name in ("code", "codium", "code-insiders"):
        p = shutil.which(name)
        if p:
            return [p]
    if config.IS_WINDOWS:
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
            for sub in (r"Programs\Microsoft VS Code\bin\code.cmd", r"Microsoft VS Code\bin\code.cmd"):
                p = os.path.join(base, sub)
                if base and os.path.isfile(p):
                    return [p]
    for p in ("/usr/bin/code", "/usr/share/code/bin/code", "/opt/visual-studio-code/bin/code",
              "/snap/bin/code", "/var/lib/flatpak/exports/bin/com.visualstudio.code"):
        if os.access(p, os.X_OK):
            return [p]
    return None


def open_vscode(folder, file=None):
    code = find_code()
    if not code:
        say("  VS Code not found - open %s yourself (or install it: cs1002 setup)" % folder)
        return False
    args = code + ["--new-window", folder] + ([file] if file else [])
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     shell=config.IS_WINDOWS and code[0].lower().endswith(".cmd"),
                     **({"start_new_session": True} if not config.IS_WINDOWS else {}))
    say("  VS Code: " + folder)
    return True


def open_file(path):
    try:
        if config.IS_WINDOWS:
            os.startfile(path)                     # noqa: (Windows only)
        else:
            webbrowser.open("file://" + os.path.abspath(path))
    except Exception:
        say("  open it yourself: " + path)


def main_java(folder):
    """The .java file with main() (else the first .java) in a code folder."""
    javas = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "Tests"]
        javas += [os.path.join(root, f) for f in sorted(files) if f.endswith(".java")]
    for j in javas:
        try:
            with open(j, encoding="utf-8", errors="replace") as f:
                if re.search(r"static\s+void\s+main\s*\(", f.read()):
                    return j
        except OSError:
            pass
    return javas[0] if javas else None


# ------------------------------------------------------------ what -> target
class Target:
    """A set of tests and the folder to run them from."""

    def __init__(self, label, run_dir, tests, code_dir):
        self.label, self.run_dir, self.tests, self.code_dir = label, run_dir, tests, code_dir


def _week_name(s):
    m = re.match(r"^(?:w|week)?\s*0*(\d+)$", s.strip(), re.I)
    return "W%02d" % int(m.group(1)) if m else None


def _assignment_name(s):
    m = re.match(r"^(?:a|assignment|ass)\s*0*(\d+)$", s.strip(), re.I)
    return "Assignment%d" % int(m.group(1)) if m else None


def resolve(what=None):
    """Turn 'W08' / '8' / 'a2' / 'mock' / a path / nothing (= current folder) into a Target."""
    cwd = os.path.realpath(os.getcwd())
    if what is None:
        for base, kind in ((config.EXERCISES, "week"), (config.COURSEWORK, "assignment"), (config.MOCK, "mock")):
            base = os.path.realpath(base)
            if cwd == base or cwd.startswith(base + os.sep):
                rel = os.path.relpath(cwd, base).split(os.sep)
                if rel[0] not in (".", ""):
                    what = "mock:" + os.path.join(base, rel[0]) if kind == "mock" else rel[0]
                    break
        if what is None:
            if kind_folder_has_tests(cwd):
                what = cwd
            else:
                w = workspace.weeks()
                if not w:
                    raise SystemExit("No exercises yet - run:  cs1002 sync")
                what = w[-1]
                say("(not inside a week's folder - using the newest week, %s)" % what)
    if what.lower() == "mock" or what.startswith("mock:"):
        attempt = what[5:] if what.startswith("mock:") else workspace.latest_mock()
        if not attempt or not os.path.isdir(attempt):
            raise SystemExit("No mock test started yet - run:  cs1002 mock")
        tests = workspace.top_tests(attempt)
        return Target("Mock test (%s)" % os.path.basename(attempt), attempt, tests,
                      os.path.join(attempt, tests[0][1]) if tests else attempt)
    week = _week_name(what)
    if week:
        src = os.path.join(config.MIRROR, "Exercises", week)
        if not os.path.isdir(src):
            raise SystemExit("%s isn't on this computer - run:  cs1002 sync" % week)
        tests = workspace.top_tests(src)
        run_dir = os.path.join(config.EXERCISES, week)
        code_dir = os.path.join(run_dir, tests[0][1]) if len(tests) == 1 else run_dir
        return Target(week, run_dir, tests, code_dir)
    a = _assignment_name(what)
    if a:
        src = os.path.join(config.MIRROR, "Coursework", a)
        if not os.path.isdir(src):
            raise SystemExit("%s isn't on this computer - run:  cs1002 sync" % a)
        tests = workspace.top_tests(src)
        run_dir = os.path.join(config.COURSEWORK, a)
        code_dir = os.path.join(run_dir, tests[0][1]) if len(tests) == 1 else run_dir
        return Target(a, run_dir, tests, code_dir)
    path = os.path.abspath(os.path.expanduser(what))
    if os.path.isdir(path):
        tests = workspace.top_tests(path) or ([(path, workspace.read_srcdir(os.path.join(path, "practical.config")))]
                                              if os.path.exists(os.path.join(path, "practical.config")) else [])
        return Target(os.path.basename(path), cwd, tests, cwd)
    raise SystemExit("Don't know '%s'. Try W08, 8, a2, mock, or a Tests folder." % what)


def kind_folder_has_tests(folder):
    return os.path.isdir(os.path.join(folder, "Tests"))


# ------------------------------------------------------------------ commands
def cmd_setup(args):
    import setup_check
    return setup_check.run(install=args.install)


def cmd_login(args):
    import studres
    head("StudRes sign-in")
    ok = studres.login(force_window=args.window)
    say("Signed in." if ok else "Not signed in.")
    return 0 if ok else 1


def cmd_sync(args):
    import studres
    head("Downloading from StudRes")
    folders = args.folders or None
    new, updated, skipped, failed = studres.sync(folders=folders, max_mb=args.max_mb,
                                                 include_big=args.all, dry_run=args.dry_run)
    verb = "would download" if args.dry_run else "downloaded"
    say("  %s %d new and %d changed file(s) into %s" % (verb, len(new), len(updated), config.MIRROR))
    for p in (new + updated)[:30]:
        say("    + " + p)
    if len(new + updated) > 30:
        say("    ... and %d more" % (len(new + updated) - 30))
    if updated:
        say("  changed on StudRes since last time (the School edits tests without telling anyone):")
        for p in updated[:10]:
            say("    ~ " + p)
    if skipped:
        say("  skipped %d big file(s) (slide decks/videos; --all gets them):" % len(skipped))
        for p in skipped[:5]:
            say("    - " + p)
    if failed:
        say("  couldn't download %d file(s):" % len(failed))
        for p in failed[:10]:
            say("    ! " + p)
    if args.dry_run:
        return 0
    head("Your folders")
    copied, kept, wfailed = workspace.update_workspace()
    if copied:
        say("  added %d new file(s)/folder(s) to %s:" % (len(copied), config.HOME))
        for c in copied[:30]:
            say("    + " + c)
        if len(copied) > 30:
            say("    ... and %d more" % (len(copied) - 30))
    else:
        say("  nothing new - your files are up to date")
    say("  %d file(s) of yours left untouched (never overwritten)" % kept)
    for f in wfailed[:10]:
        say("    ! " + f)
    w = workspace.weeks()
    if w:
        say("")
        say("Newest week: %s   ->   cs1002 code %s   then   cs1002 test %s" % (w[-1], w[-1], w[-1]))
    return 1 if failed else 0


def run_stacscheck(test_dir, run_dir, extra=()):
    os.makedirs(run_dir, exist_ok=True)
    cmd = [config.PY, RUNNER] + list(extra) + [test_dir]
    return subprocess.call(cmd, cwd=run_dir)


def cmd_test(args):
    t = resolve(args.what)
    if not t.tests:
        raise SystemExit("No stacscheck tests found for %s." % t.label)
    tests = t.tests
    if args.part:
        tests = [(os.path.join(d, args.part), s) for d, s in tests if os.path.isdir(os.path.join(d, args.part))]
        if not tests:
            raise SystemExit("No test part '%s' in %s" % (args.part, t.label))
    if not os.path.isdir(t.run_dir):
        raise SystemExit("%s doesn't exist yet - run:  cs1002 sync" % t.run_dir)
    _mock_time_left(t.run_dir)
    rc = 0
    for tdir, srcdir in tests:
        head("%s  -  stacscheck %s" % (t.label, os.path.relpath(tdir, config.HOME) if tdir.startswith(config.HOME) else tdir))
        say("(code folder: %s)" % os.path.join(t.run_dir, srcdir or ""))
        extra = ["-v"] if args.verbose else []
        if args.html:
            extra += ["--html", os.path.join(t.run_dir, "stacscheck-report.html")]
        rc |= run_stacscheck(tdir, t.run_dir, extra)
        if args.html:
            open_file(os.path.join(t.run_dir, "stacscheck-report.html"))
    _mock_time_left(t.run_dir)
    return rc


def cmd_stacscheck(args):
    return subprocess.call([config.PY, RUNNER] + args.rest)


def cmd_code(args):
    t = resolve(args.what)
    folder = t.code_dir if os.path.isdir(t.code_dir) else t.run_dir
    open_vscode(folder, main_java(folder))
    return 0


def cmd_zip(args):
    t = resolve(args.what)
    folders = [os.path.join(t.run_dir, s) for _, s in t.tests if s] or [t.code_dir]
    for folder in dict.fromkeys(folders):
        if not os.path.isdir(folder):
            say("  %s doesn't exist" % folder)
            continue
        out = os.path.join(t.run_dir, os.path.basename(folder) + ".zip")
        n = workspace.zip_for_mms(folder, out)
        say("  %s  (%d files) - upload this to MMS" % (out, n))
    return 0


# ---------------------------------------------------------------------- mock
def _mock_time_left(run_dir):
    info = workspace.mock_info(run_dir)
    if not info:
        return
    left = info["end"] - time.time()
    if left > 0:
        say("Mock test: %d min left (ends %s)" % (left // 60 + 1, time.strftime("%H:%M", time.localtime(info["end"]))))
    else:
        say("Mock test: TIME'S UP (ended %s) - what passes now is your score" %
            time.strftime("%H:%M", time.localtime(info["end"])))


def cmd_mock(args):
    if args.action == "test":
        args.what, args.part, args.verbose, args.html = "mock", None, False, False
        return cmd_test(args)
    zips = workspace.mock_zips()
    if not zips:
        raise SystemExit("No mock test on this computer - run:  cs1002 sync   (it's in StudRes Coursework/MockTest1)")
    if args.action == "resume":
        attempt = workspace.latest_mock()
        if not attempt or not workspace.mock_info(attempt):
            raise SystemExit("No mock test to resume - run:  cs1002 mock")
        info = workspace.mock_info(attempt)
    else:
        minutes = args.minutes
        if args.extra_time:
            minutes = -(-minutes * (100 + args.extra_time) // 100)     # round up: 50 min + 25 % = 63
        attempt = workspace.new_mock_attempt(zips[-1])
        info = {"start": time.time(), "end": time.time() + minutes * 60, "minutes": minutes,
                "zip": os.path.basename(zips[-1])}
        workspace.save_mock_info(attempt, info)
        head("Mock test - %s" % os.path.basename(attempt))
        say("  fresh copy in %s" % attempt)
        say("  %d minutes: ends at %s" % (minutes, time.strftime("%H:%M", time.localtime(info["end"]))))
        say("  Exam conditions: no AI extensions, only StudRes material and your own exercises.")
        specs = [os.path.join(r, f) for r, _, fs in os.walk(attempt) for f in fs
                 if f.lower().endswith((".html", ".pdf")) and "Tests" not in r.split(os.sep)]
        tests = workspace.top_tests(attempt)
        code_dir = os.path.join(attempt, tests[0][1]) if tests else attempt
        if not args.no_open:
            for s in specs[:1]:
                open_file(s)
            open_vscode(code_dir, main_java(code_dir))
        say("")
        say("  Test as you go (in another terminal, or VS Code's):   cs1002 test mock")
    say("")
    say("Timer running - Ctrl+C hides it (the test keeps its end time; `cs1002 mock resume` shows it again).")
    try:
        warned = set()
        while True:
            left = info["end"] - time.time()
            if left <= 0:
                sys.stdout.write("\r  TIME'S UP. Stop typing - run  cs1002 test mock  to see your score.      \n\a")
                sys.stdout.flush()
                return 0
            for mark in (10, 5, 1):
                if left <= mark * 60 and mark not in warned:
                    warned.add(mark)
                    sys.stdout.write("\a")
            sys.stdout.write("\r  time left  %02d:%02d   (ends %s)  " % (left // 60, left % 60,
                                                                      time.strftime("%H:%M", time.localtime(info["end"]))))
            sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        say("")
        return 0


def cmd_status(args):
    head("cs1002_home")
    say("  your work:      %s" % config.HOME)
    say("  StudRes copy:   %s" % config.MIRROR)
    m = config.load_manifest()
    say("  files synced:   %d" % len(m))
    w = workspace.weeks()
    say("  exercise weeks: %s" % (", ".join(w) if w else "none yet (cs1002 sync)"))
    a = workspace.assignments()
    say("  assignments:    %s" % (", ".join(a) if a else "none yet"))
    mt = workspace.latest_mock()
    say("  mock attempts:  %s" % (os.path.basename(mt) if mt else "none"))
    if args.online:
        import studres
        with studres.Browser(headless=True) as b:
            say("  StudRes:        %s" % ("signed in" if b.signed_in() else "NOT signed in (cs1002 login)"))
    if w:
        t = resolve(w[-1])
        say("")
        say("  newest week %s:" % w[-1])
        say("    write code in  %s" % t.code_dir)
        for tdir, _ in t.tests:
            say("    test with      cs1002 test %s     (= stacscheck %s)" % (w[-1], tdir))
    return 0


def cmd_update(args):
    if os.path.isdir(os.path.join(HERE, ".git")) and shutil.which("git"):
        return subprocess.call(["git", "-C", HERE, "pull", "--ff-only"])
    say("Not a git clone - download the newest zip from https://github.com/JackRubiralta/cs1002_home")
    return 1


# ---------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(prog="cs1002", description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="\n".join(__doc__.split("\n")[2:]))
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("setup", help="check Java, Git Bash, VS Code and the browser")
    s.add_argument("--install", action="store_true", help="install what's missing (Windows: winget)")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("login", help="sign in to StudRes")
    s.add_argument("--window", action="store_true", help="always open the browser window")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("sync", help="download new StudRes files + add new starter code")
    s.add_argument("folders", nargs="*", help="StudRes folders (default: Exercises Coursework Tutorials Examples Lectures)")
    s.add_argument("--max-mb", type=int, default=60, help="skip files bigger than this (default 60)")
    s.add_argument("--all", action="store_true", help="also slide decks (.pptx) and videos")
    s.add_argument("--dry-run", action="store_true", help="only show what would be downloaded")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("test", help="run the stacscheck tests")
    s.add_argument("what", nargs="?", help="W08 / 8 / a2 / mock / a Tests folder (default: where you are)")
    s.add_argument("--part", help="one part only, e.g. CheckStyle or Mug")
    s.add_argument("-v", "--verbose", action="store_true")
    s.add_argument("--html", action="store_true", help="also write and open an HTML report")
    s.set_defaults(fn=cmd_test)

    s = sub.add_parser("mock", help="timed mock test")
    s.add_argument("action", nargs="?", choices=["start", "resume", "test"], default="start")
    s.add_argument("--minutes", type=int, default=50, help="length (default 50, like the real test)")
    s.add_argument("--extra-time", type=int, default=0, metavar="PERCENT",
                   help="add extra time, e.g. 25 for 15 min per hour")
    s.add_argument("--no-open", action="store_true", help="don't open the spec and VS Code")
    s.set_defaults(fn=cmd_mock)

    s = sub.add_parser("code", help="open VS Code on a week / assignment / mock")
    s.add_argument("what", nargs="?")
    s.set_defaults(fn=cmd_code)

    s = sub.add_parser("zip", help="zip your code for MMS")
    s.add_argument("what", nargs="?")
    s.set_defaults(fn=cmd_zip)

    s = sub.add_parser("status", help="what's on this computer")
    s.add_argument("--online", action="store_true", help="also check the StudRes sign-in")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("stacscheck", help="run stacscheck directly", add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_stacscheck)

    s = sub.add_parser("update", help="get the newest version (git pull)")
    s.set_defaults(fn=cmd_update)

    args = p.parse_args(argv)
    if not getattr(args, "fn", None):
        p.print_help()
        return 0
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        say("")
        return 130


if __name__ == "__main__":
    sys.exit(main())
