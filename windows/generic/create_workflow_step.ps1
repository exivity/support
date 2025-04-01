##############################################################################
# USER CONFIGURABLE SECTION
##############################################################################
$ExivityServer = "https://localhost"   # Root URL of your Exivity instance
$Username      = "admin"              # The Exivity username
$Password      = "exivity"            # The Exivity password
# The workflow name & description
$WorkflowName  = "Example vnd.api+json Workflow"
$WorkflowDesc  = "Workflow that runs an edify step with report_id=3"

##############################################################################
# (Optional) If using a self-signed certificate, bypass certificate checks.
# WARNING: This is insecure in production. Only do this in a test environment.
##############################################################################
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {
    param($sender, $cert, $chain, $sslPolicyErrors)
    return $true
}

##############################################################################
# STEP 1: Log in using form-encoded credentials (POST /v1/auth/token)
##############################################################################
$LoginUri = "$ExivityServer/v1/auth/token"

# Construct headers for form-encoded login
$loginHeaders = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
$loginHeaders.Add("Content-Type", "application/x-www-form-urlencoded")
$loginHeaders.Add("Accept",       "application/json")

# Build form-encoded body
$loginBody = "username=$($Username)&password=$($Password)"

try {
    $LoginResponse = Invoke-RestMethod -Uri $LoginUri -Method 'POST' `
        -Headers $loginHeaders -Body $loginBody
    # Inspect raw response if needed
    # $LoginResponse | ConvertTo-Json -Depth 10 | Write-Host
}
catch {
    Write-Host "Failed to log in via form-encoded credentials: $($_.Exception.Message)"
    return
}

# Extract token from the response
# Depending on your version, it might be at $LoginResponse.data.attributes.token
# or $LoginResponse.token. Adjust accordingly if needed.
$AuthToken = $LoginResponse.token
if (-not $AuthToken) {
    Write-Host "No token found in login response. Check credentials/logs."
    return
}
Write-Host "Authenticated successfully. Token (partial): $($AuthToken.Substring(0,10))..."

##############################################################################
# STEP 2: Create a new workflow (POST /v1/workflows) with application/vnd.api+json
##############################################################################
$CreateWorkflowUri = "$ExivityServer/v1/workflows"

# Typically for older endpoints: "type": "workflow", "attributes": { "name", "description" }
$headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
$headers.Add("Content-Type", "application/vnd.api+json")
$headers.Add("Accept",       "application/vnd.api+json")
$headers.Add("Authorization","Bearer $AuthToken")

$WorkflowBody = @'
{
  "data": {
    "type": "workflow",
    "attributes": {
      "name": "WORKFLOW_NAME",
      "description": "WORKFLOW_DESC"
    }
  }
}
'@

# Replace placeholders with your actual variables
$WorkflowBody = $WorkflowBody -replace "WORKFLOW_NAME",   $WorkflowName
$WorkflowBody = $WorkflowBody -replace "WORKFLOW_DESC",   $WorkflowDesc

try {
    $WorkflowResponse = Invoke-RestMethod -Method 'POST' -Uri $CreateWorkflowUri `
        -Headers $headers -Body $WorkflowBody
    # $WorkflowResponse | ConvertTo-Json -Depth 10 | Write-Host
}
catch {
    Write-Host "Failed to create workflow. Error:" $_.Exception.Message
    return
}

# Typically the new workflow ID is at $WorkflowResponse.data.id
$WorkflowId = $WorkflowResponse.data.id
if (-not $WorkflowId) {
    Write-Host "No workflow ID returned. Check logs/response."
    return
}
Write-Host "Created new workflow with ID=$WorkflowId."

##############################################################################
# STEP 3: Create a single edify step (POST /v1/workflowsteps)
##############################################################################
# In your example JSON, we had "type": "workflowstep", "attributes": { "type": "edify" ... },
# plus "relationships": { "workflow": { "data": { "type": "workflow", "id": <workflowId> }} }

$CreateStepUri = "$ExivityServer/v1/workflowsteps"

# We'll specify "report_id=3", "from_date=-2", "to_date=-1" for demonstration.
# If you want a different offset or multiple steps, adapt as necessary.
$StepBody = @'
{
  "data": {
    "type": "workflowstep",
    "attributes": {
      "type": "edify",
      "timeout": 600,
      "options": {
        "report_id": 3,
        "from_date": -2,
        "to_date": "-1"
      }
    },
    "relationships": {
      "workflow": {
        "data": {
          "type": "workflow",
          "id": "WORKFLOW_ID"
        }
      }
    }
  }
}
'@

# Replace placeholder with the newly created workflow ID
$StepBody = $StepBody -replace "WORKFLOW_ID", $WorkflowId

try {
    $StepResponse = Invoke-RestMethod -Method 'POST' -Uri $CreateStepUri `
        -Headers $headers -Body $StepBody
    # $StepResponse | ConvertTo-Json -Depth 10 | Write-Host
}
catch {
    Write-Host "Failed to create step. Error:" $_.Exception.Message
    return
}

# Typically the new step ID is at $StepResponse.data.id
$StepId = $StepResponse.data.id
if (-not $StepId) {
    Write-Host "No step ID returned. Check logs/response."
    return
}
Write-Host "Created a single step ID=$StepId to run edify with (report_id=3, offsets=-2..-1)."
