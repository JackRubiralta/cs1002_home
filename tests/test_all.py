"""Offline tests: run with  python -m unittest discover -s tests -v

They build a fake StudRes copy (no course material is stored in this repo) with
tests in the same shapes the School uses - build-all.sh, prog-run.sh + .in/.out,
test-*.sh that export a Linux CLASSPATH with ${TESTDIR}/../libs/*, and
`java -jar "$TESTDIR/../libs/x.jar"` like the CheckStyle test - then run the
real `cs1002 test` / stacscheck on them. GitHub Actions runs this on Windows
(Git Bash) and Linux.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HAVE_JAVA = bool(shutil.which("javac") and shutil.which("jar"))

LISTING = """<table>
<tr><td valign="top"><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/CS1002/Coursework/">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/compressed.gif" alt="[   ]"></td><td><a href="CS1002%20MockTest.zip">CS1002 MockTest.zip</a></td><td align="right">2026-10-06 12:16  </td><td align="right">4.7M</td><td>&nbsp;</td></tr>
<tr><td valign="top"><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="W01%20-%20Intro%20&amp;%20Objects/">W01 - Intro &amp; Objects/</a></td><td align="right">2026-10-06 16:43  </td><td align="right">  - </td><td>&nbsp;</td></tr>
</table>"""

HELLO_OK = """\
import java.util.Scanner;

public class Hello {
    public static String greet(String name) {
        return "Hello, " + name + "!";
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        String name = in.nextLine();
        System.out.println(greet(name));
        System.out.println("Bye");
    }
}
"""
HELLO_STARTER = HELLO_OK.replace('"Hello, " + name + "!"', '""')

TESTER = """\
public class FixtureTester {
    public static void main(String[] args) throws Exception {
        if (args.length > 0 && args[0].equals("selftest")) {
            System.out.println("ok");
            return;
        }
        Class<?> c = Class.forName("Hello");
        Object r = c.getMethod("greet", String.class).invoke(null, "Ann");
        if (!"Hello, Ann!".equals(r)) {
            System.out.println("greet(\\"Ann\\") gave " + r);
            System.exit(1);
        }
        System.out.println("ok");
    }
}
"""


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(textwrap.dedent(text))
    if mode:
        os.chmod(path, mode)


def make_fake_week(mirror, week="W01"):
    """A StudRes-shaped exercise week in the mirror."""
    wk = os.path.join(mirror, "Exercises", week)
    src = week + "Exercises"
    write(os.path.join(wk, src + ".html"), "<html><body>sheet</body></html>")
    write(os.path.join(wk, src, "Hello.java"), HELLO_STARTER)
    t = os.path.join(wk, "Tests")
    write(os.path.join(t, "practical.config"), "[info]\npractical = %s Exercises\ncourse = CS1002\nsrcdir = %s\n" % (week, src))
    write(os.path.join(t, "build-all.sh"), "#!/bin/bash\njavac *.java\n", 0o755)
    write(os.path.join(t, "Main", "prog-run.sh"), "#!/bin/bash\njava Hello\n", 0o755)
    write(os.path.join(t, "Main", "ann.in"), "Ann\n")
    write(os.path.join(t, "Main", "ann.out"), "Hello, Ann!\nBye\n")
    write(os.path.join(t, "Tester", "test-classpath.sh"),
          "#!/bin/bash\nexport CLASSPATH=.:..:${TESTDIR}/..:${TESTDIR}/../libs/*\njava FixtureTester\n", 0o755)
    write(os.path.join(t, "Jar", "test-jar.sh"),
          "#!/bin/bash\nresult=$(java -jar \"$TESTDIR/../libs/fixture.jar\" selftest)\n"
          "echo \"$result\"\n[ \"$result\" = ok ]\n", 0o755)
    # libs/fixture.jar built from FixtureTester.java
    build = tempfile.mkdtemp()
    write(os.path.join(build, "FixtureTester.java"), TESTER)
    subprocess.check_call(["javac", "FixtureTester.java"], cwd=build)
    os.makedirs(os.path.join(t, "libs"), exist_ok=True)
    subprocess.check_call(["jar", "cfe", os.path.join(t, "libs", "fixture.jar"), "FixtureTester", "FixtureTester.class"], cwd=build)
    shutil.rmtree(build, ignore_errors=True)
    return wk


class Env:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="cs1002test")
        self.home = os.path.join(self.dir, "CS1002")
        self.mirror = os.path.join(self.home, "studres", "CS1002")
        self.env = dict(os.environ, CS1002_HOME=self.home, CS1002_STATE=os.path.join(self.dir, "state"),
                        PYTHONIOENCODING="utf-8")

    def cs1002(self, *args, cwd=None):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "cs1002.py")] + list(args), env=self.env,
                           cwd=cwd or self.dir, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=300)
        return r.returncode, r.stdout + r.stderr

    def workspace(self):
        code = ("import sys; sys.path.insert(0, %r); import workspace, json;"
                "print(json.dumps(workspace.update_workspace()))" % ROOT)
        out = subprocess.run([sys.executable, "-c", code], env=self.env, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        return out.stdout

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class ListingTest(unittest.TestCase):
    def test_parse(self):
        import studres
        rows = studres.parse_listing(LISTING)
        self.assertEqual(rows, [("CS1002 MockTest.zip", False, "2026-10-06 12:16", "4.7M"),
                                ("W01 - Intro & Objects", True, "2026-10-06 16:43", "-")])
        self.assertEqual(studres.size_bytes("4.7M"), int(4.7 * 1024 ** 2))
        self.assertTrue(studres.SKIP_RE.search("Exercises/W01/a.java:Zone.Identifier"))


class NamesTest(unittest.TestCase):
    def test_names(self):
        import cs1002
        self.assertEqual(cs1002._week_name("8"), "W08")
        self.assertEqual(cs1002._week_name("w8"), "W08")
        self.assertEqual(cs1002._week_name("W08"), "W08")
        self.assertEqual(cs1002._week_name("week 10"), "W10")
        self.assertEqual(cs1002._assignment_name("a2"), "Assignment2")
        self.assertEqual(cs1002._assignment_name("assignment 1"), "Assignment1")
        self.assertIsNone(cs1002._week_name("mock"))

    def test_posix_path(self):
        import run_stacscheck
        if os.name == "nt":
            self.assertEqual(run_stacscheck.to_posix(r"C:\Users\jack\x"), "/c/Users/jack/x")


@unittest.skipUnless(HAVE_JAVA, "needs a JDK")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        make_fake_week(self.e.mirror)

    def tearDown(self):
        self.e.close()

    def test_workspace_never_overwrites(self):
        self.e.workspace()
        mine = os.path.join(self.e.home, "Exercises", "W01", "W01Exercises", "Hello.java")
        self.assertTrue(os.path.isfile(mine))
        self.assertTrue(os.path.isfile(os.path.join(self.e.home, "Exercises", "W01", "W01Exercises.html")))
        self.assertFalse(os.path.exists(os.path.join(self.e.home, "Exercises", "W01", "Tests")))
        with open(mine, "w") as f:
            f.write("// my answer\n")
        self.e.workspace()
        with open(mine) as f:
            self.assertEqual(f.read(), "// my answer\n")

    def test_stacscheck_fail_then_pass(self):
        self.e.workspace()
        rc, out = self.e.cs1002("test", "W01")
        self.assertIn("Testing CS1002 W01 Exercises", out)
        self.assertIn("2 out of 4 tests passed", out, out)        # build + the jar self-test pass
        mine = os.path.join(self.e.home, "Exercises", "W01", "W01Exercises", "Hello.java")
        with open(mine, "w", newline="\n") as f:
            f.write(HELLO_OK)
        rc, out = self.e.cs1002("test", "1")
        self.assertIn("4 out of 4 tests passed", out, out)

    def test_from_inside_folder(self):
        self.e.workspace()
        mine = os.path.join(self.e.home, "Exercises", "W01", "W01Exercises")
        with open(os.path.join(mine, "Hello.java"), "w", newline="\n") as f:
            f.write(HELLO_OK)
        rc, out = self.e.cs1002("test", cwd=mine)
        self.assertIn("4 out of 4 tests passed", out, out)
        rc, out = self.e.cs1002("test", "W01", "--part", "Main")
        self.assertIn("2 out of 2 tests passed", out, out)        # build + the .in/.out test

    def test_zip(self):
        self.e.workspace()
        self.e.cs1002("test", "W01")          # leaves .class files behind
        rc, out = self.e.cs1002("zip", "W01")
        z = os.path.join(self.e.home, "Exercises", "W01", "W01Exercises.zip")
        names = zipfile.ZipFile(z).namelist()
        self.assertIn("W01Exercises/Hello.java", [n.replace("\\", "/") for n in names])
        self.assertFalse([n for n in names if n.endswith(".class")])

    def test_mock(self):
        # a mock-test zip shaped like StudRes' (project/ with Tests inside, srcdir = project)
        wk = os.path.join(self.e.mirror, "Exercises", "W01")
        mdir = os.path.join(self.e.mirror, "Coursework", "MockTest1")
        os.makedirs(mdir)
        with zipfile.ZipFile(os.path.join(mdir, "CS1002 MockTest.zip"), "w") as z:
            z.writestr("project/MockTestSpecification.html", "<html>spec</html>")
            z.writestr("project/Hello.java", HELLO_OK)
            for root, _, files in os.walk(os.path.join(wk, "Tests")):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, wk).replace(os.sep, "/")
                    with open(full, "rb") as fh:
                        data = fh.read()
                    if f == "practical.config":
                        data = b"[info]\npractical = Mock Test\ncourse = CS1002\nsrcdir = project\n"
                    z.writestr("project/" + rel, data)
        rc, out = self.e.cs1002("mock", "--no-open", "--minutes", "0")
        self.assertIn("attempt-1", out, out)
        self.assertIn("TIME'S UP", out)
        rc, out = self.e.cs1002("test", "mock")
        self.assertIn("4 out of 4 tests passed", out, out)
        rc, out = self.e.cs1002("mock", "--no-open", "--minutes", "0")
        self.assertIn("attempt-2", out)


if __name__ == "__main__":
    unittest.main()
