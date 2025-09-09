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
    
    def __init__(self, api, config=None):
        self.api = api
        self.config = config
        
        # Set default CSV folder - use config if available, otherwise fallback to hardcoded path
        if config:
            self.default_csv_folder = Path(config.get('rate.csv_folder', './csv'))
        else:
            # Fallback to hardcoded path relative to CLI root
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
                            continue
                    else:
                        continue
                        
            except UnicodeDecodeError:
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
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        
        # Build existing rates lookup for fast duplicate checking
        existing_rates_lookup = set()
        for rate in dump_data.get('rate', []):
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            existing_rates_lookup.add((account_id, service_id, effective_date))
        
        print(f"📋 Found {len(existing_rates_lookup)} existing rates in system")
        if services_with_tiers:
            print(f"📋 Found {len(services_with_tiers)} services with rate tiers (will be skipped)")

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
            skipped_tiers = 0
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
                    
                    # Check if this service has rate tiers - skip if it does
                    if str(svc) in services_with_tiers:
                        print(f"Row {row_num}: Service {svc} has rate tiers (not supported) - skipping")
                        skipped_tiers += 1
                        continue
                    
                    # Convert date format for lookup
                    if len(eff_date) == 8 and eff_date.isdigit():
                        formatted_date = f"{eff_date[:4]}-{eff_date[4:6]}-{eff_date[6:8]}"
                    else:
                        formatted_date = eff_date
                    
                    # Check if rate revision already exists using fast lookup
                    if (str(acc), str(svc), formatted_date) in existing_rates_lookup:
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
                    error_rows += 1
                    continue
                except Exception as e:
                    error_rows += 1
                    continue
            
            print(f"📋 Summary:")
            print(f"   • Total data rows processed: {processed_rows}")
            print(f"   • New rates to create: {len(new_rates)}")
            print(f"   • Skipped existing rates: {skipped_count}")
            if skipped_tiers > 0:
                print(f"   • Skipped services with rate tiers: {skipped_tiers}")
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
                        # Fall back to individual creation for this batch
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
            
            # Clear the dump cache after processing since we may have added new rates
            self.api.clear_dump_cache()
            
            print(f"\n✅ Finished processing CSV:")
            print(f"   • Total data rows in file: {processed_rows}")
            print(f"   • Successfully processed: {processed_count} rows")
            print(f"   • Skipped (already exist): {skipped_count} rows")
            if skipped_tiers > 0:
                print(f"   • Skipped (services with rate tiers): {skipped_tiers} rows")
            print(f"   • Errors: {processed_rows - processed_count - skipped_count - skipped_tiers} rows")

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

    def rate_indexation_interactive(self):
        """Interactive rate indexation - apply percentage changes to existing rates"""
        print("📈 Rate Indexation Tool")
        print("Apply percentage increases/decreases to existing rates")
        print("-" * 50)
        
        # Choose indexation scope
        scope = questionary.select(
            "Choose indexation scope:",
            choices=[
                questionary.Choice("🌐 All account-specific rates", "global"),
                questionary.Choice("🏢 Account-specific rates (single account)", "account"),
                questionary.Choice("📝 List prices (default rates for all services)", "list_prices"),
                questionary.Choice("⬅️  Back to rate management", "back")
            ]
        ).ask()
        
        if scope == "back":
            return
        
        # Get indexation parameters
        percentage = questionary.text(
            "Percentage change (e.g., 5 for +5%, -3 for -3%):",
            validate=lambda x: self._validate_percentage(x)
        ).ask()
        
        if not percentage:
            print("❌ Percentage is required")
            return
        
        percentage_value = float(percentage)
        
        # Get effective date for new rate revisions
        effective_date = questionary.text(
            "Effective date for indexed rates (YYYYMMDD or YYYY-MM-DD):",
            validate=lambda x: self._validate_date_format(x)
        ).ask()
        
        if not effective_date:
            print("❌ Effective date is required")
            return
        
        # Normalize date format
        if len(effective_date) == 8 and effective_date.isdigit():
            formatted_date = f"{effective_date[:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
            display_date = effective_date
        else:
            formatted_date = effective_date
            display_date = effective_date.replace("-", "")
        
        # Account-specific logic
        target_account_id = None
        if scope == "account":
            account_id = questionary.text("Account ID to index:").ask()
            if not account_id:
                print("❌ Account ID is required for account-specific indexation")
                return
            
            try:
                target_account_id = int(account_id)
            except ValueError:
                print("❌ Invalid account ID format")
                return
        
        # Show confirmation
        if scope == "list_prices":
            scope_text = "List prices (default rates)"
        elif scope == "account":
            scope_text = f"Account {target_account_id}"
        else:
            scope_text = "All account-specific rates"
            
        change_text = f"+{percentage_value}%" if percentage_value > 0 else f"{percentage_value}%"
        
        print(f"\n📋 Indexation Summary:")
        print(f"   • Scope: {scope_text}")
        print(f"   • Change: {change_text}")
        print(f"   • New effective date: {display_date}")
        
        confirm = questionary.confirm(
            "Proceed with rate indexation?",
            default=False
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        # Execute indexation
        try:
            if scope == "global":
                self._perform_global_indexation(percentage_value, formatted_date, display_date)
            elif scope == "account":
                self._perform_account_indexation(target_account_id, percentage_value, formatted_date, display_date)
            elif scope == "list_prices":
                self._perform_list_price_indexation(percentage_value, formatted_date, display_date)
        except Exception as e:
            print(f"❌ Error during indexation: {e}")

    def export_rates_to_csv_interactive(self):
        """Interactive CSV export with options for list prices or account-specific rates"""
        print("📤 Rate Export Tool")
        print("Export rates to CSV format for backup or transfer")
        print("-" * 50)
        
        # Choose export type
        export_type = questionary.select(
            "Choose export type:",
            choices=[
                questionary.Choice("📝 List prices (default rates for all services)", "list_prices"),
                questionary.Choice("🏢 Account-specific rates", "account_rates"),
                questionary.Choice("⬅️  Back to rate management", "back")
            ]
        ).ask()
        
        if export_type == "back":
            return
        
        # Get output file path
        default_filename = f"rate_export_{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_path = self.default_csv_folder / default_filename
        
        # Ensure CSV folder exists
        self.default_csv_folder.mkdir(parents=True, exist_ok=True)
        
        output_path = questionary.path(
            "Output CSV file path:",
            default=str(default_path)
        ).ask()
        
        if not output_path:
            print("❌ Output path is required")
            return
        
        output_path = Path(output_path)
        
        # Confirm if file exists
        if output_path.exists():
            overwrite = questionary.confirm(
                f"File '{output_path}' already exists. Overwrite?",
                default=False
            ).ask()
            if not overwrite:
                print("Operation cancelled.")
                return
        
        # Perform the export
        try:
            if export_type == "list_prices":
                self._export_list_prices(output_path)
            elif export_type == "account_rates":
                self._export_account_rates(output_path)
        except Exception as e:
            print(f"❌ Error during export: {e}")

    def _export_list_prices(self, output_path: Path):
        """Export list prices (default rates) to CSV"""
        print("📝 Exporting list prices...")
        
        # Get all data from dump
        print("📊 Loading system data...")
        dump_data = self.api.fetch_dump_data()
        
        services = dump_data.get('service', [])
        rates = dump_data.get('rate', [])
        
        if not services:
            print("❌ No services found")
            return
        
        if not rates:
            print("❌ No rates found")
            return
        
        print(f"📋 Found {len(services)} services and {len(rates)} rates")
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        
        # Filter for list prices (rates with no account_id)
        list_price_rates = []
        for rate in rates:
            account_id = rate.get('account_id', '')
            if not account_id or account_id == '' or account_id == 'null':
                list_price_rates.append(rate)
        
        print(f"📋 Found {len(list_price_rates)} list price rates")
        
        # Group by service to get latest list price per service
        latest_list_prices = {}
        for rate in list_price_rates:
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            
            if not service_id:
                continue
                
            try:
                service_id_int = int(service_id)
                # Skip services with rate tiers
                if str(service_id_int) in services_with_tiers:
                    continue
                    
                # Validate that this service has manual rate configuration
                rate_value = float(rate.get('rate', 0))
                cogs_value = float(rate.get('cogs_rate', 0))
                
                # Only include services that have configured manual rates
                if rate_value > 0 or cogs_value > 0:
                    if service_id_int not in latest_list_prices or effective_date > latest_list_prices[service_id_int]['effective_date']:
                        latest_list_prices[service_id_int] = rate
                        
            except (ValueError, TypeError):
                continue
        
        print(f"📋 Found {len(latest_list_prices)} services with configured list prices")
        
        if not latest_list_prices:
            print("❌ No services with configured list prices found")
            print("💡 List prices are default rates for services with manual rate configuration")
            return
        
        # Build service lookup - handle both dump format and direct service data
        service_lookup = {}
        for service in services:
            service_id = service.get('id', '')
            if service_id:
                # Extract service information from dump format
                service_info = {
                    'key': service.get('key', ''),
                    'description': service.get('description', '')
                }
                # Also check attributes if it's in JSON:API format
                if 'attributes' in service:
                    attrs = service['attributes']
                    service_info['key'] = attrs.get('key', service_info['key'])
                    service_info['description'] = attrs.get('description', service_info['description'])
                
                service_lookup[service_id] = service_info
        
        # Prepare CSV data
        csv_data = []
        for service_id_int, rate_info in latest_list_prices.items():
            service_id_str = str(service_id_int)
            service_info = service_lookup.get(service_id_str, {})
            
            # Convert effective_date from YYYY-MM-DD to YYYYMMDD
            effective_date = rate_info.get('effective_date', '')
            if effective_date and len(effective_date) == 10:
                revision_start_date = effective_date.replace('-', '')
            else:
                revision_start_date = effective_date
            
            csv_row = {
                'account_id': '',  # Empty for list prices
                'service_id': service_id_int,
                'service_key': service_info.get('key', ''),
                'service_description': service_info.get('description', ''),
                'rate': float(rate_info.get('rate', 0)),
                'cogs': float(rate_info.get('cogs_rate', 0)),
                'revision_start_date': revision_start_date,
                'effective_date_formatted': effective_date
            }
            csv_data.append(csv_row)
        
        # Sort by service_id for consistent output
        csv_data.sort(key=lambda x: x['service_id'])
        
        # Write CSV file
        self._write_csv_file(output_path, csv_data, is_list_prices=True)
        
        print(f"✅ List prices exported to: {output_path}")
        print(f"📊 Exported {len(csv_data)} list price records")

    def _export_account_rates(self, output_path: Path):
        """Export account-specific rates to CSV"""
        print("🏢 Exporting account-specific rates...")
        
        # Get all data from dump
        print("📊 Loading system data...")
        dump_data = self.api.fetch_dump_data()
        
        services = dump_data.get('service', [])
        rates = dump_data.get('rate', [])
        accounts = dump_data.get('account', [])
        
        if not services:
            print("❌ No services found")
            return
        
        if not rates:
            print("❌ No rates found")
            return
        
        if not accounts:
            print("❌ No accounts found")
            return
        
        print(f"📋 Found {len(services)} services, {len(rates)} rates, and {len(accounts)} accounts")
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        
        # Filter for account-specific rates (rates with account_id)
        account_rates = []
        for rate in rates:
            account_id = rate.get('account_id', '')
            if account_id and account_id != '' and account_id != 'null':
                try:
                    int(account_id)  # Validate account_id is numeric
                    account_rates.append(rate)
                except (ValueError, TypeError):
                    continue
        
        print(f"📋 Found {len(account_rates)} account-specific rates")
        
        # Group by account/service to get latest rate per combination
        latest_account_rates = {}
        for rate in account_rates:
            account_id = rate.get('account_id', '')
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            
            if not account_id or not service_id:
                continue
                
            try:
                account_id_int = int(account_id)
                service_id_int = int(service_id)
                
                # Skip services with rate tiers
                if str(service_id_int) in services_with_tiers:
                    continue
                    
                # Validate rate values
                rate_value = float(rate.get('rate', 0))
                cogs_value = float(rate.get('cogs_rate', 0))
                
                # Only include rates that have meaningful values
                if rate_value > 0 or cogs_value > 0:
                    key = (account_id_int, service_id_int)
                    if key not in latest_account_rates or effective_date > latest_account_rates[key]['effective_date']:
                        latest_account_rates[key] = rate
                        
            except (ValueError, TypeError):
                continue
        
        print(f"📋 Found {len(latest_account_rates)} unique account/service combinations with configured rates")
        
        if not latest_account_rates:
            print("❌ No account-specific rates found")
            print("💡 Account-specific rates are custom rates that override default list prices")
            return
        
        # Build lookups - handle both dump format and direct service data
        service_lookup = {}
        for service in services:
            service_id = service.get('id', '')
            if service_id:
                # Extract service information from dump format
                service_info = {
                    'key': service.get('key', ''),
                    'description': service.get('description', '')
                }
                # Also check attributes if it's in JSON:API format
                if 'attributes' in service:
                    attrs = service['attributes']
                    service_info['key'] = attrs.get('key', service_info['key'])
                    service_info['description'] = attrs.get('description', service_info['description'])
                
                service_lookup[service_id] = service_info
        
        account_lookup = {}
        for account in accounts:
            account_id = account.get('id', '')
            if account_id:
                # Extract account information from dump format
                account_info = {
                    'name': account.get('name', '')
                }
                # Also check attributes if it's in JSON:API format
                if 'attributes' in account:
                    attrs = account['attributes']
                    account_info['name'] = attrs.get('name', account_info['name'])
                
                account_lookup[account_id] = account_info
        
        # Prepare CSV data
        csv_data = []
        for (account_id_int, service_id_int), rate_info in latest_account_rates.items():
            account_id_str = str(account_id_int)
            service_id_str = str(service_id_int)
            
            account_info = account_lookup.get(account_id_str, {})
            service_info = service_lookup.get(service_id_str, {})
            
            # Convert effective_date from YYYY-MM-DD to YYYYMMDD
            effective_date = rate_info.get('effective_date', '')
            if effective_date and len(effective_date) == 10:
                revision_start_date = effective_date.replace('-', '')
            else:
                revision_start_date = effective_date
            
            csv_row = {
                'account_id': account_id_int,
                'account_name': account_info.get('name', ''),
                'service_id': service_id_int,
                'service_key': service_info.get('key', ''),
                'service_description': service_info.get('description', ''),
                'rate': float(rate_info.get('rate', 0)),
                'cogs': float(rate_info.get('cogs_rate', 0)),
                'revision_start_date': revision_start_date,
                'effective_date_formatted': effective_date
            }
            csv_data.append(csv_row)
        
        # Sort by account_id, then service_id for consistent output
        csv_data.sort(key=lambda x: (x['account_id'], x['service_id']))
        
        # Write CSV file
        self._write_csv_file(output_path, csv_data, is_list_prices=False)
        
        print(f"✅ Account-specific rates exported to: {output_path}")
        print(f"📊 Exported {len(csv_data)} account-specific rate records")

    def _write_csv_file(self, output_path: Path, csv_data: List[Dict], is_list_prices: bool = False):
        """Write CSV data to file with proper headers for import compatibility"""
        if not csv_data:
            print("❌ No data to export")
            return
        
        # Define headers based on import requirements
        if is_list_prices:
            # For list prices, we need the minimum required fields for import
            headers = ['account_id', 'service_id', 'rate', 'cogs', 'revision_start_date']
            # Optional additional headers for reference
            additional_headers = ['service_key', 'service_description', 'effective_date_formatted']
        else:
            # For account rates, include all useful fields
            headers = ['account_id', 'service_id', 'rate', 'cogs', 'revision_start_date']
            # Optional additional headers for reference
            additional_headers = ['account_name', 'service_key', 'service_description', 'effective_date_formatted']
        
        # Combine headers
        all_headers = headers + additional_headers
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_headers, extrasaction='ignore')
                writer.writeheader()
                
                for row in csv_data:
                    # For list prices, ensure account_id is empty string for import compatibility
                    if is_list_prices:
                        row['account_id'] = ''
                    writer.writerow(row)
                    
        except Exception as e:
            print(f"❌ Error writing CSV file: {e}")
            raise

    def show_rate_management_menu(self):
        """Enhanced rate management menu with indexation"""
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
                    questionary.Choice("📤 Export rates to CSV file", "export_csv"),
                    questionary.Choice("📈 Rate indexation (percentage adjustments)", "indexation"),
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
            elif choice == "export_csv":
                self.export_rates_to_csv_interactive()
                self._pause_for_review()
            elif choice == "indexation":
                self.rate_indexation_interactive()
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

    def _validate_percentage(self, value: str) -> bool:
        """Validate percentage input"""
        try:
            float_val = float(value)
            if float_val == 0:
                return "Percentage cannot be zero"
            if abs(float_val) > 100:
                return "Percentage seems too large (>100%). Please confirm this is correct."
            return True
        except ValueError:
            return "Please enter a valid number (e.g., 5, -3, 2.5)"

    def _validate_date_format(self, value: str) -> bool:
        """Validate date format"""
        if not value:
            return "Date is required"
        
        # Check YYYYMMDD format
        if len(value) == 8 and value.isdigit():
            try:
                year = int(value[:4])
                month = int(value[4:6])
                day = int(value[6:8])
                if year < 2000 or year > 2100:
                    return "Year should be between 2000-2100"
                if month < 1 or month > 12:
                    return "Month should be between 01-12"
                if day < 1 or day > 31:
                    return "Day should be between 01-31"
                return True
            except ValueError:
                return "Invalid date format"
        
        # Check YYYY-MM-DD format
        if len(value) == 10 and value.count('-') == 2:
            try:
                parts = value.split('-')
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                if year < 2000 or year > 2100:
                    return "Year should be between 2000-2100"
                if month < 1 or month > 12:
                    return "Month should be between 01-12"
                if day < 1 or day > 31:
                    return "Day should be between 01-31"
                return True
            except (ValueError, IndexError):
                return "Invalid date format"
        
        return "Please use YYYYMMDD or YYYY-MM-DD format"

    def _get_services_with_rate_tiers(self, dump_data: Dict) -> set:
        """Get set of service IDs that have rate tiers configured"""
        services_with_tiers = set()
        
        # Look for rate tier data in dump
        # Rate tiers might be in 'ratetier' model or referenced in rate data
        ratetiers = dump_data.get('ratetier', [])
        
        for tier in ratetiers:
            service_id = tier.get('service_id', '')
            if service_id:
                services_with_tiers.add(str(service_id))
        
        # Also check rates that have tier_aggregation_level set
        rates = dump_data.get('rate', [])
        for rate in rates:
            tier_level = rate.get('tier_aggregation_level', '')
            if tier_level and tier_level != '' and tier_level is not None:
                service_id = rate.get('service_id', '')
                if service_id:
                    services_with_tiers.add(str(service_id))
        
        if services_with_tiers:
            print(f"📋 Detected services with rate tiers: {sorted(services_with_tiers)}")
        
        return services_with_tiers

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
                continue
            
            # Validate rate values
            try:
                float(rate.get('rate', 0))
                float(rate.get('cogs_rate', 0))
            except (ValueError, TypeError):
                continue
            
            key = (account_id, service_id)
            
            if key not in latest_rates or effective_date > latest_rates[key]['effective_date']:
                latest_rates[key] = rate
        
        return latest_rates

    def _rate_exists_for_date(self, account_id: int, service_id: int, target_date: str, existing_rates: List[Dict]) -> bool:
        """Check if a rate already exists for the target date"""
        for rate in existing_rates:
            if (str(rate.get('account_id', '')) == str(account_id) and 
                str(rate.get('service_id', '')) == str(service_id) and 
                rate.get('effective_date', '') == target_date):
                return True
        return False

    def _create_indexed_rates_batch(self, indexed_rates: List[Dict]):
        """Create indexed rates using batch processing"""
        print(f"🔄 Creating {len(indexed_rates)} indexed rate revisions...")
        
        created_count = 0
        failed_count = 0
        
        # Process in batches of 50
        batch_size = 50
        total_batches = (len(indexed_rates) + batch_size - 1) // batch_size
        
        for i in range(0, len(indexed_rates), batch_size):
            batch = indexed_rates[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            try:
                print(f"   Creating batch {batch_num}/{total_batches} ({len(batch)} rates)...")
                result = self.api.create_rate_revisions_batch(batch)
                
                # Count successful creations
                atomic_results = result.get("atomic:results", [])
                successful_in_batch = len([r for r in atomic_results if "data" in r])
                created_count += successful_in_batch
                
                if successful_in_batch == len(batch):
                    print(f"   ✅ Batch {batch_num} completed successfully")
                else:
                    print(f"   ⚠️  Batch {batch_num}: {successful_in_batch}/{len(batch)} created")
                
            except Exception as e:
                print(f"   ❌ Batch {batch_num} failed: {e}")
                print("   🔄 Falling back to individual rate creation...")
                
                # Fall back to individual creation for this batch
                for rate in batch:
                    try:
                        self.api.create_rate_revision(
                            rate["account_id"], 
                            rate["service_id"], 
                            rate["rate"], 
                            rate["cogs"], 
                            rate["effective_date"]
                        )
                        created_count += 1
                    except Exception as e2:
                        failed_count += 1
        
        # Clear dump cache since we added new rates
        self.api.clear_dump_cache()
        
        # Summary
        print(f"\n📊 Indexation Summary:")
        print(f"   ✅ Successfully created: {created_count} rate revisions")
        if failed_count > 0:
            print(f"   ❌ Failed: {failed_count} rate revisions")
        
        total_attempted = len(indexed_rates)
        success_rate = (created_count / total_attempted * 100) if total_attempted > 0 else 0
        print(f"   📈 Success rate: {success_rate:.1f}%")

    def _perform_global_indexation(self, percentage: float, formatted_date: str, display_date: str):
        """Perform rate indexation for all accounts"""
        print(f"🌐 Starting indexation for all accounts ({percentage:+.2f}%)...")
        
        # Get all existing rates from dump data
        print("📊 Loading existing rates...")
        dump_data = self.api.fetch_dump_data()
        existing_rates = dump_data.get('rate', [])
        
        if not existing_rates:
            print("❌ No existing rates found")
            return
        
        print(f"📋 Found {len(existing_rates)} existing rates")
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        if services_with_tiers:
            print(f"⚠️  Found {len(services_with_tiers)} service(s) with rate tiers - these will be skipped")
        
        # Group rates by account/service to get latest rates
        latest_rates = self._get_latest_rates_by_account_service(existing_rates)
        
        print(f"📋 Found {len(latest_rates)} unique account/service combinations")
        
        # Create indexed rates
        indexed_rates = []
        skipped_invalid = 0
        skipped_existing = 0
        skipped_tiers = 0
        
        for (account_id, service_id), rate_info in latest_rates.items():
            try:
                # Convert to integers for consistency
                account_id_int = int(account_id)
                service_id_int = int(service_id)
                
                # Skip services with rate tiers
                if str(service_id_int) in services_with_tiers:
                    skipped_tiers += 1
                    continue
                
                # Check if indexed rate already exists
                if self._rate_exists_for_date(account_id_int, service_id_int, formatted_date, existing_rates):
                    skipped_existing += 1
                    continue
                
                # Calculate new rates
                current_rate = float(rate_info.get('rate', 0))
                current_cogs = float(rate_info.get('cogs_rate', 0))
                
                if current_rate == 0 and current_cogs == 0:
                    skipped_invalid += 1
                    continue
                
                new_rate = current_rate * (1 + percentage / 100)
                new_cogs = current_cogs * (1 + percentage / 100)
                
                indexed_rates.append({
                    "account_id": account_id_int,
                    "service_id": service_id_int,
                    "rate": round(new_rate, 6),
                    "cogs": round(new_cogs, 6),
                    "effective_date": display_date,
                    "original_rate": current_rate,
                    "original_cogs": current_cogs
                })
                
            except (ValueError, TypeError) as e:
                skipped_invalid += 1
                continue
        
        if not indexed_rates:
            print("❌ No rates to index")
            if skipped_existing > 0:
                print(f"   • {skipped_existing} rates already exist for target date")
            if skipped_invalid > 0:
                print(f"   • {skipped_invalid} rates had invalid data")
            if skipped_tiers > 0:
                print(f"   • {skipped_tiers} services with rate tiers (not supported)")
            return
        
        print(f"📋 Will create {len(indexed_rates)} indexed rates for all accounts")
        if skipped_existing > 0:
            print(f"   • {skipped_existing} rates already exist (will skip)")
        if skipped_invalid > 0:
            print(f"   • {skipped_invalid} rates had invalid data (skipped)")
        if skipped_tiers > 0:
            print(f"   • {skipped_tiers} services with rate tiers (skipped - not supported)")
        
        # Show sample of changes
        print("\n📊 Sample of rate changes:")
        for i, rate in enumerate(indexed_rates[:5]):
            print(f"   • Account {rate['account_id']}, Service {rate['service_id']}: "
                  f"{rate['original_rate']:.6f} → {rate['rate']:.6f} "
                  f"(COGS: {rate['original_cogs']:.6f} → {rate['cogs']:.6f})")
        
        if len(indexed_rates) > 5:
            print(f"   ... and {len(indexed_rates) - 5} more")
        
        # Final confirmation
        confirm = questionary.confirm(
            f"\nCreate {len(indexed_rates)} indexed rate revisions across all accounts?",
            default=True
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        # Create the indexed rates
        self._create_indexed_rates_batch(indexed_rates)

    def _perform_account_indexation(self, account_id: int, percentage: float, formatted_date: str, display_date: str):
        """Perform account-specific rate indexation with improved error handling"""
        print(f"🏢 Starting indexation for Account {account_id} ({percentage:+.2f}%)...")
        
        # Get all existing rates from dump data
        print("📊 Loading existing rates...")
        dump_data = self.api.fetch_dump_data()
        existing_rates = dump_data.get('rate', [])
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        if services_with_tiers:
            print(f"⚠️  Found {len(services_with_tiers)} service(s) with rate tiers - these will be skipped")
        
        # Filter rates for the target account with validation
        account_rates = []
        for rate in existing_rates:
            try:
                rate_account_id = rate.get('account_id', '')
                if rate_account_id and int(rate_account_id) == account_id:
                    account_rates.append(rate)
            except (ValueError, TypeError):
                continue  # Skip invalid account_id values
        
        if not account_rates:
            print(f"❌ No existing rates found for Account {account_id}")
            return
        
        print(f"📋 Found {len(account_rates)} existing rates for Account {account_id}")
        
        # Group by service to get latest rates with validation
        latest_rates = {}
        for rate in account_rates:
            try:
                service_id = rate.get('service_id', '')
                effective_date = rate.get('effective_date', '')
                
                # Validate service_id
                if not service_id or service_id == '':
                    continue
                
                service_id_int = int(service_id)
                
                # Validate rate values
                rate_value = float(rate.get('rate', 0))
                cogs_value = float(rate.get('cogs_rate', 0))
                
                key = service_id_int
                if key not in latest_rates or effective_date > latest_rates[key]['effective_date']:
                    latest_rates[key] = rate
                    
            except (ValueError, TypeError):
                continue  # Skip invalid data
        
        print(f"📋 Found {len(latest_rates)} unique services for Account {account_id}")
        
        # Create indexed rates
        indexed_rates = []
        skipped_existing = 0
        skipped_invalid = 0
        skipped_tiers = 0
        
        for service_id_int, rate_info in latest_rates.items():
            try:
                # Skip services with rate tiers
                if str(service_id_int) in services_with_tiers:
                    skipped_tiers += 1
                    continue
                
                # Check if indexed rate already exists
                if self._rate_exists_for_date(account_id, service_id_int, formatted_date, existing_rates):
                    skipped_existing += 1
                    continue
                
                # Calculate new rates
                current_rate = float(rate_info.get('rate', 0))
                current_cogs = float(rate_info.get('cogs_rate', 0))
                
                if current_rate == 0 and current_cogs == 0:
                    skipped_invalid += 1
                    continue
                
                new_rate = current_rate * (1 + percentage / 100)
                new_cogs = current_cogs * (1 + percentage / 100)
                
                indexed_rates.append({
                    "account_id": account_id,
                    "service_id": service_id_int,
                    "rate": round(new_rate, 6),
                    "cogs": round(new_cogs, 6),
                    "effective_date": display_date,
                    "original_rate": current_rate,
                    "original_cogs": current_cogs
                })
                
            except (ValueError, TypeError) as e:
                skipped_invalid += 1
                continue
        
        if not indexed_rates:
            print("❌ No rates to index")
            if skipped_existing > 0:
                print(f"   • {skipped_existing} rates already exist for target date")
            if skipped_invalid > 0:
                print(f"   • {skipped_invalid} rates had invalid data")
            if skipped_tiers > 0:
                print(f"   • {skipped_tiers} services with rate tiers (not supported)")
            return
        
        print(f"📋 Will create {len(indexed_rates)} indexed rates for Account {account_id}")
        if skipped_tiers > 0:
            print(f"   • {skipped_tiers} services with rate tiers skipped (not supported)")
        
        # Show all changes for account-specific indexation
        print(f"\n📊 Rate changes for Account {account_id}:")
        for rate in indexed_rates:
            print(f"   • Service {rate['service_id']}: "
                  f"{rate['original_rate']:.6f} → {rate['rate']:.6f} "
                  f"(COGS: {rate['original_cogs']:.6f} → {rate['cogs']:.6f})")
        
        # Final confirmation
        confirm = questionary.confirm(
            f"\nCreate {len(indexed_rates)} indexed rate revisions for Account {account_id}?",
            default=True
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        # Create the indexed rates
        self._create_indexed_rates_batch(indexed_rates)

    def _perform_list_price_indexation(self, percentage: float, formatted_date: str, display_date: str):
        """Perform list price indexation for services with manual rates"""
        print(f"📝 Starting list price indexation ({percentage:+.2f}%)...")
        
        # Get all existing rates from dump data
        print("📊 Loading existing rates...")
        dump_data = self.api.fetch_dump_data()
        existing_rates = dump_data.get('rate', [])
        
        if not existing_rates:
            print("❌ No existing rates found")
            return
        
        print(f"📋 Found {len(existing_rates)} existing rates")
        
        # Get services with rate tiers to exclude them
        services_with_tiers = self._get_services_with_rate_tiers(dump_data)
        if services_with_tiers:
            print(f"⚠️  Found {len(services_with_tiers)} service(s) with rate tiers - these will be skipped")
        
        # Find list prices (rates with account_id = null/empty)
        list_price_rates = []
        for rate in existing_rates:
            account_id = rate.get('account_id', '')
            # List prices have no account_id (null or empty)
            if not account_id or account_id == '' or account_id == 'null':
                list_price_rates.append(rate)
        
        if not list_price_rates:
            print("❌ No list prices found")
            print("💡 List prices are default rates that apply to all accounts when no account-specific rate exists")
            return
        
        print(f"📋 Found {len(list_price_rates)} existing list prices")
        
        # Group by service to get latest list price per service
        latest_list_prices = {}
        for rate in list_price_rates:
            service_id = rate.get('service_id', '')
            effective_date = rate.get('effective_date', '')
            
            if not service_id:
                continue
                
            try:
                service_id_int = int(service_id)
                # Validate rate values
                float(rate.get('rate', 0))
                float(rate.get('cogs_rate', 0))
                
                if service_id_int not in latest_list_prices or effective_date > latest_list_prices[service_id_int]['effective_date']:
                    latest_list_prices[service_id_int] = rate
            except (ValueError, TypeError):
                continue
        
        print(f"📋 Found {len(latest_list_prices)} services with list prices")
        
        # Create indexed list prices
        indexed_rates = []
        skipped_invalid = 0
        skipped_existing = 0
        skipped_tiers = 0
        
        for service_id_int, rate_info in latest_list_prices.items():
            try:
                # Skip services with rate tiers
                if str(service_id_int) in services_with_tiers:
                    skipped_tiers += 1
                    continue
                
                # Check if indexed list price already exists
                if self._list_price_exists_for_date(service_id_int, formatted_date, existing_rates):
                    skipped_existing += 1
                    continue
                
                # Calculate new rates
                current_rate = float(rate_info.get('rate', 0))
                current_cogs = float(rate_info.get('cogs_rate', 0))
                
                if current_rate == 0 and current_cogs == 0:
                    skipped_invalid += 1
                    continue
                
                new_rate = current_rate * (1 + percentage / 100)
                new_cogs = current_cogs * (1 + percentage / 100)
                
                indexed_rates.append({
                    "service_id": service_id_int,
                    "rate": round(new_rate, 6),
                    "cogs": round(new_cogs, 6),
                    "effective_date": display_date,
                    "original_rate": current_rate,
                    "original_cogs": current_cogs
                })
                
            except (ValueError, TypeError) as e:
                skipped_invalid += 1
                continue
        
        if not indexed_rates:
            print("❌ No list prices to index")
            if skipped_existing > 0:
                print(f"   • {skipped_existing} list prices already exist for target date")
            if skipped_invalid > 0:
                print(f"   • {skipped_invalid} list prices had invalid data")
            if skipped_tiers > 0:
                print(f"   • {skipped_tiers} services with rate tiers (not supported)")
            return
        
        print(f"📋 Will create {len(indexed_rates)} indexed list prices")
        if skipped_existing > 0:
            print(f"   • {skipped_existing} list prices already exist (will skip)")
        if skipped_invalid > 0:
            print(f"   • {skipped_invalid} list prices had invalid data (skipped)")
        if skipped_tiers > 0:
            print(f"   • {skipped_tiers} services with rate tiers (skipped - not supported)")
        
        # Show sample of changes
        print("\n📊 Sample of list price changes:")
        for i, rate in enumerate(indexed_rates[:5]):
            print(f"   • Service {rate['service_id']}: "
                  f"{rate['original_rate']:.6f} → {rate['rate']:.6f} "
                  f"(COGS: {rate['original_cogs']:.6f} → {rate['cogs']:.6f})")
        
        if len(indexed_rates) > 5:
            print(f"   ... and {len(indexed_rates) - 5} more")
        
        # Final confirmation
        confirm = questionary.confirm(
            f"\nCreate {len(indexed_rates)} indexed list prices?",
            default=True
        ).ask()
        
        if not confirm:
            print("Operation cancelled.")
            return
        
        # Create the indexed list prices
        self._create_indexed_list_prices_batch(indexed_rates)

    def _list_price_exists_for_date(self, service_id: int, target_date: str, existing_rates: List[Dict]) -> bool:
        """Check if a list price already exists for the target date"""
        for rate in existing_rates:
            account_id = rate.get('account_id', '')
            # Check for list price (no account_id) and matching service/date
            if (not account_id or account_id == '' or account_id == 'null') and \
               str(rate.get('service_id', '')) == str(service_id) and \
               rate.get('effective_date', '') == target_date:
                return True
        return False

    def _create_indexed_list_prices_batch(self, indexed_rates: List[Dict]):
        """Create indexed list prices using batch processing"""
        print(f"🔄 Creating {len(indexed_rates)} indexed list prices...")
        
        created_count = 0
        failed_count = 0
        
        # Process in batches of 50
        batch_size = 50
        total_batches = (len(indexed_rates) + batch_size - 1) // batch_size
        
        for i in range(0, len(indexed_rates), batch_size):
            batch = indexed_rates[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            try:
                print(f"   Creating batch {batch_num}/{total_batches} ({len(batch)} list prices)...")
                result = self.api.create_list_price_revisions_batch(batch)
                
                # Count successful creations
                atomic_results = result.get("atomic:results", [])
                successful_in_batch = len([r for r in atomic_results if "data" in r])
                created_count += successful_in_batch
                
                if successful_in_batch == len(batch):
                    print(f"   ✅ Batch {batch_num} completed successfully")
                else:
                    print(f"   ⚠️  Batch {batch_num}: {successful_in_batch}/{len(batch)} created")
                
            except Exception as e:
                print(f"   ❌ Batch {batch_num} failed: {e}")
                print("   🔄 Falling back to individual list price creation...")
                
                # Fall back to individual creation for this batch
                for rate in batch:
                    try:
                        self.api.create_list_price_revision(
                            rate["service_id"], 
                            rate["rate"], 
                            rate["cogs"], 
                            rate["effective_date"]
                        )
                        created_count += 1
                    except Exception as e2:
                        failed_count += 1
                        print(f"   ❌ Failed to create list price for Service {rate['service_id']}: {e2}")
        
        # Clear dump cache since we added new rates
        self.api.clear_dump_cache()
        
        # Summary
        print(f"\n📊 List Price Indexation Summary:")
        print(f"   ✅ Successfully created: {created_count} list price revisions")
        if failed_count > 0:
            print(f"   ❌ Failed: {failed_count} list price revisions")
        
        total_attempted = len(indexed_rates)
        success_rate = (created_count / total_attempted * 100) if total_attempted > 0 else 0
        print(f"   📈 Success rate: {success_rate:.1f}%")
