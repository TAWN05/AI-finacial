"""Interactive helper to fetch and summarize SEC company facts for one ticker."""

import json
import os
import re

import requests


z = 0
y = 0
failed = 0
failed_list = []
# The SEC mandates descriptive User-Agent strings for scripted access.
headers = {
    "User-Agent": "jo boulement jo@gmx.at",
    "Accept-Encoding": "gzip, deflate"
    }

def to_10_digits(n) -> str:
    """Return the zero-padded string format the SEC expects for CIKs."""

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
user_input = input("enter ticker: ").lower()
# ``company_tickers.json`` includes every CIK; scan until we locate the
# requested symbol so we can construct the API URL below.
for x in response_tickers:
    if response_tickers[x]['ticker'] == user_input:
        # Once the symbol matches we capture its CIK and stop searching.
        cik = to_10_digits(response_tickers[x]['cik_str'])
        current_ticker = response_tickers[x]['ticker']
url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
response = requests.request("GET", url, headers=headers, data=payload)


#with open(f"output/{current_ticker}-facts-json/full_{current_ticker}.json", 'r') as f:
#    response = json.load(f)

response = response.text
response = response.lower()
response = json.loads(response)
eps_diluted = response['facts']['us-gaap']['earningspersharediluted']['units']['usd/shares']
operating_cashflow = response['facts']['us-gaap']['netcashprovidedbyusedinoperatingactivities']['units']['usd']
start_year = 2022
eps_json = {
    "company": current_ticker,
    "metric": "epsd",
}
revenue_json = {
    "company": current_ticker,
    "metric": "total revenue",
}
cashflow_json = {
    "company": current_ticker,
    "metric": "operating cashflow",
}
rev_quarter_year = []
rev_num = []

def add_q(json: dict, year: int, value: int | float, quarter: str):
    """Create the nested ``years`` structure if it does not exist."""

    json.setdefault("years", {}).setdefault(year, {})[quarter] = value

def eps(start_year, eps_json):
    """Extract quarterly EPS data for the requested year."""

    frame_check = "cy" + str(start_year)
    for x in eps_diluted:
        if x['form'] == '10-q' or x['form'] == '10-k':
            #print("starting try block",x)
            try:
                if x['frame'] == f"{frame_check}q1":
                    q1_eps = x['val']

                    #print(f"q1 eps for {start_year} is: {q1_eps}")
                    add_q(eps_json, start_year, q1_eps, quarter="q1")
            except:
                pass
                #print("frame not found",x)
                try:
                    if q1_eps:
                        pass
                    else:
                        pass
                except NameError:
                    # When frames are absent, infer the quarter from the ``fp``
                    # designation and the date range.
                    if x['fp'] == 'q1':
                            if f"{start_year}-01" in x['start']:
                                if f"{start_year}-03" in x['end']:
                                    q1_eps = x['val']
                                    add_q(eps_json, start_year, q1_eps, quarter="q1")


            try:
                if x['frame'] == f"{frame_check}q2":
                    q2_eps = x['val']
                    #print(f"q2 eps for {start_year} is: {q2_eps}")
                    add_q(eps_json, start_year, q2_eps, quarter="q2")
                    #print("got q2 from frame")
            except:
                try:
                    if q2_eps:
                        pass
                    else:
                        pass
                except NameError:
                    # Fall back to fiscal-period parsing when explicit frames
                    # are missing, mirroring the quarterly logic above.
                    if x['fp'] == 'q2':
                            if f"{start_year}-01" in x['start']:
                                if f"{start_year}-06" in x['end']:

                                    q2_eps = (x['val'] - q1_eps)
                                    add_q(eps_json, start_year, q2_eps, quarter="q2")

                                    #print("got q2 from fp calc")
                            elif f"{start_year}-03" in x['start']:
                                if f"{start_year}-06" in x['end']:

                                    q2_eps = x['val']
                                    add_q(eps_json, start_year, q2_eps, quarter="q2")

                                    #print("got q2 from fp")
                            elif f"{start_year}-04" in x['start']:
                                if f"{start_year}-06" in x['end']:

                                    q2_eps = x['val']
                                    add_q(eps_json, start_year, q2_eps, quarter="q2")

                                    #print("got q2 from fp spec")

            try:
                if x['frame'] == f"{frame_check}q3":
                    q3_eps = x['val']
                    #print(f"q3 eps for {start_year} is: {q3_eps}")
                    add_q(eps_json, start_year, q3_eps, quarter="q3")
            except:
                try:
                    if q3_eps:
                        pass
                    else:
                        pass
                except NameError:
                    if x['fp'] == 'q3':
                            if f"{start_year}-01" in x['start']:
                                if f"{start_year}-09" in x['end']:

                                    q3_eps = (x['val'] - (q1_eps + q2_eps))
                                    add_q(eps_json, start_year, q3_eps, quarter="q3")

                            elif f"{start_year}-06" in x['start']:
                                if f"{start_year}-09" in x['end']:

                                    q3_eps = x['val']
                                    add_q(eps_json, start_year, q3_eps, quarter="q3")

                            elif f"{start_year}-07" in x['start']:
                                if f"{start_year}-09" in x['end']:

                                    q3_eps = x['val']
                                    add_q(eps_json, start_year, q3_eps, quarter="q3")

            try:
                if x['frame'] == f"{frame_check}":
                    q4_eps = round(x['val'] - (q1_eps + q2_eps + q3_eps), 4)
                    #print(f"q4 or end year eps for {start_year} is: {str(q4_eps)}")
                    add_q(eps_json, start_year, q4_eps, quarter="q4")

            except:
                try:
                    if q4_eps:
                        pass
                    else:
                        pass
                except NameError:
                    # ``fp`` equals FY at year end, so subtract the cumulative
                    # total to derive the stand-alone fourth quarter.
                    if x['fp'] == 'FY':
                            if f"{start_year}-01" in x['start']:
                                if f"{start_year}-12" in x['end']:

                                    q4_eps = (x['val'] - (q1_eps + q2_eps + q3_eps))
                                    add_q(eps_json, start_year, q4_eps, quarter="q4")

                            elif f"{start_year}-09" in x['start']:
                                if f"{start_year}-12" in x['end']:

                                    q4_eps = x['val']
                                    add_q(eps_json, start_year, q4_eps, quarter="q4")

                            elif f"{start_year}-10" in x['start']:
                                if f"{start_year}-12" in x['end']:

                                    q4_eps = x['val']
                                    add_q(eps_json, start_year, q4_eps, quarter="q4")

        else:
            pass
    return eps_json

def cashflow(start_year, cashflow_json):
    """Derive quarterly operating cash flow numbers from cumulative filings."""

    frame_check = "cy" + str(start_year)
    for x in operating_cashflow:
        #print(x)
        for y in x:
            if y == "frame":
                if x['frame'] == f"{frame_check}q1":
                    q1_csh = x['val']

                if x['frame'] == f"{frame_check}q2":

                     q2_csh = round(x['val'] - (q1_csh), 4)

                if x['frame'] == f"{frame_check}q3":

                    q3_csh = round(x['val'] - (q1_csh + q2_csh), 4)

                if x['frame'] == f"{frame_check}":

                    q4_csh = round(x['val'] - (q1_csh + q2_csh + q3_csh), 4)
                
            if y == "fp":
                if x['fp'] == "q1":
                    if f"{start_year}-01" in x['start']:
                        if f"{start_year}-03" in x['end']:
                            q1_csh = x['val']

                elif x['fp'] == "q2":
                    if f"{start_year}-01" in x['start']:
                        if f"{start_year}-06" in x['end']:
                            q2_csh = round(x['val'] - (q1_csh), 4)

                elif x['fp'] == "q3":
                    if f"{start_year}-01" in x['start']:
                        if f"{start_year}-09" in x['end']:
                            q3_csh = round(x['val'] - (q1_csh + q2_csh), 4)
                elif x['fp'] == "q4":
                    if f"{start_year}-01" in x['start']:
                        if f"{start_year}-12" in x['end']:
                            q4_csh = round(x['val'] - (q1_csh + q2_csh + q3_csh), 4)

    add_q(cashflow_json, start_year, q1_csh, quarter="q1")
    add_q(cashflow_json, start_year, q2_csh, quarter="q2")
    add_q(cashflow_json, start_year, q3_csh, quarter="q3")
    add_q(cashflow_json, start_year, q4_csh, quarter="q4")
                    #print(f"q4 or end year eps for {start_year} is: {str(q4_csh)}")"""
    return cashflow_json

def rev(response):
    """Collect revenue frames from any GAAP line containing "revenue"."""

    # Capture both the numeric value and the frame label so later steps can
    # deduplicate overlapping quarters and keep the best observation.
    all_frame_rev = []
    rev = response['facts']['us-gaap']
    for x in rev:
        match_python = re.search(r"revenue", x)
        if match_python:
            #print(x)
            #print(f"\n\n these numbers are from {x}")
            try:
                for y in rev[x]['units']['usd']:
                    if y['form'] == '10-q' or y['form'] == '10-k':
                    #print(f"\n\n these numbers are from {x}")
                        try:
                            all_frame_rev += [str(y['val']) + "_" + y['frame']]
                        except:
                            try:
                                if y['fp'] == 'q1':
                                    if f"{start_year}-01" in y['start']:
                                        if f"{start_year}-03" in y['end']:
                                            all_frame_rev += [str(y['val']) + "_" + f"cy{start_year}q1"]
                            except:
                                pass
                            try:
                                if y['fp'] == 'q2':
                                    if f"{start_year}-03" in y['start']:
                                        if f"{start_year}-06" in y['end']:
                                            all_frame_rev += [str(y['val']) + "_" + f"cy{start_year}q2"]
                                    elif f"{start_year}-04" in y['start']:
                                        if f"{start_year}-06" in y['end']:
                                            all_frame_rev += [str(y['val']) + "_" + f"cy{start_year}q2"]
                            except:
                                pass
                            try:
                                if y['fp'] == 'q3':
                                    if f"{start_year}-06" in y['start']:
                                        if f"{start_year}-09" in y['end']:
                                            all_frame_rev += [str(y['val']) + "_" + f"cy{start_year}q2"]
                                    elif f"{start_year}-07" in y['start']:
                                        if f"{start_year}-09" in y['end']:
                                            all_frame_rev += [str(y['val']) + "_" + f"cy{start_year}q2"]
                            except:
                                pass
            except:
                pass

    """unique_list = []
    try:    
        for item in all_frame_rev:
            if item not in unique_list:
                unique_list.append(item)
    except:
        pass
    return unique_list"""
    return all_frame_rev
def rev_graph(start_year, all_frame_rev, revenue_json):
    """Pick the largest revenue per quarter and normalize the year-end figure."""

    i = 0
    z = 0
    rev_qy_test = []
    rev_num_test = []
    unique_list = []
    rev_qy_trailed = []
    rev_num_trailed = []
    for x in all_frame_rev:
        match_python = re.search(f"cy{start_year}", x)
        if match_python:
            x = x.split("_")
            for y in x:
                i += 1
                if (i % 2) == 0:
                    rev_qy_test += [y]
                    #print("all quarters found:", rev_qy_test)
                    #rev_quarter_year += [y]
                    pass
                
                else:
                    rev_num_test += [y]
                    #print("all rev num found:", rev_num_test)
                    #rev_num += [y]
                    pass
    for item in rev_qy_test:
        if item not in unique_list:
            unique_list.append(item)
    # Sort the quarter labels chronologically so duplicates collapse in a
    # predictable order even if the API returns mixed formatting.
    PERIOD_RE = re.compile(r'^cy(?P<year>\d{4})(?:q(?P<q>[1-4]))?$')
    def period_key(s: str):
        m = PERIOD_RE.match(s.lower())
        if not m:
            # Push unknown formats to the end, preserving original order via sort stability
            return (float('inf'), float('inf'))
        year = int(m.group('year'))
        q = m.group('q')
        # Quarter 1-4 rank before the year-only entry (rank 5)
        rank = int(q) if q is not None else 5
        return (year, rank)
    def sort_periods(labels):
        return sorted(labels, key=period_key)
    # Example
    unique_list = sort_periods(unique_list)
    #print(f"sorted dupes")
    # -> ['cy2022q1', 'cy2022q2', 'cy2022q3', 'cy2022']
    for x in unique_list:
        list_num = []
        z = 0
        o = 0
        for y in rev_qy_test:
            if x == y:
                #print(f"dupe for {y} found related number = {rev_num_test[o]}")
                list_num += [int(rev_num_test[o])]
            o += 1
        #print(f"all num dupes for {x} all nums assosiated with this value are {list_num}")
        largest_rev = max(list_num)
        if x == f"cy{start_year}q1" or x == f"cy{start_year}q2" or x == f"cy{start_year}q3" or x == f"cy{start_year}":
            #print(f"frame: {x} passed frame check adding")
            rev_qy_trailed += [x]
            rev_num_trailed += [largest_rev]
        else:
            pass
            #print(f"frame: {x} did not pass check not adding to list")
    try:
        if rev_qy_trailed[3] == (f"cy{start_year}"):
            calc = 0
            calc = ((rev_num_trailed[0] + rev_num_trailed[1] + rev_num_trailed[2]))
            end_of_year_rev = rev_num_trailed[3]
            fourth_q_rev = (end_of_year_rev - calc)
            del rev_num_trailed[-1]
            rev_num_trailed += [fourth_q_rev]
            #print(f"non-trailed number added for {rev_qy_trailed[3]} {fourth_q_rev}")
        #print(rev_qy_trailed)
        
        #rev_qy_deduped += rev_qy_trailed
        #rev_num_deduped += rev_num_trailed
    except:
        pass
        #print(f"4q not found adding base vars for {rev_qy_trailed}")
        #print(rev_qy_trailed)
        #print(rev_num_trailed)
        #rev_qy_deduped += rev_qy_trailed
        #rev_num_deduped += rev_num_trailed
    for x in range(len(rev_qy_trailed)):
        try:
            add_q(revenue_json, start_year, rev_num_trailed[z], quarter=f"q{z + 1}")
            #print(f"added {rev_num_trailed[z]} to q{z} in revenue json")
        except:
            pass
            #print("failed to add rev to revenue_json")
        z += 1
    return revenue_json
all_frame_rev = rev(response)




# Step through each calendar year sequentially so the derived structures are
# populated continuously until we reach the stopping year.
while True:
    try: 
        eps_json = eps(start_year, eps_json)
    except:
        pass
        #print("failed eps")
    try: 
        cashflow_json = cashflow(start_year, cashflow_json)
    except:
        pass
        #print("failed cashflow")
    try:
        revenue_json = rev_graph(start_year, all_frame_rev, revenue_json)
    except:
        pass
        #print("failed rev")
    start_year = int(start_year)
    start_year += 1
    if start_year > 2025:
        break
    
#print(rev_qy_deduped, rev_num_deduped)
pretty_eps_json_output = json.dumps(eps_json, indent=4)
#print(pretty_eps_json_output)
pretty_cash_json_output = json.dumps(cashflow_json, indent=4)
#print(pretty_cash_json_output)
pretty_rev_json_output = json.dumps(revenue_json, indent=4)
#print(pretty_rev_json_output)
# Persist the derived data so it can be reused or inspected later.
path_company = f"output/{current_ticker}-facts-json"
os.makedirs(path_company, exist_ok=True)
try:
    os.mkdir(path_company)
except FileExistsError:
    #print("file alread exists")
    pass
#print(f"Nested directories '{path_company}' created (or already exist).")
with open(f"{path_company}/epsd_{current_ticker}.json", 'w') as f:
    json.dump(eps_json, f, indent=4)
with open(f"{path_company}/cash_{current_ticker}.json", 'w') as f:
    json.dump(cashflow_json, f, indent=4)
with open(f"{path_company}/rev_{current_ticker}.json", 'w') as f:
    json.dump(revenue_json, f, indent=4)
