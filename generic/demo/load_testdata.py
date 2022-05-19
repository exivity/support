import http.client
import ssl
import json
import hashlib
import requests

# Settings
base_url="exivity"
username="admin"
password="exivity"
from_date="2022-01-01"
to_date="2022-05-30"
report_name="ECB"

# Authenticate
conn = http.client.HTTPSConnection(
    base_url,
    context = ssl._create_unverified_context()
)
payload = "username=" + username + "&password=" + password
headers = {
  'Content-Type': 'application/x-www-form-urlencoded',
  'Accept': 'application/json'
}
conn.request("POST", "/v1/auth/token", payload, headers)
response = conn.getresponse()
data = response.read()
json_response = json.loads(data.decode("utf-8"))
token=json_response["token"]

# Create ECB Extractor
print("Creating Extractor...\n===========================")
payload = json.dumps({
  "name": "ECB",
  "contents": "#===================== Introduction ======================#\n#\n#  This is a template Extractor for obtaining currency \n#  exchange rates. It provides all common currencies to \n#  EUR, which can be used for currency normalisation tasks \n#  in the Exivity Transformer ETL engine.\n#\n#  No parameters are required to execute. \n#\n#  For more information, consult the ECB API docs:\n#  - https://sdw-wsrest.ecb.europa.eu\n#\n#===================== Introduction ======================#\n\n#=================  Start Configuration ==================#\n#\n\n# The hostname of the ECB API end point\npublic var API_host = \"sdw-wsrest.ecb.europa.eu\"\n# Pick D (for Daily) or M (for Monthly) to get Daily or Monthly aggregates\npublic var measure_frequency = \"D\" \n# The first day for which you want to obtain exchange rates in yyyy-mm-dd format in case of Daily frequency. Use yyyy-mm in case of Monthly. \npublic var start_period = \"2017-01-01\"\n# The folder to place the extracted files, relative to the Exivity home folder\npublic var CSV_File = \"system/extracted/ecb/exchange_rates.csv\"\n\n#\n#=================  End Configuration ==================#\n\n#/ Connect to the ECB API\nprint \"Getting ECB Exchange Rates...\"\n\n# Set up the HTTP request parameters\nset http_header \"Accept: text/csv\"\nset http_savefile \"${CSV_File}\"\nbuffer ecb_rates = http get \"https://${API_host}/service/data/EXR/${measure_frequency}...SP00.A?startPeriod=${start_period}\"\n\nif (${HTTP_STATUS_CODE} != 200) {\n\tprint Got HTTP status ${HTTP_STATUS_CODE}, expected a status of 200\n\tprint The server response was:\n\tprint {ecb_rates}\n\tterminate with error\n}\nprint \"Succesfully obtained exchange rates.\""
})
headers = {
  'Authorization': "Bearer " + token,
  'Content-Type': 'application/json',
  'Accept': 'application/json'
}
conn.request("POST", "/v1/extractors", payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

# run Extractor
print("Running Extractor...\n===========================")
payload = "{}"
conn.request("POST", "/v1/extractors/ECB/run?arguments=", payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

# Create ECB Transformer
print("Creating Transformer...\n===========================")
payload = json.dumps({
  "name": "ECB",
  # "contents": "# Test Transformer using ECB Rates"
  "contents": "# Test Transformer using ECB Rates\n\nimport \"system/extracted/ecb/exchange_rates.csv\" source ecb alias rates \n\nwhere ([TIME_PERIOD] !~ /${dataYear}-${dataMonth}-${dataDay}/) {\n    delete rows\n}\n\nif (!@DSET_EMPTY(ecb.rates) ) {\n  \ncreate column quantity value 1\n\nfinish\n\n  services {\n    # Service Definition\n    service_type = \"automatic\"      # service type manual / automatic\n    usages_col = KEY       # the column containing the friendly name of the service\n    description_col = TITLE   # column with service key value. Should be unique\n    category = \"ECB Exchange Rates\"         # column with category description\n    instance_col = TITLE_COMPL         # the chargable instance i.e. vm-id, username, etc\n    interval = \"daily\"            # the interval value\n    unit_label_col = UNIT          # the column containing the unit label\n    consumption_col = quantity      # the column containing the consumed quantity\n    model = \"unprorated\"            # for price: unprorated or prorated model\n    charge_model = \"peak\"           # for quantity: peak or average calculation\n    # Service Rate / Revision\n    # effective_date = \"20220101\"     # initial rate revision, leave empty for \n    set_rate_using = OBS_VALUE           # column value with initial rate\n    set_cogs_using = OBS_VALUE           # column value with intiial costs\n  }\n}\n"
})
headers = {
  'Authorization': "Bearer " + token,
  'Content-Type': 'application/json',
  'Accept': 'application/json'
}
conn.request("POST", "/v1/transformers", payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

# run ECB Transformer
print("Running Transformer...\n===========================")
payload = "{}"
conn.request("POST", "/v1/transformers/ECB/run?start_date=" + from_date + "&end_date=" + to_date , payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

# create report
print("Creating Report...\n===========================")
payload = "{\"data\":{\"type\":\"report\",\"attributes\":{\"name\":\"" + report_name + "\",\"dset\":\"ecb.rates\",\"lvl1_key_col\":\"KEY\",\"lvl1_name_col\":\"TITLE\",\"lvl1_label\":\"FX Title\"}}}"
conn.request("POST", "/v1/reports", payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

# get report ID
conn.request("GET", "/v1/reports?filter[name]==ECB", payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))
json_response = json.loads(data.decode("utf-8"))
report_id=json_response["data"][0]["id"]

#prepare report
print("Preparing Report...\n===========================")
payload = "{}"
conn.request("PATCH", "/v1/reports/" + report_id + "/prepare?start=" + from_date + "&end=" + to_date, payload, headers)
res = conn.getresponse()
data = res.read()
#print(data.decode("utf-8"))

print("Done!\n===========================")