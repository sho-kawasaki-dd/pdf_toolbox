$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot '..\build-exe.ps1') @PSBoundParameters