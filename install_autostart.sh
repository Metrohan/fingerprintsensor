#!/bin/bash
# Otomatik başlatma servisi kurulum scripti

echo "================================================"
echo "Fingerprint Attendance System - Autostart Setup"
echo "================================================"

# Proje dizini
PROJECT_DIR="/home/ilab/Desktop/fingerprint"

# Systemd service dosyası oluştur
SERVICE_FILE="/etc/systemd/system/fingerprint-attendance.service"

echo "Creating systemd service file..."

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Fingerprint Attendance System
After=network.target

[Service]
Type=forking
User=ilab
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/start_all.sh
ExecStop=$PROJECT_DIR/stop_all.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created at: $SERVICE_FILE"

# Systemd'yi yeniden yükle
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Servisi etkinleştir (boot'ta otomatik başlat)
echo "Enabling service for autostart..."
sudo systemctl enable fingerprint-attendance.service

# Servis durumunu göster
echo ""
echo "================================================"
echo "Installation complete!"
echo "================================================"
echo ""
echo "Commands:"
echo "  Start service:   sudo systemctl start fingerprint-attendance"
echo "  Stop service:    sudo systemctl stop fingerprint-attendance"
echo "  Check status:    sudo systemctl status fingerprint-attendance"
echo "  View logs:       sudo journalctl -u fingerprint-attendance -f"
echo "  Disable autostart: sudo systemctl disable fingerprint-attendance"
echo ""
echo "The service will automatically start on next boot!"
echo "================================================"
