# cs1002_home

Do your CS1002 exercises, assignments and the mock test **on your own computer**
(Windows or Linux) with the same tests the lab uses.

| Command | What it does |
|---|---|
| `cs1002 login` | Signs in to StudRes once. A browser window opens and does the Microsoft sign-in for you (email and password from `.env` if you put them there). You only type the Authenticator number it shows. "Stay signed in" is ticked, so later syncs don't open a window |
| `cs1002 sync` | Downloads everything new from StudRes CS1002 (Exercises, Coursework, Tutorials, Examples, Lecture PDFs), then adds new starter code and sheets to your folders. **It never replaces a file you already have**, so your answers are safe |
| `cs1002 test` | Runs the School's `stacscheck` on the folder you're in, or `cs1002 test W08`, `cs1002 test 8`, `cs1002 test a2`, `cs1002 test mock`. `--part CheckStyle` runs one part. `--html` also writes a report |
| `cs1002 mock` | Starts the mock test: a fresh copy in `MockTest/attempt-N`, the spec and VS Code open, and a 50-minute countdown. `--extra-time 25` adds 15 min per hour. `cs1002 test mock` checks your score while you work |
| `cs1002 code W08` | Opens VS Code on that week's code folder with the main `.java` file |
| `cs1002 zip W08` | Makes `W08Exercises.zip` (without `.class` files) to upload to MMS |
| `cs1002 status` | What's on this computer, the newest week, and where to write code. `--online` also checks the sign-in |
| `cs1002 setup` | Checks Java, Git Bash (Windows), VS Code and the browser. On Windows `--install` installs whatever is missing with winget |
| `cs1002 update` | Gets the newest version of this program |

## Install

You need **Python 3.9+**, a **Java JDK** (21 is what the lab PCs use) and, on Windows,
**Git for Windows**, because the tests are bash scripts and Git Bash runs them.
`cs1002 setup` tells you what's missing.

**Windows** (PowerShell):

```powershell
winget install --id Git.Git -e
winget install --id EclipseAdoptium.Temurin.21.JDK -e
# open a NEW PowerShell, then:
cd $HOME
git clone https://github.com/JackRubiralta/cs1002_home
cd cs1002_home
powershell -ExecutionPolicy Bypass -File install.ps1
```

Windows signs in with Microsoft Edge, which every Windows PC already has, so there's no browser to download.

**Linux / macOS:**

```bash
git clone https://github.com/JackRubiralta/cs1002_home ~/cs1002_home
~/cs1002_home/install.sh       # venv + Playwright Chromium + `cs1002` in ~/.local/bin
```

**Then, on either system:**

```bash
cs1002 login
cs1002 sync
cs1002 status
```

## Where things go

Everything lives in `~/CS1002` (on Windows, `C:\Users\<you>\CS1002`). Set `CS1002_HOME` to use a different folder.

```
CS1002/
  studres/CS1002/...            a copy of StudRes (like /cs/studres on a lab PC) - tests live here
  Exercises/W08/
      W08Exercises.html         the sheet
      W08Exercises/             your code: write your answers here
  Coursework/Assignment2/       your assignment work (spec + the folder the tests look for)
  MockTest/attempt-1/project/   a fresh mock test each time you run `cs1002 mock`
```

`cs1002 test W08` is the same as the lab's
`cd W08 && stacscheck /cs/studres/CS1002/Exercises/W08/Tests`, only with your local copy:
`cs1002 stacscheck ~/CS1002/studres/CS1002/Exercises/W08/Tests` works too.

## How it works

* **Sign-in.** StudRes sits behind the University's Microsoft sign-in, so plain downloads get nothing. The program keeps its own browser profile in `~/.cs1002_home/browser` (Playwright: Edge on Windows, Chromium elsewhere). It drives the login pages with the same steps `cs_lab_start` uses on the lab PCs: email, password, "Stay signed in? → Yes", choosing Authenticator and printing the number. Files are then fetched with that profile's cookies, without opening a page. When the StudRes session runs out, it first tries to sign in silently with the remembered Microsoft sign-in, and opens a window only if Microsoft asks for you.
* **Sync.** It reads StudRes' folder listings and downloads only files whose StudRes time changed since the last sync (`~/.cs1002_home/manifest.json`). The School edits tests after release, so `sync` lists files that changed. Slide decks (`.pptx`, 100–300 MB) and videos are skipped unless you pass `--all`. It never deletes anything.
* **Tests on Windows.** `vendor/stacscheck.py` is the School's stacscheck 3.3.0 (MIT licence, unchanged). `run_stacscheck.py` runs it as is on Linux. On Windows it makes three changes: it runs the test scripts with Git Bash, uses `taskkill` for timeouts, and passes `TESTDIR` in `/c/...` form. The `shims/java` and `shims/javac` wrappers turn the Linux-style `CLASSPATH=.:${TESTDIR}/../libs/*` the tests export into Windows form. Output comparison already ignores `\r\n`. GitHub Actions runs the full test suite on Windows and Linux on every push.

## Privacy

`.env` (optional `EMAIL=` / `PASSWORD=`) is never committed. On Linux it is kept `chmod 600`, and the password is only typed into Microsoft's password box. Leave `PASSWORD` empty to type it yourself in the window. No course material is stored in this repository; it is downloaded to your computer with your own sign-in.

## Rules

The mock test and the class tests forbid AI extensions in the test environment. The assignments allow AI only where your support plan permits it, and you have to document it. This program only downloads material and runs the School's own tests. The real class tests still happen in the lab with `/cs/studres/ct/class-test`.
