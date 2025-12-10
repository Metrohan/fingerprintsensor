#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waveshare UART Fingerprint Sensor Test
Simple test script to verify sensor communication
"""

import serial
import time
import sys

PORT = "/dev/serial0"
BAUD = 19200

def calc_checksum(*bytes_list):
    """Calculate XOR checksum."""
    result = 0
    for b in bytes_list:
        result ^= b
    return result

def send_command(ser, cmd, p1=0x00, p2=0x00, p3=0x00, p4=0x00):
    """Send 8-byte command packet."""
    packet = bytearray(8)
    packet[0] = 0xF5  # Header
    packet[1] = cmd
    packet[2] = p1
    packet[3] = p2
    packet[4] = p3
    packet[5] = p4
    packet[6] = calc_checksum(cmd, p1, p2, p3, p4)
    packet[7] = 0xF5  # Tail
    
    print(f"[TX] {' '.join(f'{b:02X}' for b in packet)}")
    ser.write(packet)
    time.sleep(0.2)

def read_response(ser, timeout=3.0):
    """Read 8-byte response packet."""
    start = time.time()
    buffer = bytearray()
    
    while (time.time() - start) < timeout:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer.extend(data)
            
            # Look for valid packet
            while len(buffer) >= 8:
                if buffer[0] == 0xF5 and buffer[7] == 0xF5:
                    packet = bytes(buffer[:8])
                    print(f"[RX] {' '.join(f'{b:02X}' for b in packet)}")
                    return packet
                else:
                    buffer.pop(0)
        
        time.sleep(0.02)
    
    print("[RX] No response (timeout)")
    return None

def main():
    print("=" * 60)
    print("Waveshare UART Fingerprint Sensor Test")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Baud: {BAUD}")
    print()
    
    try:
        # Open serial port
        print("[1] Opening serial port...")
        ser = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(0.5)
        ser.reset_input_buffer()
        print("    ✓ Port opened successfully")
        print()
        
        # Test 1: Get user count
        print("[2] Testing: Get User Count (CMD=0x09)")
        send_command(ser, 0x09)
        resp = read_response(ser)
        
        if resp and len(resp) >= 4:
            count = (resp[2] << 8) | resp[3]
            ack = resp[4]
            print(f"    ✓ ACK: 0x{ack:02X}")
            print(f"    ✓ Enrolled users: {count}")
        else:
            print("    ✗ Failed to get response")
        
        print()
        
        # Test 2: Delete all users (optional, commented out)
        # print("[3] Testing: Delete All Users (CMD=0x05)")
        # send_command(ser, 0x05)
        # resp = read_response(ser)
        # if resp:
        #     print(f"    ✓ Response received")
        # print()
        
        # Test 3: Add fingerprint
        print("[3] Testing: Add Fingerprint (ID=1)")
        print("    Place your finger on the sensor when prompted...")
        print()
        
        # Step 1
        print("    STEP 1: Place finger FIRMLY on sensor now...")
        send_command(ser, 0x01, 0x00, 0x01, 0x01)  # ID=1, permission=1
        resp1 = read_response(ser, timeout=25)
        
        if resp1 and len(resp1) >= 5:
            ack1 = resp1[4]
            if ack1 == 0x00:
                print(f"    ✓ STEP 1 OK (ACK=0x{ack1:02X})")
            else:
                print(f"    ✗ STEP 1 FAILED (ACK=0x{ack1:02X})")
                ser.close()
                return
        else:
            print("    ✗ STEP 1 no response")
            ser.close()
            return
        
        time.sleep(2)
        
        # Step 2
        print("    STEP 2: Remove and place finger FIRMLY again...")
        send_command(ser, 0x02, 0x00, 0x01, 0x01)
        resp2 = read_response(ser, timeout=25)
        
        if resp2 and len(resp2) >= 5:
            ack2 = resp2[4]
            if ack2 == 0x00:
                print(f"    ✓ STEP 2 OK (ACK=0x{ack2:02X})")
            else:
                print(f"    ✗ STEP 2 FAILED (ACK=0x{ack2:02X})")
                ser.close()
                return
        else:
            print("    ✗ STEP 2 no response")
            ser.close()
            return
        
        time.sleep(2)
        
        # Step 3
        print("    STEP 3: Remove and place finger FIRMLY again...")
        send_command(ser, 0x03, 0x00, 0x01, 0x01)
        resp3 = read_response(ser, timeout=25)
        
        if resp3 and len(resp3) >= 5:
            ack3 = resp3[4]
            if ack3 == 0x00:
                print(f"    ✓ STEP 3 OK (ACK=0x{ack3:02X})")
                print()
                print("    🎉 Fingerprint enrolled successfully!")
            else:
                print(f"    ✗ STEP 3 FAILED (ACK=0x{ack3:02X})")
        else:
            print("    ✗ STEP 3 no response")
        
        print()
        
        # Test 4: Match fingerprint with comparison level
        print("[4] Testing: Match Fingerprint (CMD=0x0C, comparison_level=6)")
        print("    Place finger FIRMLY on sensor...")
        send_command(ser, 0x0C, 0x00, 0x06)  # comparison level 6
        resp = read_response(ser, timeout=15)
        
        if resp and len(resp) >= 5:
            ack = resp[4]
            if ack == 0x00:
                user_id = (resp[2] << 8) | resp[3]
                print(f"    ✓ Match found! User ID: {user_id}")
            else:
                print(f"    ✗ No match (ACK=0x{ack:02X})")
        else:
            print("    ✗ No response")
        
        print()
        print("=" * 60)
        print("Test completed!")
        print("=" * 60)
        
        ser.close()
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
