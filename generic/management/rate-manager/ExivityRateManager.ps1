#Requires -Version 5.1

<#
.SYNOPSIS
    Exivity Rate Management Tool - Enhanced with Service Key Support
    
.DESCRIPTION
    A lean, single-file PowerShell script for managing Exivity rates via an
    interactive console menu. Supports CSV import/export with service_key lookup
    and status checking. No dependencies required - runs on any Windows system
    with PowerShell 5.1+
    
    NEW: Supports service_key in addition to service_id for easier rate management
    
.NOTES
    Version: 2.0.0
    Author: Exivity
    
.EXAMPLE
    # Interactive mode
    .\ExivityRateManager_v2.ps1
    
.EXAMPLE
    # Interactive mode (always launched)
    .\ExivityRateManager_v2.ps1
#>

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

$script:Token = $null
$script:BaseUrl = $null
$script:VerifySSL = $false
$script:ServiceCache = @{}
$script:ServiceKeyToIdMap = @{}
$script:ServiceIdToKeyMap = @{}
$script:ServiceIdToDescriptionMap = @{}

function Resolve-BaseUrl {
    <#
    .SYNOPSIS
        Ensure the supplied base URL includes a scheme and no trailing slash
    #>
    [CmdletBinding()]
    param(
        [Parameter()]
        [string]$Url,
        
        [Parameter()]
        [string]$DefaultScheme = 'https://'
    )
    
    if ([string]::IsNullOrWhiteSpace($Url)) {
        return $null
    }
    
    $trimmed = $Url.Trim()
    
    if ($trimmed -notmatch '^[a-z][a-z0-9+\-.]*://') {
        $trimmed = "$DefaultScheme$trimmed"
    }
    
    $normalized = $trimmed.TrimEnd('/')
    return $normalized
}

# ============================================================================
# API FUNCTIONS
# ============================================================================

function Connect-ExivityRateAPI {
    <#
    .SYNOPSIS
        Connect to Exivity API and obtain authentication token
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,
        
        [Parameter(Mandatory = $true)]
        [string]$Username,
        
        [Parameter(Mandatory = $true)]
        [string]$Password,
        
        [Parameter(Mandatory = $false)]
        [bool]$VerifySSL = $false
    )
    
    $normalizedBaseUrl = Resolve-BaseUrl -Url $BaseUrl
    if (-not $normalizedBaseUrl) {
        throw "BaseUrl cannot be empty."
    }

    try {
        $null = [System.Uri]$normalizedBaseUrl
    }
    catch {
        throw "Invalid BaseUrl '$BaseUrl'. $_"
    }

    if ($BaseUrl -and ($normalizedBaseUrl -ne $BaseUrl.Trim())) {
        Write-Verbose "Normalized BaseUrl from '$BaseUrl' to '$normalizedBaseUrl'"
    }

    $script:BaseUrl = $normalizedBaseUrl
    $script:VerifySSL = $VerifySSL
    
    # Disable SSL verification if requested
    if (-not $VerifySSL) {
        # PowerShell 6+ (Core) uses different method
        if ($PSVersionTable.PSVersion.Major -ge 6) {
            # For PowerShell 6+, we'll use -SkipCertificateCheck parameter in Invoke-RestMethod
            Write-Verbose "Using PowerShell 6+ SSL bypass method"
        }
        else {
            # PowerShell 5.1 method
            if (-not ([System.Management.Automation.PSTypeName]'TrustAllCertsPolicy').Type) {
                Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint srvPoint, X509Certificate certificate,
        WebRequest request, int certificateProblem) {
        return true;
    }
}
"@
            }
            [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        }
    }
    
    try {
        $authUrl = "$script:BaseUrl/v2/auth/token"
        $authBody = @{
            username = $Username
            password = $Password
        } | ConvertTo-Json
        
        Write-Verbose "Connecting to: $authUrl"
        
        # Build parameters for Invoke-RestMethod
        $restParams = @{
            Uri = $authUrl
            Method = 'Post'
            Body = $authBody
            ContentType = 'application/json'
        }
        
        # Add SkipCertificateCheck for PowerShell 6+ if SSL verification is disabled
        if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $VerifySSL) {
            $restParams['SkipCertificateCheck'] = $true
        }
        
        $response = Invoke-RestMethod @restParams
        $script:Token = $response.data.attributes.token
        
        Write-Host "✅ Connected to Exivity API" -ForegroundColor Green
        
        # Load service cache automatically
        Load-ServiceCache
        
        return $true
    }
    catch {
        Write-Error "❌ Authentication failed: $_"
        return $false
    }
}

function Invoke-ExivityRateAPI {
    <#
    .SYNOPSIS
        Make an authenticated request to the Exivity API
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Endpoint,
        
        [Parameter(Mandatory = $false)]
        [ValidateSet('GET', 'POST', 'PUT', 'DELETE', 'PATCH')]
        [string]$Method = 'GET',
        
        [Parameter(Mandatory = $false)]
        [object]$Body
    )
    
    if (-not $script:Token) {
        throw "Not authenticated. Please call Connect-ExivityRateAPI first."
    }
    
    $url = "$script:BaseUrl$Endpoint"
    $headers = @{
        'Authorization' = "Bearer $script:Token"
        'Content-Type' = 'application/json'
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $headers
        }
        
        if ($Body) {
            $jsonBody = ($Body | ConvertTo-Json -Depth 10 -Compress)
            $params['Body'] = $jsonBody
            
            # Debug: Show first 500 chars of payload for POST/PUT/PATCH
            if ($Method -in @('POST', 'PUT', 'PATCH')) {
                $preview = if ($jsonBody.Length -gt 500) { $jsonBody.Substring(0, 500) + "..." } else { $jsonBody }
                Write-Verbose "Request payload: $preview"
            }
        }
        
        # Add SkipCertificateCheck for PowerShell 6+ if SSL verification is disabled
        if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $script:VerifySSL) {
            $params['SkipCertificateCheck'] = $true
        }
        
        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        $errorDetails = ""
        if ($_.Exception.Response) {
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $reader.BaseStream.Position = 0
                $errorDetails = $reader.ReadToEnd()
                Write-Verbose "API error details: $errorDetails"
            }
            catch {}
        }
        
        # Throw the error so it can be caught by calling code
        $errorMessage = "API request failed: $_ $(if($errorDetails){"`nDetails: $errorDetails"})"
        throw $errorMessage
    }
}

function Load-ServiceCache {
    <#
    .SYNOPSIS
        Load all services into memory for service_key to service_id lookups
    #>
    [CmdletBinding()]
    param()
    
    Write-Host "🔄 Loading service cache..." -ForegroundColor Cyan
    
    try {
        $allServices = @()
        $limit = 500  # Use large page size for fewer requests
        $offset = 1
        $totalServices = $null
        
        do {
            $endpoint = "/v2/services?limit=$limit&page[offset]=$offset"
            Write-Verbose "Fetching services page $offset (limit=$limit)..."
            $response = Invoke-ExivityRateAPI -Endpoint $endpoint -Method GET
            
            if ($response -and $response.data -and $response.data.Count -gt 0) {
                $allServices += $response.data
                
                # Get total from first response
                if ($null -eq $totalServices -and $response.meta -and $response.meta.pagination -and $response.meta.pagination.total) {
                    $totalServices = $response.meta.pagination.total
                    Write-Verbose "Total services to load: $totalServices"
                }
                
                Write-Verbose "Loaded $($response.data.Count) services (total so far: $($allServices.Count))"
                
                # Check if there are more pages
                if ($response.links -and $response.links.next) {
                    $offset++
                }
                else {
                    Write-Verbose "No more pages"
                    break
                }
            }
            else {
                Write-Verbose "No more services"
                break
            }
        } while ($true)
        
        if ($allServices.Count -eq 0) {
            Write-Warning "No services loaded"
            return $false
        }
        
        Write-Verbose "Loaded total of $($allServices.Count) services"
            
        # Build lookup maps
        $script:ServiceCache = @{}
        $script:ServiceKeyToIdMap = @{}
        $script:ServiceIdToKeyMap = @{}
        $script:ServiceIdToDescriptionMap = @{}
        
        $servicesWithKeys = 0
        foreach ($service in $allServices) {
            $serviceId = $service.id
            $serviceKey = $service.attributes.key
            $serviceDescription = $service.attributes.description
            
            $script:ServiceCache[$serviceId] = $service
            
            if ($serviceKey -and $serviceKey -ne "") {
                $script:ServiceKeyToIdMap[$serviceKey] = $serviceId
                $script:ServiceIdToKeyMap[$serviceId] = $serviceKey
                $servicesWithKeys++
            }
            
            # Store description separately for display purposes
            if ($serviceDescription -and $serviceDescription -ne "") {
                $script:ServiceIdToDescriptionMap[$serviceId] = $serviceDescription
            }
        }
        
        Write-Host "✅ Loaded $($allServices.Count) services ($servicesWithKeys with service keys)" -ForegroundColor Green
        
        return $true
    }
    catch {
        Write-Warning "Failed to load service cache: $_"
        Write-Warning "Service key lookups will not be available"
        return $false
    }
}

function Resolve-ServiceId {
    <#
    .SYNOPSIS
        Resolve service_key to service_id, or validate service_id
    #>
    [CmdletBinding()]
    param(
        [Parameter()]
        [string]$ServiceId,
        
        [Parameter()]
        [string]$ServiceKey
    )
    
    # If service_id is provided and not empty, use it
    if ($ServiceId -and $ServiceId -ne "") {
        return $ServiceId
    }
    
    # If service_key is provided, look it up
    if ($ServiceKey -and $ServiceKey -ne "") {
        if ($script:ServiceKeyToIdMap.ContainsKey($ServiceKey)) {
            $resolvedId = $script:ServiceKeyToIdMap[$ServiceKey]
            Write-Verbose "Resolved service_key '$ServiceKey' to service_id $resolvedId"
            return $resolvedId
        }
        else {
            Write-Warning "Service key '$ServiceKey' not found in cache"
            return $null
        }
    }
    
    Write-Warning "Neither service_id nor service_key provided"
    return $null
}

function Get-ServiceKey {
    <#
    .SYNOPSIS
        Get service_key for a given service_id
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$ServiceId
    )
    
    if ([string]::IsNullOrWhiteSpace($ServiceId)) {
        return ""
    }
    
    if ($script:ServiceIdToKeyMap.ContainsKey($ServiceId)) {
        return $script:ServiceIdToKeyMap[$ServiceId]
    }
    
    return ""
}

function Get-ServiceDescription {
    <#
    .SYNOPSIS
        Get service description for a given service_id
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$ServiceId
    )
    
    if ([string]::IsNullOrWhiteSpace($ServiceId)) {
        return ""
    }
    
    if ($script:ServiceIdToDescriptionMap.ContainsKey($ServiceId)) {
        return $script:ServiceIdToDescriptionMap[$ServiceId]
    }
    
    return ""
}

# ============================================================================
# RATE MANAGEMENT FUNCTIONS
# ============================================================================

function Import-RatesFromCSV {
    <#
    .SYNOPSIS
        Import rates from CSV file (supports both service_id and service_key)
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$CSVPath,
        
        [Parameter(Mandatory = $false)]
        [int]$BatchSize = 50
    )
    
    if (-not (Test-Path $CSVPath)) {
        Write-Error "❌ CSV file not found: $CSVPath"
        return
    }
    
    Write-Host "`n📥 Importing rates from: $CSVPath" -ForegroundColor Cyan
    
    # Try different encodings
    $encodings = @('UTF8', 'Default', 'Unicode', 'ASCII')
    $csvData = $null
    
    foreach ($encoding in $encodings) {
        try {
            $csvData = Import-Csv -Path $CSVPath -Encoding $encoding -ErrorAction Stop
            Write-Verbose "Successfully read CSV with $encoding encoding"
            break
        }
        catch {
            continue
        }
    }
    
    if (-not $csvData) {
        Write-Error "❌ Failed to read CSV file with any encoding"
        return
    }
    
    if ($csvData.Count -eq 0) {
        Write-Error "❌ CSV file is empty"
        return
    }
    
    Write-Host "🔍 Validating CSV contents..." -ForegroundColor Cyan
    
    # Validate CSV columns
    $csvColumns = $csvData[0].PSObject.Properties.Name
    
    $hasServiceId = $csvColumns -contains 'service_id'
    $hasServiceKey = $csvColumns -contains 'service_key'
    
    if (-not $hasServiceId -and -not $hasServiceKey) {
        Write-Error "❌ CSV must contain either 'service_id' or 'service_key' column"
        return
    }
    
    if (-not ($csvColumns -contains 'account_id')) {
        Write-Error "❌ CSV must contain 'account_id' column"
        return
    }
    
    if (-not ($csvColumns -contains 'rate')) {
        Write-Error "❌ CSV must contain 'rate' column"
        return
    }
    
    if (-not ($csvColumns -contains 'revision_start_date')) {
        Write-Error "❌ CSV must contain 'revision_start_date' column"
        return
    }
    
    # Validate each row before sending anything to the API
    $validationErrors = @()
    $validRates = @()
    $rowNumber = 1
    
    foreach ($row in $csvData) {
        $rowNumber++
        $rowIssues = @()
        
        # Account validation
        $accountIdValue = $null
        $accountIdRaw = if ($row.PSObject.Properties['account_id']) { $row.account_id } else { $null }
        if ([string]::IsNullOrWhiteSpace([string]$accountIdRaw)) {
            $rowIssues += "Missing account_id"
        }
        else {
            [int]$parsedAccount = 0
            if (-not [int]::TryParse($accountIdRaw, [ref]$parsedAccount)) {
                $rowIssues += "Invalid account_id '$accountIdRaw'"
            }
            else {
                $accountIdValue = $parsedAccount
            }
        }
        
        # Service resolution
        $resolvedServiceId = Resolve-ServiceId -ServiceId $row.service_id -ServiceKey $row.service_key
        if (-not $resolvedServiceId) {
            $rowIssues += "Unable to resolve service_id/service_key"
        }
        
        # Rate validation
        $rateValue = $null
        $rateRaw = if ($row.PSObject.Properties['rate']) { $row.rate } else { $null }
        if ([string]::IsNullOrWhiteSpace([string]$rateRaw)) {
            $rowIssues += "Missing rate"
        }
        else {
            [decimal]$parsedRate = 0
            if (-not [decimal]::TryParse($rateRaw, [ref]$parsedRate)) {
                $rowIssues += "Invalid rate '$rateRaw'"
            }
            else {
                $rateValue = $parsedRate
            }
        }
        
        # COGS validation (optional)
        $cogsValue = $null
        if ($csvColumns -contains 'cogs' -and -not [string]::IsNullOrWhiteSpace([string]$row.cogs)) {
            [decimal]$parsedCogs = 0
            if (-not [decimal]::TryParse($row.cogs, [ref]$parsedCogs)) {
                $rowIssues += "Invalid cogs '$($row.cogs)'"
            }
            else {
                $cogsValue = $parsedCogs
            }
        }
        
        # Date validation (expect YYYYMMDD or YYYY-MM-DD)
        $dateDigits = $null
        $dateRaw = if ($row.PSObject.Properties['revision_start_date']) { $row.revision_start_date } else { $null }
        if ([string]::IsNullOrWhiteSpace([string]$dateRaw)) {
            $rowIssues += "Missing revision_start_date"
        }
        else {
            $normalizedDate = $dateRaw.ToString().Trim()
            $digits = $normalizedDate -replace '-', ''
            if ($digits -notmatch '^[0-9]{8}$') {
                $rowIssues += "Invalid revision_start_date '$normalizedDate' (expected YYYYMMDD)"
            }
            else {
                $dateDigits = $digits
            }
        }
        
        if ($rowIssues.Count -gt 0) {
            foreach ($issue in $rowIssues) {
                $validationErrors += [PSCustomObject]@{
                    Row = $rowNumber
                    Message = $issue
                }
            }
            continue
        }
        
        $validRates += [PSCustomObject]@{
            account_id = $accountIdValue
            service_id = $row.service_id
            service_key = if ($hasServiceKey) { $row.service_key } else { $null }
            rate = $rateValue
            cogs = $cogsValue
            revision_start_date = $dateDigits
            resolved_service_id = $resolvedServiceId
            source_row_number = $rowNumber
        }
    }
    
    if ($validationErrors.Count -gt 0) {
        Write-Host "`n❌ CSV validation failed. No changes were sent to the API." -ForegroundColor Red
        foreach ($entry in ($validationErrors | Sort-Object Row | Select-Object -First 10)) {
            Write-Host "   Row $($entry.Row): $($entry.Message)" -ForegroundColor Yellow
        }
        if ($validationErrors.Count -gt 10) {
            Write-Host "   ...and $($validationErrors.Count - 10) more issue(s)." -ForegroundColor Yellow
        }
        return
    }
    
    if ($validRates.Count -eq 0) {
        Write-Error "❌ No valid rates found in CSV"
        return
    }
    
    $duplicateGroups = $validRates |
        Group-Object { "{0}|{1}|{2}" -f $_.account_id, $_.resolved_service_id, $_.revision_start_date } |
        Where-Object { $_.Count -gt 1 }
    
    if ($duplicateGroups.Count -gt 0) {
        Write-Host "`n❌ CSV contains duplicate account/service/date combinations. No changes were sent." -ForegroundColor Red
        foreach ($dup in $duplicateGroups) {
            $sample = $dup.Group[0]
            $serviceLabel = if ($sample.service_key) { $sample.service_key } else { $sample.resolved_service_id }
            $rows = ($dup.Group | ForEach-Object { $_.source_row_number }) -join ', '
            Write-Host "   Account $($sample.account_id), Service $serviceLabel, Date $($sample.revision_start_date): rows $rows" -ForegroundColor Yellow
        }
        return
    }
    
    Write-Host "✅ Validation passed for $($validRates.Count) row(s)." -ForegroundColor Green
    
    if ($BatchSize -le 0) {
        $BatchSize = 1
    }
    
    $totalRates = $validRates.Count
    $imported = 0
    $failed = 0
    $skippedExisting = 0
    $combinedErrorSummary = @{}
    $combinedSkipSummary = @{}
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    
    for ($i = 0; $i -lt $totalRates; $i += $BatchSize) {
        $batchEndIndex = [math]::Min($i + $BatchSize - 1, $totalRates - 1)
        $batch = if ($batchEndIndex -eq $i) { @($validRates[$i]) } else { $validRates[$i..$batchEndIndex] }
        $batchNumber = [math]::Floor($i / $BatchSize) + 1
        $totalBatches = [math]::Ceiling($totalRates / $BatchSize)
        $processed = [math]::Min($i + $batch.Count, $totalRates)
        $percentComplete = if ($totalRates -eq 0) { 100 } else { [math]::Round(($processed / $totalRates) * 100, 2) }
        $firstRow = $batch[0].source_row_number
        $lastRow = $batch[$batch.Count - 1].source_row_number
        
        Write-Progress -Activity "Importing Rates" -Status "Batch $batchNumber of $totalBatches (Processed: $processed/$totalRates)" -PercentComplete $percentComplete
        Write-Host ("   -> Batch {0}/{1}: rows {2}-{3} ({4}% complete)" -f $batchNumber, $totalBatches, $firstRow, $lastRow, [math]::Round($percentComplete, 0)) -ForegroundColor DarkGray
        
        $result = Send-RateBatch -Rates $batch
        $imported += $result.Success
        $failed += $result.Failed
        $skippedExisting += $result.SkippedExisting
        
        if ($result.ErrorSummary) {
            foreach ($errorType in $result.ErrorSummary.Keys) {
                if (-not $combinedErrorSummary.ContainsKey($errorType)) {
                    $combinedErrorSummary[$errorType] = @{
                        Count = 0
                        Examples = @()
                    }
                }
                $combinedErrorSummary[$errorType].Count += $result.ErrorSummary[$errorType].Count
                foreach ($example in $result.ErrorSummary[$errorType].Examples) {
                    if ($combinedErrorSummary[$errorType].Examples.Count -lt 5) {
                        $combinedErrorSummary[$errorType].Examples += $example
                    }
                }
            }
        }
        
        if ($result.SkippedSummary) {
            foreach ($skipType in $result.SkippedSummary.Keys) {
                if (-not $combinedSkipSummary.ContainsKey($skipType)) {
                    $combinedSkipSummary[$skipType] = @{
                        Count = 0
                        Examples = @()
                    }
                }
                $combinedSkipSummary[$skipType].Count += $result.SkippedSummary[$skipType].Count
                foreach ($example in $result.SkippedSummary[$skipType].Examples) {
                    if ($combinedSkipSummary[$skipType].Examples.Count -lt 5) {
                        $combinedSkipSummary[$skipType].Examples += $example
                    }
                }
            }
        }
    }
    
    $stopwatch.Stop()
    Write-Progress -Activity "Importing Rates" -Completed
    
    Write-Host "`n📊 Import Summary:" -ForegroundColor Cyan
    Write-Host "   Total rows processed: $totalRates"
    Write-Host "   Imported: $imported" -ForegroundColor Green
    if ($skippedExisting -gt 0) {
        Write-Host "   Skipped (already existed): $skippedExisting" -ForegroundColor Yellow
        if ($combinedSkipSummary.Count -gt 0) {
            Write-Host "`n   Skipped details:" -ForegroundColor Cyan
            foreach ($skipType in $combinedSkipSummary.Keys) {
                $skipInfo = $combinedSkipSummary[$skipType]
                Write-Host "   • $skipType : $($skipInfo.Count)" -ForegroundColor Yellow
                foreach ($example in $skipInfo.Examples) {
                    Write-Host "     - $example" -ForegroundColor DarkGray
                }
            }
        }
    }
    if ($failed -gt 0) {
        Write-Host "   Failed: $failed" -ForegroundColor Red
        if ($combinedErrorSummary.Count -gt 0) {
            Write-Host "`n   Failure details:" -ForegroundColor Cyan
            foreach ($errorType in $combinedErrorSummary.Keys) {
                $errorInfo = $combinedErrorSummary[$errorType]
                Write-Host "   • $errorType : $($errorInfo.Count)" -ForegroundColor Red
                foreach ($example in $errorInfo.Examples) {
                    Write-Host "     - $example" -ForegroundColor DarkGray
                }
            }
        }
    }
    else {
        Write-Host "   Failed: 0" -ForegroundColor Green
    }
    Write-Host ("   Duration: {0:c}" -f $stopwatch.Elapsed) -ForegroundColor DarkGray
}

function Send-RateBatch {
    <#
    .SYNOPSIS
        Send a batch of rates to the API using atomic operations
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [array]$Rates
    )
    
    $successCount = 0
    $failCount = 0
    $skippedExisting = 0
    $errorSummary = @{}
    $skippedSummary = @{}
    
    foreach ($rate in $Rates) {
        $serviceId = if ($rate.resolved_service_id) { [string]$rate.resolved_service_id } elseif ($rate.service_id) { [string]$rate.service_id } else { $null }
        $serviceLabel = if ($rate.service_key) { $rate.service_key } else { $serviceId }
        $accountIdValue = if ($null -ne $rate.account_id) { [int]$rate.account_id } else { 0 }
        $accountIdDisplay = if ($accountIdValue -eq 0) { "0" } else { [string]$accountIdValue }
        $sourceRow = if ($rate.PSObject.Properties['source_row_number']) { $rate.source_row_number } else { 'n/a' }

        $dateDigits = if ($rate.revision_start_date) { ($rate.revision_start_date.ToString() -replace '-', '') } else { $null }
        if ($dateDigits -and $dateDigits -match '^[0-9]{8}$') {
            $effectiveDate = "{0}-{1}-{2}" -f $dateDigits.Substring(0,4), $dateDigits.Substring(4,2), $dateDigits.Substring(6,2)
        }
        else {
            # Should not be hit thanks to earlier CSV validation
            $effectiveDate = if ($rate.revision_start_date) { [string]$rate.revision_start_date } else { (Get-Date).ToString('yyyy-MM-dd') }
        }

        $attributes = @{
            rate = [decimal]$rate.rate
            rate_col = ""
            min_commit = 0
            effective_date = $effectiveDate
            end_date = $null
            fixed = $null
            fixed_col = $null
            cogs_rate = if ($null -ne $rate.cogs) { [decimal]$rate.cogs } else { 0 }
            cogs_rate_col = ""
            cogs_fixed = $null
            cogs_fixed_col = $null
            tier_aggregation_level = $null
        }

        $relationships = @{
            service = @{
                data = @{
                    id = $serviceId
                    type = "service"
                }
            }
            ratetiers = @{
                data = @()
            }
        }

        if ($accountIdValue -eq 0) {
            $relationships.account = @{ data = $null }
        }
        else {
            $relationships.account = @{
                data = @{
                    type = "account"
                    id = $accountIdDisplay
                }
            }
        }

        $payload = @{
            data = @{
                type = "rate"
                attributes = $attributes
                relationships = $relationships
            }
        }

        try {
            Write-Verbose "Importing rate (row $sourceRow): account $accountIdDisplay, service $serviceLabel, date $effectiveDate"
            $null = Invoke-ExivityRateAPI -Endpoint "/v2/rates" -Method POST -Body $payload
            $successCount++
        }
        catch {
            $errorMessage = $_.ToString()
            
            $errorCategory = if ($errorMessage -match "overlapping date") {
                "Overlapping date (rate already exists)"
            }
            elseif ($errorMessage -match "service.*not found") {
                "Service not found"
            }
            elseif ($errorMessage -match "account.*not found") {
                "Account not found"
            }
            elseif ($errorMessage -match "validation") {
                "Validation error"
            }
            else {
                "Other error"
            }

            $example = "row $sourceRow -> account=$accountIdDisplay, service=$serviceLabel, date=$effectiveDate"

            if ($errorCategory -eq "Overlapping date (rate already exists)") {
                $skippedExisting++
                if (-not $skippedSummary.ContainsKey($errorCategory)) {
                    $skippedSummary[$errorCategory] = @{
                        Count = 0
                        Examples = @()
                    }
                }
                $skippedSummary[$errorCategory].Count += 1
                if ($skippedSummary[$errorCategory].Examples.Count -lt 5) {
                    $skippedSummary[$errorCategory].Examples += $example
                }
                Write-Verbose "▫ Rate already exists (row $sourceRow)"
                continue
            }

            if (-not $errorSummary.ContainsKey($errorCategory)) {
                $errorSummary[$errorCategory] = @{
                    Count = 0
                    Examples = @()
                }
            }
            $errorSummary[$errorCategory].Count += 1
            if ($errorSummary[$errorCategory].Examples.Count -lt 5) {
                $errorSummary[$errorCategory].Examples += $example
            }
            $failCount++
            Write-Verbose "✗ Rate import failed ($errorCategory): $example"
        }
    }

    return @{
        Success = $successCount
        Failed = $failCount
        ErrorSummary = $errorSummary
        SkippedExisting = $skippedExisting
        SkippedSummary = $skippedSummary
    }
}

function Export-RatesToCSV {
    <#
    .SYNOPSIS
        Export rates to CSV file (includes service_key for easier reference)
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$CSVPath,
        
        [Parameter(Mandatory = $false)]
        [int]$AccountId
    )
    
    Write-Host "`n📤 Exporting rates to: $CSVPath" -ForegroundColor Cyan
    
    try {
        $allRatesData = @()
        $allIncludedServices = @{}
        $allIncludedAccounts = @{}
        $limit = 500
        $offset = 1
        $totalRates = $null
        
        do {
            $endpoint = "/v2/rates?limit=$limit&page[offset]=$offset&include=service,account"
            if ($AccountId) {
                $endpoint += "&filter[account_id]=$AccountId"
            }
            
            Write-Verbose "Fetching rates page $offset (limit=$limit)..."
            $response = Invoke-ExivityRateAPI -Endpoint $endpoint -Method GET
            
            if ($response -and $response.data -and $response.data.Count -gt 0) {
                $allRatesData += $response.data
                
                # Get total from first response
                if ($null -eq $totalRates -and $response.meta -and $response.meta.pagination -and $response.meta.pagination.total) {
                    $totalRates = $response.meta.pagination.total
                    Write-Verbose "Total rates to export: $totalRates"
                }
                
                # Collect included services and accounts from this page
                if ($response.included) {
                    foreach ($item in $response.included) {
                        if ($item.type -eq "service" -and -not $allIncludedServices.ContainsKey($item.id)) {
                            $allIncludedServices[$item.id] = $item.attributes
                        }
                        elseif ($item.type -eq "account" -and -not $allIncludedAccounts.ContainsKey($item.id)) {
                            $allIncludedAccounts[$item.id] = $item.attributes
                        }
                    }
                }
                
                Write-Verbose "Loaded $($response.data.Count) rates (total so far: $($allRatesData.Count))"
                
                # Check if there are more pages
                if ($response.links -and $response.links.next) {
                    $offset++
                }
                else {
                    Write-Verbose "No more pages"
                    break
                }
            }
            else {
                Write-Verbose "No more rates"
                break
            }
        } while ($true)
        
        if ($allRatesData.Count -eq 0) {
            Write-Warning "No rates found to export"
            return
        }
        
        Write-Verbose "Loaded total of $($allRatesData.Count) rates"
        Write-Verbose "Loaded $($allIncludedServices.Count) unique services and $($allIncludedAccounts.Count) unique accounts"
        
        # Process all rates
        $allRates = @()
        foreach ($rate in $allRatesData) {
            # Get service_id and account_id from relationships
            $serviceId = if ($rate.relationships.service.data) { $rate.relationships.service.data.id } else { $null }
            $accountId = if ($rate.relationships.account.data) { $rate.relationships.account.data.id } else { $null }
            
            # Get service key and description from included data or cache
            $serviceKey = ""
            $serviceDescription = ""
            
            if ($serviceId) {
                if ($allIncludedServices.ContainsKey($serviceId)) {
                    $serviceKey = $allIncludedServices[$serviceId].key
                    $serviceDescription = $allIncludedServices[$serviceId].description
                }
                else {
                    # Fallback to cache
                    $serviceKey = Get-ServiceKey -ServiceId $serviceId
                    $serviceDescription = Get-ServiceDescription -ServiceId $serviceId
                }
            }
            
            $rateObj = [PSCustomObject]@{
                account_id = $accountId
                service_id = $serviceId
                service_key = $serviceKey
                service_description = $serviceDescription
                rate = $rate.attributes.rate
                cogs = $rate.attributes.cogs_rate
                revision_start_date = $rate.attributes.effective_date -replace '-', ''
            }
            
            $allRates += $rateObj
        }
        
        if ($allRates.Count -eq 0) {
            Write-Warning "No rates found to export"
            return
        }
        
        # Export to CSV
        $allRates | Export-Csv -Path $CSVPath -NoTypeInformation -Encoding UTF8
        
        # Count rates with service keys
        $ratesWithKeys = ($allRates | Where-Object { $_.service_key -and $_.service_key -ne "" }).Count
        
        Write-Host "✅ Exported $($allRates.Count) rates to $CSVPath" -ForegroundColor Green
        Write-Host "   - Rates with service_key: $ratesWithKeys" -ForegroundColor Cyan
        Write-Host "   - Rates without service_key: $($allRates.Count - $ratesWithKeys)" -ForegroundColor Cyan
    }
    catch {
        Write-Error "❌ Export failed: $_"
    }
}

function Test-RateExists {
    <#
    .SYNOPSIS
        Check if a specific rate exists
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$AccountId,
        
        [Parameter()]
        [int]$ServiceId,
        
        [Parameter()]
        [string]$ServiceKey,
        
        [Parameter(Mandatory = $true)]
        [string]$EffectiveDate
    )
    
    $limit = 1
    
    # Resolve service_id
    $resolvedServiceId = Resolve-ServiceId -ServiceId $ServiceId -ServiceKey $ServiceKey
    if (-not $resolvedServiceId) {
        Write-Error "❌ Could not resolve service"
        return
    }
    
    $dateStr = $EffectiveDate -replace '-', ''
    
    try {
        $endpoint = "/v2/rates?limit=$limit&filter[account_id]=$AccountId&filter[service_id]=$resolvedServiceId&filter[revision_start_date]=$dateStr"
        $response = Invoke-ExivityRateAPI -Endpoint $endpoint -Method GET
        
        if ($response -and $response.data -and $response.data.Count -gt 0) {
            $rate = $response.data[0].attributes
            Write-Host "✅ Rate found:" -ForegroundColor Green
            Write-Host "   Account ID: $($rate.account_id)"
            Write-Host "   Service ID: $($rate.service_id)"
            
            if ($rate.service_id) {
                $serviceKey = Get-ServiceKey -ServiceId $rate.service_id
                if ($serviceKey) {
                    Write-Host "   Service Key: $serviceKey"
                }
            }
            
            Write-Host "   Rate: $($rate.rate)"
            Write-Host "   COGS: $($rate.cogs)"
            Write-Host "   Effective: $($rate.revision_start_date)"
            return $true
        }
        else {
            Write-Host "❌ Rate not found" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Error "❌ Check failed: $_"
        return $false
    }
}

# ============================================================================
# INTERACTIVE MENU
# ============================================================================

function Show-Menu {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  EXIVITY RATE MANAGER v2.0" -ForegroundColor Cyan
    Write-Host "  (with Service Key Support)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Import rates from CSV"
    Write-Host "2. Export rates to CSV"
    Write-Host "3. Check if rate exists"
    Write-Host "4. Reload service cache"
    Write-Host "Q. Quit"
    Write-Host ""
}

function Start-InteractiveMode {
    Write-Host "🚀 Starting Interactive Mode" -ForegroundColor Cyan
    Write-Host ""
    
    # Get connection details
    $baseUrlInput = Read-Host "Enter Exivity Base URL (e.g., https://localhost)"
    $baseUrl = Resolve-BaseUrl -Url $baseUrlInput
    if (-not $baseUrl) {
        Write-Host "❌ Base URL is required. Exiting." -ForegroundColor Red
        return
    }
    if ($baseUrlInput -and ($baseUrl -ne $baseUrlInput.Trim())) {
        Write-Host "ℹ️ Normalized Base URL to: $baseUrl" -ForegroundColor DarkGray
    }
    else {
        Write-Host "ℹ️ Using Base URL: $baseUrl" -ForegroundColor DarkGray
    }

    $username = Read-Host "Enter Username"
    $securePassword = Read-Host "Enter Password" -AsSecureString
    $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    )
    
    # Connect
    $connected = Connect-ExivityRateAPI -BaseUrl $baseUrl -Username $username -Password $password
    
    if (-not $connected) {
        Write-Host "❌ Failed to connect. Exiting." -ForegroundColor Red
        return
    }
    
    # Main menu loop
    do {
        Show-Menu
        $choice = Read-Host "Enter your choice"
        
        switch ($choice) {
            '1' {
                $csvPath = Read-Host "Enter CSV file path"
                $batchSize = Read-Host "Enter batch size (default: 50)"
                if ([string]::IsNullOrWhiteSpace($batchSize)) { $batchSize = 50 }
                Import-RatesFromCSV -CSVPath $csvPath -BatchSize ([int]$batchSize)
                Read-Host "`nPress Enter to continue"
            }
            '2' {
                $csvPath = Read-Host "Enter output CSV file path"
                $accountId = Read-Host "Enter Account ID (optional, leave blank for all)"
                if ([string]::IsNullOrWhiteSpace($accountId)) {
                    Export-RatesToCSV -CSVPath $csvPath
                }
                else {
                    Export-RatesToCSV -CSVPath $csvPath -AccountId ([int]$accountId)
                }
                Read-Host "`nPress Enter to continue"
            }
            '3' {
                $accountId = Read-Host "Enter Account ID"
                Write-Host "You can provide either service_id OR service_key"
                $serviceId = Read-Host "Enter Service ID (leave blank to use service_key)"
                $serviceKey = ""
                if ([string]::IsNullOrWhiteSpace($serviceId)) {
                    $serviceKey = Read-Host "Enter Service Key"
                }
                $effectiveDate = Read-Host "Enter effective date (YYYYMMDD or YYYY-MM-DD)"
                
                if ([string]::IsNullOrWhiteSpace($serviceId)) {
                    Test-RateExists -AccountId ([int]$accountId) -ServiceKey $serviceKey -EffectiveDate $effectiveDate
                }
                else {
                    Test-RateExists -AccountId ([int]$accountId) -ServiceId ([int]$serviceId) -EffectiveDate $effectiveDate
                }
                Read-Host "`nPress Enter to continue"
            }
            '4' {
                Load-ServiceCache
                Read-Host "`nPress Enter to continue"
            }
            'Q' {
                Write-Host "`n👋 Goodbye!" -ForegroundColor Green
                return
            }
            default {
                Write-Host "❌ Invalid choice. Please try again." -ForegroundColor Red
                Start-Sleep -Seconds 1
            }
        }
    } while ($true)
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

Start-InteractiveMode
