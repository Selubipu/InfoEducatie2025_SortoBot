import os
import cv2
import time
import numpy as np
from collections import Counter
from datetime import datetime
import threading
import requests
import tkinter as tk
from tkinter import ttk
from ultralytics import YOLO

RECEIVED_FOLDER = "received"
PROCESSED_FOLDER = "processed"
esp32_ip = "192.168.137.10"  # IP implicit

def get_esp32_url():
    return f"http://{esp32_ip}/led"

if not os.path.exists(PROCESSED_FOLDER):
    os.makedirs(PROCESSED_FOLDER)

def hue_to_color(hue):
    if 0 <= hue <= 10 or 160 <= hue <= 180:
        return 'Red'
    elif 20 <= hue <= 35:
        return 'Yellow'
    elif 36 <= hue <= 85:
        return 'Green'
    elif 90 <= hue <= 130:
        return 'Blue'
    return 'Unknown'

def detect_dominant_color(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hsv = cv2.GaussianBlur(hsv, (11, 11), 0)
    h, w = hsv.shape[:2]
    cx, cy = w // 2, h // 2
    r = h // 4

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    masked = cv2.bitwise_and(hsv, hsv, mask=mask)
    mask_sat = (masked[:, :, 1] > 50) & (masked[:, :, 2] > 50)
    hue = masked[:, :, 0][mask_sat]
    if hue.size == 0:
        return 'Unknown'
    counts = Counter(hue_to_color(h) for h in hue)
    return counts.most_common(1)[0][0]

def send_led_command(color):
    try:
        requests.get(f"{get_esp32_url()}?color={color.lower()}", timeout=2)
        print(f"📡 LED trimis: {color}")
    except Exception as e:
        print(f"❌ Eroare LED: {e}")

def process_all_images():
    files = sorted(os.listdir(RECEIVED_FOLDER))
    for fname in files:
        path = os.path.join(RECEIVED_FOLDER, fname)
        img = cv2.imread(path)
        if img is None:
            print(f"⚠️ Fișier corupt sau invalid: {fname}")
            os.remove(path)
            continue
        img_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        img_gray = cv2.flip(img_gray, 0)
        img_gray = cv2.resize(img_gray, (224, 224))
        # Convert grayscale (1-channel) to 3-channel grayscale
        img_gray_3ch = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
        res = model(img_gray_3ch)
        confidence = res[0].boxes.conf.numpy()
        print(confidence)
        if (confidence > 0.65).any():
            color = detect_dominant_color(img)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"esp32_{color.lower()}_{timestamp}.jpg"
            new_path = os.path.join(PROCESSED_FOLDER, new_filename)
            cv2.imwrite(new_path, img)
            os.remove(path)
            print(f"Culoare detectată: {color} → fișier salvat: {new_filename}")
            if color in ["Green", "Blue", "Yellow"]:
                send_led_command(color)
            else:
                send_led_command("Yellow")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"esp32_empty_{timestamp}.jpg"
            new_path = os.path.join(PROCESSED_FOLDER, new_filename)
            cv2.imwrite(new_path, img)
            os.remove(path)
            print(f"Nu a fost detectat niciun cos → fișier salvat: {new_filename}")
            send_led_command("Red")

def gui_loop():
    def on_button_click(color):
        send_led_command(color)
        status_label.config(text=f"LED {color} aprins", fg="green")

    root = tk.Tk()
    root.title("LED Manual Control - ESP32")

    frame = tk.Frame(root)
    frame.pack(padx=20, pady=20)

    tk.Label(frame, text="Comandă manuală LED:", font=("Arial", 14)).pack(pady=10)

    colors = [("Red", "#ff4d4d"), ("Green", "#4CAF50"),
              ("Blue", "#2196F3"), ("Yellow", "#FFD700")]
    for name, hex_color in colors:
        b = tk.Button(frame, text=name, bg=hex_color, fg="white" if name != "Yellow" else "black",
                      font=("Arial", 12), width=15,
                      command=lambda n=name: on_button_click(n))
        b.pack(pady=5)

    global status_label
    status_label = tk.Label(frame, text="", font=("Arial", 12))
    status_label.pack(pady=10)

    # IP și buton Schimbă
    ip_frame = tk.Frame(root)
    ip_frame.pack(pady=10)

    ip_label_var = tk.StringVar(value=f"IP SortoBOT - CENTRAL: {esp32_ip}")
    ip_label = tk.Label(ip_frame, textvariable=ip_label_var, font=("Arial", 12))
    ip_label.pack(side=tk.LEFT, padx=10)

    def change_ip_popup():
        popup = tk.Toplevel()
        popup.title("Setează IP ESP32")
        popup.geometry("300x120")
        tk.Label(popup, text="Introduceți IP nou:", font=("Arial", 12)).pack(pady=5)

        ip_entry = tk.Entry(popup, font=("Arial", 12))
        ip_entry.insert(0, esp32_ip)
        ip_entry.pack(pady=5)

        def confirm_ip():
            global esp32_ip
            esp32_ip = ip_entry.get().strip()
            ip_label_var.set(f"IP SortoBOT - CENTRAL: {esp32_ip}")
            popup.destroy()

        tk.Button(popup, text="CONFIRM", command=confirm_ip, font=("Arial", 11)).pack(pady=5)

    tk.Button(ip_frame, text="SCHIMBĂ", command=change_ip_popup, font=("Arial", 10)).pack(side=tk.LEFT)

    root.mainloop()

if __name__ == "__main__":
    print("🧠 Procesator + GUI activ...")
    t = threading.Thread(target=gui_loop, daemon=True)
    t.start()
    model = YOLO('C:\\SortoBot\\yolo_model.pt')
    while True:
        process_all_images()
        time.sleep(1)
