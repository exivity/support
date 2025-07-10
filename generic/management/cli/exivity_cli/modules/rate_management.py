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

    def show_rate_management_menu(self):
        """Enhanced rate management menu with system insights"""
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
            elif choice == "check_status":
                self.check_rate_status_interactive()
                self._pause_for_review()
            elif choice == "back":
                break

    def _pause_for_review(self):
        """Pause to let user review output before returning to menu"""
        print("\n" + "-"*40)
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
