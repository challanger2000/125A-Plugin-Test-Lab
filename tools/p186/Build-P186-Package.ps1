# CI producer for a strictly offline existing-data tool. No audio executable in root.
[CmdletBinding()]param([string]$Destination,[string]$ProfilePath,[string]$TestlabSource,[string]$AweSource='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(Test-Path $Destination){throw 'P186 package destination must be fresh'}
New-Item -ItemType Directory $Destination | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'P186-*') $Destination
foreach($name in @('P185-ANALYZE.ps1','P185-DIAGNOSTICS.ps1')){Copy-Item (Join-Path $PSScriptRoot ('../p185/'+$name)) $Destination}
Copy-Item -LiteralPath $ProfilePath -Destination (Join-Path $Destination 'P186-SOURCE-PROFILES.json')
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$source=Join-Path $Destination 'source/testlab';New-Item -ItemType Directory -Force $source | Out-Null
$tmpBase=if($env:RUNNER_TEMP){$env:RUNNER_TEMP}else{[IO.Path]::GetTempPath()}
$archive=Join-Path $tmpBase ('p186-source-'+[Guid]::NewGuid().ToString('N')+'.zip')
git -C $repo archive --format=zip --output=$archive $TestlabSource
if($LASTEXITCODE -ne 0){throw 'P186 exact source archive failed'}
Expand-Archive $archive $source
$dest=(Resolve-Path $Destination).Path;$files=[ordered]@{}
Get-ChildItem $dest -Recurse -File | Sort-Object FullName | ForEach-Object {
  $relative=$_.FullName.Substring($dest.Length+1).Replace('\','/')
  $files[$relative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
@{schema='125a-p186-offline-package-v1';testlab_source=$TestlabSource;awe_source=$AweSource;files=$files;new_hardware_test=$false;release_approved=$false} | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $Destination 'P186-PACKAGE.json') -Encoding UTF8
