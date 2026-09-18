# Create a desktop shortcut for E.V. on the current user's desktop.
# Run it from the project folder:  powershell -ExecutionPolicy Bypass -File config\create_desktop_shortcut.ps1
# Every path is derived from this script's location, so it works wherever the
# project is installed. No machine-specific paths are stored in the repository.

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    $Python = 'python'   # fall back to whatever Python is on PATH
}

$Main = Join-Path $ProjectRoot 'main.py'
if (-not (Test-Path $Main)) {
    throw "main.py was not found in $ProjectRoot. Run this script from inside the E.V. project folder."
}

$Icon = Join-Path $ProjectRoot 'assets\ev_logo.ico'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'E.V..lnk'

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Python
$Shortcut.Arguments = '"' + $Main + '"'
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.WindowStyle = 7          # start minimized to the tray
$Shortcut.Description = 'Launch E.V. — personal AI assistant'
if (Test-Path $Icon) {
    $Shortcut.IconLocation = "$Icon,0"
}
$Shortcut.Save()

Write-Host "Desktop shortcut created: $ShortcutPath"
