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
if ([string]::IsNullOrWhiteSpace($account) -or [string]::IsNullOrWhiteSpace($password) -or [string]::IsNullOrWhiteSpace($tempRoot)) { throw "Inspector credentials/environment missing" }
if (-not (Test-Path $Python) -or -not (Test-Path $WorkingDirectory) -or -not (Test-Path $EvidenceRoot)) { throw "Required path missing" }

$stdoutPath = Join-Path $EvidenceRoot $LogName
$stderrPath = Join-Path $EvidenceRoot "$LogName.stderr.txt"
$exitPath = Join-Path $EvidenceRoot "$LogName.exit-code.txt"
$launcherPath = Join-Path $tempRoot "guardian-inspector-launch.py"
$configPath = Join-Path $tempRoot "guardian-inspector-launch.json"
$innerStdout = Join-Path $tempRoot "$LogName.stdout"
$innerStderr = Join-Path $tempRoot "$LogName.stderr"
$innerExit = Join-Path $tempRoot "$LogName.exit"
$profilePath = Join-Path $env:SystemDrive "Users\$account"

$launcher = @'
import json
import pathlib
import subprocess
import sys

config_path = pathlib.Path(sys.argv[1])
config = json.loads(config_path.read_text(encoding="utf-8-sig"))
try:
    result = subprocess.run(
        [config["python"], *config["arguments"]],
        cwd=config["working_directory"],
        env=config["environment"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    pathlib.Path(config["stdout"]).write_bytes(result.stdout)
    pathlib.Path(config["stderr"]).write_bytes(result.stderr)
    pathlib.Path(config["exit"]).write_text(str(result.returncode), encoding="ascii")
except Exception as exc:
    pathlib.Path(config["stderr"]).write_text(repr(exc), encoding="utf-8")
    pathlib.Path(config["exit"]).write_text("125", encoding="ascii")
    raise
sys.exit(result.returncode)
'@
$launcher | Set-Content -Path $launcherPath -Encoding utf8
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
$credential = [System.Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$account", $securePassword)

$bootstrapPython = (Get-Command python -ErrorAction Stop).Source
$originalEnvironment = [Environment]::GetEnvironmentVariables("Process")
try {
    foreach ($key in @($originalEnvironment.Keys)) {
        [Environment]::SetEnvironmentVariable([string]$key, $null, "Process")
    }
    $minimal = @{
        SystemRoot = $env:SystemRoot
        WINDIR = $env:SystemRoot
        COMSPEC = "$env:SystemRoot\System32\cmd.exe"
        PATHEXT = ".COM;.EXE;.BAT;.CMD"
        PATH = "$(Split-Path -Parent $Python);$env:SystemRoot\System32;$env:SystemRoot"
        USERNAME = $account
        USERDOMAIN = $env:COMPUTERNAME
        USERPROFILE = $profilePath
        HOME = $profilePath
        HOMEDRIVE = $env:SystemDrive
        HOMEPATH = "\Users\$account"
        APPDATA = (Join-Path $profilePath "AppData\Roaming")
        LOCALAPPDATA = (Join-Path $profilePath "AppData\Local")
        TEMP = $tempRoot
        TMP = $tempRoot
        PYTHONUTF8 = "1"
        PYTHONIOENCODING = "utf-8"
        PYTHONDONTWRITEBYTECODE = "1"
        GITHUB_SHA = $TargetCommit
        RUNNER_OS = "Windows"
    }
    foreach ($entry in $minimal.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
    }
    $config = @{
        python = $Python
        arguments = @($Arguments)
        working_directory = $WorkingDirectory
        environment = $minimal
        stdout = $innerStdout
        stderr = $innerStderr
        exit = $innerExit
    }
    $config | ConvertTo-Json -Depth 8 | Set-Content -Path $configPath -Encoding utf8
    $quotedConfig = '"' + $configPath.Replace('"', '\"') + '"'
    $process = Start-Process -FilePath $bootstrapPython -Credential $credential -LoadUserProfile -WorkingDirectory $WorkingDirectory -ArgumentList @($launcherPath, $configPath) -Wait -PassThru
    if (-not (Test-Path $innerExit)) { throw "Inspector launcher did not write an exit code; outer exit=$($process.ExitCode)" }
    $innerCode = [int](Get-Content $innerExit -Raw)
    if (Test-Path $innerStdout) { Copy-Item $innerStdout $stdoutPath -Force } else { [IO.File]::WriteAllText($stdoutPath, "") }
    if (Test-Path $innerStderr) { Copy-Item $innerStderr $stderrPath -Force } else { [IO.File]::WriteAllText($stderrPath, "") }
    Set-Content -Path $exitPath -Value ([string]$innerCode) -Encoding ascii
    Write-Output "Inspector account: $account"
    Write-Output "Inspector process exit: $innerCode"
    if ($innerCode -ne 0) {
        if (Test-Path $stderrPath) { Write-Output "Inspector stderr:"; Get-Content $stderrPath -Raw | Write-Output }
        throw "Inspector child process failed: $innerCode"
    }
}
finally {
    foreach ($key in @([Environment]::GetEnvironmentVariables("Process").Keys)) {
        [Environment]::SetEnvironmentVariable([string]$key, $null, "Process")
    }
    foreach ($entry in $originalEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value, "Process")
    }
}
