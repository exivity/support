import http.client
import ssl
import argparse, sys
import json
import csv
import hashlib
import requests
import getpass

# get a token
def authenticate(url,username,password):
    # Authenticate
    conn = http.client.HTTPSConnection(
        url,
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
    return token


# get the exivity logs
def get_logs(component,limit,filter,fileout):
    token=authenticate(url,username,password)
    headers = {
        'Authorization': "Bearer " + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    conn = http.client.HTTPSConnection(
        url,
        context = ssl._create_unverified_context()
    )
    payload={}
    conn.request("GET", "/v1/log?component=" + component + "&limit=" + limit + "&filter=" + filter, payload, headers)
    res = conn.getresponse()
    data = res.read()
    #print(data.decode("utf-8"))
    json_response = json.loads(data.decode("utf-8"))
    #report_id=json_response["data"][0]["id"]
    f = open(fileout, "a")
    for logfile in json_response["logfiles"]:
        f.write("==============================================================\n")
        f.write(logfile["filename"]+ "\n")
        f.write("--------------------------------------------------------------\n")
        for logline in logfile["lines"]:
            f.write(str(logline)+ "\n")
    f.close()


# Parse commandline arguments 
parser=argparse.ArgumentParser()
parser.add_argument("--url", help="hostname of Exivity API")
parser.add_argument("--username", help="username with access to log endpoint")
parser.add_argument("--password", help="password for the username")
parser.add_argument("--components", help="components for which to obtain logs, as comma seperated list. Default: use,transcript,edify,proximity,pigeon,chronos,merlin,griffon,horizon")
parser.add_argument("--limit", help="number of log lines to return per component. Default: 100")
args=parser.parse_args()
# Configure settings or ask user if not provided
url = args.url
username = args.username
password = args.password
if args.url is None:
    url = input("Provide Exivity hostname:")
if args.username is None:
    username = input("Provide Exivity username:")
if args.password is None:
    password = getpass.getpass("Provide Exivity password:")
if args.components is None:
    components = ["use","transcript","edify","proximity","pigeon","chronos","merlin","griffon","horizon"]
else:
    components = (args.components).split(",")
if args.limit is None:
    limit = "100"

# get a token for the endpoint
#authenticate(url,username,password)

# wipe the file
outfile="exivity_logs.log"
f = open(outfile, "w")
f.close()
# write the logs
for component in components:
    get_logs(component, limit ,"*",outfile)
