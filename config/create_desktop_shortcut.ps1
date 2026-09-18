# Create a Desktop shortcut for E.V.
# Works from wherever the project is checked out: the paths are derived from
# this script's own location, so nothing here is machine-specific.

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot      # ...\E.V\config -> ...\E.V
if (-not (Test-Path (Join-Path $projectRoot 'main.py'))) {
    throw "main.py was not found in $projectRoot. Run this script from the project's config folder."
}

$python = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $python)) {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path $python)) {
    throw "No virtual environment found at $projectRoot\.venv. Create it first: python -m venv .venv"
}

$mainScript = Join-Path $projectRoot 'main.py'
$icon       = Join-Path $projectRoot 'assets\ev_logo.ico'
$desktop    = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'E.V..lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $python
$shortcut.Arguments        = '"{0}"' -f $mainScript
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle      = 7
$shortcut.Description      = 'E.V. — Personal AI Assistant'
if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
