# read config
$config_json=Get-Content $env:EXIVITY_HOME_PATH/system/config.json|ConvertFrom-Json
# load psql vars
$pg_host=$config_json.db.parameters.host
$pg_port=$config_json.db.parameters.port
$pg_sslmode=$config_json.db.parameters.sslmode
$pg_dbname=$config_json.db.parameters.dbname
$pg_user=$config_json.db.parameters.user
$pg_password=$config_json.db.parameters.password

echo "================================================================================"
echo "  Connecting to Exivity PSQL Database '$pg_dbname' on  '$pg_host' ..."
echo "================================================================================"
echo ""
$env:PGPASSWORD=$pg_password
Invoke-Expression -Command "$env:EXIVITY_PROGRAM_PATH/server/pgsql/bin/psql.exe -h $pg_host -p $pg_port -U $pg_user $pg_dbname "