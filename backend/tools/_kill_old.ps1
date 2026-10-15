Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    "PID " + $_.OwningProcess + " still listening on 8765"
}
(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "---python procs after kill---"
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    "PID " + $_.Id + " StartTime=" + $_.StartTime
}