param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$EvidenceRoot,
    [Parameter(Mandatory = $true)][string]$LogName,
    [Parameter(Mandatory = $true)][string]$TargetCommit,
    [Parameter(Mandatory = $true)][string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$account = $env:INSPECTOR_ACCOUNT
$password = $env:INSPECTOR_PASSWORD
$tempRoot = $env:INSPECTOR_TEMP

if ([string]::IsNullOrWhiteSpace($account) -or
    [string]::IsNullOrWhiteSpace($password) -or
    [string]::IsNullOrWhiteSpace($tempRoot)) {
    throw "Ephemeral Inspector credentials/environment are not initialized"
}
if (-not (Test-Path $Python)) { throw "Python executable not found: $Python" }
if (-not (Test-Path $WorkingDirectory)) { throw "Working directory not found: $WorkingDirectory" }
if (-not (Test-Path $EvidenceRoot)) { throw "Evidence directory not found: $EvidenceRoot" }

$profilePath = Join-Path $env:SystemDrive "Users\$account"
$pythonDirectory = Split-Path -Parent $Python
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $Python
$psi.WorkingDirectory = $WorkingDirectory
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UserName = $account
$psi.Domain = $env:COMPUTERNAME
$psi.Password = $password
$psi.LoadUserProfile = $true

# Deliberately do not inherit GITHUB_WORKSPACE, RUNNER_TEMP, GITHUB_ENV,
# GITHUB_TOKEN, ACTIONS_RUNTIME_TOKEN, cache credentials, or other runner data.
$psi.Environment.Clear()
$psi.Environment["SystemRoot"] = $env:SystemRoot
$psi.Environment["WINDIR"] = $env:WINDIR
$psi.Environment["COMSPEC"] = $env:COMSPEC
$psi.Environment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
$psi.Environment["PATH"] = "$pythonDirectory;$env:SystemRoot\System32;$env:SystemRoot"
$psi.Environment["USERPROFILE"] = $profilePath
$psi.Environment["HOME"] = $profilePath
$psi.Environment["HOMEDRIVE"] = $env:SystemDrive
$psi.Environment["HOMEPATH"] = "\Users\$account"
$psi.Environment["APPDATA"] = Join-Path $profilePath "AppData\Roaming"
$psi.Environment["LOCALAPPDATA"] = Join-Path $profilePath "AppData\Local"
$psi.Environment["TEMP"] = $tempRoot
$psi.Environment["TMP"] = $tempRoot
$psi.Environment["PYTHONUTF8"] = "1"
$psi.Environment["PYTHONIOENCODING"] = "utf-8"
$psi.Environment["PYTHONDONTWRITEBYTECODE"] = "1"
$psi.Environment["GITHUB_SHA"] = $TargetCommit
$psi.Environment["RUNNER_OS"] = "Windows"

foreach ($argument in $Arguments) {
    $psi.ArgumentList.Add([string]$argument)
}

$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $psi
if (-not $process.Start()) { throw "Could not start isolated Inspector process" }

$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$process.WaitForExit()
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()

$stdoutPath = Join-Path $EvidenceRoot $LogName
$stderrPath = Join-Path $EvidenceRoot "$LogName.stderr.txt"
$exitPath = Join-Path $EvidenceRoot "$LogName.exit-code.txt"
Set-Content -Path $stdoutPath -Value $stdout -Encoding utf8
if (-not [string]::IsNullOrEmpty($stderr)) {
    Set-Content -Path $stderrPath -Value $stderr -Encoding utf8
}
Set-Content -Path $exitPath -Value ([string]$process.ExitCode) -Encoding ascii
Write-Output "Inspector SID: $account"
Write-Output "Inspector process exit: $($process.ExitCode)"
