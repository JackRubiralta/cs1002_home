#!/usr/bin/env python3
"""Run the School's stacscheck (vendor/stacscheck.py, unchanged) on Linux, macOS or Windows.

Usage: python run_stacscheck.py <stacscheck args...>   e.g.  ... ~/CS1002/studres/CS1002/Exercises/W08/Tests

On Linux/macOS this is exactly stacscheck. On Windows the tests are bash scripts
written for the lab's Linux, so we run them with Git Bash and patch the three
places stacscheck assumes Linux:
  * process groups (os.setsid / os.killpg) -> taskkill /T on timeout
  * "bash" -> Git Bash (not WSL's bash.exe in System32)
  * TESTDIR/SCRATCHDIR are given to the scripts as /c/Users/... paths, and the
    shims/java + shims/javac wrappers turn the Linux-style CLASSPATH the tests
    export (.:..:${TESTDIR}/../libs/*) into Windows form (cygpath -wp)
Output comparison already ignores trailing whitespace, so Windows' \\r\\n is fine.
"""

import os
import runpy
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STACSCHECK = os.path.join(HERE, "vendor", "stacscheck.py")
SHIMS = os.path.join(HERE, "shims")


def find_git_bash():
    """Path to Git for Windows' bash.exe, or None."""
    cands = []
    git = shutil.which("git")
    if git:   # ...\Git\cmd\git.exe or ...\Git\bin\git.exe or ...\Git\mingw64\bin\git.exe
        g = os.path.dirname(os.path.dirname(os.path.realpath(git)))
        cands += [os.path.join(g, "bin", "bash.exe"), os.path.join(os.path.dirname(g), "bin", "bash.exe")]
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands += [os.path.join(base, "Git", "bin", "bash.exe"),
                      os.path.join(base, "Programs", "Git", "bin", "bash.exe")]
    b = shutil.which("bash")
    if b and "system32" not in b.lower() and "windowsapps" not in b.lower():
        cands.append(b)
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def to_posix(path):
    """C:\\Users\\jack\\x -> /c/Users/jack/x (what Git Bash expects)."""
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p[0].lower() + p[2:]
    return p


def patch_for_windows():
    bash = find_git_bash()
    if not bash:
        sys.exit("stacscheck needs Git Bash on Windows (the tests are bash scripts).\n"
                 "Install Git for Windows:  winget install --id Git.Git -e   then open a new terminal.")
    git_root = os.path.dirname(os.path.dirname(bash))
    extra_path = [SHIMS, os.path.join(git_root, "usr", "bin"), os.path.join(git_root, "bin")]
    real_popen = subprocess.Popen

    class WinPopen(real_popen):
        def __init__(self, args, *a, **kw):
            kw.pop("preexec_fn", None)                     # not supported on Windows
            if isinstance(args, (list, tuple)) and args and args[0] == "bash":
                args = [bash] + list(args[1:])
            env = kw.get("env")
            if env is not None:
                env = dict(env)
                for k in ("TESTDIR", "SCRATCHDIR"):
                    if env.get(k):
                        env[k] = to_posix(env[k])
                env["PATH"] = os.pathsep.join(extra_path + [env.get("PATH", "")])
                env["CS1002_SHIMS"] = to_posix(SHIMS)
                kw["env"] = env
            kw.setdefault("creationflags", subprocess.CREATE_NEW_PROCESS_GROUP)
            super().__init__(args, *a, **kw)

    subprocess.Popen = WinPopen
    os.setsid = lambda: None
    os.getpgid = lambda pid: pid
    os.killpg = lambda pid, sig: subprocess.call(["taskkill", "/F", "/T", "/PID", str(pid)],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if os.name == "nt":
        patch_for_windows()
        try:   # print the School's coloured/UTF-8 output without crashing old consoles
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.argv = ["stacscheck"] + sys.argv[1:]
    runpy.run_path(STACSCHECK, run_name="__main__")


if __name__ == "__main__":
    main()
