
echo "`n------------------------------------------------------------"
echo "This script will enable and enforce TLS for the"
echo "RabbitMQ deployment of Exivity on Windows"
echo "------------------------------------------------------------"
echo "`nWARNING!!!"
echo "This will force communication on localhost 5671 for RabbitMQ"
echo "and will change the Exivity configuration accordingly."
echo "This operation is irreverable."
echo "Make sure to have a recent backup in the event of a failure."
echo "`nBy continuing your agree to overwrite any existing Exivity"
echo "or RabbitQM configuration parameters.`n"
echo "`bTo cancel this process now, close this screen or press CTRL-C`n"
pause
echo "=============================================================================="
echo "                              PROCESS STARTED                                 "
echo "=============================================================================="

$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

$CertPath = $("$env:EXIVITY_PROGRAM_PATH\common\certificates") -replace '\\','\\'
pushd $certpath

# if openssl is not installed download and install openssl
$OpenSSLInstallPath = "$env:ProgramFiles\OpenSSL-Win64"
$OpenSSLDownloadPath = "$env:USERPROFILE\Downloads\Win64OpenSSL_Light-3_0_7.exe"

if (-Not $env:RABBITMQ_HOME){
    $env:RABBITMQ_HOME = "$env:EXIVITY_PROGRAM_PATH\server\rabbitmq"
}
$RabbitMQPath = "$env:RABBITMQ_HOME\sbin"

$OpenSSLService =  [bool] (Get-Command openssl -ErrorAction SilentlyContinue)

$OpenSSLSetupExists = Test-Path $OpenSSLDownloadPath -PathType Leaf

$NewLine = "`r`n`r`n"

if (-Not $OpenSSLService){

    if(-Not $OpenSSLSetupExists){
		Write-Host "OpenSSL is not installed. Downloading OpenSSL 64 bit.." $NewLine

		#Download
		try {
            Invoke-WebRequest https://slproweb.com/download/Win64OpenSSL_Light-3_0_7.exe -OutFile $OpenSSLDownloadPath
        } catch {
            "ERROR - unable to download OpenSSL"
        }
	}

    #Install silently if not installed
	Write-Host "OpenSSL is being installed silently.." $NewLine
	try {
        Start-Process -FilePath $OpenSSLDownloadPath -Verb runAs -ArgumentList '/silent /verysilent /sp- /suppressmsgboxes' -Wait
    } catch {
        "ERROR - unable to install OpenSSL"
    }
}


#Reload system path and set OpenSSL as system path 
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:Path = $env:Path + ";" + $OpenSSLInstallPath + "\bin;" + $RabbitMQPath


#Setup Self sign config for open ssl
$SelfSignConfContent = '[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no
[req_distinguished_name]
CN = localhost
[v3_req]
keyUsage = critical, digitalSignature, keyAgreement
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
DNS.3 = ::1'

$SelfSignConfLocation = "$CertPath"
$SelfSignConf = "req.cnf"


#Create a self signed certficate
$SelfSignedCAFile = "rabbitmq-selfsigned.crt"
$SelfSignedKey = "rabbitmq-selfsigned.key"
$SelfSignedCRT = "rabbitmq-selfsigned.crt"

Write-Host "Creating OpenSSL config for self signed certficate generation..." $NewLine
$FileResponse = New-Item -Path $SelfSignConfLocation -Name $SelfSignConf -ItemType "file" -Value $SelfSignConfContent -force
Write-Host $NewLine
Write-Host "Generating self signed certs as no certs were provided..." $NewLine
openssl req -x509 -nodes -days 9999 -newkey rsa:2048 -keyout "$SelfSignedKey" -out "$SelfSignedCRT" -config "$SelfSignConfLocation\$SelfSignConf" -sha256

if($SelfSignedCAFile -eq "" -or $SelfSignedKey -eq "") {
	Write-Host "Certificate CA or Key was not found or supplied. Exiting with code 111"
	exit 111
}


# Add to cert store
#certutil -addstore -user -f "Root" $SelfSignedCRT

# create rabbitmq config
$SSLRabbitConfig = 'listeners.tcp  = none
listeners.ssl.default = 5671
ssl_options.verify               = verify_none
ssl_options.fail_if_no_peer_cert = false
ssl_options.cacertfile           = ' + $CertPath + '\\' + $SelfSignedCAFile + '
ssl_options.certfile             = ' + $CertPath + '\\' + $SelfSignedCRT + '
ssl_options.keyfile              = ' + $CertPath + '\\' + $SelfSignedKey + '
'

Write-Host 'Writing rabbit config...' $NewLine + $SSLRabbitConfig
Set-Content -Path $Env:RABBITMQ_CONF_ENV_FILE -Value $SSLRabbitConfig
New-Item -ItemType SymbolicLink -Path "$env:appdata\rabbitmq\rabbitmq.conf" -Target "$Env:RABBITMQ_CONF_ENV_FILE" -Force

# Re-install Rabbit MQ service
Write-Host "Re-install RabbitMQ service for config to take effect..."
$env:RABBITMQ_SERVICENAME="""Exivity MQ Service"""
rabbitmq-service remove
rabbitmq-service install
rabbitmq-service start

Write-Host "Waiting for RabbitMQ to be completely up.. waiting for 30 secs" $NewLine
Start-Sleep -s 30

$SSLResponse = tnc localhost -p 5671

if($SSLResponse.TcpTestSucceeded -eq $true) {
	Write-Host  $NewLine "TLS now successfully enabled on RabbitMQ! Changing Exivity config..." $NewLine
    $config_json = get-content "$env:EXIVITY_HOME_PATH/system/config.json" -raw | Convertfrom-json
    $cacertfile = "$CertPath" + "/" + $SelfSignedCAFile -replace '\\\\','/'
    foreach ($server in $config_json.mq.servers) {
        $server.port = 5671
        $server.secure = $true
        if(Get-Member -inputobject $server -name "cacertfile" -Membertype Properties){
            $server.cacertfile = $cacertfile
            $server.cn = "localhost"
        } else {
            $server | Add-Member -Type NoteProperty -Name 'cacertfile' -Value $cacertfile
            $server | Add-Member -Type NoteProperty -Name 'cn' -Value "localhost"
        }
    }
    $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False
    $json_out = ConvertTo-Json $config_json -Depth 4 
    [System.IO.File]::WriteAllLines("$env:EXIVITY_HOME_PATH/system/config.json", $json_out, $Utf8NoBomEncoding)
    Write-Host "Restarting Exivity services..."
	Restart-Service Exivity*
    Write-Host "`n-------Exivity RabbitMQ TLS Script Finished---------"
} else {
    Write-Host "ERROR - SSL Connections failed! Aborting."
}