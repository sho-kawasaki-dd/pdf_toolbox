param(
    [switch]$Pause
)

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$specPath = Join-Path $projectRoot 'pdf_toolbox.spec'
$issPath = Join-Path $projectRoot 'pdf_toolbox.iss'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $specPath)) {
    throw "Spec file not found: $specPath"
}

if (-not (Test-Path $issPath)) {
    throw "Installer definition file not found: $issPath"
}

function Resolve-InnoSetupCompiler {
    $compilerCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue

    if ($null -eq $compilerCommand) {
        $compilerCommand = Get-Command iscc -ErrorAction SilentlyContinue
    }

    if ($null -ne $compilerCommand) {
        return $compilerCommand.Source
    }

    $candidatePaths = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path $candidatePath) {
            return $candidatePath
        }
    }

    return $null
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

    $isccPath = Resolve-InnoSetupCompiler

    if (-not $isccPath) {
        throw 'Inno Setup Compiler was not found. Install Inno Setup or add ISCC.exe to PATH.'
    }

    $versionScript = Join-Path $projectRoot 'scripts\get_version.py'
    $version = & $venvPython $versionScript

    Write-Host "Using Inno Setup Compiler: $isccPath"
    & $isccPath "/DMyAppVersion=$version" $issPath

    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed with exit code $LASTEXITCODE"
    }

    $distPath = Join-Path $projectRoot 'dist\PDFToolbox'
    $installerPath = Join-Path $projectRoot "installer\PDF Toolbox_Setup_v$version.exe"

    if (Test-Path $distPath) {
        Write-Host "Build completed: $distPath"
    }

    if (Test-Path $installerPath) {
        Write-Host "Installer created: $installerPath"
    }
}
finally {
    Pop-Location
}

if ($Pause) {
    Read-Host 'Press Enter to continue'
}