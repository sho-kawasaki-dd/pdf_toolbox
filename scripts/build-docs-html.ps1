Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

$readmeMd = Join-Path $repoRoot 'README.md'
$readmeHtml = Join-Path $repoRoot 'README.html'
$docsDir = Join-Path $repoRoot 'docs'
$cssRoot = Join-Path $repoRoot 'github-markdown.css'

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    throw 'pandoc was not found. Install pandoc and run this script again.'
}

if (-not (Test-Path $cssRoot)) {
    throw "CSS file was not found: $cssRoot"
}

pandoc $readmeMd -s -o $readmeHtml -c 'github-markdown.css'

Get-ChildItem $docsDir -Filter '*.md' -File | ForEach-Object {
    $outputHtml = Join-Path $_.DirectoryName ($_.BaseName + '.html')
    pandoc $_.FullName -s -o $outputHtml -c '../github-markdown.css'
}

Write-Host 'HTML regeneration completed:'
Get-ChildItem $readmeHtml, (Join-Path $docsDir '*.html') |
    Sort-Object FullName |
    Select-Object Name, LastWriteTime |
    Format-Table -AutoSize
