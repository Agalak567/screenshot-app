from google.oauth2.service_account import Credentials
import gspread
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
from datetime import datetime

# Google API Setup
scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
service_account_file = 'credentials.json'

credentials = Credentials.from_service_account_file(service_account_file, scopes=scopes)
gc = gspread.authorize(credentials)
drive_service = build('drive', 'v3', credentials=credentials)

# Google Sheet and Drive Setup
spreadsheet_id = '1OHzJc9hvr6tgi2ehogkfP9sZHYkI3dW1nB62JCpM9D0'
sheet_name = 'Database' 
sheet = gc.open_by_key(spreadsheet_id).worksheet(sheet_name)
records = sheet.get_all_records()  # Assumes first row is header

# Selenium Setup
chrome_options = Options()
chrome_options.add_argument("--headless")

# Add any Chrome options you need here
service = Service(ChromeDriverManager().install())

driver = webdriver.Chrome(service=service, options=chrome_options)
driver.maximize_window()

for record in records:
    url = record['Link']
    folder_id = record['Link to folder']
    
    # Navigate and take a screenshot
    driver.get(url)

    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Get the dimensions of the full page
    page_width = driver.execute_script('return document.body.scrollWidth')
    page_height = driver.execute_script('return document.body.scrollHeight')
    
    # Format the filename to include the current date, client, and platform
    screenshot_path = f"{current_date}-{record['Client']}-{record['Platform']}.png"

    # Resize the window to the page size
    driver.set_window_size(page_width, page_height)
    driver.save_screenshot(screenshot_path)
    
    # Upload to Google Drive
    file_metadata = {'name': screenshot_path, 'parents': [folder_id]}
    media = MediaFileUpload(screenshot_path, mimetype='image/png')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    # Optionally, delete the local file after upload
    os.remove(screenshot_path)

driver.quit()
