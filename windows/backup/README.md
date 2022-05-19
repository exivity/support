# Backup and Restore scripts

## backup_exivity.ps1
This script can be used for backing up the important user data from a source system and storing them inside a zip archive. The zip archive will be stored in EXIVITY_HOME_PATH/system/backup.

Quick execute tip:
`$script=wget https://raw.githubusercontent.com/exivity/support/main/windows/backup/backup_exivity.ps1;echo "$script.content" | powershell -noprofile -command { $input | iex }`

## restore_exivity.ps1
This script can be used for restoring user data of Exivity which has been created using the backup_exivity.ps1 script. It assumes a backup zip file in EXIVITY_HOME_PATH/system/backup in order for it to work.

Quick execute tip:
`$script=wget https://raw.githubusercontent.com/exivity/support/main/windows/backup/restore_exivity.ps1;echo "$script.content" | powershell -noprofile -command { $input | iex }`