#!/usr/bin/env python3

import Adafruit_GPIO.Platform as Platform

Platform.platform_detect = lambda: Platform.RASPBERRY_PI

import requests
import serial
import time
import re
import os
import logging
from datetime import datetime
import urllib3
import Adafruit_SSD1306
import textwrap
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("/home/pi/SMS/sms_gateway.log"),
        logging.StreamHandler(),
    ],
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration Constants
LOGIN_URL = "https://www.telemetry-adaro.id/api/login"
TELEMETRY_URL = "https://www.telemetry-adaro.id/api/telemetry"
USERNAME = "sms_adaro"
PASSWORD = "sms_adaro"
PORT = "/dev/ttyUSB0"  # Adjust according to your modem's port
BAUDRATE = 115200
SMS_LIMIT = 20
SMS_STORAGE_PATH = "/home/pi/SMS/sms_storage"

# OLED Configuration
OLED_WIDTH = 128
OLED_HEIGHT = 64
oled = Adafruit_SSD1306.SSD1306_128_64(rst=None)

# Font Configuration
font_path = "/home/pi/SMS/fonts/Tahoma.ttf"
font = ImageFont.truetype(font_path, 11)


def initialize_directories():
    """Ensure necessary directories exist"""
    os.makedirs(SMS_STORAGE_PATH, exist_ok=True)
    logging.info(f"Initialized directory: {SMS_STORAGE_PATH}")


def display_message(line1, line2=""):
    """Display messages on OLED screen"""
    try:
        oled.begin()
        oled.clear()
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)

        char_width = font.getlength("A")
        char_height = font.getbbox("A")[3]
        max_chars_per_line = OLED_WIDTH // char_width

        wrapped_text = textwrap.wrap(line1, width=max_chars_per_line)
        total_text_height = len(wrapped_text) * char_height
        y_offset = (OLED_HEIGHT - total_text_height) // 2

        for line in wrapped_text:
            text_width = font.getlength(line)
            x_offset = (OLED_WIDTH - text_width) // 2
            draw.text((x_offset, y_offset), line, font=font, fill=255)
            y_offset += char_height

        oled.image(image)
        oled.display()
    except Exception as e:
        logging.error(f"OLED Display Error: {e}")


def check_internet_connection(timeout=5):
    """Check internet connectivity"""
    try:
        headers = {"Accept": "application/json"}
        requests.get("https://www.telemetry-adaro.id", headers=headers, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout) as e:
        logging.warning(f"Internet Connection Error: {e}")
        return False


def get_access_token():
    """Obtain access token from login API"""
    if not check_internet_connection():
        display_message("Internet terputus. Menunggu koneksi...")
        logging.warning("Internet connection lost")
        return None

    try:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {"username": USERNAME, "password": PASSWORD}
        response = requests.post(LOGIN_URL, json=payload, headers=headers, verify=False)

        if response.status_code == 200:
            token = response.json().get("access_token")
            logging.info("Successfully obtained access token")
            return token

        logging.error(f"Login failed: {response.text}")
        return None

    except Exception as e:
        logging.error(f"Token retrieval error: {e}")
        return None


def initialize_modem(ser):
    """Initialize modem with AT commands"""
    try:
        ser.write(b"AT\r")
        time.sleep(1)
        ser.write(b"AT+CMEE=2\r")  # Verbose error reporting
        time.sleep(1)
        ser.write(b"AT+CMGF=1\r")  # Text mode
        time.sleep(1)
        ser.write(b'AT+CPMS="SM"\r')  # Select SIM memory
        time.sleep(1)
        logging.info("Modem initialized successfully")
    except Exception as e:
        logging.error(f"Modem Initialization Error: {e}")


def read_sms():
    """Read SMS messages from modem with robust error handling"""
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=5)

        # Initialize modem
        ser.write(b"AT\r")
        time.sleep(1)
        ser.write(b"AT+CMGF=1\r")  # Set to text mode
        time.sleep(1)

        # Try different SMS reading commands
        commands = [
            b'AT+CMGL="REC UNREAD"\r',  # Read unread messages
            b'AT+CMGL="ALL"\r',  # Read all messages
            b"AT+CMGL\r",  # Alternative command
        ]

        for cmd in commands:
            ser.write(cmd)
            time.sleep(3)
            response = ser.read(ser.inWaiting()).decode(errors="ignore")

            logging.info(f"SMS Reading Command: {cmd}")
            logging.info(f"Response: {response}")

            # Check if response contains SMS messages
            if "+CMGL:" in response:
                ser.close()
                return response

        ser.close()
        logging.warning("No SMS messages found")
        return ""

    except serial.SerialException as e:
        logging.error(f"Serial Communication Error: {e}")
        return ""
    except Exception as e:
        logging.error(f"Unexpected SMS reading error: {e}")
        return ""


def parse_sms(sms_text):
    """Parse SMS messages with enhanced error handling"""
    sms_list = []
    try:
        sms_pattern = r'\+CMGL: \d+,"REC UNREAD","(?P<phone>[\+\d]+)".*?\n(?P<message>.+?)(?=\n\+CMGL|\Z)'
        # sms_pattern = r'\+CMGL: \d+,"REC UNREAD","(?P<phone>\+?\d+)",,"(?P<timestamp>[^"]+)"\n(?P<message>.*?)(?=\n\+CMGL|\Z)'

        matches = re.finditer(sms_pattern, sms_text, re.DOTALL)

        for match in matches:
            phone_number = match.group("phone")
            message = match.group("message").strip()

            logging.info(f"Parsed SMS - Phone: {phone_number}")
            logging.info(f"Message: {message}")

            if "AIN" in message or "DIN" in message:
                sms_list.append({"phone_number": phone_number, "message": message})

    except Exception as e:
        logging.error(f"SMS Parsing Error: {e}")

    return sms_list


def save_sms_to_file(phone_number, message):
    """Save SMS to file with timestamp"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{SMS_STORAGE_PATH}/{timestamp}_{phone_number}.txt"
        with open(filename, "w") as file:
            file.write(message)
        logging.info(f"SMS saved to {filename}")
        return filename
    except Exception as e:
        logging.error(f"Error saving SMS to file: {e}")
        return None


def extract_sensor_data(message, mode):
    """Extract sensor data from SMS message"""
    data = {
        "ph": 0.0,
        "tds": 0,
        "tss": 0,
        "debit": 0,
        "rainfall": 0,
        "water_height": 0,
        "temperature": 0,
        "humidity": 0,
        "wind_direction": 0,
        "wind_speed": 0,
        "solar_radiation": 0,
        "evaporation": 0,
        "dissolve_oxygen": 0,
    }

    ain_values = re.findall(r"AIN(\d+):([\d.]+)", message)

    if mode == "climatology":
        for sensor, value in ain_values:
            sensor, value = int(sensor), float(value)
            if sensor == 0:
                data["temperature"] = value
            elif sensor == 1:
                data["humidity"] = value
            elif sensor == 2:
                data["wind_direction"] = value
            elif sensor == 3:
                data["wind_speed"] = value
            elif sensor == 4:
                data["solar_radiation"] = value
            elif sensor == 5:
                data["evaporation"] = value

    elif mode == "floating_hd":
        for sensor, value in ain_values:
            sensor, value = int(sensor), float(value)
            if sensor == 0:
                data["dissolve_oxygen"] = value
            elif sensor == 1:
                data["ph"] = value
            elif sensor == 2:
                data["tss"] = value

    elif mode == "spas":
        for sensor, value in ain_values:
            sensor, value = int(sensor), float(value)
            if sensor == 0:
                data["water_height"] = value
            elif sensor == 1:
                data["ph"] = value
            elif sensor == 2:
                data["tss"] = value
            elif sensor == 3:
                data["tds"] = value

    din_values = re.findall(r"DIN(\d+):([\d.]+)", message)
    for sensor, value in din_values:
        sensor, value = int(sensor), float(value)
        if sensor == 0:
            data["rainfall"] = value

    return data


def send_telemetry(access_token, phone_number, sensor_data, filename, sent_at):
    """Send sensor data to telemetry API"""
    if not check_internet_connection():
        logging.warning("Internet disconnected. Cannot send telemetry.")
        display_message("Internet terputus. Data tidak terkirim.")
        return False

    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"phone_number": phone_number, "created_at": sent_at, **sensor_data}

        logging.info(f"Sending telemetry data: {payload}")
        response = requests.post(
            TELEMETRY_URL, json=payload, headers=headers, verify=False
        )

        if response.status_code == 200:
            logging.info(f"Data sent successfully for {phone_number}")
            display_message(f"Data berhasil dikirim {phone_number}")
            os.remove(filename)
            return True
        else:
            logging.error(f"Telemetry send error: {response.text}")
            return False

    except Exception as e:
        logging.error(f"Telemetry send exception: {e}")
        return False


def process_stored_sms(token):
    """Process stored SMS files"""
    if not check_internet_connection():
        logging.warning("Internet disconnected. Stored SMS not processed.")
        return

    try:
        for filename in sorted(os.listdir(SMS_STORAGE_PATH)):
            filepath = os.path.join(SMS_STORAGE_PATH, filename)

            # Extract timestamp and phone number from filename
            timestamp_str = filename[:15]
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            with open(filepath, "r") as file:
                message = file.read().strip()

            parts = filename.split("+")
            if len(parts) > 1:
                phone_number = f"+{parts[1].split('.')[0]}"

                if phone_number == "+628115013798":
                    sensor_data = extract_sensor_data(message, "climatology")
                elif phone_number == "+628115113495":
                    sensor_data = extract_sensor_data(message, "floating_hd")
                else:
                    sensor_data = extract_sensor_data(message, "spas")

                send_telemetry(
                    token, phone_number, sensor_data, filepath, formatted_timestamp
                )

    except Exception as e:
        logging.error(f"Stored SMS processing error: {e}")


def delete_all_sms():
    """Delete all SMS from modem"""
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=3)
        ser.write(b"AT+CMGD=1,4\r")
        time.sleep(2)
        ser.close()
        logging.info("All SMS deleted from modem")
        display_message("Semua SMS dihapus dari modem")
    except Exception as e:
        logging.error(f"SMS deletion error: {e}")


def main():
    """Main program loop"""
    initialize_directories()

    while True:
        try:
            token = get_access_token()

            if token:
                # Process stored SMS first
                process_stored_sms(token)

                # Read new SMS
                logging.info("Reading new SMS from modem...")
                display_message("Membaca SMS baru dari modem...")

                sms_data = read_sms()
                parsed_sms_list = parse_sms(sms_data)

                for sms in parsed_sms_list:
                    if sms["phone_number"] == "+628115013798":
                        sensor_data = extract_sensor_data(sms["message"], "climatology")
                    elif sms["phone_number"] == "+6282195431503":
                        sensor_data = extract_sensor_data(sms["message"], "floating_hd")
                    else:
                        sensor_data = extract_sensor_data(sms["message"], "spas")

                    filename = save_sms_to_file(sms["phone_number"], sms["message"])

                    if filename:
                        send_telemetry(
                            token,
                            sms["phone_number"],
                            sensor_data,
                            filename,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        )

                # Check SMS count
                ser = serial.Serial(PORT, BAUDRATE, timeout=3)
                ser.write(b'AT+CMGL="ALL"\r')
                time.sleep(8)
                sms_response = ser.read(ser.inWaiting()).decode(errors="ignore")
                sms_count = sms_response.count("+CMGL:")
                ser.close()

                logging.info(f"Total SMS count: {sms_count}")
                if sms_count >= SMS_LIMIT:
                    delete_all_sms()

            logging.info("Waiting for new SMS...")
            display_message("Menunggu SMS baru...")
            time.sleep(10)

        except Exception as e:
            logging.error(f"Main loop error: {e}")
            display_message("Error dalam proses SMS")
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
