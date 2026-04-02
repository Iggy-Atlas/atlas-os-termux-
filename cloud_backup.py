# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

#!/usr/bin/env python3
"""
Google Cloud Backup Script - rclone integration
Backs up database.db to Google Drive via rclone
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

def backup_to_google_drive():
    """
    Execute rclone backup command to sync database.db to Google Drive.
    Assumes rclone is configured with 'remote:' name locally in Termux.
    """
    
    # Source file
    source_file = "database.db"
    
    # Destination on Google Drive
    destination = "remote:AtlasBackup/"
    
    # Check if source file exists
    if not Path(source_file).exists():
        print(f"❌ Error: {source_file} not found in current directory")
        sys.exit(1)
    
    # Construct rclone command
    cmd = ["rclone", "copy", source_file, destination, "-v"]
    
    print(f"🛰️  Starting backup: {source_file} → {destination}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"📦 File size: {Path(source_file).stat().st_size / (1024*1024):.2f} MB")
    print("-" * 60)
    
    try:
        # Execute rclone command
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print("-" * 60)
        print(f"✅ Backup successful!")
        print(f"📍 Location: {destination}")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Backup failed with error code: {e.returncode}")
        print(f"Make sure rclone is installed and configured with 'remote:' name")
        sys.exit(1)
        
    except FileNotFoundError:
        print("❌ Error: rclone not found. Please install rclone first:")
        print("   pip install rclone  OR  apt install rclone")
        sys.exit(1)

if __name__ == "__main__":
    backup_to_google_drive()