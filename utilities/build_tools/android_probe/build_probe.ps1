[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [string]$Distro = 'Ubuntu-24.04'
)

$ErrorActionPreference = 'Stop'
$probeRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $probeRoot 'artifacts'
}

$wslStatus = & wsl.exe --list --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "WSL2 is not installed or initialized.`n$($wslStatus -join [Environment]::NewLine)"
}
if ($Distro -notin $wslStatus) {
    throw "WSL distro '$Distro' was not found. Available distros: $($wslStatus -join ', ')"
}

$probeInterop = $probeRoot.Replace('\', '/')
$outputInterop = $OutputDirectory.Replace('\', '/')
$probeWsl = (& wsl.exe -d $Distro -- wslpath -a $probeInterop).Trim()
$outputWsl = (& wsl.exe -d $Distro -- wslpath -a $outputInterop).Trim()
if (-not $probeWsl -or -not $outputWsl) {
    throw 'Could not translate the probe/output paths into WSL paths.'
}

& wsl.exe -d $Distro -- bash "$probeWsl/build_probe.sh" $outputWsl
if ($LASTEXITCODE -ne 0) {
    throw "Android probe build failed with exit code $LASTEXITCODE"
}

Write-Host "Android probe artifacts: $OutputDirectory"
