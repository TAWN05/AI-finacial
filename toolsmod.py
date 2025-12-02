"""Utility helpers for working with cached EDGAR filings."""

import json
import os

from edgar import Company


## tools
def cache_fetcher():
    """Let a user search the local cache for a previously downloaded 10-Q."""

    directory_path = "cache"
    while True:
        # Allow the user to narrow down cached filings by fuzzy matching the
        # filename (which contains the company name and filing metadata).
        search_term = input("enter the name of the company you are looking for: ")  # The term to search for in file names
        print(f"Files containing '{search_term}' in '{directory_path}':")
        x = 0
        cache_list = []
        try:
            # Build an index of matching files while remembering their display
            # order so the user can select them by number.
            for item in os.listdir(directory_path):
                full_path = os.path.join(directory_path, item)
                if os.path.isfile(full_path) and search_term.lower() in item.lower():
                    x += 1
                    print(item,"number:", x)
                    cache_list += [item]
        except:
            print("error getting cache list")
            exit
            
        user_input = input("are any of these the file you where looking for? (y, n or q to quit): ").lower()
        if user_input == "y":
            break
        elif user_input == "n":
            continue
        else:
            print("invalid input")
            continue
    user_input = int(input("what form would you like to use? (num: 1, 2, 3, type 0 to exit to fetch mode)?: "))
    user_input = user_input - 1
    if user_input == -1:
        return
    stockinfo = []
    # Filenames follow ``Company_Form_Date.json``; split the parts so callers
    # can present the metadata alongside the filing contents.
    stockinfo = cache_list[user_input].split('_')
    stockinfo[2] = stockinfo[2].replace(".json", "")
    with open(f"{directory_path}/{cache_list[user_input]}", 'r') as f:
        tenq = json.load(f)
    tenqitem2 = tenq['item 2']
    tenqitem2cont = tenqitem2['contents']
    #debug
    #print(tenqitem2cont)

    return tenqitem2cont, stockinfo

def edgar_fetcher():
    """Fetch the latest 10-Q via ``edgar`` and cache it for reuse."""

    while True:
        # Keep asking for a ticker until the user confirms we located the
        # correct company.
        ticker = input("please enter the ticker symbol of the company you are looking for: ").lower()
        app = Company(ticker)
        forms = app.get_filings(form="10-Q")
        print(forms)
        user_input = input("is this the stock you where looking for? (y, n): ")
        if user_input == "y":
            break
        else:
            print("please try your ticker again")
            pass
    
    latest10q = forms.latest()
    try:
        tenq = latest10q.obj()
    except:
        print(f"no 10-Q documents found in {ticker} this company is not supported under edgartools")
        return
    tenqitems = tenq.items
    
    #print(tenqitems)
    
    #item = tenqitems[1]
    #tenqcontent = tenq[item]

    item1 = tenqitems[0]
    item2 = tenqitems[1]
    item3 = tenqitems[2]
    item4 = tenqitems[3]
    item5 = tenqitems[4]
    item6 = tenqitems[5]
    tenqjson = {
        "ticker" : ticker,
        "form" : latest10q.form,
        "item 1" : {
            "item name" : tenqitems[0],
            "contents" : tenq[item1],
        },
        "item 2" : {
            "item name" : tenqitems[1],
            "contents" : tenq[item2],
        },
        "item 3" : {
            "item name" : tenqitems[2],
            "contents" : tenq[item3],
        },
        "item 4" : {
            "item name" : tenqitems[3],
            "contents" : tenq[item4],
        },
        "item 5" : {
            "item name" : tenqitems[4],
            "contents" : tenq[item5],
        },
        "item 6" : {
            "item name" : tenqitems[5],
            "contents" : tenq[item6],
        },


    }
    
    # Store a JSON snapshot locally so that repeated lookups do not have to
    # hit the network.
    path = f"cache/{latest10q.company}_{latest10q.form}_{latest10q.filing_date}.json"
    if os.path.exists(path):
        # Reuse the existing snapshot to avoid duplicating files.
        pass
    else:
        with open(f"{path}", 'w') as f:
            json.dump(tenqjson, f, indent=4)
    tenqitem2 = tenqjson['item 2']
    tenqitem2cont = tenqitem2['contents']
    
    stockinfo = []
    # Provide a lightweight tuple so callers can surface the company name,
    # form type, and filing date alongside the textual content.
    stockinfo += (f"{latest10q.company}"), (f"{latest10q.form}"), (f"{latest10q.filing_date}")
    return tenqitem2cont, stockinfo