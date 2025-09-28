#!/bin/bash

# Replace YOUR_ODOO_DOMAIN with your actual Odoo instance URL
ODOO_URL="http://localhost:12069"

# Outgoing call
curl -X POST "$ODOO_URL/asterisk_plus/create_call" \
  -H "Content-Type: application/json" \
  -d '{
    "uniqueid": "test-1234567890-1",
    "calling_number": "+1234567890",
    "called_number": "+987654321",
    "status": "answered",
    "started": "2024-01-15 14:30:00",
    "answered": "2024-01-15 14:35:00",
    "ended": "2024-01-15 14:40:00",
    "direction": "out"
  }'

# Incoming call
curl -X POST "$ODOO_URL/asterisk_plus/create_call" \
  -H "Content-Type: application/json" \
  -d '{
    "uniqueid": "test-1234567890-2",
    "calling_number": "+1234567890",
    "called_number": "+987654321",
    "status": "answered",
    "started": "2024-01-15 14:30:00",
    "answered": "2024-01-15 14:35:00",
    "ended": "2024-01-15 14:40:00",
    "direction": "in"
  }'


curl -X POST \
          -F "uniqueid=test-1234567890-1" \
          -F "recording_file=@/tmp/test.wav" \
          -F "filename=custom_name.wav" \
          $ODOO_URL/asterisk_plus/upload_recording