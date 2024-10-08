print("Starting script")
import os
print("Imported os")
import time
print("Imported time")
import random
print("Imported random")
import json
print("Imported json")
import hashlib
print("Imported hashlib")
from datetime import datetime
print("Imported datetime")
from urllib.parse import urlparse
print("Imported urlparse")
from concurrent.futures import ThreadPoolExecutor, as_completed
print("Imported ThreadPoolExecutor")
from selenium.webdriver.support.ui import WebDriverWait
print("Imported WebDriverWait")
from selenium.webdriver.support import expected_conditions as EC
print("Imported expected_conditions")
from selenium.common.exceptions import TimeoutException, WebDriverException
print("Imported selenium exceptions")
from selenium.webdriver.chrome.options import Options
print("Imported Options")
from selenium.webdriver.common.by import By
print("Imported By")
from selenium.webdriver.chrome.service import Service
print("Imported Service")
from selenium import webdriver
print("Imported webdriver")
from webdriver_manager.chrome import ChromeDriverManager
print("Imported ChromeDriverManager")
import gspread
print("Imported gspread")
from google.oauth2 import service_account
print("Imported service_account")
from googleapiclient.discovery import build
print("Imported googleapiclient.discovery")
from googleapiclient.http import MediaFileUpload
print("Imported MediaFileUpload")
from googleapiclient.errors import HttpError
print("Imported HttpError")
import socket
print("Imported socket")
from time import sleep
print("Imported sleep")

# Import webdriver and webdriver-manager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# Google API Setup
user_to_impersonate = 'a.zhubekov@prpillar.com'

scopes = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]
service_account_info = os.getenv('GOOGLE_SERVICE_ACCOUNT')
if service_account_info:
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_info),
        scopes=scopes,
        subject=user_to_impersonate
    )
else:
    credentials = service_account.Credentials.from_service_account_file(
        '../credentials.json',
        scopes=scopes,
        subject=user_to_impersonate
    )

gc = gspread.authorize(credentials)
drive_service = build('drive', 'v3', credentials=credentials)

# Google Sheet and Drive Setup
spreadsheet_id = '1OHzJc9hvr6tgi2ehogkfP9sZHYkI3dW1nB62JCpM9D0'
sheet_name = 'Database'
sheet = gc.open_by_key(spreadsheet_id).worksheet(sheet_name)
records = sheet.get_all_records()  # Assumes first row is header

def sanitize_filename(url):
    # Ensure the URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('.', '_')
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return f"{domain}_{url_hash}"

def process_record(record):
    url = record['Link']
    folder_id = record['Link to folder']

    # Ensure the URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    successful_connection = False

    # Check if folder_id is valid
    if not folder_id:
        print(f"No folder ID provided for {url}, skipping upload.")
        return

    # Selenium Setup
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode.
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        # Attempt to access the URL with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(url)
                # Dynamic wait: Wait until the page is fully loaded
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                successful_connection = True
                break
            except (TimeoutException, WebDriverException) as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(random.uniform(5, 10))
        if not successful_connection:
            return

        # Proceed with screenshot
        try:
            current_date = datetime.now().strftime('%Y-%m-%d')
            page_width = driver.execute_script('return document.body.scrollWidth')
            page_height = driver.execute_script('return document.body.scrollHeight')

            # Validate dimensions
            if not page_width or not page_height:
                page_width = 800
                page_height = 600

            safe_url = sanitize_filename(url)
            client_name = sanitize_filename(record['Client'])
            screenshot_path = f"{current_date}-{client_name}-{safe_url}.png"

            driver.set_window_size(page_width, page_height)
            # Additional wait to ensure elements are loaded
            time.sleep(random.uniform(1, 2))
            driver.save_screenshot(screenshot_path)
        except Exception as e:
            print(f"Error while processing {url}: {e}")
            return

        # Try to upload to Google Drive
        max_upload_retries = 3
        for attempt in range(max_upload_retries):
            try:
                file_metadata = {'name': os.path.basename(screenshot_path), 'parents': [folder_id]}
                media = MediaFileUpload(screenshot_path, mimetype='image/png', resumable=True)

                # Check storage quota before uploading
                about = drive_service.about().get(fields="storageQuota").execute()
                storage_quota = about.get('storageQuota', {})
                used = int(storage_quota.get('usage', 0))
                total = int(storage_quota.get('limit', 0))
                if total > 0 and used >= total:
                    print("Drive storage quota exceeded, stopping uploads.")
                    return

                request = drive_service.files().create(body=file_metadata, media_body=media, fields='id')
                response = None
                while response is None:
                    status, response = request.next_chunk()
                print(f"Uploaded {screenshot_path} to Google Drive.")
                break  # Break if upload is successful
            except (HttpError, socket.timeout, socket.error) as e:
                print(f"Failed to upload {screenshot_path} to Google Drive: {e}")
                if attempt < max_upload_retries - 1:
                    sleep_time = 2 ** attempt  # Exponential backoff
                    print(f"Retrying upload in {sleep_time} seconds...")
                    sleep(sleep_time)
                else:
                    print(f"Exceeded maximum retries for {screenshot_path}.")
                    return
            except KeyError as e:
                print(f"Key error during upload: {e}")
                return

        # Delete local screenshot
        try:
            os.remove(screenshot_path)
            print(f"Deleted local screenshot {screenshot_path}.")
        except Exception as e:
            print(f"Failed to delete local screenshot {screenshot_path}: {e}")
    finally:
        driver.quit()

# Main execution using ThreadPoolExecutor for parallel processing
def main():
    max_workers = min(5, len(records))  # Limit the number of workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_record = {executor.submit(process_record, record): record for record in records}

        for future in as_completed(future_to_record):
            record = future_to_record[future]
            try:
                future.result()
            except Exception as e:
                print(f"Exception occurred while processing record {record['Link']}: {e}")

if __name__ == "__main__":
    main()
