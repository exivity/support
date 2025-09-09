# Exivity Management CLI

A comprehensive command-line interface for managing Exivity operations including rate management, workflow creation, and environment configuration.

## Features

- **Rate Management**: Import, validate, export, and index rates with CSV support
- **Workflow Management**: Create workflows with configurable environment duplication
- **Environment Management**: Manage environments with flexible naming conventions
- **Configuration Management**: YAML-based configuration with interactive editing
- **Interactive Menus**: User-friendly questionary-based navigation with topic organization
- **Batch Operations**: Efficient bulk processing with atomic operations
- **Data Validation**: Comprehensive validation against system data
- **Export Operations**: Export rates and environment settings to CSV/JSON

## Installation

1. **Install Dependencies**:
   ```bash
   pip install requests questionary PyYAML
   ```

2. **Install Package** (Optional):
   ```bash
   pip install -e .
   ```

3. **Run the CLI**:
   ```bash
   python -m exivity_cli.main
   # OR (if installed as package)
   exivity-cli
   # OR
   python exivity-cli.py
   # OR
   python run_cli.py
   ```

## Quick Start

1. **Connect to API**: Enter your Exivity server URL, credentials, and SSL preferences
2. **Choose Operation**: Select from Rate Management, Workflow Management, or Environment Management
3. **Follow Prompts**: Use the interactive menus to perform operations
4. **Configure Settings**: Use the Configuration menu to customize defaults and behavior

---

## 📖 User Manual

### 🚀 Getting Started

#### Initial Connection
When you start the CLI, you'll be prompted for:
- **Base URL**: Your Exivity server URL (e.g., `https://localhost`)
- **SSL Verification**: Choose "No" for self-signed certificates
- **Username**: Default is "admin" (configurable)
- **Password**: Default is "exivity" (configurable)

The CLI now supports YAML-based configuration in `config.yaml` for default connection settings, environment naming conventions, and other preferences.

### 💰 Rate Management

#### System Overview
View comprehensive system statistics:
- Total accounts, services, and rates
- Account hierarchy breakdown
- Service categories
- Rate distribution by account
- Date ranges of existing rates

#### Export Rates to CSV
Export existing rates for backup or analysis:
1. Select "Export rates to CSV file"
2. Choose export format (account rates or list prices)
3. Select date range and filters
4. Review export summary
5. Download CSV file

**Features**:
- **Account Rates Export**: Complete rate data with account/service details
- **List Prices Export**: Simplified pricing data format
- **Date Range Filtering**: Export rates for specific time periods
- **Service Name Inclusion**: Optional service name lookup
- **Multiple Formats**: YYYYMMDD or YYYY-MM-DD date formats

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
Create workflows that run across configurable environments:

**Process**:
1. Enter workflow name and description
2. Handle existing workflows (delete/recreate option)
3. Configure date offsets for all steps
4. Build workflow steps interactively

**Configuration Options**:
- **Environment Count**: Configure number of environments (default: 24)
- **Naming Convention**: Customize environment naming (e.g., hour_00, shift_01)
- **Variable Creation**: Automatically add environment variables
- **Timeout Settings**: Default timeout per workflow step

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
Configuration: 24 environments (hour_00-hour_23)
Steps:
1. Extract: "DataSource" script
2. Transform: "ProcessData" script  
3. Prepare Report: Report ID 123

Result: 48 total steps (2 × 24 environments)
```

#### Advanced Workflow Tools
- **Hourly Workflow Tools**: Create, list, duplicate, and delete hourly workflows
- **Cross-Hour Duplication**: Copy workflows across different time periods
- **Workflow Editing**: Modify existing workflow parameters
- **Bulk Operations**: Manage multiple workflows simultaneously

#### Environment Management

**Environment Status**:
View status of configured environments:
- ✅ Existing environments with IDs
- ❌ Missing environments
- 🏠 Default environment identification
- 📊 Environment health checking

**Environment Operations**:
- **Create Missing**: Automatically creates missing environments based on configuration
- **Bulk Configuration**: Update multiple environment settings simultaneously
- **Export/Import Settings**: Backup and restore environment configurations
- **Interactive Creation/Deletion**: Manual environment management

**Flexible Configuration**:
- **Configurable Count**: Set any number of environments (not limited to 24)
- **Custom Naming**: Define prefix, suffix format (e.g., `region_01`, `hour_00`)
- **Variable Management**: Automatically create environment-specific variables
- **Naming Patterns**: Support for various naming conventions via config.yaml

### ⚙️ Configuration Management

#### YAML Configuration
The CLI now uses a comprehensive YAML configuration system (`config.yaml`):

**Configuration Sections**:
- **Connection**: Default hostname, port, credentials, SSL settings
- **Environments**: Count, naming conventions, variable creation
- **Workflows**: Default timeouts, date offsets, wait settings
- **Rates**: Default values, CSV export formats
- **API**: Timeout, retry settings, pagination
- **Logging**: Debug levels, request logging
- **Paths**: Directory locations for CSV, logs, environments

**Interactive Configuration**:
- **Show Configuration**: View current settings
- **Edit Configuration**: Modify settings through interactive prompts
- **Reload Configuration**: Refresh from config.yaml
- **Save Configuration**: Persist changes to file

**Example Configuration**:
```yaml
environments:
  count: 24
  naming:
    prefix: "hour_"
    suffix_format: "{:02d}"
  variables:
    - name: "hour"
      value_format: "{:02d}"
      encrypted: false
```

### 🔧 Advanced Features

#### Enhanced Menu System
- **Topic-Based Navigation**: Organized by Rate, Workflow, Environment, and Configuration
- **Streamlined Interface**: Simplified menu structure with clear categorization
- **Context-Sensitive Options**: Menu items adapt based on current state
- **Progress Indicators**: Visual feedback for long-running operations
#### API Debugging
Built-in tools for troubleshooting:
- **Endpoint Testing**: Check v1/v2 API availability
- **Dump Endpoint Testing**: Verify data export functionality
- **Environment Creation Testing**: Debug environment issues
- **SSL Configuration**: Handle certificate problems
- **Configuration Validation**: Verify settings and connectivity

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
├── config.yaml              # Main configuration file
├── csv/                     # CSV files for rate import
├── environments/            # Environment configurations  
├── workflows/              # Workflow templates
├── exivity_cli/
│   ├── __init__.py         # Package initialization
│   ├── main.py            # Main entry point
│   ├── config.py          # Configuration management
│   ├── api/
│   │   ├── client.py      # API client with all endpoints
│   │   └── debug.py       # Debug and testing tools
│   └── modules/
│       ├── rate_management.py      # Rate operations
│       ├── workflow_management.py  # Workflow operations
│       └── environment_management.py # Environment operations
├── setup.py               # Package installation
├── exivity-cli.py         # Standalone script
├── run_cli.py            # Development runner
└── README.md             # This file
```

### 🎯 Best Practices

#### Rate Management
- **Validate First**: Always use CSV validation before importing
- **Export Before Changes**: Use rate export to backup existing data
- **Test Indexation**: Try account-specific indexation on small accounts first
- **Monitor Progress**: Watch batch processing for any failures
- **Use Configuration**: Set default values in config.yaml for consistency

#### Workflow Management  
- **Environment Check**: Verify all configured environments exist before workflow creation
- **Configure Defaults**: Use config.yaml to set standard timeout and date offset values
- **Date Offsets**: Use consistent offsets across all steps
- **Step Order**: Plan extract → transform → report sequence
- **Testing**: Test workflows on single environment first

#### Environment Management
- **Configure Naming**: Use config.yaml to define consistent naming patterns
- **Health Checks**: Regularly verify environment status
- **Backup Settings**: Export environment configurations before major changes
- **Variable Management**: Use automatic variable creation for consistency

#### Configuration Management
- **YAML-First**: Configure defaults in config.yaml rather than entering repeatedly
- **Version Control**: Keep config.yaml in version control for team consistency
- **Environment-Specific**: Use different config files for dev/staging/production
- **Validation**: Use the configuration menu to verify settings

#### File Management
- **CSV Organization**: Keep CSV files in the `csv/` folder (configurable)
- **Naming Convention**: Use descriptive names like `rates_2024_Q4.csv`
- **Encoding**: Save CSV files as UTF-8 with BOM for best compatibility
- **Configuration Files**: Organize environment and workflow templates in respective folders

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

**Configuration Issues**:
```
Check: config.yaml syntax, file permissions, default values
Solution: Use configuration menu to validate and edit settings
```

**Environment Creation Failures**:
```
Check: Environment naming conflicts, default environment issues
Solution: Use environment debug tools and configuration validation
```

#### Debug Mode
Enable detailed logging:
1. Select debug options in relevant menus
2. Review API endpoint responses
3. Check payload formats
4. Verify server compatibility
5. Use configuration menu to check settings

#### Performance Tips
- Use batch operations for large datasets
- Enable data caching for repeated operations
- Configure appropriate timeout values in config.yaml
- Use account-specific operations when possible
- Leverage YAML configuration to avoid repetitive input

### 📊 Supported Operations Summary

| Feature | Batch Support | Validation | Fallback | Progress Tracking | Configuration |
|---------|---------------|------------|----------|-------------------|---------------|
| CSV Import | ✅ (50/batch) | ✅ | ✅ | ✅ | ✅ |
| CSV Export | ✅ | ✅ | ✅ | ✅ | ✅ |
| Rate Indexation | ✅ (50/batch) | ✅ | ✅ | ✅ | ✅ |
| Workflow Creation | ✅ (Atomic) | ✅ | ✅ | ✅ | ✅ |
| Environment Creation | ✅ | ✅ | ✅ | ✅ | ✅ |
| Environment Export/Import | ✅ | ✅ | ✅ | ✅ | ✅ |
| Configuration Management | N/A | ✅ | N/A | N/A | ✅ |

### 🔄 Version Compatibility

**API Versions**:
- Primary: v2 API with atomic operations
- Fallback: v1 API for compatibility
- Auto-detection: Automatically tries best available method

**Exivity Compatibility**:
- Tested with Exivity 4.x and newer
- Backward compatibility with v1 endpoints
- SSL/TLS support for secure connections
- Configuration-driven defaults for various Exivity versions

**Installation Methods**:
- **Development**: Direct Python execution with dependencies
- **Package**: Install via setup.py for system-wide access
- **Portable**: Standalone script execution

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Use built-in debug tools
3. Review API endpoint responses
4. Check configuration settings in config.yaml
5. Consult Exivity documentation for API specifics

**New in Recent Updates**:
- ✨ YAML-based configuration system
- 🔧 Interactive configuration management
- 📤 Rate export functionality
- 🏗️ Flexible environment naming and count
- 📋 Enhanced menu organization
- ⚙️ Package installation support
- 🔄 Improved error handling and validation

**Happy managing! 🚀**
