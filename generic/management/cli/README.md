# Exivity Management CLI

A comprehensive command-line interface for managing Exivity operations including rate management, workflow creation, and environment configuration.

## Features

- **Rate Management**: Import, validate, and index rates with CSV support
- **Workflow Management**: Create workflows with 24-hour environment duplication
- **Environment Management**: Manage hourly environments (H00-H23)
- **Interactive Menus**: User-friendly questionary-based navigation
- **Batch Operations**: Efficient bulk processing with atomic operations
- **Data Validation**: Comprehensive validation against system data

## Installation

1. **Install Dependencies**:
   ```bash
   pip install requests questionary
   ```

2. **Run the CLI**:
   ```bash
   python -m exivity_cli.main
   # OR
   python exivity-cli.py
   # OR
   python run_cli.py
   ```

## Quick Start

1. **Connect to API**: Enter your Exivity server URL, credentials, and SSL preferences
2. **Choose Operation**: Select from Rate Management or Workflow Management
3. **Follow Prompts**: Use the interactive menus to perform operations

---

## 📖 User Manual

### 🚀 Getting Started

#### Initial Connection
When you start the CLI, you'll be prompted for:
- **Base URL**: Your Exivity server URL (e.g., `https://localhost`)
- **SSL Verification**: Choose "No" for self-signed certificates
- **Username**: Default is "admin"
- **Password**: Default is "exivity"

### 💰 Rate Management

#### System Overview
View comprehensive system statistics:
- Total accounts, services, and rates
- Account hierarchy breakdown
- Service categories
- Rate distribution by account
- Date ranges of existing rates

#### CSV Rate Import

**Supported CSV Format**:
```csv
account_id,service_id,rate,cogs,revision_start_date
1234,56,10.50,8.25,20241201
5678,78,25.00,20.00,20241201
```

**Required Columns**:
- `account_id`: Numeric account identifier
- `service_id`: Numeric service identifier  
- `rate`: Rate value (decimal)
- `cogs`: Cost of goods sold (decimal)
- `revision_start_date`: Date in YYYYMMDD or YYYY-MM-DD format

**Import Process**:
1. Place CSV files in the `csv/` folder or specify custom path
2. Select "Import rates from CSV file"
3. Choose your CSV file from the list
4. Review validation results
5. Confirm import

**Features**:
- **Multiple encoding support**: UTF-8, UTF-8-BOM, CP1252, ISO-8859-1
- **Duplicate detection**: Automatically skips existing rates
- **Batch processing**: Efficient atomic operations (50 records per batch)
- **Error handling**: Individual fallback for failed batches
- **Progress tracking**: Real-time status updates

#### CSV Validation
Test your CSV before importing:
1. Select "Validate CSV before import"
2. Choose CSV file
3. Review validation report:
   - ✅ Valid rows ready for import
   - ❌ Invalid account/service IDs
   - ⚠️ Missing required fields
   - 📊 Existing rates (will be skipped)

#### Rate Indexation
Apply percentage changes to existing rates:

**Global Indexation** (All Accounts):
1. Select "Rate indexation" → "All accounts"
2. Enter percentage change (e.g., `5` for +5%, `-3` for -3%)
3. Enter effective date (YYYYMMDD or YYYY-MM-DD)
4. Review proposed changes
5. Confirm creation

**Account-Specific Indexation**:
1. Select "Rate indexation" → "Account-specific rates"
2. Enter target account ID
3. Enter percentage change
4. Enter effective date
5. Review proposed changes
6. Confirm creation

**Features**:
- **Smart rate selection**: Automatically finds latest rate per account/service
- **Duplicate prevention**: Checks for existing rates on target date
- **Data validation**: Skips invalid or zero rates
- **Batch processing**: Efficient creation with progress tracking
- **Preview changes**: Shows sample rate calculations before execution

#### Rate Status Checker
Verify if specific rate revisions exist:
1. Enter account ID, service ID, and effective date
2. Get instant status: EXISTS or NOT FOUND
3. Optional debug mode for API troubleshooting

### ⚙️ Workflow Management

#### Hourly Workflow Creation
Create workflows that run across all 24 hourly environments:

**Process**:
1. Enter workflow name and description
2. Handle existing workflows (delete/recreate option)
3. Configure date offsets for all steps
4. Build workflow steps interactively:

**Step Types**:

**Extract Steps**:
- Script name (required)
- Arguments (optional)
- From/to date offsets
- Automatically assigned to environment

**Transform Steps**:
- Script name (required)  
- From/to date offsets
- Automatically assigned to environment

**Prepare Report Steps**:
- Report ID (required)
- From/to date offsets
- No environment assignment needed

**Example Workflow**:
```
Workflow: Daily Processing
Steps:
1. Extract: "DataSource" script
2. Transform: "ProcessData" script  
3. Prepare Report: Report ID 123

Result: 48 total steps (2 × 24 environments)
```

#### Environment Management

**Hourly Environments Status**:
View status of H00-H23 environments:
- ✅ Existing environments with IDs
- ❌ Missing environments
- 🏠 Default environment identification

**Recreate Missing Environments**:
- Automatically creates missing H00-H23 environments
- Adds hour variables (hour=00, hour=01, etc.)
- Protects existing environments

**Delete Hourly Environments**:
- ⚠️ **CAUTION**: Deletes all H00-H23 environments
- 🛡️ **Protection**: Default environment cannot be deleted
- Requires double confirmation for safety

### 🔧 Advanced Features

#### API Debugging
Built-in tools for troubleshooting:
- **Endpoint Testing**: Check v1/v2 API availability
- **Dump Endpoint Testing**: Verify data export functionality
- **Environment Creation Testing**: Debug environment issues
- **SSL Configuration**: Handle certificate problems

#### Data Caching
Optimized performance features:
- **Dump Data Caching**: Reduces API calls for validation
- **Smart Cache Clearing**: Refreshes after data modifications
- **Efficient Lookups**: Fast duplicate detection

#### Error Handling
Comprehensive error management:
- **Multiple Fallbacks**: v2 → v1 → simplified approaches
- **Detailed Logging**: Full error reporting with solutions
- **Graceful Degradation**: Continue processing despite individual failures
- **Progress Recovery**: Resume operations after interruptions

### 📂 File Organization

```
cli/
├── csv/                    # CSV files for rate import
├── environments/           # Environment configurations  
├── workflows/             # Workflow templates
├── exivity_cli/
│   ├── main.py           # Main entry point
│   ├── api/
│   │   ├── client.py     # API client with all endpoints
│   │   └── debug.py      # Debug and testing tools
│   └── modules/
│       ├── rate_management.py      # Rate operations
│       ├── workflow_management.py  # Workflow operations
│       └── environment_management.py # Environment operations
├── exivity-cli.py        # Standalone script
├── run_cli.py           # Development runner
└── README.md            # This file
```

### 🎯 Best Practices

#### Rate Management
- **Validate First**: Always use CSV validation before importing
- **Backup Data**: Export existing rates before major changes
- **Test Indexation**: Try account-specific indexation on small accounts first
- **Monitor Progress**: Watch batch processing for any failures

#### Workflow Management  
- **Environment Check**: Verify all 24 environments exist before workflow creation
- **Date Offsets**: Use consistent offsets across all steps
- **Step Order**: Plan extract → transform → report sequence
- **Testing**: Test workflows on single environment first

#### File Management
- **CSV Organization**: Keep CSV files in the `csv/` folder
- **Naming Convention**: Use descriptive names like `rates_2024_Q4.csv`
- **Encoding**: Save CSV files as UTF-8 with BOM for best compatibility

### 🚨 Troubleshooting

#### Common Issues

**SSL Certificate Errors**:
```
Solution: Choose "No" for SSL verification during connection
```

**CSV Import Failures**:
```
Check: File encoding, column names, data format
Solution: Use CSV validation first
```

**Authentication Issues**:
```
Check: Username, password, server URL
Solution: Use debug mode to test endpoints
```

**Environment Creation Failures**:
```
Check: Default environment conflicts
Solution: Use environment debug tools
```

#### Debug Mode
Enable detailed logging:
1. Select debug options in relevant menus
2. Review API endpoint responses
3. Check payload formats
4. Verify server compatibility

#### Performance Tips
- Use batch operations for large datasets
- Enable data caching for repeated operations
- Close and restart CLI if memory usage grows
- Use account-specific operations when possible

### 📊 Supported Operations Summary

| Feature | Batch Support | Validation | Fallback | Progress Tracking |
|---------|---------------|------------|----------|-------------------|
| CSV Import | ✅ (50/batch) | ✅ | ✅ | ✅ |
| Rate Indexation | ✅ (50/batch) | ✅ | ✅ | ✅ |
| Workflow Creation | ✅ (Atomic) | ✅ | ✅ | ✅ |
| Environment Creation | ✅ | ✅ | ✅ | ✅ |
| Data Export | ✅ | ✅ | ✅ | ✅ |

### 🔄 Version Compatibility

**API Versions**:
- Primary: v2 API with atomic operations
- Fallback: v1 API for compatibility
- Auto-detection: Automatically tries best available method

**Exivity Compatibility**:
- Tested with Exivity 4.x and newer
- Backward compatibility with v1 endpoints
- SSL/TLS support for secure connections

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Use built-in debug tools
3. Review API endpoint responses
4. Consult Exivity documentation for API specifics

**Happy managing! 🚀**
