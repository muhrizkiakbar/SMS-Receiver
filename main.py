import Adafruit_GPIO.Platform as Platform

Platform.platform_detect = lambda: Platform.RASPBERRY_PI
import requests
import serial
import time
import re
import os
from datetime import datetime
import urllib3
import Adafruit_SSD1306
import textwrap
from PIL import Image, ImageDraw, ImageFont

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Muat font custom (sesuaikan path font jika berbeda)
font_path = "/home/pi/SMS/fonts/Tahoma.ttf"
font = ImageFont.truetype(font_path, 11)  # Ukuran font 16px

# Konfigurasi
LOGIN_URL = "https://www.telemetry-adaro.id/api/login"
TELEMETRY_URL = "https://www.telemetry-adaro.id/api/telemetry"
USERNAME = "sms_adaro"
PASSWORD = "sms_adaro"
PORT = "/dev/ttyUSB0"  # Sesuaikan dengan port modem Anda
BAUDRATE = 115200
SMS_LIMIT = 27
SMS_STORAGE_PATH = "./sms_storage"

# Konfigurasi OLED
OLED_WIDTH = 128
OLED_HEIGHT = 64
oled = Adafruit_SSD1306.SSD1306_128_64(rst=None)

# Inisialisasi OLED
oled.begin()
oled.clear()
oled.display()

if not os.path.exists(SMS_STORAGE_PATH):
    os.makedirs(SMS_STORAGE_PATH)


def display_message(line1, line2=""):
    oled.clear()
    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)

    # Hitung jumlah karakter per baris berdasarkan lebar layar
    char_width = font.getlength("A")  # Estimasi lebar karakter
    char_height = font.getbbox("A")[3]  # Estimasi tinggi karakter
    max_chars_per_line = OLED_WIDTH // char_width  # Maksimum karakter per baris

    # Bungkus teks menjadi beberapa baris
    wrapped_text = textwrap.wrap(line1, width=max_chars_per_line)

    # Hitung total tinggi teks yang akan ditampilkan
    total_text_height = len(wrapped_text) * char_height

    # Mulai menggambar teks dari posisi tengah vertikal
    y_offset = (OLED_HEIGHT - total_text_height) // 2

    for line in wrapped_text:
        # Hitung lebar teks untuk baris ini
        text_width = font.getlength(line)
        # Hitung posisi X agar teks ada di tengah
        x_offset = (OLED_WIDTH - text_width) // 2

        draw.text((x_offset, y_offset), line, font=font, fill=255)
        y_offset += char_height  # Pindah ke baris berikutnya

    oled.image(image)
    oled.display()


# Fungsi cek koneksi internet
def check_internet_connection():
    try:
        headers = {
            "Accept": "application/json"  # Added Accept header
        }
        requests.get("https://www.telemetry-adaro.id", headers=headers, timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


# Fungsi untuk mendapatkan access_token
def get_access_token():
    if not check_internet_connection():
        display_message("Internet terputus. Menunggu koneksi...")
        print("Internet terputus. Menunggu koneksi...")
        return None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",  # Added Accept header
    }
    payload = {"username": USERNAME, "password": PASSWORD}
    response = requests.post(LOGIN_URL, json=payload, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json().get("access_token")
    print("Login failed:", response.text)
    return None


# Fungsi untuk membaca SMS dari modem
def read_sms():
    ser = serial.Serial(PORT, BAUDRATE, timeout=3)
    time.sleep(1)
    ser.write(b"AT+CMGF=1\r")
    time.sleep(1)
    ser.write(b'AT+CMGL="REC UNREAD"\r')
    time.sleep(2)
    response = ser.read(ser.inWaiting()).decode(errors="ignore")
    ser.close()
    return response


# Fungsi untuk parsing SMS
def parse_sms(sms_text):
    sms_pattern = r'\+CMGL: \d+,"REC UNREAD","(?P<phone>[\+\d]+)".*?\n(?P<message>.+?)(?=\n\+CMGL|\Z)'
    matches = re.finditer(sms_pattern, sms_text, re.DOTALL)
    sms_list = []
    for match in matches:
        phone_number = match.group("phone")
        message = match.group("message").strip()
        if "AIN" in message:
            sms_list.append({"phone_number": phone_number, "message": message})
    return sms_list


# Fungsi untuk menyimpan SMS ke file
def save_sms_to_file(phone_number, message):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SMS_STORAGE_PATH}/{timestamp}_{phone_number}.txt"
    with open(filename, "w") as file:
        file.write(message)
    return filename


# Fungsi untuk ekstraksi data sensor
def extract_sensor_data(message, mode):
    data = {
        "ph": 0.0,
        "tds": 0,
        "tss": 0,
        "velocity": 0,
        "rainfall": 0,
        "water_height": 0,
        "temperature": 0,
        "humidity": 0,
        "wind_direction": 0,
        "wind_speed": 0,
        "solar_radiation": 0,
        "evaporation": 0,
    }
    ain_values = re.findall(r"AIN(\d+):([\d.]+)", message)

    if mode == "climatology":
        for sensor, value in ain_values:
            sensor = int(sensor)
            value = float(value)
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
            sensor = int(sensor)
            value = float(value)
            if sensor == 0:
                data["dissolve_oxygen"] = value
            elif sensor == 1:
                data["ph"] = value
            elif sensor == 2:
                data["tss"] = value
    elif mode == "spas":
        for sensor, value in ain_values:
            sensor = int(sensor)
            value = float(value)
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
        sensor = int(sensor)
        value = float(value)
        if sensor == 0:
            data["rainfall"] = value

    return data


# Fungsi untuk mengirim data ke API
def send_telemetry(access_token, phone_number, sensor_data, filename, sent_at):
    if not check_internet_connection():
        print("Internet terputus. Menyimpan data untuk dikirim nanti...")
        display_message("Internet terputus. Menyimpan data untuk dikirim nanti...")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"phone_number": phone_number, "created_at": sent_at, **sensor_data}

    print("===================================================================")
    print(f"Mengirim data dari {filename}:")
    print(payload)
    # display_message(f"Mengirim data dari {filename}")

    print(f"memulai kirim")
    response = requests.post(TELEMETRY_URL, json=payload, headers=headers, verify=False)
    if response.status_code == 200:
        print(
            f"Data berhasil dikirim untuk {phone_number}. Menghapus file {filename}..."
        )
        display_message(f"Data berhasil dikirim untuk {phone_number}.")
        os.remove(filename)
    else:
        print("===================================================================")
        print(f"Error mengirim data: {response.text}")


# Fungsi untuk menghapus semua SMS jika mencapai limit
def delete_all_sms():
    ser = serial.Serial(PORT, BAUDRATE, timeout=3)
    time.sleep(1)
    ser.write(b"AT+CMGD=1,4\r")
    time.sleep(2)
    ser.close()
    print("Semua SMS dihapus dari modem.")
    display_message("Semua SMS dihapus dari modem.")


def process_stored_sms(token):
    if not check_internet_connection():
        print("Internet terputus. Data tidak dikirim.")
        display_message("Internet terputus. Data tidak dikirim.")
        return

    for filename in sorted(os.listdir(SMS_STORAGE_PATH)):
        filepath = os.path.join(SMS_STORAGE_PATH, filename)
        # Ambil bagian timestamp dari filename
        timestamp_str = filename[:15]  # Ambil 20250302_113642

        # Konversi ke datetime object
        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

        # Format ke bentuk yang diinginkan
        formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(filepath, "r") as file:
                message = file.read().strip()

            # Split berdasarkan '+', lalu ambil bagian nomor telepon
            parts = filename.split("+")
            if len(parts) > 1:
                phone_number = (
                    f"+{parts[1].split('.')[0]}"  # Ambil hanya nomor sebelum ".txt"
                )
                if phone_number == "+628115013798":
                    # if phone_number == "+6281257634242":
                    print(message)
                    sensor_data = extract_sensor_data(message, "climatology")
                elif phone_number == "+628115113495":
                    # if phone_number == "+6281257634242":
                    print(message)
                    sensor_data = extract_sensor_data(message, "floating_hd")
                else:
                    print(message)
                    sensor_data = extract_sensor_data(message, "spas")

                send_telemetry(
                    token, phone_number, sensor_data, filepath, formatted_timestamp
                )
            else:
                print(f"Filename tidak sesuai format: {filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")


# Loop utama
while True:
    token = get_access_token()

    if token:
        # **1. Cek dan kirim semua data yang tersimpan lebih dahulu**
        process_stored_sms(token)

        # **2. Setelah file kosong, baru membaca SMS baru**
        print("Membaca SMS baru dari modem...")
        display_message("Membaca SMS baru dari modem...")
        sms_data = read_sms()
        parsed_sms = parse_sms(sms_data)

        for sms in parsed_sms:
            if sms["phone_number"] == "+628115013798":
                print(sms["message"])
                sensor_data = extract_sensor_data(sms["message"], "climatology")
            elif sms["phone_number"] == "+628115113495":
                print(sms["message"])
                sensor_data = extract_sensor_data(sms["message"], "floating_hd")
            else:
                print(sms["message"])
                sensor_data = extract_sensor_data(sms["message"], "spas")

            filename = save_sms_to_file(sms["phone_number"], sms["message"])
            send_telemetry(
                token,
                sms["phone_number"],
                sensor_data,
                filename,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

        # **3. Cek jumlah SMS di modem**
        ser = serial.Serial(PORT, BAUDRATE, timeout=3)
        time.sleep(1)
        ser.write(b'AT+CMGL="ALL"\r')
        time.sleep(2)
        sms_response = ser.read(ser.inWaiting()).decode(errors="ignore")
        sms_count = sms_response.count("+CMGL:")
        ser.close()

        print(f"Banyak sms: {sms_count}")
        if sms_count >= SMS_LIMIT:
            delete_all_sms()

    print("Menunggu SMS baru...")
    display_message("Menunggu SMS baru...")
    time.sleep(7)
