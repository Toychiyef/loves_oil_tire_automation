import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
import os
import json

# --- 1. CONFIGURATION ---
# This looks for the Secret we named GCP_JSON_KEY
SERVICE_ACCOUNT_INFO = os.environ.get('GCP_JSON_KEY')
SPREADSHEET_KEY = '1Zt-DqXuEnB3ypsg67btFfVXorY6ljCV-XuhcAqRGIh4'

def update_google_sheets(tire_val, oil_val):
    print("Connecting to Google Sheets...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Check if the secret was actually found
    if not SERVICE_ACCOUNT_INFO:
        print("ERROR: GCP_JSON_KEY secret not found!")
        return

    # Parse the JSON string from the environment variable
    info = json.loads(SERVICE_ACCOUNT_INFO)
    creds = Credentials.from_service_account_info(info, scopes=scope)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).sheet1
    
    # Define Uzbekistan Time (UTC +5)
    uzb_timezone = timezone(timedelta(hours=5))
    # Get current time in Uzbekistan
    now = datetime.now(uzb_timezone)
    # Calculate "yesterday" based on your local time
    yesterday = now - timedelta(days=1)
    # Format the date/time
    formatted_dt = yesterday.strftime("%m/%d/%Y %H:%M")
    
    row_to_add = [formatted_dt, tire_val, oil_val]
    sheet.append_row(row_to_add)
    print(f"Spreadsheet updated successfully: {row_to_add}")

# --- 2. SELENIUM SETUP ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 15)

try:
    # --- 3. LOGIN PHASE ---
    driver.get("https://shopconnect.loves.com/#/work-orders/dashboard")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    print("Logging in...")
    user_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Username']")))
    user_field.send_keys("Truck.me_Fleet")

    pass_field = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
    pass_field.send_keys("Truckme123$")

    driver.find_element(By.XPATH, "//button[contains(., 'Login')]").click()
    wait.until(EC.url_contains("dashboard"))
    print("Login complete.")

    # --- 4. NAVIGATION ---
    print("Navigating to Tire Care Dashboard...")
    tire_care_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Tire Care Dashboard']")))
    driver.execute_script("arguments[0].click();", tire_care_btn)

    print("Waiting for dashboard elements to stabilize...")
    time.sleep(5)

    # --- 5. DATA SCRAPING: TIRES ---
    print("Fetching 'Tires' count...")
    specific_xpath = "//span[contains(text(), 'Selected Month Purchases')]/parent::div//span[contains(@class, 'bigNUM')]"
    
    wait.until(EC.visibility_of_element_located((By.XPATH, specific_xpath)))
    
    for i in range(10):
        raw_tire_text = driver.find_element(By.XPATH, specific_xpath).text.strip()
        if raw_tire_text and any(char.isdigit() for char in raw_tire_text):
            break
        time.sleep(1)
    else:
        raise Exception("Timed out waiting for Tires count to display digits.")

    tire_amount = int(re.sub(r'[^\d]', '', raw_tire_text))
    print(f"Tire Amount Captured: {tire_amount}")

    # --- 6. SWITCH PRODUCT: PREVENTATIVE MAINTENANCE ---
    print("Opening Product Dropdown...")
    product_dropdown = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//kendo-dropdownlist[contains(@class, 'product-picker')]//button[@aria-label='Select']")
    ))
    driver.execute_script("arguments[0].click();", product_dropdown)
    time.sleep(1)

    print("Selecting 'Preventative Maintenance'...")
    try:
        selection = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//li[contains(@class, 'k-list-item')]//span[text()='Preventative Maintenance']")
        ))
        driver.execute_script("arguments[0].click();", selection)
    except:
        selection = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Preventative')]")))
        driver.execute_script("arguments[0].click();", selection)

    # --- 7. APPLY FILTERS & SCRAPE OIL ---
    apply_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button-filter")))
    driver.execute_script("arguments[0].click();", apply_btn)
    print("Filter applied. Waiting for refresh...")
    time.sleep(5)

    print("Fetching 'Preventative Maintenance' count...")
    wait.until(lambda d: d.find_element(By.XPATH, specific_xpath).text.strip() != "")
    raw_oil_text = driver.find_element(By.XPATH, specific_xpath).text.strip()
    oil_amount = int(re.sub(r'[^\d]', '', raw_oil_text))
    print(f"Oil Amount Captured: {oil_amount}")

    # --- 8. FINAL EXPORT TO GOOGLE SHEETS ---
    update_google_sheets(tire_amount, oil_amount)

except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
finally:
    print("\nProcess finished.")
    driver.quit()
