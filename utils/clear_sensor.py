#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clear all fingerprints from sensor
"""

import serial
import time

PORT = "/dev/serial0"
BAUD = 19200

def calc_checksum(*bytes_list):
    result = 0
    for b in bytes_list:
        result ^= b
    return result

def send_clear_all():
    print("Connecting to sensor...")
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(0.5)
    ser.reset_input_buffer()
    
    print("Sending CLEAR ALL command (0x05)...")
    packet = bytearray(8)
    packet[0] = 0xF5
    packet[1] = 0x05  # Delete all
    packet[2] = 0x00
    packet[3] = 0x00
    packet[4] = 0x00
    packet[5] = 0x00
    packet[6] = calc_checksum(0x05, 0x00, 0x00, 0x00, 0x00)
    packet[7] = 0xF5
    
    print(f"[TX] {' '.join(f'{b:02X}' for b in packet)}")
    ser.write(packet)
    time.sleep(0.5)
    
    if ser.in_waiting > 0:
        resp = ser.read(8)
        print(f"[RX] {' '.join(f'{b:02X}' for b in resp)}")
        
        if len(resp) >= 5:
            ack = resp[4]
            if ack == 0x00:
                print("✓ All fingerprints cleared successfully!")
            else:
                print(f"✗ Failed with ACK=0x{ack:02X}")
    else:
        print("✗ No response from sensor")
    
    ser.close()

if __name__ == "__main__":
    try:
        send_clear_all()
    except Exception as e:
        print(f"Error: {e}")
