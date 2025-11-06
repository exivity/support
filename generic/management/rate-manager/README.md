# Exivity Rate Manager

Interactive PowerShell tool for managing Exivity rates via CSV import/export.

## Requirements

- PowerShell 5.1 or later
- Access to Exivity API (v2)

## Usage

Run the script to launch the interactive menu:

```powershell
.\ExivityRateManager.ps1
```

You'll be prompted to:
1. Enter your Exivity Base URL (e.g., `https://localhost` or `localhost`)
2. Provide credentials
3. Choose from the menu options

## Features

- **Import rates from CSV** - Batch import with validation and progress tracking
- **Export rates to CSV** - Export all rates or filter by account
- **Check if rate exists** - Verify specific rates by account, service, and date
- **Reload service cache** - Refresh the service key mappings

## CSV Format

The tool supports both `service_id` and `service_key` for easier rate management:

```csv
account_id,service_id,service_key,rate,cogs,revision_start_date
3726,,C3i|CPU|D,0.00542937240000,0,20251001
3727,182,,0.020691400797809,0,20251001
```

### Required Columns

- `account_id` - Account ID (numeric)
- `service_id` OR `service_key` - At least one must be provided
- `rate` - Rate value (decimal)
- `revision_start_date` - Date in YYYYMMDD format

### Optional Columns

- `cogs` - Cost of goods sold (decimal)
- `service_description` - Description (not used for import, included in exports)

## Notes

- BaseURL auto-normalizes: `localhost` → `https://localhost`
- CSV validation runs before any API calls to prevent partial imports
- Duplicate account/service/date combinations are detected and rejected
- Existing rates (overlapping dates) are skipped, not failed
- Service keys are cached on connection for fast lookups
- SSL verification is disabled by default for self-signed certificates

## Example Workflow

1. Run the script
2. Connect to your Exivity instance
3. Select "1. Import rates from CSV"
4. Provide the path to your CSV file
5. Review the import summary

For exports, the CSV will include both `service_id` and `service_key` for maximum compatibility.
