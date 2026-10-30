# Start the Krishna AI Assistant web app.
# Default URL: http://127.0.0.1:8123 (port 8000 stays free for llama-ui)

param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $workspace

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
if (-not $env:KRSNA_PORT) {
    $env:KRSNA_PORT = "8123"
}

# Load local secrets from .env (never committed) so the app just works.
$envFile = Join-Path $workspace ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $k, $v = $line.Split("=", 2)
            $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
            if ($k -and -not (Test-Path "env:$k")) {
                Set-Item -Path "env:$k" -Value $v
            }
        }
    }
} else {
    Write-Host "WARNING: .env not found - copy .env.example to .env and set KRSNA_LLM_API_KEY." -ForegroundColor Red
}

Write-Host ""
Write-Host "Starting Krishna AI Assistant..." -ForegroundColor Cyan
Write-Host "Open: http://127.0.0.1:$($env:KRSNA_PORT)" -ForegroundColor Yellow

if ($Background) {
    Start-Process -FilePath "python.exe" -ArgumentList "-m krsna_ai.app" -WorkingDirectory $workspace -WindowStyle Hidden
    Write-Host "Krishna AI Assistant started in background." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
    Write-Host ""
    python -m krsna_ai.app
}
