# parse_sms.py

from datetime import datetime, timedelta
import re
import logging


def parse_sms(sms_text):
    """Parse SMS messages including timestamp"""
    sms_list = []
    try:
        sms_pattern = (
            r'\+CMGL: \d+,"REC (?:READ|UNREAD)","(?P<phone>[\+\d]+)",,"(?P<timestamp>[^"]+)"\n'
            r"(?P<message>.*?)(?=\n\+CMGL|\Z)"
        )

        matches = re.finditer(sms_pattern, sms_text, re.DOTALL)

        for match in matches:
            phone_number = match.group("phone")
            timestamp = match.group("timestamp")
            message = match.group("message").strip()

            # Konversi timestamp
            timestamp = convert_timestamp(timestamp)

            logging.info(f"Parsed SMS - Phone: {phone_number}")
            logging.info(f"Timestamp: {timestamp}")
            logging.info(f"Message: {message}")

            if "AIN" in message or "DIN" in message:
                sms_list.append(
                    {
                        "phone_number": phone_number,
                        "timestamp": timestamp,
                        "message": message,
                    }
                )

    except Exception as e:
        logging.error(f"SMS Parsing Error: {e}")

    return sms_list


def convert_timestamp(raw_timestamp):
    """
    Convert '25/04/29,08:00:42+28' → '2025-04-29 08:00:42'
    """
    try:
        # Hilangkan bagian timezone +28
        no_timezone = raw_timestamp.split("+")[0]

        # Parse string ke datetime
        dt = datetime.strptime(no_timezone, "%y/%m/%d,%H:%M:%S")

        # Tambah 1 jam
        dt += timedelta(hours=1)

        # Format jadi string yang diinginkan
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.error(f"Timestamp conversion error: {e}")
        return raw_timestamp  # fallback kalau error
