<#
.SYNOPSIS
  Launch OpenDesign Studio with MetaHackathon workspace and LiteLLM Gateway wiring.
#>
[CmdletBinding()]
param()

$OD_DIR = "U:\AI\open-design"
$BAT_FILE = Join-Path $OD_DIR "launch_opendesign_metahackathon.bat"

if (-not (Test-Path $BAT_FILE)) {
    Write-Error "Launcher script not found at $BAT_FILE"
    exit 1
}

Write-Host "Starting OpenDesign Studio for MetaHackathon..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$BAT_FILE`"" -WorkingDirectory $OD_DIR
Write-Host "OpenDesign launched in a new window." -ForegroundColor Green
Write-Host "Web UI will be live at: http://127.0.0.1:62402/" -ForegroundColor Green
