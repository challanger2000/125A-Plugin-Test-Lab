[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Installer,
 [Parameter(Mandatory=$true)][string]$ExpectedSha256,
 [Parameter(Mandatory=$true)][string]$OutputFolder,
 [switch]$ApproveExecution,
 [int]$TimeoutSeconds=240,
 [string[]]$InventoryRoots=@()
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$report=[ordered]@{schema='125A-p98-v1';status='NOT_RUN';installer_sha256='';expected_sha256=$ExpectedSha256.ToLowerInvariant();exit_code=$null;timed_out=$false;execution_approved=[bool]$ApproveExecution;added=@();removed=@();changed=@();executables=@();registry_before=@();registry_after=@();error='';release_approved=$false}
$folder=[IO.Path]::GetFullPath($OutputFolder)
New-Item -Path $folder -ItemType Directory -Force | Out-Null
$reportFile=Join-Path $folder 'INSTALLER-INVENTORY.json'
function Save-Report {$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportFile -Encoding UTF8}
function Snapshot-Files {
 param([string[]]$Roots)
 $table=@{}
 foreach($root in $Roots){
  if(-not(Test-Path -LiteralPath $root -PathType Container)){continue}
  Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
   $f=$_
   if(-not $f.FullName.StartsWith($folder,[StringComparison]::OrdinalIgnoreCase)){
    $table[$f.FullName]=[ordered]@{size=$f.Length;mtime=$f.LastWriteTimeUtc.Ticks}
   }
  }
 }
 return $table
}
function Snapshot-Registry {
 $lines=@()
 foreach($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')){
  if(Test-Path $key){
   Get-ChildItem $key -ErrorAction SilentlyContinue | ForEach-Object {
    $p=Get-ItemProperty -LiteralPath $_.PSPath -ErrorAction SilentlyContinue
    if($p){$lines+= [ordered]@{key=$_.Name;name=[string]($p | Select-Object -ExpandProperty DisplayName -ErrorAction SilentlyContinue);version=[string]($p | Select-Object -ExpandProperty DisplayVersion -ErrorAction SilentlyContinue);location=[string]($p | Select-Object -ExpandProperty InstallLocation -ErrorAction SilentlyContinue)}}
   }
  }
 }
 return ,$lines
}
try{
 if($env:OS -ne 'Windows_NT'){throw 'Requires Windows'}
 if(-not $ApproveExecution){throw 'DENIED: explicit -ApproveExecution required'}
 if($TimeoutSeconds -lt 10 -or $TimeoutSeconds -gt 900){throw 'Timeout must be 10..900'}
 if($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$'){throw 'Invalid SHA256'}
 if(-not (Test-Path -LiteralPath $Installer -PathType Leaf)){throw 'Installer not found'}
 $installerPath=(Resolve-Path -LiteralPath $Installer).Path
 if([IO.Path]::GetExtension($installerPath).ToLowerInvariant() -ne '.exe'){throw 'EXE only'}
 $sha=(Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
 $report.installer_sha256=$sha
 if($sha -ne $ExpectedSha256.ToLowerInvariant()){throw 'Installer SHA256 mismatch'}
 $roots=@($env:ProgramFiles,$env:ProgramData,$env:LOCALAPPDATA,$env:APPDATA,[Environment]::GetFolderPath('ProgramFilesX86')) | Where-Object {$_ -and (Test-Path $_)} | Select-Object -Unique
 if($InventoryRoots.Count -gt 0){$roots=@($InventoryRoots)}
 $before=Snapshot-Files -Roots $roots
 $report.registry_before=@(Snapshot-Registry)
 $proc=Start-Process -FilePath $installerPath -PassThru
 if(-not $proc.WaitForExit($TimeoutSeconds*1000)){
  $report.timed_out=$true
  & taskkill.exe /T /F /PID $proc.Id 2>$null | Out-Null
  throw 'Installer timed out; process tree termination requested'
 }
 $report.exit_code=$proc.ExitCode
 $after=Snapshot-Files -Roots $roots
 $report.registry_after=@(Snapshot-Registry)
 $report.added=@($after.Keys | Where-Object {-not $before.ContainsKey($_)} | Sort-Object)
 $report.removed=@($before.Keys | Where-Object {-not $after.ContainsKey($_)} | Sort-Object)
 $report.changed=@($after.Keys | Where-Object {$before.ContainsKey($_) -and (($before[$_].size -ne $after[$_].size) -or ($before[$_].mtime -ne $after[$_].mtime))} | Sort-Object)
 $report.executables=@($report.added | Where-Object {$_ -match '(?i)(emulatorx\.exe|\.vst3|\.dll)$'} | ForEach-Object {[ordered]@{path=$_;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()}})
 if($proc.ExitCode -ne 0){throw "Installer exited $($proc.ExitCode)"}
 $report.status='INSTALLER_EXECUTED_INVENTORY_CAPTURED'
}catch{
 $report.status='FAIL'
 $report.error=$_.Exception.Message
}finally{Save-Report}
if($report.status -eq 'FAIL'){exit 1}
