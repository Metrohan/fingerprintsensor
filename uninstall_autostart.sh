#!/bin/bash
# Otomatik başlatma servisini kaldırma scripti

echo "================================================"
echo "Fingerprint Attendance System - Remove Autostart"
echo "================================================"

SERVICE_FILE="/etc/systemd/system/fingerprint-attendance.service"

# Servisi durdur
echo "Stopping service..."
sudo systemctl stop fingerprint-attendance.service

# Servisi devre dışı bırak
echo "Disabling service..."
sudo systemctl disable fingerprint-attendance.service

# Service dosyasını sil
echo "Removing service file..."
sudo rm -f $SERVICE_FILE

# Systemd'yi yeniden yükle
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ""
echo "================================================"
echo "Autostart has been removed successfully!"
echo "================================================"
