$backup_path="$env:EXIVITY_HOME_PATH/system/backup"
$files = Get-ChildItem -Path "$backup_path/*.zip" -File | Sort-Object LastWriteTime -Descending
$fileChoices = @()

if ($files.count -eq 0) {
    echo "`nError - no valid backups found in $backup_path."
    echo "Should be matching following naming convention: backup_exivity_yyyyMMdd_HH-mm-ss.zip.`nExiting...`n"
    exit
}

if ($files.count -gt 1) {
    for ($i=0; $i -lt $files.Count; $i++) {
      $fileChoices += [System.Management.Automation.Host.ChoiceDescription]("$($files[$i].Name) &$($i+1)")
    }

    $userChoice = $host.UI.PromptForChoice('Select Backup', 'Choose a file to restore', $fileChoices, 0)
    $backup_file=$files[$userChoice].Name
    echo "`nThe following backup has been selected:"
    echo "- $backup_file"

} else {
    $backup_file=$files[0].Name
    echo "`nFound one valid backup`:"
    echo "----------------------------------------"
    echo "- $backup_file`n"
    pause
}

# expand the archive if it does not exist
$backup_directory = $backup_file.Substring(0,$backup_file.Length -4)
if (Test-Path -Path "$backup_path/$backup_directory") {
    echo "backup directory $backup_directory already exists, skipping extraction..."
} else {
    echo "`nexpanding archive from backup $backup_file..."
    
    Expand-Archive "$backup_path/$backup_file" "$backup_path/$backup_directory"
}

$restore_list=Get-ChildItem -Path "$backup_path/$backup_directory" -Directory -Force -ErrorAction SilentlyContinue | Select-Object Name
$restore_dirs=$restore_list.Name
if ($restore_dirs -eq "") {
    echo "ERROR! No data found to restore... "
    echo "`nAborting."
    exit
}
echo "`nThe following items will be restored:"
echo "----------------------------------------"
echo $restore_dirs
echo "----------------------------------------"
echo "`nWARNING!!!"
echo "ALL Existing Data will be overwritten/"
echo "This operation is irreverable."
echo "`nBy continuing your agree to`noverwrite any existing content."
echo "`bTo cancel this restore:`Close this screen or press CTRL-C`n"
pause
echo "=============================================================================="
echo "                              RESTORE STARTED                                 "
echo "=============================================================================="

foreach ($dir in $restore_dirs) {
    echo "restoring $dir..."
    if ($dir -eq "transcript" -Or $dir -eq "use" -Or $dir -eq "edify") {
        echo "  copy $dir to $env:EXIVITY_HOME_PATH/system/config/$dir"
        Copy-Item -Path "$backup_path/$backup_directory/$dir/*" -destination "$env:EXIVITY_HOME_PATH/system/config/$dir/" -Force
    }
    if ($dir -eq "report" -Or $dir -eq "extracted") {
        echo "  extacting $dir to $env:EXIVITY_HOME_PATH/system/"
        #Copy-Item -Path "$backup_path/$backup_directory/$dir" -destination "$env:EXIVITY_HOME_PATH/system/" -Force
        Expand-Archive "$backup_path/$backup_directory/$dir/$dir.zip" "$env:EXIVITY_HOME_PATH/system/$dir/" -Force
    }
    if ($dir -eq "exported" -Or $dir -eq "import") {
        echo "  extracting $dir to $env:EXIVITY_HOME_PATH/"
        #Copy-Item -Path "$backup_path/$backup_directory/$dir" -destination "$env:EXIVITY_HOME_PATH/" -Force
        Expand-Archive "$backup_path/$backup_directory/$dir/$dir.zip" "$env:EXIVITY_HOME_PATH/$dir/" -Force
    }
    if ($dir -eq "env" ) {
        $env_files=Get-ChildItem -Path "$backup_path/$backup_directory/$dir" -File -Force -ErrorAction SilentlyContinue | Select-Object Name
        foreach ($env_file in $env_files) {
            $this_env=$env_file.Name
            $current_env=[Environment]::GetEnvironmentVariable("$this_env")
            echo "  restoring environment variable: $this_env"
            echo "  current value: $current_env"
            $env_value=Get-Content -Path "$backup_path/$backup_directory/$dir/$this_env"
            [System.Environment]::SetEnvironmentVariable("$this_env", "$env_value")
            $new_env=[Environment]::GetEnvironmentVariable("$this_env")
            echo "  new value: $new_env`n"
        }
    }
    if ($dir -eq "db") {
        # set path
        $Env:PATH += ";$env:EXIVITY_PROGRAM_PATH/server/pgsql/bin"
        # read config
        $config_json=Get-Content $env:EXIVITY_HOME_PATH/system/config.json|ConvertFrom-Json
        # load psql vars
        $pg_host=$config_json.db.parameters.host
        $pg_port=$config_json.db.parameters.port
        $pg_sslmode=$config_json.db.parameters.sslmode
        $pg_dbname=$config_json.db.parameters.dbname
        $pg_user=$config_json.db.parameters.user
        $pg_password=$config_json.db.parameters.password
        $env:PGPASSWORD=$pg_password
        pg_restore.exe -c -h $pg_host -p $pg_port -U $pg_user --d $pg_dbname $backup_path/$backup_directory/$dir/database_backup.sql 2> Out-Null
        $workflow_step=pg_restore -f - -Fc -t workflow_step $backup_path/$backup_directory/$dir/database_backup.sql
        $workflow_step=$query.replace("SELECT pg_catalog.set_config('search_path', '', false);","")
        echo "fix for workflow_step..."
        $workflow_step|psql.exe -h $pg_host -p $pg_port -U $pg_user -d $pg_dbname 2> Out-Null
    }
}

echo "=============================================================================="
echo "                              RESTORE FINISHED                                "
echo "=============================================================================="