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
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
$credential = [System.Management.Automation.PSCredential]::new("$env:COMPUTERNAME\$account", $securePassword)

function Quote-WindowsArgument([string]$value) {
    if ($value -notmatch '[\s"]') { return $value }
    $escaped = $value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}
$argumentLine = (@($Arguments | ForEach-Object { Quote-WindowsArgument ([string]$_) }) -join ' ')
$pythonDirectory = Split-Path -Parent $Python
$profilePath = Join-Path $env:SystemDrive "Users\$account"
$childEnvironment = @{
    SystemRoot = $env:SystemRoot
    WINDIR = $env:SystemRoot
    COMSPEC = $env:COMSPEC
    PATHEXT = ".COM;.EXE;.BAT;.CMD"
    PATH = "$pythonDirectory;$env:SystemRoot\System32;$env:SystemRoot"
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
$process = Start-Process -FilePath $Python -Credential $credential -LoadUserProfile -WorkingDirectory $WorkingDirectory -ArgumentList $argumentLine -Environment $childEnvironment -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -Wait -PassThru
Set-Content -Path $exitPath -Value ([string]$process.ExitCode) -Encoding ascii
Write-Output "Inspector account: $account"
Write-Output "Inspector process exit: $($process.ExitCode)"
