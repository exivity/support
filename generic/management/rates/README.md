# Get Services with Rates

A Python script to export the latest global rates for all services from Exivity.

## Purpose

This script fetches all services and their most recent global rate information, outputting a CSV report showing:
- Service ID and name
- Latest effective date for global rates
- Current rate (per-unit or fixed)
- Current COGS (cost of goods sold)

## Requirements

```bash
pip install requests
```

## Configuration

Set environment variables or modify the script defaults:

```bash
export EXIVITY_BASE_URL="https://localhost"
export EXIVITY_USERNAME="admin"
export EXIVITY_PASSWORD="exivity"
```

For self-signed certificates, set `VERIFY = False` in the script.

## Usage

```bash
python get_services_with_rates.py
```

## Output

CSV format with headers:
```csv
service_id,service_name,rate_effective_date,rate,cogs
360,"EC2 Instance",2025-01-01,0.05,0.03
361,"S3 Storage",2025-01-01,0.02,0.01
```

## Features

- **Pagination support** - Handles large datasets efficiently
- **Global rates only** - Filters out account-specific rates
- **Latest rates** - Shows most recent effective date per service
- **Flexible rate types** - Prefers per-unit rates, falls back to fixed rates
- **Error handling** - Graceful failure with informative messages

## API Endpoints Used

- `GET /v1/auth/token` - Authentication
- `GET /v1/rates` - Rate data with service relationships
- `GET /v1/services` - Service names and descriptions