import http.client
import ssl
import json
import hashlib
import requests

#
# Example script to add multiple prepare steps to an existing Workflow ID
#

# Settings
base_url="localhost"
protocol="http"
username="admin"
password="password"
report_id="1"
workflow_id="182"
steps_total=31

# Authenticate http or else https
if protocol=="http":
    conn = http.client.HTTPConnection(
        base_url,
    )
    conn = http.client.HTTPSConnection(
        base_url,
        context = ssl._create_unverified_context()
    )
else:
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

# create the prepare jobs
for x in range(steps_total):
  print('adding step '+str(x)+' Workflow id '+ workflow_id +'...')
  payload_string = '{"data":{"type":"workflowstep","workflow_id":"'+str(workflow_id)+'","attributes":{"type":"edify","timeout":7200,"wait":false,"options":{"report_id":"'+str(report_id)+'","from_date":"-'+str(x)+'","to_date":"-'+str(x)+'"}},"relationships":{"workflow":{"data":{"type":"workflow","id":"'+str(workflow_id)+'"}}}}}' 
  payload_json = json.loads(payload_string)
  payload = json.dumps(payload_json)
  headers = {
    'Authorization': "Bearer " + token,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
  conn.request("POST", "/v1/workflowsteps", payload, headers)
  res = conn.getresponse()
  data = res.read()
  json_response = json.loads(data.decode("utf-8"))