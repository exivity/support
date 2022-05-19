import http.client
import ssl
import json
import hashlib
import requests

# Settings
base_url="dev.exivity.net"
username="admin"
password="exivity"
steps_total=30
workflow_name="Gui Glitch Workflow"

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


for x in range(steps_total):
  print('adding step '+str(x)+' Workflow '+ workflow_name +'...')
  payload_string = '{"data":{"type":"workflowstep","attributes":{"sort":0,"type":"execute","options":{"command":"echo test '+str(x)+'"},"timeout":3600,"wait":true},"relationships":{"workflow":{"data":{"type":"workflow","id":"'+ workflow_id +'"}}}}}' 
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