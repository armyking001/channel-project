Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    "PID " + $_.OwningProcess + " listens on 8765"
}
Write-Host "---python procs---"
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    "PID " + $_.Id + " StartTime=" + $_.StartTime + " Path=" + $_.Path
}