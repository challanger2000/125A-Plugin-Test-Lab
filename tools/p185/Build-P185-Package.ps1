# CI packaging only. Never required on the user's machine.
[CmdletBinding()]param([string]$Build,[string]$Destination,[string]$TestlabSource,[string]$AweSource='', [string]$AweBundle='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(Test-Path $Destination){throw 'Package directory must be fresh'}
New-Item -ItemType Directory $Destination | Out-Null
foreach($name in @('125A_Test_Lab_ETW.exe','125A_Test_Lab_Physical_ASIO.exe','125A_QA_ASIO_Reference_MIDI.vst3')){
  $file=@(Get-ChildItem $Build -Recurse -File -Filter $name)
  if($file.Count -ne 1){throw ('Ambiguous binary '+$name)}
  Copy-Item -LiteralPath $file[0].FullName -Destination (Join-Path $Destination $name)
}
Copy-Item (Join-Path $PSScriptRoot 'P185-*') $Destination
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$src=Join-Path $Destination 'source/testlab';New-Item -ItemType Directory -Force $src | Out-Null
# git archive pins the actual committed corresponding test-tool source.
$archive=Join-Path $env:RUNNER_TEMP ('p185-source-'+[Guid]::NewGuid().ToString('N')+'.zip')
git -C $repo archive --format=zip --output=$archive $TestlabSource
if($LASTEXITCODE -ne 0){throw 'Exact source archive failed'}
Expand-Archive $archive $src
if(Test-Path (Join-Path $repo 'LICENSE')){Copy-Item (Join-Path $repo 'LICENSE') (Join-Path $Destination 'TESTLAB-LICENSE')}
Copy-Item (Join-Path $repo 'asio-sdk/LICENSE.txt') (Join-Path $Destination 'ASIO-SDK-LICENSE.txt')
$asioSrc=Join-Path $Destination 'source/asio-sdk';New-Item -ItemType Directory -Force $asioSrc | Out-Null
Get-ChildItem (Join-Path $repo 'asio-sdk') -Force | Where-Object {$_.Name -ne '.git'} | Copy-Item -Destination $asioSrc -Recurse
if($AweBundle){
  Copy-Item -LiteralPath $AweBundle -Destination (Join-Path $Destination 'AWE-UNCHANGED.vst3') -Recurse
}
$files=[ordered]@{}
$dest=(Resolve-Path $Destination).Path
Get-ChildItem $dest -Recurse -File | Sort-Object FullName | ForEach-Object {
  $relative=$_.FullName.Substring($dest.Length+1).Replace('\','/')
  $files[$relative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
@{schema='125a-p185-package-v1';testlab_source=$TestlabSource;awe_source=$AweSource;asio_sdk_source='496a0765b8bb9c26f764f22f9a9712a937177db2';vst3_sdk_source='3cdf9ca5d1f5b1b21e0a86832aa4abe55607bd96';files=$files;physical_asio='NOT_RUN';release_approved=$false} | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $Destination 'P185-PACKAGE.json') -Encoding UTF8
