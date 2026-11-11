"""`cs1002 setup`: check (and on Windows, optionally install) what the program needs."""

import os
import re
import shutil
import subprocess
import sys

import config
from config import say

WINGET = {
    "java": ("EclipseAdoptium.Temurin.21.JDK", "Java 21 JDK (the version the lab PCs use)"),
    "git": ("Git.Git", "Git for Windows (gives Git Bash, which runs the test scripts)"),
    "code": ("Microsoft.VisualStudioCode", "VS Code"),
}


def _out(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def java_version():
    out = _out(["java", "-version"])
    if not out:
        return None
    m = re.search(r'version "(\d+)', out)
    return int(m.group(1)) if m else None


def linux_install_hint(what):
    pm = {"pacman": {"java": "sudo pacman -S jdk21-openjdk", "code": "yay -S visual-studio-code-bin"},
          "apt": {"java": "sudo apt install openjdk-21-jdk", "code": "sudo snap install code --classic"},
          "dnf": {"java": "sudo dnf install java-21-openjdk-devel", "code": "see code.visualstudio.com/docs/setup/linux"}}
    for name, cmds in pm.items():
        if shutil.which(name):
            return cmds.get(what, "")
    return {"java": "install a Java 21 JDK", "code": "install VS Code from code.visualstudio.com"}[what]


def run(install=False):
    say("")
    say("== Checking this computer " + "=" * 36)
    problems = []

    v = sys.version_info
    say("  Python      %d.%d  %s" % (v.major, v.minor, "ok" if v >= (3, 9) else "TOO OLD (need 3.9+)"))
    if v < (3, 9):
        problems.append("python")

    jv = java_version()
    javac = shutil.which("javac")
    if jv and javac:
        say("  Java        %d  %s" % (jv, "ok" if jv >= 17 else "old - the lab uses 21"))
    else:
        say("  Java        MISSING (need a JDK, not just a JRE: java + javac)")
        problems.append("java")

    if config.IS_WINDOWS:
        sys.path.insert(0, config.HERE)
        from run_stacscheck import find_git_bash
        gb = find_git_bash()
        say("  Git Bash    %s" % (gb or "MISSING - the test scripts are bash"))
        if not gb:
            problems.append("git")
    else:
        say("  bash        %s" % (shutil.which("bash") or "MISSING"))

    import cs1002
    code = cs1002.find_code()
    say("  VS Code     %s" % (code[0] if code else "not found (optional, but `cs1002 code` uses it)"))
    if not code:
        problems.append("code")
    else:
        exts = _out(code + ["--list-extensions"]) or ""
        if "vscjava.vscode-java-pack" not in exts:
            say("              tip: install the 'Extension Pack for Java':  code --install-extension vscjava.vscode-java-pack")

    try:
        import playwright  # noqa: F401
        say("  Playwright  ok")
    except ImportError:
        say("  Playwright  MISSING - run the installer again (./install.sh or install.ps1)")
        problems.append("playwright")
    else:
        if not config.IS_WINDOWS:          # Windows uses Edge, which is always there
            r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                               capture_output=True, text=True)
            say("  Browser     %s" % ("ok (Playwright Chromium)" if r.returncode == 0 else
                                      "couldn't install: " + (r.stderr or r.stdout).strip()[:200]))
        else:
            say("  Browser     Microsoft Edge (built in)")

    say("  Your work   %s" % config.HOME)
    if not problems:
        say("")
        say("All good. Next:  cs1002 login   then   cs1002 sync")
        return 0

    say("")
    if config.IS_WINDOWS:
        todo = [k for k in problems if k in WINGET]
        if install and todo and shutil.which("winget"):
            for k in todo:
                pkg, what = WINGET[k]
                say("Installing %s ..." % what)
                subprocess.call(["winget", "install", "--id", pkg, "-e", "--accept-package-agreements",
                                 "--accept-source-agreements"])
            say("")
            say("Done. CLOSE this terminal and open a new one (so it sees the new programs), then: cs1002 setup")
            return 0
        for k in todo:
            pkg, what = WINGET[k]
            say("  %-10s winget install --id %s -e      (%s)" % (k, pkg, what))
        if todo:
            say("Or let me do it:  cs1002 setup --install")
    else:
        for k in problems:
            if k in ("java", "code"):
                say("  %-10s %s" % (k, linux_install_hint(k)))
    return 1
