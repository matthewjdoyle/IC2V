$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Push-Location $projectRoot
try {
    $distPath = Join-Path $projectRoot "dist"
    if (Test-Path -LiteralPath $distPath) {
        Remove-Item -Recurse -Force -LiteralPath $distPath
    }
    $buildPath = Join-Path $projectRoot "build"
    if (Test-Path -LiteralPath $buildPath) {
        Remove-Item -Recurse -Force -LiteralPath $buildPath
    }
    
    & $python -m PyInstaller --noconfirm (Join-Path $PSScriptRoot "ic2v-gui.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    & $python -m pip freeze | Set-Content (Join-Path $projectRoot "dist\IC2V\BUILD_INFO.txt")

    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $localIscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $localIscc) {
            $iscc = Get-Item -LiteralPath $localIscc
        } else {
            throw "Inno Setup 6 is required and ISCC.exe must be on PATH."
        }
    }
    & $iscc (Join-Path $PSScriptRoot "windows-installer.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
}
finally {
    Pop-Location
}
