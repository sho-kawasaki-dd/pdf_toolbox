$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

pyinstaller --noconfirm --clean PDFSplitter.spec

Read-Host "Press Enter to continue..."