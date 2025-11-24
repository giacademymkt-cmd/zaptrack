import requests

TOKEN = "EAAWO7Ib7baoBQIWhZAMhdkxVoGVxBkGUvUKFw1d6Yz7hc4Apl2GFE7jmPNqXh3TzigqUX6gQYnFSJyKSvnZBZC7FAD34qpD1fzZC2yFYZBBJFq5JkG0zAyfh6Kmt85387qZCRWixACIfveQo0vLTp2L7JWtr4KUZAy74uxIzUzAEJxz3NyZAbbyXaFRS3Ef0oGoWGAZDZD"

def check_token():
    print(f"Checking token: {TOKEN[:10]}...")
    
    # 0. Check User & App
    try:
        resp = requests.get(f"https://graph.facebook.com/v19.0/me?access_token={TOKEN}")
        user_data = resp.json()
        print(f"\n--- Token Owner ---")
        print(f"Name: {user_data.get('name')}")
        print(f"ID: {user_data.get('id')}")
        
        resp = requests.get(f"https://graph.facebook.com/v19.0/app?access_token={TOKEN}")
        app_data = resp.json()
        print(f"\n--- App Info ---")
        print(f"Name: {app_data.get('name')}")
        print(f"ID: {app_data.get('id')}")
    except Exception as e:
        print(f"Failed to get user/app info: {e}")

    # 1. Check Permissions
    url_perms = f"https://graph.facebook.com/v19.0/me/permissions?access_token={TOKEN}"
    try:
        resp = requests.get(url_perms)
        data = resp.json()
        print("\n--- Permissions ---")
        if 'data' in data:
            for perm in data['data']:
                print(f" - {perm['permission']}: {perm['status']}")
        else:
            print(f"Error fetching permissions: {data}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 2. Check Ad Accounts
    url_accounts = f"https://graph.facebook.com/v19.0/me/adaccounts?access_token={TOKEN}&fields=name,account_id,account_status"
    try:
        resp = requests.get(url_accounts)
        data = resp.json()
        print("\n--- Accessible Ad Accounts ---")
        if 'data' in data:
            for acc in data['data']:
                print(f" - Name: {acc.get('name')} | ID: act_{acc.get('account_id')} | Status: {acc.get('account_status')}")
        else:
            print(f"Error fetching accounts: {data}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 3. Check Specific Ad Account from secrets.toml
    specific_account_id = "act_3608750109443101"
    print(f"\n--- Checking Specific Account: {specific_account_id} ---")
    url_specific = f"https://graph.facebook.com/v19.0/{specific_account_id}/campaigns?access_token={TOKEN}&limit=1"
    try:
        resp = requests.get(url_specific)
        data = resp.json()
        if 'data' in data:
            print(f"SUCCESS! Can access campaigns for {specific_account_id}")
            print(f"Found {len(data['data'])} campaigns.")
        else:
            print(f"FAILED to access {specific_account_id}")
            print(f"Error: {data}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_token()
