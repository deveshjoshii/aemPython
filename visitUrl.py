import csv
import json
import urllib.parse
import time
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set up Chrome options for capturing performance logs
options = Options()
options.add_argument("--ignore-certificate-errors")  # Ignore SSL errors
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

# Initialize the WebDriver
driver = Chrome(options=options)


def urlDecode(string):
    """URL decode the query string and return the parameters as a dictionary."""
    decoded_query_string = urllib.parse.unquote(string)
    params = dict(urllib.parse.parse_qsl(decoded_query_string))
    return params


def read_urls_from_csv(csv_file):
    """Read URLs and associated data from a CSV file, skipping the header row."""
    data = []
    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Url']:  # Ensure the URL is not empty
                data.append(row)
    return data


def visitBrowser(row):
    """Visit the URL and capture network logs."""
    url = row['Url']
    driver.get(url)
    driver.implicitly_wait(10)

    # Store all relevant requests in a dictionary
    requests_dict = {}

    # Wait for network calls after page load
    timeout = 10
    end_time = time.time() + timeout

    while time.time() < end_time:
        logs = driver.get_log('performance')
        for log in logs:
            log_json = json.loads(log['message'])['message']
            if log_json['method'] == 'Network.responseReceived':
                response_url = log_json['params']['response']['url']
                # Check for relevant requests
                if 'amexpressprod' in response_url or '/b/ss' in response_url:
                    # Capture the request data
                    request_data = {
                        'url': response_url,
                        'status': log_json['params']['response']['status'],
                        'headers': log_json['params']['response']['headers'],
                        'request_id': log_json['params']['requestId'],
                        'timestamp': log_json['params']['timestamp'],
                        'params': {},  # Nested dict for decrypted URL parameters
                    }

                    # Decrypt and store URL parameters if present
                    if '?' in response_url:
                        url_params = urlDecode(response_url.split('?')[-1])
                        request_data['params'] = url_params  # Store params as a nested dict

                    requests_dict[request_data['request_id']] = request_data  # Store entire request in dict
        time.sleep(1)  # Wait a moment before checking again

    print(json.dumps(requests_dict, indent=2))  # Pretty print the captured requests
    return requests_dict  # Return the dictionary of captured requests


def perform_action(action):
    """Perform the specified action on the page."""
    if action:
        action_parts = action.split('|')
        if len(action_parts) == 2:
            action_type, locator = action_parts
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, locator.strip()))
            )
            if action_type.strip().lower() == 'click':
                element.click()
            # Add more actions as needed


# Read data from CSV
csv_file_path = 'url.csv'  # Replace with your CSV file path (if different)
rows = read_urls_from_csv(csv_file_path)

# Process each row
for row in rows:
    requests_dict = visitBrowser(row)  # Initial visit to capture requests
    if row['Action']:  # Ensure the header in the CSV matches this key
        perform_action(row['Action'])  # Perform the action

# Final assertion to check the captured requests
for row in rows:
    fieldname = row['Fieldname'].strip()
    expected_value = row['Value'].strip()

    # Check if any request contains params that match the field name and expected value
    found = False
    for request in requests_dict.values():
        if fieldname in request['params'] and request['params'][fieldname] == expected_value:
            found = True
            break

    # Update status based on assertion
    row['Status'] = 'Pass' if found else 'Fail'  # Mark as Pass or Fail

# Close the browser after all operations
driver.quit()

# Write results back to CSV
with open('url.csv', mode='w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())  # Use the headers from the first row
    writer.writeheader()
    writer.writerows(rows)
