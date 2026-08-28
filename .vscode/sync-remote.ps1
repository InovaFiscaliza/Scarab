[CmdletBinding()]
param(
    [string]$SshHost = "ContainerHost",
    [string]$RemoteRoot = "services/scarab"
)

$ErrorActionPreference = "Stop"

if ([System.IO.Path]::IsPathRooted($RemoteRoot) -or $RemoteRoot.StartsWith("..")) {
    throw "RemoteRoot must be a path relative to the remote user's home directory."
}

$repositoryRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
    throw "The current workspace is not a Git repository."
}

$deletedFiles = @(& git -C $repositoryRoot diff --name-only --diff-filter=D HEAD --)
if ($LASTEXITCODE -ne 0) {
    throw "Failed to inspect deleted Git files."
}
if ($deletedFiles.Count -gt 0) {
    throw "Remote sync does not delete files. Commit and push deletions, then update the remote checkout."
}

$trackedFiles = @(& git -C $repositoryRoot diff --name-only --diff-filter=ACMRTUXB HEAD --)
if ($LASTEXITCODE -ne 0) {
    throw "Failed to inspect modified Git files."
}

$untrackedFiles = @(& git -C $repositoryRoot ls-files --others --exclude-standard)
if ($LASTEXITCODE -ne 0) {
    throw "Failed to inspect untracked Git files."
}

$blockedFiles = @(".env", "config/config.json")
$files = @($trackedFiles + $untrackedFiles) |
    ForEach-Object { $_.Replace("\", "/") } |
    Where-Object { $_ -and $_ -notin $blockedFiles } |
    Sort-Object -Unique

if ($files.Count -eq 0) {
    Write-Output "No local changes need to be synchronized."
    exit 0
}

foreach ($relativePath in $files) {
    if ($relativePath.Contains("'") -or $relativePath.Contains("`n") -or $relativePath.Contains("`r")) {
        throw "Unsupported path for remote synchronization: $relativePath"
    }

    $localPath = Join-Path $repositoryRoot $relativePath
    if (-not (Test-Path -LiteralPath $localPath -PathType Leaf)) {
        throw "Local file not found: $localPath"
    }

    $remotePath = "$RemoteRoot/$relativePath"
    $remoteParent = $remotePath.Substring(0, $remotePath.LastIndexOf("/"))

    & ssh -o BatchMode=yes $SshHost "mkdir -p -- '$remoteParent'"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the remote directory for $relativePath."
    }

    & scp -q -o BatchMode=yes -- $localPath "${SshHost}:$remotePath"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to synchronize $relativePath."
    }

    Write-Output "Synchronized $relativePath"
}