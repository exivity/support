<#
.SYNOPSIS
    Export an Exivity report run to CSV.

.DESCRIPTION
    Prompts for Exivity host, credentials, report id, depth, and date range.
    Authenticates against /v2/auth/token and downloads the CSV from /v1/reports/{id}/run.
    Designed for older Windows PowerShell and Exivity servers using self-signed certificates.
#>

param(
    [string]$ExivityHost,
    [string]$Username,
    [string]$Password,
    [string]$ReportId,
    [string]$Depth,
    [string]$FromDate,
    [string]$ToDate,
    [string]$OutputFile
)

function Enable-SelfSignedCertificateSupport {
    $trustAllCertsPolicyExists = $true
    try {
        $null = [TrustAllCertsPolicy]
    }
    catch {
        $trustAllCertsPolicyExists = $false
    }

    if (-not $trustAllCertsPolicyExists) {
        Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;

public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint srvPoint,
        X509Certificate certificate,
        WebRequest request,
        int certificateProblem) {
        return true;
    }
}
"@
    }

    [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
}

function ConvertFrom-SecureStringToPlainText {
    param(
        [Parameter(Mandatory = $true)]
        [Security.SecureString]$SecureString
    )

    $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Get-ExivityBaseUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HostName
    )

    $hostName = $HostName.Trim().TrimEnd('/')
    if ($hostName -notmatch '^https?://') {
        $hostName = "https://$hostName"
    }

    return $hostName
}

function ConvertTo-JsonStringLiteral {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        return ""
    }

    return $Value.Replace('\', '\\').Replace('"', '\"').Replace("`r", '\r').Replace("`n", '\n').Replace("`t", '\t')
}

Enable-SelfSignedCertificateSupport

if ($null -eq $ExivityHost -or $ExivityHost.Trim().Length -eq 0) {
    $ExivityHost = Read-Host "Exivity hostname, for example exivity.example.com"
}

if ($null -eq $Username -or $Username.Trim().Length -eq 0) {
    $Username = Read-Host "Username"
}

if ($null -eq $Password) {
    $securePassword = Read-Host "Password" -AsSecureString
    $Password = ConvertFrom-SecureStringToPlainText -SecureString $securePassword
}

if ($null -eq $ReportId -or $ReportId.Trim().Length -eq 0) {
    $ReportId = Read-Host "Report ID"
}

if ($null -eq $Depth -or $Depth.Trim().Length -eq 0) {
    $Depth = Read-Host "Report depth"
}

if ($null -eq $FromDate -or $FromDate.Trim().Length -eq 0) {
    $FromDate = Read-Host "From date, for example 2026-06-01"
}

if ($null -eq $ToDate -or $ToDate.Trim().Length -eq 0) {
    $ToDate = Read-Host "To date, for example 2026-06-30"
}

if ($null -eq $OutputFile) {
    $OutputFile = Read-Host "Output CSV file path, leave empty for default"
}

if ($null -eq $OutputFile -or $OutputFile.Trim().Length -eq 0) {
    $OutputFile = Join-Path -Path (Get-Location) -ChildPath ("exivity-report-{0}.csv" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
}

$baseUrl = Get-ExivityBaseUrl -HostName $ExivityHost

try {
    Write-Host "Requesting token..."

    $authBody = '{"username":"' + (ConvertTo-JsonStringLiteral $Username) + '","password":"' + (ConvertTo-JsonStringLiteral $Password) + '"}'

    $authClient = New-Object System.Net.WebClient
    $authClient.Headers.Add("Content-Type", "application/json")
    $tokenResponse = $authClient.UploadString("$baseUrl/v2/auth/token", "POST", $authBody)
    $tokenMatch = [Regex]::Match($tokenResponse, '"token"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')

    if (-not $tokenMatch.Success) {
        throw "Token was not found in the authentication response."
    }

    $token = $tokenMatch.Groups[1].Value

    if ($null -eq $token -or $token.Trim().Length -eq 0) {
        throw "Token was not found in the authentication response."
    }

    Write-Host "Downloading report CSV..."

    $query = "start={0}&end={1}&format=csv&include=account_key%2Caccount_name%2Cservice_key%2Cservice_description%2Cservicecategory_name%2Cstart_date%2Cend_date&summary_options=services%2Caccounts&dimension=accounts%2Cservices&timeline=day&depth={2}" -f `
        [Uri]::EscapeDataString($FromDate),
        [Uri]::EscapeDataString($ToDate),
        [Uri]::EscapeDataString($Depth)

    $reportUrl = "$baseUrl/v1/reports/$([Uri]::EscapeDataString($ReportId))/run?$query"

    $webClient = New-Object System.Net.WebClient
    $webClient.Headers.Add("Authorization", "Bearer $token")
    $webClient.Headers.Add("Accept", "text/csv")
    $webClient.DownloadFile($reportUrl, $OutputFile)

    Write-Host "CSV written to: $OutputFile"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
