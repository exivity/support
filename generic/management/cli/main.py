class ExivityCLI:
    """Main CLI application class"""
    
    def __init__(self):
        self.api: Optional[ExivityAPI] = None
        self.rate_manager: Optional[RateManager] = None
        self.workflow_manager: Optional[WorkflowManager] = None
        self.environment_manager: Optional[EnvironmentManager] = None
    
    def show_main_menu(self):
        """Display the main topic selection menu"""
        if not self.api:
            print("❌ Not connected to API. Please connect first.")
            return
        
        print("\n" + "="*60)
        print("🎯 EXIVITY MANAGEMENT CLI")
        print("="*60)
        
        choice = questionary.select(
            "Select a management area:",
            choices=[
                questionary.Choice("💰 Rate Management", "rates"),
                questionary.Choice("⚙️  Workflow Management", "workflows"), 
                questionary.Choice("🌐 Environment Management", "environments"),
                questionary.Choice("🔄 Reconnect to API", "reconnect"),
                questionary.Choice("❌ Exit", "exit")
            ],
            style=questionary.Style([
                ('question', 'bold'),
                ('answer', 'fg:#ff9d00 bold'),
                ('pointer', 'fg:#ff9d00 bold'),
                ('highlighted', 'fg:#ff9d00 bold'),
                ('selected', 'fg:#cc5454'),
                ('separator', 'fg:#cc5454'),
                ('instruction', ''),
                ('text', ''),
                ('disabled', 'fg:#858585 italic')
            ])
        ).ask()
        
        if choice == "rates":
            self.show_rate_management_menu()
        elif choice == "workflows":
            self.show_workflow_management_menu()
        elif choice == "environments":
            self.show_environment_management_menu()
        elif choice == "reconnect":
            self.connect_to_api()
        elif choice == "exit":
            print("👋 Goodbye!")
            return False
        
        return True
    
    def show_rate_management_menu(self):
        """Rate management topic menu"""
        while True:
            print("\n" + "="*60)
            print("💰 RATE MANAGEMENT")
            print("="*60)
            
            choice = questionary.select(
                "Choose a rate management operation:",
                choices=[
                    questionary.Choice("📁 Import rates from CSV file", "import_csv"),
                    questionary.Choice("🔍 Validate CSV file format", "validate_csv"),
                    questionary.Choice("📊 Check rate revision status", "check_status"),
                    questionary.Choice("📈 Batch rate operations", "batch_ops"),
                    questionary.Choice("⬅️  Back to main menu", "back")
                ],
                style=questionary.Style([
                    ('question', 'bold'),
                    ('answer', 'fg:#ff9d00 bold'),
                    ('pointer', 'fg:#ff9d00 bold'),
                    ('highlighted', 'fg:#ff9d00 bold'),
                    ('selected', 'fg:#cc5454'),
                ])
            ).ask()
            
            if choice == "import_csv":
                csv_path = questionary.path(
                    "📁 Select CSV file:",
                    validate=lambda x: "File is required" if not x else True
                ).ask()
                if csv_path:
                    self.rate_manager.update_rates_from_csv(csv_path)
                    self._pause_for_review()
                    
            elif choice == "validate_csv":
                csv_path = questionary.path(
                    "📁 Select CSV file to validate:",
                    validate=lambda x: "File is required" if not x else True
                ).ask()
                if csv_path:
                    self.rate_manager.validate_csv_format(csv_path)
                    self._pause_for_review()
                    
            elif choice == "check_status":
                self.rate_manager.check_rate_status_interactive()
                self._pause_for_review()
                
            elif choice == "batch_ops":
                self._show_batch_operations_menu()
                
            elif choice == "back":
                break
    
    def show_workflow_management_menu(self):
        """Workflow management topic menu"""
        while True:
            print("\n" + "="*60)
            print("⚙️  WORKFLOW MANAGEMENT")
            print("="*60)
            
            choice = questionary.select(
                "Choose a workflow management operation:",
                choices=[
                    questionary.Choice("🆕 Create new workflow", "create"),
                    questionary.Choice("📋 List existing workflows", "list"),
                    questionary.Choice("🔄 Duplicate workflow", "duplicate"),
                    questionary.Choice("✏️  Edit workflow", "edit"),
                    questionary.Choice("🗑️  Delete workflow", "delete"),
                    questionary.Choice("🕐 Hourly workflow tools", "hourly_tools"),
                    questionary.Choice("⬅️  Back to main menu", "back")
                ],
                style=questionary.Style([
                    ('question', 'bold'),
                    ('answer', 'fg:#ff9d00 bold'),
                    ('pointer', 'fg:#ff9d00 bold'),
                    ('highlighted', 'fg:#ff9d00 bold'),
                    ('selected', 'fg:#cc5454'),
                ])
            ).ask()
            
            if choice == "create":
                self.workflow_manager.create_workflow_interactively()
                self._pause_for_review()
                
            elif choice == "list":
                self.workflow_manager.list_workflows_interactive()
                self._pause_for_review()
                
            elif choice == "duplicate":
                self.workflow_manager.duplicate_workflow_interactive()
                self._pause_for_review()
                
            elif choice == "edit":
                self.workflow_manager.edit_workflow_interactive()
                self._pause_for_review()
                
            elif choice == "delete":
                self.workflow_manager.delete_workflow_interactive()
                self._pause_for_review()
                
            elif choice == "hourly_tools":
                self._show_hourly_workflow_tools_menu()
                
            elif choice == "back":
                break
    
    def show_environment_management_menu(self):
        """Environment management topic menu"""
        while True:
            print("\n" + "="*60)
            print("🌐 ENVIRONMENT MANAGEMENT")
            print("="*60)
            
            choice = questionary.select(
                "Choose an environment management operation:",
                choices=[
                    questionary.Choice("📊 Show environment status", "status"),
                    questionary.Choice("🔧 Create missing environments", "create_missing"),
                    questionary.Choice("🌐 Manage hourly environments", "hourly_mgmt"),
                    questionary.Choice("🔄 Bulk environment operations", "bulk_ops"),
                    questionary.Choice("⚙️  Environment configuration", "config"),
                    questionary.Choice("⬅️  Back to main menu", "back")
                ],
                style=questionary.Style([
                    ('question', 'bold'),
                    ('answer', 'fg:#ff9d00 bold'),
                    ('pointer', 'fg:#ff9d00 bold'),
                    ('highlighted', 'fg:#ff9d00 bold'),
                    ('selected', 'fg:#cc5454'),
                ])
            ).ask()
            
            if choice == "status":
                self.environment_manager.list_hourly_environments()
                self._pause_for_review()
                
            elif choice == "create_missing":
                self.environment_manager.recreate_missing_environments()
                self._pause_for_review()
                
            elif choice == "hourly_mgmt":
                self._show_hourly_environment_menu()
                
            elif choice == "bulk_ops":
                self._show_bulk_environment_menu()
                
            elif choice == "config":
                self.environment_manager.configure_environments_interactive()
                self._pause_for_review()
                
            elif choice == "back":
                break
    
    def _show_batch_operations_menu(self):
        """Batch operations submenu for rates"""
        while True:
            print("\n" + "-"*40)
            print("📈 BATCH RATE OPERATIONS")
            print("-"*40)
            
            choice = questionary.select(
                "Choose a batch operation:",
                choices=[
                    questionary.Choice("📊 Bulk rate import", "bulk_import"),
                    questionary.Choice("🔍 Validate multiple CSV files", "validate_multiple"),
                    questionary.Choice("📈 Generate rate reports", "generate_reports"),
                    questionary.Choice("⬅️  Back to rate management", "back")
                ]
            ).ask()
            
            if choice == "bulk_import":
                self.rate_manager.bulk_import_interactive()
                self._pause_for_review()
            elif choice == "validate_multiple":
                self.rate_manager.validate_multiple_csv_files()
                self._pause_for_review()
            elif choice == "generate_reports":
                self.rate_manager.generate_rate_reports()
                self._pause_for_review()
            elif choice == "back":
                break
    
    def _show_hourly_workflow_tools_menu(self):
        """Hourly workflow tools submenu"""
        while True:
            print("\n" + "-"*40)
            print("🕐 HOURLY WORKFLOW TOOLS")
            print("-"*40)
            
            choice = questionary.select(
                "Choose an hourly workflow tool:",
                choices=[
                    questionary.Choice("🆕 Create hourly workflow", "create_hourly"),
                    questionary.Choice("📋 List hourly workflows", "list_hourly"),
                    questionary.Choice("🔄 Duplicate across hours", "duplicate_hourly"),
                    questionary.Choice("🗑️  Delete hourly workflows", "delete_hourly"),
                    questionary.Choice("⬅️  Back to workflow management", "back")
                ]
            ).ask()
            
            if choice == "create_hourly":
                self.workflow_manager.create_hourly_workflow_interactively()
                self._pause_for_review()
            elif choice == "list_hourly":
                self.workflow_manager.list_hourly_workflows()
                self._pause_for_review()
            elif choice == "duplicate_hourly":
                self.workflow_manager.duplicate_across_hours()
                self._pause_for_review()
            elif choice == "delete_hourly":
                self.workflow_manager.delete_hourly_workflows()
                self._pause_for_review()
            elif choice == "back":
                break
    
    def _show_hourly_environment_menu(self):
        """Hourly environment management submenu"""
        while True:
            print("\n" + "-"*40)
            print("🕐 HOURLY ENVIRONMENT MANAGEMENT")
            print("-"*40)
            
            choice = questionary.select(
                "Choose an hourly environment operation:",
                choices=[
                    questionary.Choice("📊 Show hour_00-hour_23 status", "show_hourly_status"),
                    questionary.Choice("🔧 Create missing hour_00-hour_23", "create_missing_hourly"),
                    questionary.Choice("🗑️  Delete hour_00-hour_23 environments", "delete_hourly"),
                    questionary.Choice("🔄 Recreate all hour_00-hour_23", "recreate_hourly"),
                    questionary.Choice("⬅️  Back to environment management", "back")
                ]
            ).ask()
            
            if choice == "show_hourly_status":
                self.environment_manager.list_hourly_environments()
                self._pause_for_review()
            elif choice == "create_missing_hourly":
                self.environment_manager.recreate_missing_environments()
                self._pause_for_review()
            elif choice == "delete_hourly":
                self.environment_manager.delete_hourly_environments_interactive()
                self._pause_for_review()
            elif choice == "recreate_hourly":
                self.environment_manager.recreate_all_hourly_environments()
                self._pause_for_review()
            elif choice == "back":
                break
    
    def _show_bulk_environment_menu(self):
        """Bulk environment operations submenu"""
        while True:
            print("\n" + "-"*40)
            print("🔄 BULK ENVIRONMENT OPERATIONS")
            print("-"*40)
            
            choice = questionary.select(
                "Choose a bulk environment operation:",
                choices=[
                    questionary.Choice("📊 Environment health check", "health_check"),
                    questionary.Choice("🔧 Bulk configuration update", "bulk_config"),
                    questionary.Choice("📋 Export environment settings", "export_settings"),
                    questionary.Choice("📁 Import environment settings", "import_settings"),
                    questionary.Choice("⬅️  Back to environment management", "back")
                ]
            ).ask()
            
            if choice == "health_check":
                self.environment_manager.run_health_check()
                self._pause_for_review()
            elif choice == "bulk_config":
                self.environment_manager.bulk_configuration_update()
                self._pause_for_review()
            elif choice == "export_settings":
                self.environment_manager.export_environment_settings()
                self._pause_for_review()
            elif choice == "import_settings":
                self.environment_manager.import_environment_settings()
                self._pause_for_review()
            elif choice == "back":
                break
    
    def _pause_for_review(self):
        """Pause to let user review output before returning to menu"""
        print("\n" + "-"*40)
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
