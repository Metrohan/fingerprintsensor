#!/bin/bash
# start_all.sh
# Tüm servisleri aynı anda başlatır: app.py, panel_ui.py, automation.py
# Log'lar data/system.log dosyasına yazılır

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Proje dizini
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Parmak İzi Yoklama Sistemi${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
sudo systemctl restart systemd-timesyncd
timedatectl status

# PID dosyaları
PID_DIR="$PROJECT_DIR/data"
mkdir -p "$PID_DIR"

APP_PID="$PID_DIR/app.pid"
PANEL_PID="$PID_DIR/panel.pid"
AUTO_PID="$PID_DIR/automation.pid"

# Önceki işlemleri durdur
stop_services() {
    echo -e "${YELLOW}Önceki servisler durduruluyor...${NC}"
    
    if [ -f "$APP_PID" ]; then
        kill $(cat "$APP_PID") 2>/dev/null
        rm -f "$APP_PID"
    fi
    
    if [ -f "$PANEL_PID" ]; then
        kill $(cat "$PANEL_PID") 2>/dev/null
        rm -f "$PANEL_PID"
    fi
tim    
    if [ -f "$AUTO_PID" ]; then
        kill $(cat "$AUTO_PID") 2>/dev/null
        rm -f "$AUTO_PID"
    fi
    
    # Python süreçlerini de temizle
    pkill -f "python3.*app.py" 2>/dev/null
    pkill -f "python3.*panel_ui.py" 2>/dev/null
    pkill -f "python3.*automation.py" 2>/dev/null
    
    sleep 1
    echo -e "${GREEN}Eski servisler durduruldu.${NC}"
}

# Servisleri başlat
start_services() {
    echo ""
    echo -e "${GREEN}Servisler başlatılıyor...${NC}"
    echo ""
    
    # 1. Flask Web Sunucusu (app.py)
    echo -e "${BLUE}[1/3]${NC} Flask sunucusu başlatılıyor..."
    python3 "$PROJECT_DIR/app.py" &
    echo $! > "$APP_PID"
    sleep 2
    
    if ps -p $(cat "$APP_PID") > /dev/null 2>&1; then
        echo -e "      ${GREEN}✓ Flask sunucusu çalışıyor (PID: $(cat $APP_PID))${NC}"
    else
        echo -e "      ${RED}✗ Flask sunucusu başlatılamadı!${NC}"
    fi
    
    # 2. LCD Panel UI (panel_ui.py)
    echo -e "${BLUE}[2/3]${NC} LCD Panel başlatılıyor..."
    python3 "$PROJECT_DIR/panel_ui.py" &
    echo $! > "$PANEL_PID"
    sleep 1
    
    if ps -p $(cat "$PANEL_PID") > /dev/null 2>&1; then
        echo -e "      ${GREEN}✓ LCD Panel çalışıyor (PID: $(cat $PANEL_PID))${NC}"
    else
        echo -e "      ${RED}✗ LCD Panel başlatılamadı!${NC}"
    fi
    
    # 3. Google Sheets Otomasyon (automation.py)
    echo -e "${BLUE}[3/3]${NC} Google Sheets otomasyonu başlatılıyor..."
    python3 "$PROJECT_DIR/data/automation.py" &
    echo $! > "$AUTO_PID"
    sleep 1
    
    if ps -p $(cat "$AUTO_PID") > /dev/null 2>&1; then
        echo -e "      ${GREEN}✓ Otomasyon çalışıyor (PID: $(cat $AUTO_PID))${NC}"
    else
        echo -e "      ${RED}✗ Otomasyon başlatılamadı!${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Tüm servisler başlatıldı!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Web arayüzü: ${BLUE}http://localhost:5000${NC}"
    echo -e "Log dosyası: ${BLUE}$PROJECT_DIR/data/system.log${NC}"
    echo ""
    echo -e "${YELLOW}Durdurmak için: ./stop_all.sh veya Ctrl+C${NC}"
}

# Durum kontrolü
status_services() {
    echo -e "${BLUE}Servis Durumları:${NC}"
    echo ""
    
    if [ -f "$APP_PID" ] && ps -p $(cat "$APP_PID") > /dev/null 2>&1; then
        echo -e "  Flask (app.py):       ${GREEN}Çalışıyor${NC} (PID: $(cat $APP_PID))"
    else
        echo -e "  Flask (app.py):       ${RED}Durdu${NC}"
    fi
    
    if [ -f "$PANEL_PID" ] && ps -p $(cat "$PANEL_PID") > /dev/null 2>&1; then
        echo -e "  Panel (panel_ui.py):  ${GREEN}Çalışıyor${NC} (PID: $(cat $PANEL_PID))"
    else
        echo -e "  Panel (panel_ui.py):  ${RED}Durdu${NC}"
    fi
    
    if [ -f "$AUTO_PID" ] && ps -p $(cat "$AUTO_PID") > /dev/null 2>&1; then
        echo -e "  Otomasyon:            ${GREEN}Çalışıyor${NC} (PID: $(cat $AUTO_PID))"
    else
        echo -e "  Otomasyon:            ${RED}Durdu${NC}"
    fi
}

# Ctrl+C yakalamak için trap
cleanup() {
    echo ""
    echo -e "${YELLOW}Kapatılıyor...${NC}"
    stop_services
    exit 0
}

trap cleanup SIGINT SIGTERM

# Ana mantık
case "${1:-start}" in
    start)
        stop_services
        start_services
        # Logları takip et
        echo -e "${BLUE}Log çıktısı (Ctrl+C ile çık):${NC}"
        echo ""
        tail -f "$PROJECT_DIR/data/system.log" 2>/dev/null || sleep infinity
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        tail -f "$PROJECT_DIR/data/system.log" 2>/dev/null || sleep infinity
        ;;
    status)
        status_services
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
