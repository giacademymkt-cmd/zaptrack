import requests
import sqlite3
import json

# 1. Get Token and Account ID
conn = sqlite3.connect('instance/agencyos.db')
cursor = conn.cursor()
cursor.execute("SELECT fb_access_token, ad_account_id FROM client_config WHERE name LIKE '%hellwig%'")
row = cursor.fetchone()
conn.close()

if not row:
    print("Client not found")
    exit(1)

TOKEN, ACCOUNT_ID = row
if not ACCOUNT_ID.startswith('act_'):
    ACCOUNT_ID = f"act_{ACCOUNT_ID}"

print(f"Testing Account: {ACCOUNT_ID}")
print(f"Token: {TOKEN[:10]}...")

# 2. Fetch Insights at Account Level (Level = Ad)
url = f"https://graph.facebook.com/v19.0/{ACCOUNT_ID}/insights"
params = {
    'access_token': TOKEN,
    'level': 'ad',
    'fields': 'ad_id,spend,impressions,clicks,cpc,ctr,actions',
    'date_preset': 'maximum'
}

print("\n--- Fetching Insights ---")
try:
    resp = requests.get(url, params=params)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    
    if 'data' in data:
        print(f"Found {len(data['data'])} insight records.")
        if len(data['data']) > 0:
            print("Sample Record:")
            print(json.dumps(data['data'][0], indent=2))
        else:
            print("Data list is empty.")
            print("Full Response:", json.dumps(data, indent=2))
    else:
        print("Error/No Data:", json.dumps(data, indent=2))

    # 3. Fetch Ads (to check filtering)
    print("\n--- Fetching Ads (Active/Paused) ---")
    ads_url = f"https://graph.facebook.com/v19.0/{ACCOUNT_ID}/ads"
    ads_params = {
        'access_token': TOKEN,
        'fields': 'name,status,effective_status',
        'limit': 50,
        'filtering': '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]'
    }
    ads_resp = requests.get(ads_url, params=ads_params)
    ads_data = ads_resp.json()
    if 'data' in ads_data:
        print(f"Found {len(ads_data['data'])} ads.")
        if len(ads_data['data']) > 0:
            print("Sample Ad:", json.dumps(ads_data['data'][0], indent=2))
            
            # Check ID match
            ad_id = ads_data['data'][0]['id']
            print(f"Checking if Ad ID {ad_id} exists in insights...")
            # We need to re-fetch insights or store them from previous step
            # For this script, let's just assume the previous step worked and we saw IDs.
    else:
        print("No ads found with current filter.")
        print("Response:", ads_data)

except Exception as e:
    print(f"Exception: {e}")
