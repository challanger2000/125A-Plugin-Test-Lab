#requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Bundle,
  [Parameter(Mandatory=$true)][string]$ExpectedManifest,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedManifestSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'P109-LinkCount.ps1')
try {
  $root = (Resolve-Path -LiteralPath $Bundle -ErrorAction Stop).ProviderPath
  $source = (Resolve-Path -LiteralPath $ExpectedManifest -ErrorAction Stop).ProviderPath
  $approvedSha = $ExpectedManifestSha256.ToLowerInvariant()
  $observedSha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($approvedSha -cne $observedSha) { throw 'P109 independent source manifest hash mismatch' }
  $manifest = Get-Content -LiteralPath $source -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($manifest.schema -ne '125a-vst3-whole-bundle-sha256-v2' -or
      $null -eq $manifest.directories -or
      $null -eq $manifest.files -or @($manifest.files).Count -lt 1 -or
      @($manifest.files).Count -gt 3000) { throw 'P109 malformed whole-bundle manifest' }
  $base = Get-Item -LiteralPath $root -Force
  if (-not $base.PSIsContainer -or $base.Extension -ne '.vst3' -or
      (($base.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'P109 VST3 root must be physical non-linked directory'
  }
  $entries = @(Get-ChildItem -LiteralPath $root -Recurse -Force -ErrorAction Stop)
  if ($entries.Count -gt 3000) { throw 'P109 VST3 inventory limit exceeded' }
  # P111 directories are part of an installed VST3 bundle contract,
  # including zero-byte/empty directories never represented by file hashes.
  $actualDirectories = @{}
  foreach ($entry in $entries) {
    if (-not $entry.PSIsContainer) { continue }
    $relativeDir = $entry.FullName.Substring($root.TrimEnd('\').Length + 1).Replace('\','/')
    $key = $relativeDir.ToLowerInvariant()
    if ($actualDirectories.ContainsKey($key)) { throw 'P111 duplicate installed bundle directories' }
    $actualDirectories[$key] = $true
  }
  if (@($manifest.directories).Count -ne $actualDirectories.Count) {
    throw 'P111 missing or extra installed VST3 directories'
  }
  $manifestDirectories = @{}
  foreach ($dir in @($manifest.directories)) {
    $relativeDir = [string]$dir
    if (-not $relativeDir -or $relativeDir.StartsWith('/') -or
        $relativeDir.Contains('\') -or $relativeDir -match '(^|/)\.\.(/|$)') {
      throw 'P111 invalid approved bundle directory path'
    }
    $key = $relativeDir.ToLowerInvariant()
    if ($manifestDirectories.ContainsKey($key) -or
        -not $actualDirectories.ContainsKey($key)) {
      throw 'P111 installed VST3 directory tree differs from approved source'
    }
    $manifestDirectories[$key] = $true
  }
  $seen = @{}
  foreach ($entry in $entries) {
    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw 'P109 linked/junction resource rejected'
    }
    if ($entry.PSIsContainer) { continue }
    Assert-P110SingleLink $entry.FullName
    Assert-P112NoAlternateStreams $entry.FullName
    $relative = $entry.FullName.Substring($root.TrimEnd('\').Length + 1).Replace('\','/')
    $key = $relative.ToLowerInvariant()
    if ($seen.ContainsKey($key)) { throw 'P109 case-colliding resource paths' }
    $seen[$key] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  if ($seen.Count -ne @($manifest.files).Count) { throw 'P109 missing or extra VST3 resource files' }
  $expected = @{}
  foreach ($f in $manifest.files) {
    $path = [string]$f.path
    $hash = [string]$f.sha256
    if (-not $path -or $path.StartsWith('/') -or $path.Contains('\') -or
        $path -match '(^|/)\.\.(/|$)' -or $hash -notmatch '^[a-f0-9]{64}$') {
      throw 'P109 malformed source manifest path/hash'
    }
    $key = $path.ToLowerInvariant()
    if ($expected.ContainsKey($key) -or
        -not $seen.ContainsKey($key) -or $seen[$key] -cne $hash) {
      throw 'P109 installed resource SHA256 differs from approved manifest'
    }
    $expected[$key] = $true
  }
  Write-Output ("P109 COMPLETE_BUNDLE_VERIFIED: " + $seen.Count + " resources")
  exit 0
} catch {
  [Console]::Error.WriteLine([string]$_.Exception.Message)
  exit 1
}
