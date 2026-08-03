[CmdletBinding()]
param(
    [string]$AvdName = "LT_API36",
    [string]$SystemImage = "system-images;android-36;google_apis;x86_64",
    [string]$Device = "pixel_6",
    [string]$AndroidSdk = "",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $AndroidSdk) {
    if ($env:ANDROID_SDK_ROOT) {
        $AndroidSdk = $env:ANDROID_SDK_ROOT
    }
    elseif ($env:ANDROID_HOME) {
        $AndroidSdk = $env:ANDROID_HOME
    }
    else {
        $AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
    }
}

$AndroidSdk = [System.IO.Path]::GetFullPath($AndroidSdk)
$sdkManager = Join-Path $AndroidSdk "cmdline-tools\latest\bin\sdkmanager.bat"
$avdManager = Join-Path $AndroidSdk "cmdline-tools\latest\bin\avdmanager.bat"
$emulator = Join-Path $AndroidSdk "emulator\emulator.exe"
$adb = Join-Path $AndroidSdk "platform-tools\adb.exe"

foreach ($tool in @($sdkManager, $avdManager, $adb)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required Android SDK tool was not found: $tool"
    }
}

if ($AvdName -notmatch "^[A-Za-z0-9_.-]+$") {
    throw "AVD name may contain only letters, numbers, dot, underscore, and dash."
}

$previousErrorAction = $ErrorActionPreference
try {
    # Windows PowerShell can promote native stderr warnings into terminating
    # NativeCommandError records while 2>&1 is active.
    $ErrorActionPreference = "Continue"
    $installedPackageOutput = & $sdkManager --list_installed 2>&1
    $installedPackageExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorAction
}
$installedPackages = $installedPackageOutput -join "`n"
if ($installedPackageExitCode -ne 0) {
    throw "Could not query installed Android SDK packages.`n$installedPackages"
}

$requiredPackages = @("emulator", $SystemImage)
foreach ($package in $requiredPackages) {
    if ($installedPackages -notmatch [regex]::Escape($package)) {
        Write-Host "Installing missing Android SDK package: $package"
        & $sdkManager $package
        if ($LASTEXITCODE -ne 0) {
            throw "Android SDK package installation failed: $package"
        }
    }
}

if (-not (Test-Path -LiteralPath $emulator -PathType Leaf)) {
    throw "Android Emulator is still missing after package installation: $emulator"
}

$avdHome = if ($env:ANDROID_AVD_HOME) {
    [System.IO.Path]::GetFullPath($env:ANDROID_AVD_HOME)
}
else {
    Join-Path $env:USERPROFILE ".android\avd"
}
$avdIni = Join-Path $avdHome "$AvdName.ini"
$avdDirectory = Join-Path $avdHome "$AvdName.avd"
$avdExists = (
    (Test-Path -LiteralPath $avdIni -PathType Leaf) -and
    (Test-Path -LiteralPath (
        Join-Path $avdDirectory "config.ini"
    ) -PathType Leaf)
)
if ($avdExists -and $Recreate) {
    Write-Host "Deleting existing AVD: $AvdName"
    & $avdManager delete avd --name $AvdName
    if ($LASTEXITCODE -ne 0) {
        throw "Could not delete AVD: $AvdName"
    }
    $avdExists = $false
}

if (-not $avdExists) {
    Write-Host "Creating AVD $AvdName from $SystemImage"
    "no" | & $avdManager create avd `
        --force `
        --name $AvdName `
        --package $SystemImage `
        --device $Device
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create AVD: $AvdName"
    }
}
else {
    Write-Host "AVD already exists: $AvdName"
}

$acceleration = (& $emulator -accel-check 2>&1) -join "`n"
if (
    -not (Test-Path -LiteralPath $avdIni -PathType Leaf) -or
    -not (Test-Path -LiteralPath (
        Join-Path $avdDirectory "config.ini"
    ) -PathType Leaf)
) {
    throw "AVD configuration files are missing for: $AvdName"
}

Write-Host ""
Write-Host "Android emulator setup is ready."
Write-Host "SDK: $AndroidSdk"
Write-Host "AVD: $AvdName"
Write-Host "System image: $SystemImage"
Write-Host "Acceleration check:"
Write-Host $acceleration
