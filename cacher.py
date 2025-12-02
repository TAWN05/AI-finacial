"""Hydrate the local cache with SEC company facts data for every ticker."""

import json
import os
import time

import requests


z = 0
y = 0
failed = 0
failed_list = []
comp = []
comp_cik = []
# The SEC requires descriptive User-Agent headers for automated traffic, so
# these values uniquely identify this script when making large volumes of
# requests.
headers = {
    "User-Agent": "jacob casey jacobrcasey135@gmail.com",
    "Accept-Encoding": "gzip, deflate"
    }

def to_10_digits(n) -> str:
    """Return ``n`` zero-padded to the 10-digit format expected by the SEC."""

    s = str(n).strip()
    if not s.isdigit():
        raise ValueError(f"Expected only digits, got {n!r}")
    if len(s) > 10:
        raise ValueError(f"Number longer than 10 digits: {n!r}")
    return s.zfill(10)

payload={}
tickers_url = "https://www.sec.gov/files/company_tickers.json"


# Pull down the canonical ticker/CIK mapping once up front so that the
# subsequent loop can run without additional metadata lookups.
response_tickers = requests.request("GET", tickers_url, headers=headers, data=payload)

response_tickers = response_tickers.text
response_tickers = response_tickers.lower()
response_tickers = json.loads(response_tickers)
z = 0

for x in response_tickers:
    try:
        # Each iteration inspects a single ticker entry, normalizes the CIK, and
        # determines whether we already have the facts dataset stored on disk.
        cik = to_10_digits(response_tickers[x]['cik_str'])
        current_ticker = response_tickers[x]['ticker']

        file_path = f"output/{current_ticker}-facts-json/full_{current_ticker}.json"

        if os.path.exists(file_path):
            # When the JSON file already exists we simply track progress and
            # skip to the next ticker; the download logic remains commented out
            # below for reference.
            print(z)
            z += 1

        else:
            #print(f"The file '{file_path}' does not exist.")

            print(f"starting: {current_ticker}")
            
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            z += 1
            print(z)
            response = requests.request("GET", url, headers=headers, data=payload)
            response = response.text
            response = response.lower()
            response = json.loads(response)

            path_company = f"output/{current_ticker}-facts-json"
            os.makedirs(path_company, exist_ok=True)
            time.sleep(0.5)
            try:
                os.mkdir(path_company)
            except FileExistsError:
                #print("file alread exists")
                pass
            #print(f"Nested directories '{path_company}' created (or already exist).")
            with open(f"{path_company}/full_{current_ticker}.json", 'w') as f:
                json.dump(response, f, indent=4)
    except:
        # Track any failures (network errors, missing keys, etc.) so that the
        # operator can re-run the script for those specific tickers.
        print(failed)
        failed_list += [current_ticker]
