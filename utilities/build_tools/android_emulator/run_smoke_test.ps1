[CmdletBinding()]
param(
    [string]$ApkPath = "",
    [string]$PackageId = "",
    [string]$AvdName = "LT_API36",
    [ValidateRange(5554, 5682)]
    [int]$EmulatorPort = 5556,
    [ValidateRange(5, 600)]
    [int]$LaunchWaitSeconds = 20,
    [ValidateRange(30, 900)]
    [int]$BootTimeoutSeconds = 300,
    [string]$AndroidSdk = "",
    [string]$InputScript = "",
    [string]$OutputDirectory = "",
    [switch]$ShowWindow,
    [switch]$KeepEmulator
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $scriptRoot "..\..\..")
)

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
$adb = Join-Path $AndroidSdk "platform-tools\adb.exe"
$emulator = Join-Path $AndroidSdk "emulator\emulator.exe"
$aaptCandidates = @(
    Get-ChildItem -LiteralPath (Join-Path $AndroidSdk "build-tools") `
        -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "aapt.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
)

foreach ($tool in @($adb, $emulator)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required Android SDK tool was not found: $tool"
    }
}
if (-not $aaptCandidates) {
    throw "No aapt.exe was found under $AndroidSdk\build-tools."
}
$aapt = $aaptCandidates[0]

if (-not $ApkPath) {
    $aliases = @(
        Get-ChildItem -LiteralPath $repoRoot -Directory -ErrorAction Stop |
        Where-Object { $_.Name -like "*_android_build" } |
        ForEach-Object {
            Get-ChildItem -LiteralPath $_.FullName `
                -Filter "lt-android-runtime-arm64-debug.apk" `
                -File -ErrorAction SilentlyContinue
        } |
        Sort-Object LastWriteTime -Descending
    )
    if (-not $aliases) {
        throw "No Android APK alias was found. Pass -ApkPath explicitly."
    }
    $ApkPath = $aliases[0].FullName
}

$ApkPath = [System.IO.Path]::GetFullPath($ApkPath)
if (-not (Test-Path -LiteralPath $ApkPath -PathType Leaf)) {
    throw "APK was not found: $ApkPath"
}
$apkSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ApkPath).Hash

$badging = (& $aapt dump badging $ApkPath 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "aapt could not inspect the APK.`n$badging"
}
$packageMatch = [regex]::Match($badging, "package: name='([^']+)'")
if (-not $PackageId) {
    if (-not $packageMatch.Success) {
        throw "Could not derive the package ID from the APK."
    }
    $PackageId = $packageMatch.Groups[1].Value
}
$launchActivityMatch = [regex]::Match(
    $badging,
    "launchable-activity: name='([^']+)'"
)
if (-not $launchActivityMatch.Success) {
    throw "Could not derive the launch activity from the APK."
}
$launchActivity = $launchActivityMatch.Groups[1].Value

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path (Split-Path -Parent $ApkPath) "emulator-tests"
}
$timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$resultDirectory = Join-Path (
    [System.IO.Path]::GetFullPath($OutputDirectory)
) $timestamp
[System.IO.Directory]::CreateDirectory($resultDirectory) | Out-Null

$serial = "emulator-$EmulatorPort"
$startedEmulator = $false
$emulatorProcess = $null
$testPassed = $false
$failureReason = ""
$installOutput = ""
$launchOutput = ""
$pidValue = ""
$deviceAbi = ""
$androidVersion = ""

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $previousErrorAction = $ErrorActionPreference
    try {
        # adb writes some successful command diagnostics to stderr. Preserve
        # that output without letting Windows PowerShell turn it into a
        # terminating NativeCommandError.
        $ErrorActionPreference = "Continue"
        & $script:adb -s $script:serial @Arguments
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Test-EmulatorReady {
    $previousErrorAction = $ErrorActionPreference
    try {
        # An absent emulator is an expected probe result. Windows PowerShell
        # otherwise promotes adb's stderr text into a terminating error.
        $ErrorActionPreference = "Continue"
        $stateOutput = & $script:adb -s $script:serial get-state 2>$null
        $stateExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $state = $stateOutput -join ""
    return $stateExitCode -eq 0 -and $state.Trim() -eq "device"
}

function Save-Screenshot {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:adb
    $startInfo.Arguments = "-s $script:serial exec-out screencap -p"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Could not start adb screenshot capture."
    }
    $file = [System.IO.File]::Create($Path)
    try {
        $process.StandardOutput.BaseStream.CopyTo($file)
    }
    finally {
        $file.Dispose()
    }
    $errorText = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "Screenshot capture failed: $errorText"
    }
}

function Invoke-InputActions {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Input action script was not found: $Path"
    }
    $parsedActions = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    # Windows PowerShell can preserve a JSON array as one pipeline object
    # inside @(...), which makes every action appear as a single combined
    # value ("wait tap ..."). Keep a one-action JSON object supported while
    # enumerating arrays one action at a time.
    $actions = if ($parsedActions -is [System.Array]) {
        $parsedActions
    }
    else {
        @($parsedActions)
    }
    $step = 0
    foreach ($action in $actions) {
        $step += 1
        switch ([string]$action.action) {
            "wait" {
                Start-Sleep -Milliseconds ([int]$action.milliseconds)
            }
            "tap" {
                Invoke-Adb shell input tap ([int]$action.x) ([int]$action.y) |
                    Out-Null
            }
            "keyevent" {
                Invoke-Adb shell input keyevent ([string]$action.keycode) |
                    Out-Null
            }
            "screenshot" {
                $safeName = ([string]$action.name) -replace "[^A-Za-z0-9_.-]", "_"
                Save-Screenshot (
                    Join-Path $script:resultDirectory (
                        "{0:D2}-{1}.png" -f $step, $safeName
                    )
                )
            }
            default {
                throw "Unsupported input action at step ${step}: $($action.action)"
            }
        }
    }
}

try {
    if (-not (Test-EmulatorReady)) {
        $emulatorArguments = @(
            "-avd", $AvdName,
            "-port", [string]$EmulatorPort,
            "-no-boot-anim",
            "-no-audio",
            "-no-snapshot",
            "-gpu", "auto"
        )
        if (-not $ShowWindow) {
            $emulatorArguments += "-no-window"
        }
        $startParameters = @{
            FilePath = $emulator
            ArgumentList = $emulatorArguments
            RedirectStandardOutput = (Join-Path $resultDirectory "emulator.stdout.log")
            RedirectStandardError = (Join-Path $resultDirectory "emulator.stderr.log")
            PassThru = $true
        }
        if (-not $ShowWindow) {
            $startParameters["WindowStyle"] = "Hidden"
        }
        $emulatorProcess = Start-Process @startParameters
        $startedEmulator = $true
    }

    $bootDeadline = [DateTime]::UtcNow.AddSeconds($BootTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $bootDeadline) {
        if (Test-EmulatorReady) {
            $bootComplete = (
                Invoke-Adb shell getprop sys.boot_completed 2>$null
            ) -join ""
            if ($bootComplete.Trim() -eq "1") {
                break
            }
        }
        if ($startedEmulator -and $emulatorProcess.HasExited) {
            throw "Emulator exited before Android finished booting."
        }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-EmulatorReady)) {
        throw "Emulator did not become ready within $BootTimeoutSeconds seconds."
    }
    $bootComplete = (Invoke-Adb shell getprop sys.boot_completed) -join ""
    if ($bootComplete.Trim() -ne "1") {
        throw "Android did not finish booting within $BootTimeoutSeconds seconds."
    }

    Invoke-Adb shell wm dismiss-keyguard | Out-Null
    Invoke-Adb shell settings put system accelerometer_rotation 0 | Out-Null
    Invoke-Adb shell settings put system user_rotation 1 | Out-Null
    Invoke-Adb shell settings put secure immersive_mode_confirmations confirmed |
        Out-Null
    $deviceAbi = ((Invoke-Adb shell getprop ro.product.cpu.abilist) -join "").Trim()
    $androidVersion = (
        (Invoke-Adb shell getprop ro.build.version.release) -join ""
    ).Trim()

    $installOutput = (
        Invoke-Adb install -r -t $ApkPath 2>&1
    ) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $installOutput -notmatch "Success") {
        throw "APK installation failed.`n$installOutput"
    }
    $apkSha256AfterInstall = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $ApkPath
    ).Hash
    if ($apkSha256AfterInstall -ne $apkSha256) {
        throw "APK changed while the smoke test was installing it."
    }

    Invoke-Adb logcat -c | Out-Null
    Invoke-Adb shell am force-stop $PackageId | Out-Null
    $launchComponent = "$PackageId/$launchActivity"
    $launchArguments = @(
        "shell", "am", "start", "-W", "-n", $launchComponent
    )
    $launchOutput = (
        Invoke-Adb -Arguments $launchArguments 2>&1
    ) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $launchOutput -match "(?m)^Error:") {
        throw "APK launch command failed.`n$launchOutput"
    }

    Start-Sleep -Seconds $LaunchWaitSeconds
    if ($InputScript) {
        Invoke-InputActions ([System.IO.Path]::GetFullPath($InputScript))
    }

    Save-Screenshot (Join-Path $resultDirectory "final.png")
    $pidValue = ((Invoke-Adb shell pidof $PackageId 2>$null) -join "").Trim()
    $logcatArguments = @("logcat", "-d", "-v", "threadtime")
    $logcat = (
        Invoke-Adb -Arguments $logcatArguments 2>&1
    ) -join "`n"
    [System.IO.File]::WriteAllText(
        (Join-Path $resultDirectory "logcat.txt"),
        $logcat + "`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $fatalPattern = (
        "FATAL EXCEPTION|Fatal signal|ANR in " +
        [regex]::Escape($PackageId) +
        "|Process " + [regex]::Escape($PackageId) +
        " .* has died|Traceback \(most recent call last\)"
    )
    $fatalMatches = @(
        $logcat -split "`r?`n" |
        Where-Object { $_ -match $fatalPattern }
    )
    [System.IO.File]::WriteAllLines(
        (Join-Path $resultDirectory "fatal-lines.txt"),
        $fatalMatches,
        [System.Text.UTF8Encoding]::new($false)
    )

    if (-not $pidValue) {
        throw "App process is not running after $LaunchWaitSeconds seconds."
    }
    if ($fatalMatches.Count -gt 0) {
        throw "Fatal Android/Python log entries were detected."
    }
    $testPassed = $true
}
catch {
    $failureReason = $_.Exception.Message
}
finally {
    $report = [ordered]@{
        schema_version = 1
        passed = $testPassed
        timestamp_utc = $timestamp
        apk = $ApkPath
        apk_sha256 = $apkSha256
        package_id = $PackageId
        launch_activity = $launchActivity
        avd = $AvdName
        serial = $serial
        android_version = $androidVersion
        device_abis = $deviceAbi
        app_pid = $pidValue
        launch_wait_seconds = $LaunchWaitSeconds
        input_script = $InputScript
        install_output = $installOutput
        launch_output = $launchOutput
        failure = $failureReason
        result_directory = $resultDirectory
    }
    $json = $report | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText(
        (Join-Path $resultDirectory "report.json"),
        $json + "`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    if ($startedEmulator -and -not $KeepEmulator) {
        try {
            Invoke-Adb emu kill | Out-Null
        }
        catch {
            # The process fallback below handles an emulator that stopped
            # responding before adb could deliver the shutdown command.
        }
        if ($emulatorProcess) {
            $shutdownDeadline = [DateTime]::UtcNow.AddSeconds(30)
            while (
                -not $emulatorProcess.HasExited -and
                [DateTime]::UtcNow -lt $shutdownDeadline
            ) {
                Start-Sleep -Milliseconds 500
                $emulatorProcess.Refresh()
            }
            if (-not $emulatorProcess.HasExited) {
                Stop-Process `
                    -Id $emulatorProcess.Id `
                    -Force `
                    -ErrorAction SilentlyContinue
            }
        }
    }
}

if (-not $testPassed) {
    Write-Error "ANDROID_EMULATOR_SMOKE_FAILED: $failureReason`nResults: $resultDirectory"
    exit 1
}

Write-Host "ANDROID_EMULATOR_SMOKE_OK"
Write-Host "Package: $PackageId"
Write-Host "Android: $androidVersion"
Write-Host "Device ABIs: $deviceAbi"
Write-Host "App PID: $pidValue"
Write-Host "Results: $resultDirectory"
