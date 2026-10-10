$ErrorActionPreference = "Stop"
$env:GRADIO_ANALYTICS_ENABLED = "False"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Launch = Join-Path $Root "funclip\launch.py"
$OutLog = Join-Path $Root "funclip_run.out.log"
$ErrLog = Join-Path $Root "funclip_run.err.log"
$Url = "http://127.0.0.1:7860"

Write-Host "FunClip 正在启动..."

if (!(Test-Path $Python)) {
    Write-Host "没有找到运行环境：$Python"
    Write-Host "请先确认 FunClip 安装完整。"
    exit 1
}

if (!(Test-Path $Launch)) {
    Write-Host "没有找到启动文件：$Launch"
    Write-Host "请先确认 FunClip 项目文件完整。"
    exit 1
}

$running = Test-NetConnection -ComputerName 127.0.0.1 -Port 7860 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $running) {
    Start-Process -FilePath $Python -ArgumentList @($Launch, "-p", "7860") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog | Out-Null
}

Write-Host "等待网页入口准备好，通常需要 30 到 90 秒..."
for ($i = 0; $i -lt 90; $i++) {
    $ready = Test-NetConnection -ComputerName 127.0.0.1 -Port 7860 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($ready) {
        Write-Host "FunClip 已启动：$Url"
        Start-Process $Url
        exit 0
    }
    Start-Sleep -Seconds 2
}

Write-Host "启动超时。请把下面的日志发给我排查："
if (Test-Path $ErrLog) {
    Get-Content -Tail 60 $ErrLog
}
exit 1
