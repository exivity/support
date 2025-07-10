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
                    print(f"DEBUG: First line with {encoding} encoding: '{first_line}'")
                    print(f"DEBUG: First line bytes: {first_line.encode('utf-8')}")
                    
                    # Reset file pointer
                    f.seek(0)
                    
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    
                    print(f"DEBUG: Detected fieldnames: {fieldnames}")
                    print(f"DEBUG: Fieldnames as list: {list(fieldnames) if fieldnames else 'None'}")
                    
                    # Clean fieldnames (remove any hidden characters)
                    if fieldnames:
                        cleaned_fieldnames = [field.strip().replace('\ufeff', '') for field in fieldnames]
                        print(f"DEBUG: Cleaned fieldnames: {cleaned_fieldnames}")
                        
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
            print(f"DEBUG: Header row (row 1) contains: {reader.fieldnames}")
            
            # Collect all rate data and check for existing revisions using dump data
            new_rates = []
            skipped_count = 0
            processed_rows = 0
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
                processed_rows += 1
                print(f"DEBUG: Processing row {row_num} (data row {processed_rows}): {row}")
                
                try:
                    # Clean the row data (remove any hidden characters)
                    cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                    
                    acc = int(cleaned_row["account_id"])
                    svc = int(cleaned_row["service_id"])
                    rate = float(cleaned_row["rate"])
                    cogs = float(cleaned_row["cogs"])
                    eff_date = cleaned_row["revision_start_date"]
                    
                    print(f"DEBUG: Parsed data - Account: {acc}, Service: {svc}, Rate: {rate}, COGS: {cogs}, Date: {eff_date}")
                    
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
                    print(f"Row {row_num}: Data: {row}")
                    continue
                except Exception as e:
                    print(f"Row {row_num}: Error processing row - {e}")
                    print(f"Row {row_num}: Data: {row}")
                    continue
            
            print(f"DEBUG: Total data rows processed: {processed_rows}")
            print(f"DEBUG: New rates to create: {len(new_rates)}")
            print(f"DEBUG: Skipped existing rates: {skipped_count}")
            
            # Create rates in batches using atomic operations
            processed_count = 0
            if new_rates:
                # Process in batches of 50 to avoid too large requests
                batch_size = 50
                for i in range(0, len(new_rates), batch_size):
                    batch = new_rates[i:i+batch_size]
                    
                    try:
                        print(f"Creating batch of {len(batch)} rate revisions...")
                        result = self.api.create_rate_revisions_batch(batch)
                        
                        # Count successful creations
                        atomic_results = result.get("atomic:results", [])
                        successful_in_batch = len([r for r in atomic_results if "data" in r])
                        processed_count += successful_in_batch
                        
                        for rate in batch:
                            print(f"Row {rate['row_num']}: Created rate revision for account {rate['account_id']}, service {rate['service_id']} ({rate['effective_date']})")
                        
                    except Exception as e:
                        print(f"Error creating batch: {e}")
                        # Fall back to individual creation for this batch
                        print("Falling back to individual rate creation...")
                        for rate in batch:
                            try:
                                self.api.create_rate_revision(
                                    rate["account_id"], 
                                    rate["service_id"], 
                                    rate["rate"], 
                                    rate["cogs"], 
                                    rate["effective_date"]
                                )
                                print(f"Row {rate['row_num']}: Created rate revision for account {rate['account_id']}, service {rate['service_id']} ({rate['effective_date']})")
                                processed_count += 1
                            except Exception as e2:
                                print(f"Row {rate['row_num']}: Error creating individual rate - {e2}")
            
            # Clear the dump cache after processing since we may have added new rates
            self.api.clear_dump_cache()
            
            print(f"✅ Finished processing CSV:")
            print(f"   - Total data rows in file: {processed_rows}")
            print(f"   - Successfully processed: {processed_count} rows")
            print(f"   - Skipped (already exist): {skipped_count} rows")
            print(f"   - Errors: {processed_rows - processed_count - skipped_count} rows")

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
                questionary.Choice("🌐 All accounts", "global"),
                questionary.Choice("🏢 Account-specific rates", "account"),
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
        scope_text = f"Account {target_account_id}" if scope == "account" else "All accounts"
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
            else:
                self._perform_account_indexation(target_account_id, percentage_value, formatted_date, display_date)
        except Exception as e:
            print(f"❌ Error during indexation: {e}")

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
        
        # Group rates by account/service to get latest rates
        latest_rates = self._get_latest_rates_by_account_service(existing_rates)
        
        print(f"📋 Found {len(latest_rates)} unique account/service combinations")
        
        # Create indexed rates
        indexed_rates = []
        skipped_invalid = 0
        skipped_existing = 0
        
        for (account_id, service_id), rate_info in latest_rates.items():
            try:
                # Convert to integers for consistency
                account_id_int = int(account_id)
                service_id_int = int(service_id)
                
                # Check if indexed rate already exists
                if self._rate_exists_for_date(account_id_int, service_id_int, formatted_date, existing_rates):
                    print(f"   ⏭️  Skipping Account {account_id_int}, Service {service_id_int} - rate already exists for {display_date}")
                    skipped_existing += 1
                    continue
                
                # Calculate new rates
                current_rate = float(rate_info.get('rate', 0))
                current_cogs = float(rate_info.get('cogs_rate', 0))
                
                if current_rate == 0 and current_cogs == 0:
                    print(f"   ⚠️  Skipping Account {account_id_int}, Service {service_id_int} - zero rates")
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
                print(f"   ⚠️  Skipping invalid data for Account {account_id}, Service {service_id}: {e}")
                skipped_invalid += 1
                continue
        
        if not indexed_rates:
            print("❌ No rates to index")
            print(f"   • {skipped_existing} rates already exist for target date")
            print(f"   • {skipped_invalid} rates had invalid data")
            return
        
        print(f"📋 Will create {len(indexed_rates)} indexed rates for all accounts")
        print(f"   • {skipped_existing} rates already exist (will skip)")
        print(f"   • {skipped_invalid} rates had invalid data (skipped)")
        
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
        
        for service_id_int, rate_info in latest_rates.items():
            try:
                # Check if indexed rate already exists
                if self._rate_exists_for_date(account_id, service_id_int, formatted_date, existing_rates):
                    print(f"   ⏭️  Skipping Service {service_id_int} - rate already exists for {display_date}")
                    skipped_existing += 1
                    continue
                
                # Calculate new rates
                current_rate = float(rate_info.get('rate', 0))
                current_cogs = float(rate_info.get('cogs_rate', 0))
                
                if current_rate == 0 and current_cogs == 0:
                    print(f"   ⚠️  Skipping Service {service_id_int} - zero rates")
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
                print(f"   ⚠️  Skipping Service {service_id_int}: {e}")
                skipped_invalid += 1
                continue
        
        if not indexed_rates:
            print("❌ No rates to index")
            print(f"   • {skipped_existing} rates already exist for target date")
            print(f"   • {skipped_invalid} rates had invalid data")
            return
        
        print(f"📋 Will create {len(indexed_rates)} indexed rates for Account {account_id}")
        
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
        for i in range(0, len(indexed_rates), batch_size):
            batch = indexed_rates[i:i+batch_size]
            
            try:
                print(f"   Creating batch {i//batch_size + 1} ({len(batch)} rates)...")
                result = self.api.create_rate_revisions_batch(batch)
                
                # Count successful creations
                atomic_results = result.get("atomic:results", [])
                successful_in_batch = len([r for r in atomic_results if "data" in r])
                created_count += successful_in_batch
                
                if successful_in_batch == len(batch):
                    print(f"   ✅ Batch {i//batch_size + 1} completed successfully")
                else:
                    print(f"   ⚠️  Batch {i//batch_size + 1}: {successful_in_batch}/{len(batch)} created")
                
            except Exception as e:
                print(f"   ❌ Batch {i//batch_size + 1} failed: {e}")
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
                        print(f"   ✅ Created indexed rate for Account {rate['account_id']}, Service {rate['service_id']}")
                    except Exception as e2:
                        failed_count += 1
                        print(f"   ❌ Failed to create rate for Account {rate['account_id']}, Service {rate['service_id']}: {e2}")
        
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
