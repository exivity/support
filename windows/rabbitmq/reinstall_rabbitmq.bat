set RABBITMQ_SERVICENAME="Exivity MQ Service"
"%EXIVITY_PROGRAM_PATH%\server\rabbitmq\sbin\rabbitmq-service.bat" stop
"%EXIVITY_PROGRAM_PATH%\server\rabbitmq\sbin\rabbitmq-service.bat" remove
"%EXIVITY_PROGRAM_PATH%\server\rabbitmq\sbin\rabbitmq-service.bat" install
"%EXIVITY_PROGRAM_PATH%\server\rabbitmq\sbin\rabbitmq-service.bat" start