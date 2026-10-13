# SceneForge installer for Windows (no admin rights needed).
# Downloads ONLY free tools (Python, Python packages, FFmpeg, the Whisper speech model) into this folder.
# Nothing of yours is uploaded anywhere.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$App = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $App "python\python.exe"
$Downloads = Join-Path $App "downloads"
$PyVersion = "3.12.10"
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
Start-Transcript -Path (Join-Path $App "install_log.txt") -Force | Out-Null

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host "INSTALL PROBLEM: $msg" -ForegroundColor Red
    Write-Host "A log was saved to install_log.txt in the SceneForge folder." -ForegroundColor Yellow
    Stop-Transcript | Out-Null
    exit 1
}
function Download($urls, $dest) {
    foreach ($u in $urls) {
        for ($try = 1; $try -le 3; $try++) {
            try {
                Write-Host "    downloading $u"
                Invoke-WebRequest -Uri $u -OutFile $dest -UseBasicParsing
                if ((Get-Item $dest).Length -gt 1000) { return }
            } catch {
                Write-Host "    (attempt $try failed: $($_.Exception.Message))" -ForegroundColor Yellow
                Start-Sleep -Seconds (2 * $try)
            }
        }
    }
    Fail "Could not download $dest. Check your internet connection and run the installer again."
}

Write-Host "SceneForge installer - folder: $App" -ForegroundColor Green
if ($App -match "[^\x00-\x7F]") {
    Write-Host "Note: the folder path contains special characters. If something fails, move the SceneForge folder to C:\SceneForge and run the installer again." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 1. Python (private copy inside this folder)
Step "1/6  Python $PyVersion"
if (-not (Test-Path $Py)) {
    $zip = Join-Path $Downloads "python-embed.zip"
    Download @("https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip") $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $App "python") -Force
    # Let this private Python use installed packages and find the SceneForge code (the parent folder).
    $pth = Get-ChildItem (Join-Path $App "python") -Filter "python*._pth" | Select-Object -First 1
    Set-Content -Path $pth.FullName -Encoding ASCII -Value @("python312.zip", ".", "Lib\site-packages", "..", "import site")
} else {
    Write-Host "    already installed"
}
$hasPip = $false
try { & $Py -m pip --version | Out-Null; $hasPip = ($LASTEXITCODE -eq 0) } catch { $hasPip = $false }
if (-not $hasPip) {
    $getpip = Join-Path $Downloads "get-pip.py"
    Download @("https://bootstrap.pypa.io/get-pip.py") $getpip
    & $Py $getpip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { Fail "Could not set up pip for Python." }
}

# ---------------------------------------------------------------- 2. Microsoft C++ runtime (needed by some packages)
Step "2/6  Microsoft Visual C++ runtime"
if (-not (Test-Path "$env:WINDIR\System32\msvcp140.dll") -or -not (Test-Path "$env:WINDIR\System32\vcruntime140_1.dll")) {
    $vc = Join-Path $Downloads "vc_redist.x64.exe"
    Download @("https://aka.ms/vs/17/release/vc_redist.x64.exe") $vc
    Write-Host "    Windows may ask for permission to install the Microsoft C++ runtime - please click Yes."
    Start-Process -FilePath $vc -ArgumentList "/install", "/quiet", "/norestart" -Wait
} else {
    Write-Host "    already installed"
}

# ---------------------------------------------------------------- 3. Python packages
Step "3/6  Python packages (Gradio, faster-whisper, OpenCV ...) - this can take a few minutes"
& $Py -m pip install --upgrade --no-warn-script-location --disable-pip-version-check -r (Join-Path $App "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "Installing Python packages failed (see messages above)." }

# ---------------------------------------------------------------- 4. FFmpeg
Step "4/6  FFmpeg"
$ffdir = Join-Path $App "ffmpeg\bin"
if (-not (Test-Path (Join-Path $ffdir "ffmpeg.exe"))) {
    $zip = Join-Path $Downloads "ffmpeg.zip"
    Download @("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
               "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip") $zip
    $tmp = Join-Path $Downloads "ffmpeg_unzip"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $exe = Get-ChildItem $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $exe) { Fail "The FFmpeg download did not contain ffmpeg.exe." }
    New-Item -ItemType Directory -Force -Path $ffdir | Out-Null
    Copy-Item (Join-Path $exe.DirectoryName "*") $ffdir -Force
    Remove-Item -Recurse -Force $tmp
} else {
    Write-Host "    already installed"
}
$env:PATH = "$ffdir;$env:PATH"

# ---------------------------------------------------------------- 5. Speech model
Step "5/6  Whisper speech model 'small' (about 460 MB, downloaded once)"
& $Py -c "from sceneforge.transcribe import load_model; load_model('small'); print('    model ready')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    The speech model could not be downloaded now. SceneForge will try again the first time you sync." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 6. Self-check + Desktop launcher
Step "6/6  Testing SceneForge and creating the Desktop launcher"
& $Py -m sceneforge.selfcheck
if ($LASTEXITCODE -ne 0) { Fail "The self-check failed (see messages above)." }

$desktop = [Environment]::GetFolderPath("Desktop")
$launcher = Join-Path $desktop "SceneForge.bat"
$start = Join-Path $App "Start_SceneForge.bat"
Set-Content -Path $launcher -Encoding ASCII -Value @(
    "@echo off",
    "rem Starts SceneForge (installed in $App)",
    "call `"$start`""
)
Remove-Item -Recurse -Force $Downloads -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "SceneForge is installed!" -ForegroundColor Green
Write-Host "Double-click 'SceneForge.bat' on your Desktop to start it." -ForegroundColor Green
Stop-Transcript | Out-Null
exit 0
