import requests
import time

def send_event(event_name, fbclid, user_data, custom_data, access_token, pixel_id):
    """
    Sends a generic event to the Facebook Conversions API.
    """
    url = f"https://graph.facebook.com/v19.0/{pixel_id}/events"
    
    payload = {
        "data": [
            {
                "event_name": event_name,
                "event_time": int(time.time()),
                "action_source": "website",
                "user_data": {
                    "fbc": f"fb.1.{int(time.time())}.{fbclid}",
                    "client_ip_address": user_data.get('ip_address'),
                    "client_user_agent": user_data.get('user_agent')
                },
                "custom_data": custom_data
            }
        ],
        "access_token": access_token
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)
