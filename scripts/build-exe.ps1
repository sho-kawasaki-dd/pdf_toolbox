$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

pyinstaller --noconfirm --clean pdf_toolbox.spec

Read-Host "Press Enter to continue..."