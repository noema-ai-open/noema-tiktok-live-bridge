param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot "dist\noema-tiktok-bridge"
$runtimeRoot = Join-Path $distRoot "runtime"
$sitePackages = Join-Path $runtimeRoot "Lib\site-packages"
$tempRoot = Join-Path $env:RUNNER_TEMP "noema-portable-python"

Remove-Item $distRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $runtimeRoot "scripts") -Force | Out-Null
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

$pythonVersion = (& python -c "import platform; print(platform.python_version())").Trim()
$pythonTag = (& python -c "import sys; print(f'python{sys.version_info.major}{sys.version_info.minor}')").Trim()
$embedUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"
$embedZip = Join-Path $tempRoot "python-embed.zip"

Write-Host "Lade offizielle portable Python-Laufzeit $pythonVersion"
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
Expand-Archive -Path $embedZip -DestinationPath $runtimeRoot -Force

$pthFile = Join-Path $runtimeRoot "$pythonTag._pth"
if (-not (Test-Path $pthFile)) {
    throw "Portable Python-Pfaddatei nicht gefunden: $pthFile"
}

@(
    "$pythonTag.zip"
    "."
    "Lib/site-packages"
    "import site"
) | Set-Content -Path $pthFile -Encoding ascii

Push-Location $repoRoot
try {
    python -m pip install --disable-pip-version-check --no-compile --target $sitePackages ".[live,windows]"
} finally {
    Pop-Location
}

# Der Projektcode bleibt sichtbar und prüfbar. Keine generierte Bootstrap-EXE.
Copy-Item (Join-Path $repoRoot "app") (Join-Path $runtimeRoot "app") -Recurse -Force
Copy-Item (Join-Path $repoRoot "frontend") (Join-Path $runtimeRoot "frontend") -Recurse -Force
Copy-Item (Join-Path $repoRoot ".env.example") (Join-Path $runtimeRoot ".env.example") -Force
Copy-Item (Join-Path $repoRoot "scripts\windows_launcher.py") (Join-Path $runtimeRoot "scripts\windows_launcher.py") -Force

# Doppelten, von pip gebauten Projektcode entfernen. Die geprüften Quellen liegen in runtime/app.
Remove-Item (Join-Path $sitePackages "app") -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $sitePackages -Filter "noema_tiktok_live_bridge-*.dist-info" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

Get-ChildItem $runtimeRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

$portablePython = Join-Path $runtimeRoot "python.exe"
if (-not (Test-Path $portablePython)) {
    throw "Portable python.exe fehlt."
}

& $portablePython -c "from app.version import __version__; import fastapi, uvicorn, edge_tts, TikTokLive, win32com.client; assert __version__ == '$Version', (__version__, '$Version'); print('Portable runtime OK', __version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Portable Laufzeit konnte die Anwendung nicht importieren."
}

$index = Get-Content (Join-Path $runtimeRoot "frontend\index.html") -Raw
$ui = Get-Content (Join-Path $runtimeRoot "frontend\noema-ui.js") -Raw
$kittCss = Get-Content (Join-Path $runtimeRoot "frontend\kitt-header.css") -Raw

if ($index -match "kitt-voicebox" -or $index -match "VOICE LINK") {
    throw "Veraltetes großes KITT-Modul ist noch im Paket enthalten."
}
if ($ui -notmatch "mountEqualizer" -or $kittCss -notmatch "\.kitt-eq") {
    throw "Der KITT-Equalizer fehlt im Paket."
}
if ($ui -match "mountKittStrip" -or $kittCss -match "\.kitt-strip") {
    throw "Veralteter KITT-Scanner ist noch im Paket enthalten."
}
if ($kittCss -match "\.kitt-console") {
    throw "Veraltete KITT-Konsolenregeln sind noch im Paket enthalten."
}

$buildInfo = [ordered]@{
    product = "NOEMA TikTok Live Bridge"
    version = $Version
    python = $pythonVersion
    commit = $env:GITHUB_SHA
    packaging = "official-python-embed"
    generated_utc = [DateTime]::UtcNow.ToString("o")
}
$buildInfo | ConvertTo-Json | Set-Content (Join-Path $distRoot "build-info.json") -Encoding utf8

Write-Host "Portable Laufzeit fertig: $distRoot"
