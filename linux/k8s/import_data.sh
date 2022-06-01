#!/bin/bash

# Configuration
restore_root=/tmp
restore_dir=$restore_root/exivity_backup
PGUSER=postgres
PGEXIVITYUSER=exivity
PGPASSWORD=Password13!
PGHOST=exivity
PGDATABASE=exivity
PGPORT=5432

echo
echo "=================================== WARNING ==================================="
echo "This script will execute a full system restore to your Exivity k8s deployment." 
echo "Be advised that this is an irreversible operation. Any existing data,"
echo "report definitions, extractors, transformers, and other Exivity components"
echo "will be overwritten. Use this script at your own risk."
echo "=================================== WARNING ==================================="
echo
read -p "Please type 'Agree' if you understand and accept above risks: " -n 5
echo
if [[ ! $REPLY =~ ^[Aa]gree$ ]]
then
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

# ask for backup zip
cur=$(pwd)
echo
echo -n "Path to Exivity backup zip file: "
read backup_path
if [ ! -f $backup_path ]; then
    echo "Please insert a correct path"
    sleep 1
    sudo $cur/import_data.sh
fi

# need to run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# get pod names
edify_pod=$(kubectl get pods -o=jsonpath='{range .items..metadata}{.name}{"\n"}{end}' | fgrep edify)
if [ -z "$edify_pod" ]
then
      echo "No Edify POD found! Exiting..."
      exit
fi
transcript_pod=$(kubectl get pods -o=jsonpath='{range .items..metadata}{.name}{"\n"}{end}' | fgrep transcript)
if [ -z "$transcript_pod" ]
then
      echo "No Transcript POD found! Exiting..."
      exit
fi

# test database
echo "Opening psql port..."
kubectl port-forward exivity-postgres-0 5432:5432 &
export portfw_pid=$!
sleep 5
export PGPASSWORD=$PGPASSWORD
pg_isready -d $PGDATABASE -h $PGHOST -p $PGPORT -U $PGUSER
retVal=$?                
if [ $retVal -ne 0 ]; then
    echo "Failed to connect to database! Exiting..."
    echo "(HINT: you might need to change database connection details in this script)" 
    kill $portfw_pid
    # there is a second process for port-forward
    export portfw_pid=$(ps -e -o pid,cmd | grep "port-forward exivity-postgres-0"  | awk '{print $1}'|head -n1)
    kill $portfw_pid
    exit
fi

# unzip backup
echo "Unpacking backup archive..."
mkdir -p $restore_dir
cd $restore_dir
unzip -qn $backup_path -d .

# restore data
echo "Restoring data..."
cd $restore_dir
kubectl cp ./use $transcript_pod:/exivity/home/system/config/use --no-preserve=true
kubectl cp ./transcript $transcript_pod:/exivity/home/system/config/transcript --no-preserve=true

cd import
unzip -qn import.zip
kubectl cp . $transcript_pod:/exivity/home/import/

cd ../exported
unzip -qn exported.zip
kubectl cp . $transcript_pod:/exivity/home/exported/

cd ../extracted
unzip -qn extracted.zip
kubectl cp . $transcript_pod:/exivity/home/system/extracted/

cd ../report
unzip -qn report.zip
kubectl cp . $edify_pod:/exivity/home/system/report/

cd ../db
echo starting restore
pg_restore -w -c -p $PGPORT -U $PGUSER -d postgresql://$PGHOST/$PGDATABASE database_backup.sql
echo setting permissions
echo "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $PGEXIVITYUSER;"|psql -U $PGUSER postgresql://$PGHOST/$PGDATABASE
echo "GRANT ALL ON ALL TABLES IN SCHEMA public TO $PGEXIVITYUSER;"|psql -U $PGUSER postgresql://$PGHOST/$PGDATABASE
kill $portfw_pid
# there is a second process for port-forward
export portfw_pid=$(ps -e -o pid,cmd | grep "port-forward exivity-postgres-0"  | awk '{print $1}'|head -n1)
kill $portfw_pid

echo "set app_key..."
cd ../env
export app_key=$(iconv EXIVITY_APP_KEY -f utf-16le|sed 's/\r$//'|base64)
kubectl get secret exivity-app-key -o json | jq '.data["app_key"]="'$app_key'"' | kubectl apply -f -

echo "set jwt_secret..."
cd ../env
export jwt_secret=$(iconv EXIVITY_JWT_SECRET -f utf-16le|sed 's/\r$//'|base64)
kubectl get secret exivity-jwt-secret -o json | jq '.data["jwt_secret"]="'$jwt_secret'"' | kubectl apply -f -
echo
echo "Finished executing restore script. You will need to (re)prepare your reports." 