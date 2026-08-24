[CmdletBinding()]
param(
    [string]$Project = 'default',
    [string]$OutputDirectory,
    [string]$Distro = 'Ubuntu-24.04',
    [string]$PackageId,
    [string]$AppName,
    [string]$VersionName,
    [Nullable[int]]$VersionCode,
    [string]$Icon,
    [ValidateSet('arm64-v8a', 'x86_64')][string]$Arch,
    [ValidateSet('debug', 'release')][string]$Mode,
    [switch]$EnableRuntimeDebugger
)

$ErrorActionPreference = 'Stop'
$runtimeRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $runtimeRoot 'artifacts'
}

$wslStatus = & wsl.exe --list --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "WSL2 is not installed or initialized.`n$($wslStatus -join [Environment]::NewLine)"
}
if ($Distro -notin $wslStatus) {
    throw "WSL distro '$Distro' was not found. Available distros: $($wslStatus -join ', ')"
}

$runtimeInterop = $runtimeRoot.Replace('\', '/')
$outputInterop = $OutputDirectory.Replace('\', '/')
$runtimeWsl = (& wsl.exe -d $Distro -- wslpath -a $runtimeInterop).Trim()
$outputWsl = (& wsl.exe -d $Distro -- wslpath -a $outputInterop).Trim()
if (-not $runtimeWsl -or -not $outputWsl) {
    throw 'Could not translate the runtime/output paths into WSL paths.'
}

$projectWsl = $Project
if (Test-Path -LiteralPath $Project -PathType Container) {
    $projectPath = (Resolve-Path -LiteralPath $Project).Path.Replace('\', '/')
    $projectWsl = (& wsl.exe -d $Distro -- wslpath -a $projectPath).Trim()
}

$iconWsl = ''
if ($Icon) {
    if (-not (Test-Path -LiteralPath $Icon -PathType Leaf)) {
        throw "Android icon PNG was not found: $Icon"
    }
    $iconPath = (Resolve-Path -LiteralPath $Icon).Path.Replace('\', '/')
    $iconWsl = (& wsl.exe -d $Distro -- wslpath -a $iconPath).Trim()
}

$defaultArg = '__LT_DEFAULT__'
$packageIdArg = if ($PackageId) { $PackageId } else { $defaultArg }
$appNameArg = if ($AppName) { $AppName } else { $defaultArg }
$versionNameArg = if ($VersionName) { $VersionName } else { $defaultArg }
$versionCodeArg = if ($null -ne $VersionCode) { [string]$VersionCode } else { $defaultArg }
$iconArg = if ($iconWsl) { $iconWsl } else { $defaultArg }
$archArg = if ($Arch) { $Arch } else { $defaultArg }
$modeArg = if ($Mode) { $Mode } else { $defaultArg }
$runtimeDebuggerArg = if ($EnableRuntimeDebugger) { '1' } else { '0' }
& wsl.exe -d $Distro -- bash "$runtimeWsl/build_runtime.sh" `
    $outputWsl `
    $projectWsl `
    $packageIdArg `
    $appNameArg `
    $versionNameArg `
    $versionCodeArg `
    $iconArg `
    $runtimeDebuggerArg `
    $modeArg `
    $archArg
if ($LASTEXITCODE -ne 0) {
    throw "Android runtime build failed with exit code $LASTEXITCODE"
}

Write-Host "Android runtime artifacts: $OutputDirectory"
