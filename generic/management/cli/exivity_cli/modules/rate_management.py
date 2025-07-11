"""
Rate Management Module

Handles all rate-related operations including CSV imports and rate revisions.
"""

import csv
import sys
import uuid
import os
import time
from typing import List, Dict, Tuple
from pathlib import Path
from datetime import datetime

import questionary


class RateManager:
    """Handles rate management operations"""
    
    def __init__(self, api):
        self.api = api
        # Set default CSV folder relative to CLI root
        self.default_csv_folder = Path(__file__).parent.parent.parent / "csv"
    
    def get_csv_files(self, folder_path: str = None) -> List[str]:
        """Get list of CSV files from specified folder or default csv folder"""
        if folder_path is None:
            folder_path = self.default_csv_folder
        else:
            folder_path = Path(folder_path)
        
        try:
            if not folder_path.exists():
                print(f"📁 Creating CSV folder: {folder_path}")
                folder_path.mkdir(parents=True, exist_ok=True)
                return []
            
            csv_files = []
            for file_path in folder_path.glob("*.csv"):
                if file_path.is_file():
                    csv_files.append(str(file_path))
            
            return sorted(csv_files)
        except Exception as e:
            print(f"❌ Error reading CSV folder {folder_path}: {e}")
            return []
    
    def select_csv_file_interactive(self, folder_path: str = None) -> str:
        """Interactive CSV file selector"""
        csv_files = self.get_csv_files(folder_path)
        
        if not csv_files:
            folder_to_show = folder_path or self.default_csv_folder
            print(f"📁 No CSV files found in: {folder_to_show}")
            
            # Ask if user wants to specify a custom path
            custom_path = questionary.confirm("Would you like to specify a custom CSV file path?").ask()
            if custom_path:
                return questionary.path("Enter CSV file path:").ask()
            return None
        
        print(f"📁 Found {len(csv_files)} CSV file(s) in: {folder_path or self.default_csv_folder}")
        
        # Create choices with just filenames for display
        choices = []
        for file_path in csv_files:
            filename = Path(file_path).name
            choices.append(questionary.Choice(title=filename, value=file_path))
        
        # Add option for custom path
        choices.append(questionary.Choice(title="📂 Browse for different file...", value="__custom__"))
        
        selected = questionary.select(
            "Select CSV file:",
            choices=choices
        ).ask()
        
        if selected == "__custom__":
            return questionary.path("Enter CSV file path:").ask()
        
        return selected

    def update_rates_from_csv(self, csv_path: str = None):
        """Update rates from CSV file using the exact original working logic"""
        if not csv_path:
            csv_path = self.select_csv_file_interactive()
        
        if not csv_path:
            print("❌ No CSV file selected")
            return
        
        # Use the exact original working CSV processing logic
        self._update_rates_from_csv_original(csv_path)

    def _update_rates_from_csv_original(self, csv_path: str):
        """Exact copy of the working update_rates_from_csv function with dump optimization"""
        # Try different encodings to handle various CSV file formats
        encodings_to_try = ['utf-8', 'utf-8-sig', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings_to_try:
            try:
                with open(csv_path, 'r', newline='', encoding=encoding) as f:
                    # Read first line to check headers
                    first_line = f.readline().strip()
                    
                    # Reset file pointer
                    f.seek(0)
                    
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    
                    # Clean fieldnames (remove any hidden characters)
                    if fieldnames:
                        cleaned_fieldnames = [field.strip().replace('\ufeff', '') for field in fieldnames]
                        
                        # Check if we have the required columns after cleaning
                        required_cols = {"account_id", "service_id", "rate", "cogs", "revision_start_date"}
                        missing = required_cols - set(cleaned_fieldnames)
                        
                        if not missing:
                            print(f"✅ Successfully parsed CSV with {encoding} encoding")
                            break
                        else:
                            print(f"Missing columns with {encoding}: {missing}")
                            continue
                    else:
                        print(f"No fieldnames detected with {encoding}")
                        continue
                        
            except UnicodeDecodeError:
                print(f"Failed to decode with {encoding}, trying next encoding...")
                continue
            except Exception as e:
                print(f"Error with {encoding}: {e}")
                continue
        else:
            print("Failed to parse CSV with any encoding. Please check the file format.")
            return

        # Pre-fetch dump data once for efficient rate checking
        print("📊 Loading system data for duplicate checking...")
        dump_data = self.api.fetch_dump_data()
        
        # Build existing rates lookup for fast duplicate checking
        existing_rates_lookup = set()
        for rate in dump_data.get('rate', []):
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            existing_rates_lookup.add((account_id, service_id, effective_date))
        
        print(f"📋 Found {len(existing_rates_lookup)} existing rates in system")

        # Re-open with the successful encoding for processing
        with open(csv_path, 'r', newline='', encoding=encoding) as f:
            reader = csv.DictReader(f)
            
            # Clean the fieldnames
            reader.fieldnames = [field.strip().replace('\ufeff', '') for field in reader.fieldnames]
            
            required_cols = {"account_id", "service_id", "rate", "cogs", "revision_start_date"}
            missing = required_cols - set(reader.fieldnames)
            if missing:
                print(f"CSV missing columns: {', '.join(missing)}")
                print(f"Available columns: {', '.join(reader.fieldnames)}")
                return

            print(f"Processing CSV file: {csv_path}")
            
            # Collect all rate data and check for existing revisions using dump data
            new_rates = []
            skipped_count = 0
            processed_rows = 0
            error_rows = 0
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
                processed_rows += 1
                
                try:
                    # Clean the row data (remove any hidden characters)
                    cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                    
                    acc = int(cleaned_row["account_id"])
                    svc = int(cleaned_row["service_id"])
                    rate = float(cleaned_row["rate"])
                    cogs = float(cleaned_row["cogs"])
                    eff_date = cleaned_row["revision_start_date"]
                    
                    # Convert date format for lookup
                    if len(eff_date) == 8 and eff_date.isdigit():
                        formatted_date = f"{eff_date[:4]}-{eff_date[4:6]}-{eff_date[6:8]}"
                    else:
                        formatted_date = eff_date
                    
                    # Check if rate revision already exists using fast lookup
                    if (str(acc), str(svc), formatted_date) in existing_rates_lookup:
                        print(f"Row {row_num}: Rate revision already exists for account {acc}, service {svc} on {eff_date} – skipping.")
                        skipped_count += 1
                        continue
                    
                    # Add to batch for creation
                    new_rates.append({
                        "account_id": acc,
                        "service_id": svc,
                        "rate": rate,
                        "cogs": cogs,
                        "effective_date": eff_date,
                        "row_num": row_num
                    })
                    
                except ValueError as e:
                    print(f"Row {row_num}: Invalid data format - {e}")
                    print(f"DEBUG: Row {row_num} data: {row}")
                    error_rows += 1
                    continue
                except Exception as e:
                    print(f"Row {row_num}: Error processing row - {e}")
                    print(f"DEBUG: Row {row_num} data: {row}")
                    error_rows += 1
                    continue
            
            print(f"📋 Summary:")
            print(f"   • Total data rows processed: {processed_rows}")
            print(f"   • New rates to create: {len(new_rates)}")
            print(f"   • Skipped existing rates: {skipped_count}")
            if error_rows > 0:
                print(f"   • Rows with errors: {error_rows}")
            
            # Create rates in batches using atomic operations
            processed_count = 0
            if new_rates:
                # Process in batches of 50 to avoid too large requests
                batch_size = 50
                total_batches = (len(new_rates) + batch_size - 1) // batch_size
                
                for i in range(0, len(new_rates), batch_size):
                    batch = new_rates[i:i+batch_size]
                    batch_num = i // batch_size + 1
                    
                    try:
                        print(f"Creating batch {batch_num}/{total_batches} ({len(batch)} rate revisions)...")
                        result = self.api.create_rate_revisions_batch(batch)
                        
                        # Count successful creations
                        atomic_results = result.get("atomic:results", [])
                        successful_in_batch = len([r for r in atomic_results if "data" in r])
                        processed_count += successful_in_batch
                        
                        if successful_in_batch == len(batch):
                            print(f"✅ Batch {batch_num} completed successfully")
                        else:
                            print(f"⚠️  Batch {batch_num}: {successful_in_batch}/{len(batch)} created")
                        
                    except Exception as e:
                        print(f"❌ Batch {batch_num} failed: {e}")
                        print(f"DEBUG: Batch error details: {e}")
                        # Fall back to individual creation for this batch
                        print("🔄 Falling back to individual rate creation...")
                        for rate in batch:
                            try:
                                self.api.create_rate_revision(
                                    rate["account_id"], 
                                    rate["service_id"], 
                                    rate["rate"], 
                                    rate["cogs"], 
                                    rate["effective_date"]
                                )
                                processed_count += 1
                            except Exception as e2:
                                print(f"❌ Row {rate['row_num']}: Error creating individual rate - {e2}")
                                print(f"DEBUG: Failed rate data: Account {rate['account_id']}, Service {rate['service_id']}, Rate {rate['rate']}, COGS {rate['cogs']}, Date {rate['effective_date']}")
            
            # Clear the dump cache after processing since we may have added new rates
            self.api.clear_dump_cache()
            
            print(f"\n✅ Finished processing CSV:")
            print(f"   • Total data rows in file: {processed_rows}")
            print(f"   • Successfully processed: {processed_count} rows")
            print(f"   • Skipped (already exist): {skipped_count} rows")
            print(f"   • Errors: {processed_rows - processed_count - skipped_count} rows")

    def debug_api_connectivity(self):
        """Debug API connectivity and available endpoints"""
        print("🔍 Debugging API connectivity...")
        self.api.debug_api_endpoints()

    def check_rate_status_interactive(self):
        """Interactive rate status checker with debug options"""
        print("🔍 Rate Status Checker")
        
        debug_mode = questionary.confirm("Enable debug mode?", default=False).ask()
        
        if debug_mode:
            self.debug_api_connectivity()
        
        account_id = questionary.text("Account ID:").ask()
        service_id = questionary.text("Service ID:").ask()
        effective_date = questionary.text("Effective date (YYYYMMDD or YYYY-MM-DD):").ask()
        
        if account_id and service_id and effective_date:
            exists = self.api.rate_revision_exists(int(account_id), int(service_id), effective_date)
            status = "✅ EXISTS" if exists else "❌ NOT FOUND"
            print(f"Rate revision status: {status}")

    def show_system_overview_interactive(self):
        """Show comprehensive system overview"""
        print("📊 Generating system overview...")
        self.api.show_system_overview()

    def validate_csv_interactive(self):
        """Interactive CSV validation against system data - optimized with dump data"""
        print("🔍 CSV Validation Tool")
        print("This will validate your CSV against actual accounts and services in the system.")
        
        csv_path = self.select_csv_file_interactive()
        if not csv_path:
            print("❌ No CSV file selected")
            return
        
        print(f"📄 Validating: {Path(csv_path).name}")
        
        # Parse CSV data
        try:
            import csv
            csv_data = []
            with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                # Clean fieldnames
                reader.fieldnames = [field.strip().replace('\ufeff', '') for field in reader.fieldnames]
                
                for row in reader:
                    cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                    csv_data.append(cleaned_row)
            
            print(f"📋 Parsed {len(csv_data)} data rows from CSV")
            
            # Validate against system using efficient dump-based validation
            validation = self.api.validate_csv_against_system(csv_data)
            
            # Show results
            print("\n" + "="*50)
            print("📊 VALIDATION RESULTS")
            print("="*50)
            
            total_rows = len(csv_data)
            valid_count = len(validation['valid_rows'])
            
            print(f"✅ Valid rows: {valid_count}/{total_rows}")
            
            if validation['missing_fields']:
                print(f"\n❌ Missing required fields ({len(validation['missing_fields'])} rows):")
                for issue in validation['missing_fields'][:5]:  # Show first 5
                    print(f"   Row {issue['row']}: Missing {', '.join(issue['missing'])}")
                if len(validation['missing_fields']) > 5:
                    print(f"   ... and {len(validation['missing_fields']) - 5} more")
            
            if validation['invalid_accounts']:
                print(f"\n❌ Invalid account IDs ({len(validation['invalid_accounts'])} rows):")
                for issue in validation['invalid_accounts'][:5]:
                    print(f"   Row {issue['row']}: Account ID {issue['account_id']} not found")
                if len(validation['invalid_accounts']) > 5:
                    print(f"   ... and {len(validation['invalid_accounts']) - 5} more")
            
            if validation['invalid_services']:
                print(f"\n❌ Invalid service IDs ({len(validation['invalid_services'])} rows):")
                for issue in validation['invalid_services'][:5]:
                    print(f"   Row {issue['row']}: Service ID {issue['service_id']} not found")
                if len(validation['invalid_services']) > 5:
                    print(f"   ... and {len(validation['invalid_services']) - 5} more")
            
            if validation['duplicate_rates']:
                print(f"\n⚠️  Existing rates (will be skipped, {len(validation['duplicate_rates'])} rows):")
                for issue in validation['duplicate_rates'][:5]:
                    print(f"   Row {issue['row']}: Rate exists for Account {issue['account_id']}, Service {issue['service_id']}, Date {issue['effective_date']}")
                if len(validation['duplicate_rates']) > 5:
                    print(f"   ... and {len(validation['duplicate_rates']) - 5} more")
            
            # Summary
            print(f"\n📊 Summary:")
            print(f"   • {valid_count} rows ready for import")
            print(f"   • {len(validation['duplicate_rates'])} existing rates (will be skipped)")
            print(f"   • {total_rows - valid_count - len(validation['duplicate_rates'])} rows with errors")
            
            if valid_count > 0:
                proceed = questionary.confirm(
                    f"Would you like to proceed with importing the {valid_count} valid rows?",
                    default=True
                ).ask()
                
                if proceed:
                    print(f"\n📄 Processing: {Path(csv_path).name}")
                    self._update_rates_from_csv_original(csv_path)
            
        except Exception as e:
            print(f"❌ Error validating CSV: {e}")

    def export_services_accounts_csv(self):
        """Export comprehensive CSV of all services and accounts with rate information"""
        print("📊 Generating comprehensive services and accounts export...")
        
        # Get output filename
        default_filename = f"services_accounts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = questionary.text(
            "Output CSV filename:",
            default=default_filename
        ).ask()
        
        if not output_path:
            print("❌ Output filename is required")
            return
        
        # Ensure .csv extension
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
        
        # Make path relative to CSV folder
        if not os.path.isabs(output_path):
            output_path = self.default_csv_folder / output_path
            
        try:
            self._generate_services_accounts_export(output_path)
        except Exception as e:
            print(f"❌ Error generating export: {e}")

    def _generate_services_accounts_export(self, output_path: Path):
        """Generate the comprehensive export CSV file"""
        print("📊 Loading system data...")
        
        # Fetch all data from dump
        dump_data = self.api.fetch_dump_data()
        accounts = dump_data.get('account', [])
        services = dump_data.get('service', [])
        rates = dump_data.get('rate', [])
        
        print(f"📋 Loaded:")
        print(f"   • {len(accounts)} accounts")
        print(f"   • {len(services)} services")
        print(f"   • {len(rates)} rates")
        
        # Build lookup dictionaries
        accounts_by_id = {account.get('id', ''): account for account in accounts}
        services_by_id = {service.get('id', ''): service for service in services}
        
        # Build latest rates lookup by account/service
        latest_rates = self._get_latest_rates_by_account_service(rates)
        
        print("🔄 Generating export data...")
        
        # Generate export rows
        export_rows = []
        
        # For each service, create rows for each account
        for service in services:
            service_id = service.get('id', '')
            service_key = service.get('key', '')
            service_name = service.get('description', '') or service.get('name', '')
            
            if not service_id:
                continue
                
            for account in accounts:
                account_id = account.get('id', '')
                account_name = account.get('name', '').strip('"')
                account_level = account.get('level', '')
                
                if not account_id:
                    continue
                
                # Look for rate for this account/service combination
                rate_key = (account_id, service_id)
                rate_info = latest_rates.get(rate_key)
                
                if rate_info:
                    # Has account-specific rate
                    revision_start_date = rate_info.get('effective_date', '')
                    rate_value = rate_info.get('rate', '')
                    cogs_value = rate_info.get('cogs_rate', '')
                else:
                    # No account-specific rate (using default)
                    revision_start_date = ''
                    rate_value = ''
                    cogs_value = ''
                
                # Create export row
                row = {
                    'service_key': service_key,
                    'service_name': service_name,
                    'service_id': service_id,
                    'account_key': account_name,  # Using name as key since there's no separate key field
                    'account_name': account_name,
                    'account_id': account_id,
                    'report_level': account_level,
                    'revision_start_date': revision_start_date,
                    'rate': rate_value,
                    'cogs': cogs_value
                }
                
                export_rows.append(row)
        
        print(f"📋 Generated {len(export_rows)} export rows")
        
        # Write to CSV
        print(f"💾 Writing to: {output_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = [
                'service_key', 'service_name', 'service_id',
                'account_key', 'account_name', 'account_id', 'report_level',
                'revision_start_date', 'rate', 'cogs'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_rows)
        
        print(f"✅ Export completed successfully!")
        print(f"📄 File saved: {output_path}")
        print(f"📊 Summary:")
        print(f"   • Total rows: {len(export_rows)}")
        
        # Count rows with rates vs without
        with_rates = len([row for row in export_rows if row['revision_start_date']])
        without_rates = len(export_rows) - with_rates
        
        print(f"   • With account-specific rates: {with_rates}")
        print(f"   • Using default rates: {without_rates}")
        
        # Show sample data
        if export_rows:
            print(f"\n📋 Sample data (first 3 rows):")
            for i, row in enumerate(export_rows[:3]):
                print(f"   Row {i+1}:")
                print(f"     Service: {row['service_name']} (ID: {row['service_id']})")
                print(f"     Account: {row['account_name']} (ID: {row['account_id']}, Level: {row['report_level']})")
                if row['revision_start_date']:
                    print(f"     Rate: {row['rate']} (COGS: {row['cogs']}) - Revision: {row['revision_start_date']}")
                else:
                    print(f"     Rate: Using default (no account-specific rate)")

    def export_rates_only_csv(self):
        """Export CSV of only accounts/services that have specific rate revisions"""
        print("📊 Generating rates-only export...")
        
        # Get output filename
        default_filename = f"rates_only_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = questionary.text(
            "Output CSV filename:",
            default=default_filename
        ).ask()
        
        if not output_path:
            print("❌ Output filename is required")
            return
        
        # Ensure .csv extension
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
        
        # Make path relative to CSV folder
        if not os.path.isabs(output_path):
            output_path = self.default_csv_folder / output_path
            
        try:
            self._generate_rates_only_export(output_path)
        except Exception as e:
            print(f"❌ Error generating export: {e}")

    def _generate_rates_only_export(self, output_path: Path):
        """Generate export CSV with only accounts/services that have rate revisions"""
        print("📊 Loading system data...")
        
        # Fetch all data from dump
        dump_data = self.api.fetch_dump_data()
        accounts = dump_data.get('account', [])
        services = dump_data.get('service', [])
        rates = dump_data.get('rate', [])
        
        print(f"📋 Loaded:")
        print(f"   • {len(accounts)} accounts")
        print(f"   • {len(services)} services")
        print(f"   • {len(rates)} rates")
        
        # Build lookup dictionaries
        accounts_by_id = {account.get('id', ''): account for account in accounts}
        services_by_id = {service.get('id', ''): service for service in services}
        
        # Build latest rates lookup by account/service
        latest_rates = self._get_latest_rates_by_account_service(rates)
        
        print("🔄 Generating export data for accounts with rates...")
        
        # Generate export rows only for combinations that have rates
        export_rows = []
        
        for (account_id, service_id), rate_info in latest_rates.items():
            account = accounts_by_id.get(account_id)
            service = services_by_id.get(service_id)
            
            if not account or not service:
                continue
            
            service_key = service.get('key', '')
            service_name = service.get('description', '') or service.get('name', '')
            account_name = account.get('name', '').strip('"')
            account_level = account.get('level', '')
            
            revision_start_date = rate_info.get('effective_date', '')
            rate_value = rate_info.get('rate', '')
            cogs_value = rate_info.get('cogs_rate', '')
            
            # Create export row
            row = {
                'service_key': service_key,
                'service_name': service_name,
                'service_id': service_id,
                'account_key': account_name,
                'account_name': account_name,
                'account_id': account_id,
                'report_level': account_level,
                'revision_start_date': revision_start_date,
                'rate': rate_value,
                'cogs': cogs_value
            }
            
            export_rows.append(row)
        
        # Sort by account name, then service name
        export_rows.sort(key=lambda x: (x['account_name'], x['service_name']))
        
        print(f"📋 Generated {len(export_rows)} export rows (rates only)")
        
        # Write to CSV
        print(f"💾 Writing to: {output_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = [
                'service_key', 'service_name', 'service_id',
                'account_key', 'account_name', 'account_id', 'report_level',
                'revision_start_date', 'rate', 'cogs'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_rows)
        
        print(f"✅ Export completed successfully!")
        print(f"📄 File saved: {output_path}")
        print(f"📊 Summary:")
        print(f"   • Total rows with rates: {len(export_rows)}")
        
        # Show account and service breakdown
        unique_accounts = len(set(row['account_id'] for row in export_rows))
        unique_services = len(set(row['service_id'] for row in export_rows))
        
        print(f"   • Unique accounts with rates: {unique_accounts}")
        print(f"   • Unique services with rates: {unique_services}")
        
        # Show sample data
        if export_rows:
            print(f"\n📋 Sample data (first 3 rows):")
            for i, row in enumerate(export_rows[:3]):
                print(f"   Row {i+1}:")
                print(f"     Service: {row['service_name']} (ID: {row['service_id']})")
                print(f"     Account: {row['account_name']} (ID: {row['account_id']}, Level: {row['report_level']})")
                print(f"     Rate: {row['rate']} (COGS: {row['cogs']}) - Revision: {row['revision_start_date']}")

    def _get_latest_rates_by_account_service(self, rates: List[Dict]) -> Dict[tuple, Dict]:
        """Get the latest rate for each account/service combination with data validation"""
        latest_rates = {}
        
        for rate in rates:
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            
            # Skip rows with empty or invalid account_id or service_id
            if not account_id or not service_id or account_id == '' or service_id == '':
                continue
            
            # Validate that account_id and service_id are numeric
            try:
                int(account_id)
                int(service_id)
            except (ValueError, TypeError):
                print(f"   ⚠️  Skipping invalid rate data: account_id='{account_id}', service_id='{service_id}'")
                continue
            
            # Validate rate values
            try:
                float(rate.get('rate', 0))
                float(rate.get('cogs_rate', 0))
            except (ValueError, TypeError):
                print(f"   ⚠️  Skipping rate with invalid values: account_id={account_id}, service_id={service_id}")
                continue
            
            key = (account_id, service_id)
            
            if key not in latest_rates or effective_date > latest_rates[key]['effective_date']:
                latest_rates[key] = rate
        
        return latest_rates

    def show_rate_management_menu(self):
        """Enhanced rate management menu with export options"""
        while True:
            print("\n" + "="*60)
            print("💰 RATE MANAGEMENT")
            print("="*60)
            
            choice = questionary.select(
                "Choose a rate management operation:",
                choices=[
                    questionary.Choice("📊 System overview (accounts, services, rates)", "overview"),
                    questionary.Choice("🔍 Validate CSV before import", "validate"),
                    questionary.Choice("📁 Import rates from CSV file", "import_csv"),
                    questionary.Choice("📈 Rate indexation (percentage adjustments)", "indexation"),
                    questionary.Choice("📤 Export all services/accounts to CSV", "export_all"),
                    questionary.Choice("📤 Export rates-only to CSV", "export_rates"),
                    questionary.Choice("🔍 Check rate revision status", "check_status"),
                    questionary.Choice("⬅️  Back to main menu", "back")
                ]
            ).ask()
            
            if choice == "overview":
                self.show_system_overview_interactive()
                self._pause_for_review()
            elif choice == "validate":
                self.validate_csv_interactive()
                self._pause_for_review()
            elif choice == "import_csv":
                self.update_rates_from_csv()
                self._pause_for_review()
            elif choice == "indexation":
                self.rate_indexation_interactive()
                self._pause_for_review()
            elif choice == "export_all":
                self.export_services_accounts_csv()
                self._pause_for_review()
            elif choice == "export_rates":
                self.export_rates_only_csv()
                self._pause_for_review()
            elif choice == "check_status":
                self.check_rate_status_interactive()
                self._pause_for_review()
            elif choice == "back":
                break

    def _pause_for_review(self):
        """Pause to let user review output before returning to menu"""
        print("\n" + "-"*40)
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
