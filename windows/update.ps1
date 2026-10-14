# Updates SceneForge's program files from GitHub (main branch).
# Keeps your installed Python, FFmpeg, speech model, presets and projects.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$App = Split-Path -Parent $PSScriptRoot
$Url = "https://github.com/ABDONLEGACY/Abdonlegacy/archive/refs/heads/main.zip"
$Tmp = Join-Path $env:TEMP ("sceneforge_update_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

try {
    Write-Host "Downloading the latest SceneForge ..." -ForegroundColor Cyan
    $zip = Join-Path $Tmp "sceneforge.zip"
    Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $Tmp -Force
    $src = Get-ChildItem $Tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName "app.py") } | Select-Object -First 1
    if (-not $src) { throw "The download did not contain SceneForge." }

    Write-Host "Replacing program files in $App ..." -ForegroundColor Cyan
    foreach ($item in Get-ChildItem $src.FullName -Force) {
        if ($item.Name -in @("python", "ffmpeg", "models", "settings")) { continue }
        $dest = Join-Path $App $item.Name
        if ($item.PSIsContainer) {
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            Copy-Item -Recurse -Force $item.FullName $dest
        } else {
            Copy-Item -Force $item.FullName $dest
        }
    }
    Get-ChildItem $App -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    $Py = Join-Path $App "python\python.exe"
    if (Test-Path $Py) {
        Write-Host "Checking Python packages ..." -ForegroundColor Cyan
        & $Py -m pip install --no-warn-script-location --disable-pip-version-check -q -r (Join-Path $App "requirements.txt")
    }
    Write-Host ""
    Write-Host "SceneForge is up to date. Start it again from the Desktop." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "UPDATE PROBLEM: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
