# Exivity Management CLI

A comprehensive command-line interface for managing Exivity instances with an intuitive menu-driven interface.

## Features

### 💰 Rate Management
- Import rate revisions from CSV files
- Validate CSV format before processing
- Check existing rate revision status
- Batch processing with atomic operations

### ⚙️ Workflow Management
- Create hourly workflows with interactive step builder
- List and manage existing workflows
- Duplicate workflows across environments
- Delete workflows with confirmation

### 🌐 Environment Management
- Manage hourly environments (H00-H23)
- Create missing environments
- Delete and recreate environments
- Status monitoring and reporting

## Installation

```bash
pip install -e .
```

## Usage

### Command Line
```bash
exivity-cli
```

### Interactive Menus
The CLI provides a user-friendly menu system:

1. **Main Menu**: Choose management area
2. **Rate Management**: Handle rate-related operations
3. **Workflow Management**: Create and manage workflows
4. **Environment Management**: Manage hourly environments

## Configuration

The CLI will prompt for:
- API Base URL
- Username/Password
- SSL verification settings

## Project Structure
```
exivity_cli/
├── __init__.py
├── main.py              # Main CLI application
├── api/
│   ├── __init__.py
│   └── client.py        # API client
└── modules/
    ├── __init__.py
    ├── rate_management.py      # Rate operations
    ├── workflow_management.py  # Workflow operations
    └── environment_management.py # Environment operations
```
