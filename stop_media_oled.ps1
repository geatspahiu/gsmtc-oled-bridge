$ErrorActionPreference = "SilentlyContinue"

Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like "*media_status.py*" -or
    ($_.Name -eq "steelclock.exe" -and (
      $_.CommandLine -like "*gsm_tc_media_clipboard.json*" -or
      $_.CommandLine -like "*gsm_tc_media_server.json*"
    ))
  } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
  }
