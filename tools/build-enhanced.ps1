# Windows x64: requires translated PC workspace and completed runtime overlay.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Compdb,
 [Parameter(Mandatory=$true)][string]$Overlay,
 [Parameter(Mandatory=$true)][string]$Output,
 [Parameter(Mandatory=$true)][string]$Identity,
 [Parameter(Mandatory=$true)][string]$Version,
 [ValidateSet('retro','base')][string]$Product='retro',
 [Parameter(Mandatory=$true)][string]$Thumbprint,
 [ValidateRange(1,64)][int]$Jobs=4
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path -Parent $PSScriptRoot
function Invoke-Checked([string]$Program,[string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}
function Require-Path([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing: $Path" }
}
foreach ($v in @('MKW_TOOLKIT','MKW_UWP_DEP','MKW_UWP_SDL','MKW_BASE_PC')) {
    $p=[Environment]::GetEnvironmentVariable($v)
    if (-not $p) { throw "Missing environment variable $v" }
    Require-Path $p
}
$env:MKW_XBOX=$root
$Compdb=(Resolve-Path -LiteralPath $Compdb).Path
$Overlay=(Resolve-Path -LiteralPath $Overlay).Path
if ((Split-Path -Leaf $Overlay) -ne 'port') { throw 'Use an overlay directory named port (upstream linker assumption).' }
foreach ($f in @('runtime/src/main.cpp','runtime/src/uwp_main.cpp','aurora-main','projects')) { Require-Path (Join-Path $Overlay $f) }
foreach ($f in @('clang.exe','ld.lld.exe','llvm-ar.exe')) { Require-Path (Join-Path $env:MKW_TOOLKIT $f) }
foreach ($f in @('include','lib/SDL3.lib','bin/SDL3.dll')) { Require-Path (Join-Path $env:MKW_UWP_SDL $f) }
foreach ($f in @('include','lib/webgpu_dawn.lib','lib/nod.lib','lib/libuwp.lib','lib/libpng16.lib','lib/z.lib','lib/dxcompiler.lib','bin/webgpu_dawn.dll','bin/nod.dll','bin/dxcompiler.dll','bin/dxil.dll','bin/libpng16.dll','bin/z.dll','bin/libuwp.dll')) { Require-Path (Join-Path $env:MKW_UWP_DEP $f) }
foreach ($f in @('dsp_coef.bin','initial_pipeline_cache.db','wii_bootstrap')) { Require-Path (Join-Path $env:MKW_BASE_PC $f) }
$Thumbprint=$Thumbprint.Replace(' ','')
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Invalid certificate thumbprint' }
$cert=Get-Item -LiteralPath "Cert:\CurrentUser\My\$Thumbprint"
if (-not $cert.HasPrivateKey -or $cert.NotAfter -lt (Get-Date)) { throw 'Valid signing certificate with private key required' }
$env:MKW_CERT=$Thumbprint
$Output=[IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw 'Use a fresh output directory to avoid stale objects' }
New-Item -ItemType Directory -Path $Output | Out-Null
$package=Join-Path $Output 'package'
$objects=Join-Path $Output 'obj';$deps=Join-Path $Output 'obj-deps'
$exe=Join-Path $Output 'WiiCompiled.exe'
$msix=Join-Path $Output 'RetroRewind.msix'
if ($Product -eq 'base') { $msix=Join-Path $Output 'MarioKartWii.msix' }
Invoke-Checked 'py' @('-3',"$PSScriptRoot\prepare-package.py","$root\package",$package,'--name',$Identity,'--publisher',$cert.Subject,'--version',$Version,'--product',$Product)
Invoke-Checked "$PSScriptRoot\compilar.cmd" @($Compdb,$objects,"--overlay=$Overlay","--jobs=$Jobs")
Invoke-Checked "$PSScriptRoot\compilar.cmd" @($Compdb,$deps,"--overlay=$Overlay","--jobs=$Jobs",'--solo=deps')
Invoke-Checked "$PSScriptRoot\enlazar.cmd" @($objects,$deps,$exe,$Product)
Invoke-Checked 'py' @('-3',"$PSScriptRoot\empaquetar-uwp.py",$exe,$msix,$package,$Thumbprint)
Require-Path $msix
Get-FileHash -LiteralPath $msix -Algorithm SHA256 | Format-List
Write-Host "Signed MSIX: $msix"
