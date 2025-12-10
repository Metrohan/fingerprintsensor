#!/bin/bash
# stop_all.sh
# Tüm servisleri durdurur

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$PROJECT_DIR/data"

echo -e "${YELLOW}Servisler durduruluyor...${NC}"

# PID dosyalarından durdur
for pid_file in "$PID_DIR/app.pid" "$PID_DIR/panel.pid" "$PID_DIR/automation.pid"; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid 2>/dev/null
            echo -e "  PID $pid durduruldu"
        fi
        rm -f "$pid_file"
    fi
done

# Kalan python süreçlerini de temizle
pkill -f "python3.*app.py" 2>/dev/null
pkill -f "python3.*panel_ui.py" 2>/dev/null
pkill -f "python3.*automation.py" 2>/dev/null

echo -e "${GREEN}Tüm servisler durduruldu.${NC}"
