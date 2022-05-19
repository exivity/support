using namespace System.Management.Automation.Host
function backup_menu {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$title,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$question,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$component
    )
    
    $no = [ChoiceDescription]::new('&No', "Will be skipping backing up of $component.")
    $yes = [ChoiceDescription]::new('&Yes', "$component will be included with this backup")

    $options = [ChoiceDescription[]]($no, $yes)

    $result = $host.ui.PromptForChoice($Title, $Question, $options, 0)

    switch ($result) {
        0 { $global:backup=0 }
        1 { $global:backup=1 }
    }

}
$home_drive=[char[]]"$env:EXIVITY_HOME_PATH"[0]
$home_drive_free=[math]::Round(((Get-Volume -DriveLetter $home_drive).SizeRemaining)/1024/1024/1024,2)

echo "=============================================================================="
echo "Before starting, ensure that enough disk space is available on $home_drive"
echo "Disk space currenly available on $home_drive : $home_drive_free GiB"
echo "=============================================================================="
# do we need to backup exported?
$exported_folder="$env:EXIVITY_HOME_PATH/exported"
$exported_size=[math]::Round(((Get-ChildItem $exported_folder -Recurse| Measure-Object -Property Length -sum).Sum)/1024/1024/1024,2)
backup_menu "Exported data folder:`n-----------------------" "Do you want to include $exported_folder in the backup? `nThis will require an additional $exported_size GiB of backup storage`n`n(NOTE - data will be compressed)`n" "Exported folder"
$exported_result="$global:backup"

# do we need to backup extracted?
$extracted_folder="$env:EXIVITY_HOME_PATH/system/extracted"
$extracted_size=[math]::Round(((Get-ChildItem $extracted_folder -Recurse| Measure-Object -Property Length -sum).Sum)/1024/1024/1024,2)
backup_menu "Extracted data folder:`n-----------------------" "Do you want to include $extracted_folder in the backupt?`nThis will require an additional $extracted_size GiB of backup storage`n`n(NOTE - data will be compressed)`n" "Extracted folder"
$extracted_result=$global:backup

# read config
$config_json=Get-Content $env:EXIVITY_HOME_PATH/system/config.json|ConvertFrom-Json
# load psql vars
$pg_host=$config_json.db.parameters.host
$pg_port=$config_json.db.parameters.port
$pg_sslmode=$config_json.db.parameters.sslmode
$pg_dbname=$config_json.db.parameters.dbname
$pg_user=$config_json.db.parameters.user
$pg_password=$config_json.db.parameters.password
# timestamp
$timestamp=get-date -format "yyyyMMdd_HH-mm-ss"
$backup_target="$env:EXIVITY_HOME_PATH/system/backup/$timestamp"
mkdir $backup_target | Out-Null


echo "=============================================================================="
echo "                              BACKUP STARTED                                  "
echo "=============================================================================="
echo "backup database..."
$backup_target_db="$backup_target/db"
mkdir $backup_target_db | Out-Null
$env:PGPASSWORD=$pg_password
Invoke-Expression -Command "$env:EXIVITY_PROGRAM_PATH/server/pgsql/bin/pg_dump.exe -E UTF8 -f $backup_target_db/database_backup.sql -Fc -T *pgp_* --clean -h $pg_host -p $pg_port -U $pg_user $pg_dbname "

echo "backup environment variables..."
$backup_target_env="$backup_target/env"
mkdir $backup_target_env | Out-Null
echo "$env:EXIVITY_APP_KEY">"$backup_target_env/EXIVITY_APP_KEY"
echo "$env:EXIVITY_JWT_SECRET">"$backup_target_env/EXIVITY_JWT_SECRET"

echo "backup extractor scripts..."
$backup_target_use="$backup_target/use"
mkdir $backup_target_use | Out-Null
Copy-Item -Path $env:EXIVITY_HOME_PATH/system/config/use/*.use -Destination $backup_target_use -Force -Recurse

echo "backup transformer scripts..."
$backup_target_transcript="$backup_target/transcript"
mkdir $backup_target_transcript | Out-Null
Copy-Item -Path $env:EXIVITY_HOME_PATH/system/config/transcript/*.trs -Destination $backup_target_transcript -Force -Recurse

echo "backup rdf data files..."
$backup_target_rdf="$backup_target/report"
mkdir $backup_target_rdf | Out-Null
#Copy-Item -Path $env:EXIVITY_HOME_PATH/system/report/* -Destination $backup_target_rdf -Force -Recurse
Compress-Archive -Path $env:EXIVITY_HOME_PATH/system/report/* -DestinationPath $backup_target_rdf/report.zip

echo "backup import & lookup data..."
$backup_target_lookup="$backup_target/import"
mkdir $backup_target_lookup | Out-Null
#Copy-Item -Path $env:EXIVITY_HOME_PATH/import/*.csv -Destination $backup_target_lookup -Force -Recurse
Compress-Archive -Path $env:EXIVITY_HOME_PATH/import/* -DestinationPath $backup_target_lookup/import.zip

if ($exported_result -eq 1) {
    echo "backup exported folder..."
    $backup_exported_folder="$backup_target/exported"
    mkdir $backup_exported_folder | Out-Null
    Compress-Archive -Path $env:EXIVITY_HOME_PATH/exported/* -DestinationPath $backup_target/exported/exported.zip
}

if ($extracted_result -eq 1) {
    echo "backup extracted folder..."
    $backup_extracted_folder="$backup_target/extracted"
    mkdir $backup_extracted_folder | Out-Null
    Compress-Archive -Path $env:EXIVITY_HOME_PATH/system/extracted/* -DestinationPath $backup_target/extracted/extracted.zip
}

echo "creating backup zip file..."
Compress-Archive -Path $backup_target/* -DestinationPath $backup_target/../backup_exivity_$timestamp.zip

echo "cleanup..."
remove-item "$backup_target" -Recurse -Force

echo "=============================================================================="
echo "                              BACKUP FINISHED                                  "
echo "=============================================================================="