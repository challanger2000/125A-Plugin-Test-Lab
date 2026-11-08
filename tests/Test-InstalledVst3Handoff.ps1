#requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WorkingRoot,
      [Parameter(Mandatory=$true)][string]$SourceBundle,
      [Parameter(Mandatory=$true)][string]$GuiHost,
      [Parameter(Mandatory=$true)][string]$AudioHost,
      [Parameter(Mandatory=$true)][string]$StressHost,
      [Parameter(Mandatory=$true)][string]$PythonExecutable)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$installerScript = Join-Path $PSScriptRoot 'Invoke-UniversalInstaller.ps1'
$postScript = Join-Path $PSScriptRoot 'Invoke-InstalledVst3QA.ps1'
$fixtureSource = Join-Path $PSScriptRoot 'p106_installer_fixture.cs'
New-Item -ItemType Directory -Path $WorkingRoot -Force | Out-Null
$fixture = Join-Path $WorkingRoot 'P106-Actual-Bundle-Install.exe'
Add-Type -Path $fixtureSource -OutputAssembly $fixture -OutputType ConsoleApplication -ErrorAction Stop
$bundle = (Resolve-Path -LiteralPath $SourceBundle).ProviderPath
$dest = Join-Path $WorkingRoot ([IO.Path]::GetFileName($bundle))
$sourceDll = Join-Path $bundle ('Contents\x86_64-win\' + [IO.Path]::GetFileName($bundle))
if (-not (Test-Path -LiteralPath $sourceDll -PathType Leaf)) { throw 'P106 actual source-built VST3 is missing its DLL' }
$destModule = Join-Path $dest ('Contents\x86_64-win\' + [IO.Path]::GetFileName($bundle))
$moduleHash = (Get-FileHash -LiteralPath $sourceDll -Algorithm SHA256).Hash.ToLowerInvariant()
$installerHash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant()
$arguments = 'copydir "' + $bundle + '" "' + $dest + '"'
$installOut = Join-Path $WorkingRoot '09-real-vst3-bundle-installer'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installerScript -Mode Run -ApproveExecution -AllowUnsigned -Installer $fixture -ExpectedSha256 $installerHash -InstallerArguments $arguments -ExpectedArtifact $destModule -ExpectedArtifactSha256 $moduleHash -OutputFolder $installOut | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destModule -PathType Leaf)) { throw 'P106 source-built VST3 bundle was not truly installed' }
$report = Join-Path $installOut 'P106-INSTALLER-RESULT.json'
$qaOut = Join-Path $WorkingRoot '10-p74-actual-installed-vst3'
$baseArgs = @('-InstallationReport',$report,'-Vst3Bundle',$dest,
              '-InstalledModule',$destModule,'-ExpectedModuleSha256',$moduleHash,
              '-GuiHost',$GuiHost,'-PythonExecutable',$PythonExecutable,
              '-AudioHost',$AudioHost,'-StressHost',$StressHost,
              '-RunTechnicalBaseline')
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript @baseArgs -OutputFolder $qaOut | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'P106 installed REAL VST3 did not pass P74 host and technical QA' }
$proof = Get-Content -LiteralPath (Join-Path $qaOut 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
if ($proof.status -ne 'INSTALL_AND_NATIVE_TECHNICAL_PASS' -or
    $proof.installed_module_sha256_verified -ne $true -or
    $proof.p74_executed -ne $true -or
    $proof.vst3_technical_baseline -ne 'PASS' -or
    $proof.release_approved -ne $false) { throw 'P106 bridge reported false-positive native technical evidence' }
Write-Host 'P106 installed actual source-built VST3 -> P74 actual native GUI, audio/state and API tests PASS'
$wrongSha = '0' * 64
$rejectOut = Join-Path $WorkingRoot '11-bad-installed-vst3-sha'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postScript @($baseArgs | Where-Object { $false }) -InstallationReport $report -Vst3Bundle $dest -InstalledModule $destModule -ExpectedModuleSha256 $wrongSha -GuiHost $GuiHost -PythonExecutable $PythonExecutable -OutputFolder $rejectOut | Out-Null
if ($LASTEXITCODE -eq 0) { throw 'P106 bridge accepted wrong installed binary hash' }
$rejected = Get-Content -LiteralPath (Join-Path $rejectOut 'P106-POSTINSTALL-VST3-RESULT.json') -Raw | ConvertFrom-Json
if ($rejected.p74_executed -ne $false -or $rejected.status -ne 'FAIL') { throw 'P106 wrong installed hash incorrectly reached native host' }
Write-Host 'P106 independent wrong installed VST3 SHA rejected before P74 starts'
