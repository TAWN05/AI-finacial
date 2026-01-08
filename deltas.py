import json
import os
import re
from math import isnan

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from massive import RESTClient
from scipy.stats import randint
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

client = RESTClient("kGEO8nQnqIpbJfiNu4LI5hfcUDPK4Kfc")

grouped = client.get_grouped_daily_aggs(
    "2025-02-28",
    adjusted="true",
)

grouped_rs = client.get_grouped_daily_aggs(
    "2025-05-30",
    adjusted="true",
)

z = 0
y = 0
parsed = 0
failed = 0
failed_list = []
comp = []
comp_cik = []
headers = {
    "User-Agent": "jo boulement jo@gmx.at",
    "Accept-Encoding": "gzip, deflate" 
    }

def to_10_digits(n) -> str:
    s = str(n).strip()
    if not s.isdigit():
        raise ValueError(f"Expected only digits, got {n!r}")
    if len(s) > 10:
        raise ValueError(f"Number longer than 10 digits: {n!r}")
    return s.zfill(10)

payload={}
tickers_url = "https://www.sec.gov/files/company_tickers.json"


response_tickers = requests.request("GET", tickers_url, headers=headers, data=payload)

response_tickers = response_tickers.text
response_tickers = response_tickers.lower()
response_tickers = json.loads(response_tickers)

current_ticker_list = []
delta_eps = []
delta_cash = []
delta_rev = []

for x in response_tickers:
    try:
        current_ticker = response_tickers[x]['ticker']
        with open(f"output/{current_ticker}-facts-json/epsd_{current_ticker}.json", 'r') as f:
            response_epsd = json.load(f)
        with open(f"output/{current_ticker}-facts-json/cash_{current_ticker}.json", 'r') as f:
            response_cash = json.load(f)
        with open(f"output/{current_ticker}-facts-json/rev_{current_ticker}.json", 'r') as f:
            response_rev = json.load(f)
    except:
        pass
    
    current_ticker_list += [current_ticker]
    try:
        delta_eps += [((response_epsd['years']['2025']['q1']) - (response_epsd['years']['2024']['q4']))]
        parsed += 1
    except:
        delta_eps += [0]
    try:
        delta_cash += [((response_cash['years']['2025']['q1']) - (response_cash['years']['2024']['q4']))]
        parsed += 1
    except:
        delta_cash += [0]
    try:
        delta_rev += [((response_rev['years']['2025']['q1']) - (response_rev['years']['2024']['q4']))]
        parsed += 1
    except:
        delta_rev += [0]

#pprint.pprint(grouped[0], indent=4, width=60)


stock_price1 = []
stock_price2 = []
stock_price_rs = []
z = 0
for x in range(len(current_ticker_list)):
    for y in range(len(grouped)):
        if current_ticker_list[x] == grouped[y].ticker.lower():
            stock_price1 += [grouped[y].close]
            break
    for y in range(len(grouped_rs)):
        if current_ticker_list[x] == grouped_rs[y].ticker.lower():
            stock_price2 += [grouped_rs[y].close]
            break
    try:
        #pass
        print(f"price for {current_ticker_list[x]} is {stock_price1[x]}")
    except:
        print(f"ticker not matched: {current_ticker_list[x]} adding 0")
        stock_price1 += ['NAN']
    try:
        #pass
        print(f"price for {current_ticker_list[x]} is {stock_price2[x]}")
    except:
        print(f"ticker not matched: {current_ticker_list[x]} adding 0")
        stock_price2 += ['NAN']

print(len(current_ticker_list))
print(len(stock_price1))
print(len(stock_price2))
for x in range(len(current_ticker_list)):
    if stock_price1[x] != 'NAN' and stock_price2[x] != 'NAN':
        print(f"{[stock_price2[x] - stock_price1[x]]}")
        try:
            stock_price_rs += [(stock_price2[x] - stock_price1[x])]
        except:
            stock_price_rs = [0]
    else:
        pass




THRESH = 10**12  # 1,000,000,000,000

def _is_bad(x, thresh=THRESH):
    # "NAN" string, None, or true NaN
    if x is None or x == "NAN":
        return True
    # Try numeric checks
    try:
        v = float(x)
    except (TypeError, ValueError):
        return True  # non-numeric => bad
    # Handle float NaN explicitly
    if isnan(v):
        return True
    return v >= thresh or v <= -thresh

def clean_rows(delta_eps, delta_cash, delta_rev, current_ticker_list, stock_price_rs, thresh=THRESH):
    anomalies = 0
    keep_eps, keep_cash, keep_rev, keep_tickers, keep_stock_price = [], [], [], [], []

    # If lengths ever differ, zip() will use the shortest safely
    for i, (eps, cash, rev, tk, price) in enumerate(zip(delta_eps, delta_cash, delta_rev, current_ticker_list, stock_price_rs)):
        if any(_is_bad(v, thresh) for v in (eps, cash, rev, price)):
            print(f"deleting row {i}: stock price={price} eps={eps}, cash={cash}, rev={rev}, ticker={tk}")
            anomalies += 1
            continue
        keep_eps.append(eps)
        keep_cash.append(cash)
        keep_rev.append(rev)
        keep_tickers.append(tk)
        keep_stock_price.append(price)

    return keep_eps, keep_cash, keep_rev, keep_tickers, keep_stock_price, anomalies
