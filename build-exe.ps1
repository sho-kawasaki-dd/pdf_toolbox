param(
    [switch]$Pause
)

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$specPath = Join-Path $projectRoot 'pdf_toolbox.spec'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $specPath)) {
    throw "Spec file not found: $specPath"
}

Push-Location $projectRoot

try {
    if (Test-Path $venvPython) {
        Write-Host "Using virtual environment Python: $venvPython"
        & $venvPython -m PyInstaller --noconfirm --clean $specPath
    }
    elseif (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
        Write-Host 'Using PyInstaller from PATH'
        & pyinstaller --noconfirm --clean $specPath
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host 'Using python -m PyInstaller from PATH'
        & python -m PyInstaller --noconfirm --clean $specPath
    }
    else {
        throw 'PyInstaller was not found. Activate your virtual environment or install PyInstaller first.'
    }

    $distPath = Join-Path $projectRoot 'dist\PDFToolbox_v1.0.3'

    if (Test-Path $distPath) {
        Write-Host "Build completed: $distPath"
    }
}
finally {
    Pop-Location
}

if ($Pause) {
    Read-Host 'Press Enter to continue'
}