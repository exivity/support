#!/usr/bin/env python3
"""
Direct runner for Exivity CLI - for testing and development
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the CLI
from exivity_cli.main import main

if __name__ == "__main__":
    print("🚀 Starting Exivity CLI directly...")
    main()
