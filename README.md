# Raspberry Pi Fingerprint Attendance System

## Overview
This project is a robust attendance system for Raspberry Pi using a Waveshare UART fingerprint sensor. It features a Flask web interface, SQLite database, and real-time user matching. The system is designed for reliability, accuracy, and ease of use in Turkish educational or office environments.

## Features
- **Fingerprint Enrollment & Matching**: Register users and match fingerprints with improved accuracy.
- **Web Dashboard**: View today's attendance, user list, and add new users via a modern UI.
- **Sensor Communication**: Optimized UART protocol handling, buffer management, and error diagnostics.
- **Database**: SQLite for user and attendance records.
- **User Feedback**: Clear error messages, live match results, and instructions in Turkish.
- **Scripts**: Tools to clear sensor, initialize DB, and test sensor communication.

## File Structure
```
app.py                # Main Flask app (sensor logic, API, UI)
clear_sensor.py       # Script to clear all fingerprints from sensor
config.py             # Configuration settings
init_db.py            # SQLite DB initializer (no sample users)
test_sensor.py        # Sensor test script
static/style.css      # CSS for web UI
templates/base.html   # Base HTML template
templates/index.html  # Dashboard (attendance)
templates/user_form.html # User registration form
templates/users.html  # User list
```

## Quick Start
1. **Initialize Database**
   ```bash
   python3 init_db.py
   ```
2. **Clear Sensor**
   ```bash
   python3 clear_sensor.py
   ```
3. **Run Web App**
   ```bash
   python3 app.py
   # Open browser: http://localhost:5000
   ```
4. **Test Sensor**
   ```bash
   python3 test_sensor.py
   ```

## Configuration
- Edit `config.py` for serial port, baud rate, and other settings.
- Default serial port: `/dev/serial0` (Raspberry Pi)

## Usage Tips
- Press finger firmly on sensor during enrollment and matching.
- Use the web UI for user management and attendance tracking.
- All error messages and instructions are in Turkish for local usability.

## Requirements
- Python 3.x
- Flask
- pyserial
- Raspberry Pi (tested on Pi 3)
- Waveshare UART fingerprint sensor

## License
MIT License
