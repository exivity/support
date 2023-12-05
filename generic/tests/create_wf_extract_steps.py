import http.client
import ssl
import json
import hashlib
import requests

#
# Example script to create a new workflow and add multiple Extractor steps
# - creates different offsets and total steps, depending settings
#

# Settings
base_url="my.exivity.local"
username="admin"
password="password"
total_days=31
days_per_step=1
steps_total=int(round((total_days/days_per_step),0))
workflow_name="Parallel Extract"
extractor_name="Test_Extractor"
timeout = 10800
wait_operator = 'false'

if wait_operator == 'false':
  wait_value = 'false'
else :
  wait_value = 'true'

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

# Create the Workflow
print("Creating Workflow "+ workflow_name +"...\n===========================")
payload_string = '{"data":{"type":"workflow","attributes":{"name":"'+workflow_name+'","description":""},"relationships":{"schedules":{"data":[]},"steps":{"data":[]}}}}'
payload_json = json.loads(payload_string)
payload = json.dumps(payload_json)
headers = {
  'Authorization': "Bearer " + token,
  'Content-Type': 'application/json',
  'Accept': 'application/json'
}
conn.request("POST", "/v1/workflows", payload, headers)
res = conn.getresponse()
data = res.read()
json_response = json.loads(data.decode("utf-8"))
workflow_id=json_response['data']['id']

total_days=total_days-1
day_offset=days_per_step-1
for x in range(steps_total):
  print('adding step '+str(x)+' Workflow '+ workflow_name +'...')
  payload_string = '{"data":{"type":"workflowstep","attributes":{"type":"use","options":{"name":"'+str(extractor_name)+'","from_date": -'+str(total_days)+',"to_date": -'+str(total_days-day_offset)+',"arguments": "","environment_id": null},"timeout":'+str(timeout)+',"wait":'+str(wait_value)+'},"relationships":{"workflow":{"data":{"type":"workflow","id":"'+ workflow_id +'"}}}}}' 
  total_days=total_days-days_per_step
  if wait_operator == 'alternating':
    if wait_value == 'false':
      wait_value = 'true'
    else:
      wait_value = 'false'
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
  print(json_response)