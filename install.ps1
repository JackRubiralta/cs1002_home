# Windows installer: a private Python environment, Playwright (uses Microsoft Edge,
# so no browser download), and a `cs1002` command on your PATH.
# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = $null
foreach ($c in @("py", "python", "python3")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    $v = & $c -c "import sys; print(sys.version_info >= (3, 9))" 2>$null
    if ($v -eq "True") { $py = $c; break }
  }
}
if (-not $py) {
  Write-Host "Python 3.9+ is needed. Installing it with winget ..."
  winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
  Write-Host "Close this window, open a new PowerShell and run install.ps1 again."
  exit 1
}

Write-Host "Setting up Python environment in $Here\.venv ..."
& $py -m venv "$Here\.venv"
& "$Here\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$Here\.venv\Scripts\python.exe" -m pip install --quiet -r "$Here\requirements.txt"

$bin = Join-Path $env:USERPROFILE ".cs1002_home\bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
"@echo off`r`n`"$Here\.venv\Scripts\python.exe`" `"$Here\cs1002.py`" %*" | Set-Content -Encoding ASCII (Join-Path $bin "cs1002.cmd")

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if (-not ($userPath.Split(";") -contains $bin)) {
  [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $bin).TrimStart(";"), "User")
  Write-Host "Added $bin to your PATH (new terminals will have the cs1002 command)."
}
$env:Path = "$env:Path;$bin"
& (Join-Path $bin "cs1002.cmd") setup
