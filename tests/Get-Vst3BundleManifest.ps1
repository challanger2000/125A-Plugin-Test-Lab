#requires -Version 5.1
<#
P109: produce an independently pin-able manifest for the ENTIRE source VST3
bundle, including non-DLL resources. Run before installing. This manifest
is not a trust certificate; compare its SHA against independently approved
source bytes when using packages from untrusted suppliers.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Bundle,
  [Parameter(Mandatory=$true)][string]$OutputFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'P109-LinkCount.ps1')
function Get-WholeBundleFiles([string]$path) {
  $root = (Resolve-Path -LiteralPath $path -ErrorAction Stop).ProviderPath
  $base = Get-Item -LiteralPath $root -Force
  if (-not $base.PSIsContainer -or $base.Extension -ne '.vst3' -or
      (($base.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'P109 source VST3 root must be a physical directory bundle'
  }
  $entries = @(Get-ChildItem -LiteralPath $root -Recurse -Force -ErrorAction Stop)
  if ($entries.Count -gt 3000) { throw 'P109 bundle exceeds 3000 entries' }
  $files = @()
  foreach ($entry in $entries) {
    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw 'P109 source VST3 contains symlink/junction/reparse entry'
    }
    if ($entry.PSIsContainer) { continue }
    Assert-P110SingleLink $entry.FullName
    $relative = $entry.FullName.Substring($root.TrimEnd('\').Length + 1).Replace('\','/')
    $files += @{ path=$relative; sha256=(Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  if ($files.Count -lt 1) { throw 'P109 empty VST3 bundle' }
  return @($files | Sort-Object path)
}
$path = [IO.Path]::GetFullPath($OutputFile)
if (Test-Path -LiteralPath $path) { throw 'P109 refuses to overwrite an existing manifest' }
$manifest = @{ schema='125a-vst3-whole-bundle-sha256-v1'; files=@(Get-WholeBundleFiles $Bundle) }
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $path -Encoding UTF8
Write-Output "P109 whole-bundle manifest generated ($($manifest.files.Count) files)"
