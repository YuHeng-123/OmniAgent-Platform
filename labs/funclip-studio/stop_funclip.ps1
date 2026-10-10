$ErrorActionPreference = "SilentlyContinue"
$items = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -like "python*") -and ($_.CommandLine -like "*funclip*launch.py*" -or $_.CommandLine -like "*funclip\launch.py*")
}

if (!$items) {
    Write-Host "FunClip 当前没有运行。"
    exit 0
}

foreach ($item in $items) {
    Stop-Process -Id $item.ProcessId -Force
}
Write-Host "FunClip 已停止。"
