param(
    [int]$Port = 8765
)

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appPath = Join-Path $projectDir 'app.py'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython -X utf8 $appPath --port $Port --open
    exit $LASTEXITCODE
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    & $pyLauncher.Source -3 -X utf8 $appPath --port $Port --open
    exit $LASTEXITCODE
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\python.exe') {
    & $pythonCommand.Source -X utf8 $appPath --port $Port --open
    exit $LASTEXITCODE
}

Write-Error 'Không tìm thấy Python 3. Cài Python 3.11+ từ python.org (tick "Add python.exe to PATH"), mở lại PowerShell rồi chạy lại. Chi tiết: docs/HUONG_DAN_CHAY.md'
exit 1
