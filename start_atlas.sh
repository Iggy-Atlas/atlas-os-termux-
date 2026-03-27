#!/bin/bash

# 1. Aktiviraj Wake Lock (Sprečava CPU sleep)
termux-wake-lock
echo "[$(date)] Wake-lock aktiviran. Sustav je budan." >> atlas_log.txt

# 2. Watchdog Petlja
while true; do
    if ! pgrep -f "uvicorn main:app" > /dev/null; then
        echo "------------------------------------------------" >> atlas_log.txt
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] KLJUČNI PAD: Atlas proces nije pronađen." >> atlas_log.txt
        
        # Tvoj prijedlog: RAM Snapshot
        echo "STATUS MEMORIJE:" >> atlas_log.txt
        free -m | grep Mem >> atlas_log.txt
        
        echo "RESTARTIRAM SUSTAV..." >> atlas_log.txt
        
        # Pokretanje s preusmjeravanjem grešaka u log
        source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 >> atlas_log.txt 2>&1 &
        
        echo "[$(date)] Atlas uspješno restartiran." >> atlas_log.txt
    fi
    sleep 30
done
