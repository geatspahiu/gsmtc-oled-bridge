$ErrorActionPreference = "Stop"

$mediaDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$steelClockDir = if ($env:STEELCLOCK_DIR) {
  $env:STEELCLOCK_DIR
} else {
  Get-ChildItem -Path (Join-Path $env:USERPROFILE "Documents") -Directory -Filter "steelclock-*-windows-amd64" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
}

if (-not $steelClockDir) {
  throw "SteelClock was not found. Set STEELCLOCK_DIR to the folder that contains steelclock.exe."
}

$steelClockExe = Join-Path $steelClockDir "steelclock.exe"
$profile = Join-Path $steelClockDir "profiles\gsm_tc_media_server.json"
$sourceProfile = Join-Path $mediaDir "steelclock_gsm_tc_media_server.json"

if (-not (Test-Path $steelClockExe)) {
  throw "steelclock.exe was not found in $steelClockDir"
}

Copy-Item -LiteralPath $sourceProfile -Destination $profile -Force

Start-Process `
  -FilePath "python" `
  -ArgumentList @(".\media_status.py", "--mode", "http", "--interval", "1", "--bar-width", "12", "--port", "8765") `
  -WorkingDirectory $mediaDir `
  -WindowStyle Hidden

if (-not (Get-Process -Name "steelclock" -ErrorAction SilentlyContinue)) {
  Start-Process `
    -FilePath $steelClockExe `
    -ArgumentList @("-config", $profile) `
    -WorkingDirectory $steelClockDir `
    -WindowStyle Hidden
}
