# Constansts that control the script
$VERSION = "1.0.0"
$PROVIDER = "Anatel"
$ENV_NAME = "regulatronCataloger"
$MINICONDA_PATH = "c:\ProgramData\miniconda3"
$MINICONDA_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$REPETITION_INTERVAL = 60 # Minutes between each run of the service
$TASK_NAME = "FileCatalogService"
$TASK_DESCRIPTION = "Regulatron file cataloging tool file_catalog.py."

# Define download URLs
$urls = @{
    "config.json" = "https://raw.githubusercontent.com/InovaFiscaliza/Tools/refs/heads/main/FileCataloger/src/config.json";
    "file_catalog.exe" = "https://raw.githubusercontent.com/InovaFiscaliza/Tools/refs/heads/main/FileCataloger/src/file_catalog.py";
    "environment.yml" = "https://raw.githubusercontent.com/InovaFiscaliza/Tools/refs/heads/main/FileCataloger/environment.yml"
}

# Print splash screen
$colunas = $Host.UI.RawUI.BufferSize.Width
Write-Host "`n"
Write-Host ("~" * $colunas) -ForegroundColor Green
Write-Host "REGULATRON" -ForegroundColor Green
Write-Host "Script de instalação de catalogador de arquivos" -ForegroundColor Green
Write-Host "Versão: $VERSION" -ForegroundColor Green
Write-Host ("~" * $colunas) -ForegroundColor Green
Write-Host "`n"



# Define, test and create download directory using current user download folder
$downloadDir = [System.IO.Path]::Combine((New-Object -ComObject Shell.Application).Namespace('shell:Downloads').Self.Path, $ENV_NAME)
if (!(Test-Path -Path $downloadDir)) {
    if (!(New-Item -ItemType Directory -Path $downloadDir)) {
        Write-Output "Failed to create download directory. Exiting script."
        exit 1
    }
}

# Define, test and create the installation path using the Program Files directory
$installPath = [System.IO.Path]::Combine($env:ProgramData, $PROVIDER, $ENV_NAME)
if (!(Test-Path -Path $installPath)) {
    if (!(New-Item -ItemType Directory -Path $installPath)) {
        Write-Output "Failed to create installation directory. Exiting script."
        exit 1
    }
}

# Download required files from the URLs defined above
foreach ($fileName in $urls.Keys) {
    $url = $urls[$fileName]
    $filePath = Join-Path -Path $downloadDir -ChildPath $fileName
    Invoke-WebRequest -Uri $url -OutFile $filePath
    Write-Output "Downloaded $fileName to $filePath"
}

#test if miniconda is already installed
if (!(Test-Path -Path $MINICONDA_PATH)) {
    # Download the Miniconda installer
    $downloadFileName = "Miniconda3-latest-Windows-x86_64.exe"
    $minicondaPath = Join-Path -Path $downloadDir -ChildPath $downloadFileName
    Invoke-WebRequest -Uri $MINICONDA_URL -OutFile $
    Write-Output "Downloaded Miniconda installer to $minicondaPath"

    # Install Miniconda silently in the install directory
    & $downloadDir/$downloadFileName /InstallationType=JustMe /AddToPath=0 /RegisterPython=0 /S /D=$MINICONDA_PATH
    Write-Output "Miniconda installed to $MINICONDA_PATH"
}

# Define the path to the Conda executable
$condaExecutable = [System.IO.Path]::Combine($MINICONDA_PATH, "Scripts\conda.exe")

# Create the Conda environment within the install directory
Write-Output "Creating Conda environment..."
& $condaExecutable create --name $ENV_NAME --file $downloadDir\environment.yml -y

# Verify environment creation (last command output is stored in $?)
if (-not $?) {
    Write-Output "Failed to create Conda environment. Exiting script."
    exit 1
}
Write-Output "Conda environment '$ENV_NAME' created successfully."

# move the config file and file_catalog.py to the install directory
Move-Item -Path "$downloadDir\config.json" -Destination "$installPath\config.json"
Move-Item -Path "$downloadDir\file_catalog.py" -Destination "$installPath\file_catalog.py"

# Remove download folder
Remove-Item -Path $downloadDir -Recurse

# Create a batch file to run the Python script in the Conda environment
$batchFilePath = [System.IO.Path]::Combine($installPath, "run_file_catalog.bat")
$batchContent = @"
@echo off
call "$condaPath\Scripts\activate.bat" $ENV_NAME
python "$installPath\file_catalog.py"
"@
$batchContent | Out-File -FilePath $batchFilePath -Encoding UTF8

# Define trigger, action, and settings for the scheduled task
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.RepetitionInterval = (New-TimeSpan -Minutes $REPETITION_INTERVAL)
$trigger.RepetitionDuration = [TimeSpan]::MaxValue

$action = New-ScheduledTaskAction -Execute $batchFilePath

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -RestartInterval (New-TimeSpan -Minutes $REPETITION_INTERVAL) `
    -RestartCount 3 `
    -MultipleInstances IgnoreNew

# Register the scheduled task
Register-ScheduledTask -TaskName $TASK_NAME `
    -Description $TASK_DESCRIPTION
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -RunLevel Highest `
    -User "SYSTEM"

Write-Output "Scheduled task '$TASK_NAME' created successfully."
