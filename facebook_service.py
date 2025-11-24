import requests
from datetime import datetime, timedelta

BASE_URL = "https://graph.facebook.com/v19.0"

# Simple in-memory cache
_cache = {}
_cache_timeout = timedelta(minutes=2)  # Reduced to minimize data delay

def _get_from_cache(key):
    """Check if key exists in cache and is not expired"""
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now() - timestamp < _cache_timeout:
            return data
    return None

def _save_to_cache(key, data):
    """Save data to cache with current timestamp"""
    _cache[key] = (data, datetime.now())

def get_active_campaigns(access_token, ad_account_id):
    """
    Fetches ONLY ACTIVE campaigns from the Facebook Ads API.
    """
    cache_key = f"campaigns_{ad_account_id}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached
    
    if not ad_account_id.startswith('act_'):
        ad_account_id = f"act_{ad_account_id}"
        
    url = f"{BASE_URL}/{ad_account_id}/campaigns"
    params = {
        "access_token": access_token,
        "level": "campaign",
        "fields": "id,name,effective_status",
        "filtering": "[{'field':'effective_status','operator':'IN','value':['ACTIVE']}]",  # Only ACTIVE
        "limit": 100
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        result = data.get("data", [])
        _save_to_cache(cache_key, result)
        return result
    except requests.exceptions.RequestException as e:
        error_msg = f"Erro ao buscar campanhas: {str(e)}"
        if response.content:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', error_msg)
            except:
                pass
        print(f"API Error: {error_msg}")
        raise Exception(error_msg)

def get_campaign_insights(access_token, campaign_id, time_range=None, date_preset='maximum'):
    """
    Fetches insights for a specific campaign.
    """
    # Cache key includes date params
    cache_key = f"insights_{campaign_id}_{date_preset}_{time_range}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached
    
    url = f"{BASE_URL}/{campaign_id}/insights"
    params = {
        "access_token": access_token,
        "fields": "spend,impressions,clicks,cpc,ctr,actions",
        "date_preset": date_preset
    }
    
    if time_range:
        import json
        params["time_range"] = json.dumps(time_range)
        params.pop("date_preset", None) # time_range takes precedence

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        result = data.get("data", [])
        _save_to_cache(cache_key, result)
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error fetching insights for campaign {campaign_id}: {e}")
        return []

def get_account_insights_breakdown(access_token, ad_account_id, date_preset='maximum', time_range=None):
    """
    Fetches account insights broken down by Age/Gender, Platform, and Region.
    Returns a dict with 'age_gender', 'platform', 'region' data.
    """
    if not ad_account_id.startswith('act_'):
        ad_account_id = f"act_{ad_account_id}"
        
    cache_key = f"breakdown_{ad_account_id}_{date_preset}_{time_range}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached

    base_params = {
        "access_token": access_token,
        "date_preset": date_preset,
        "fields": "spend,impressions,clicks,actions"
    }
    if time_range:
        import json
        base_params["time_range"] = json.dumps(time_range)
        base_params.pop("date_preset", None)

    results = {}

    # 1. Age & Gender
    try:
        params = base_params.copy()
        params['breakdowns'] = 'age,gender'
        resp = requests.get(f"{BASE_URL}/{ad_account_id}/insights", params=params)
        if resp.status_code == 200:
            results['age_gender'] = resp.json().get('data', [])
    except Exception as e:
        print(f"Error fetching age/gender breakdown: {e}")

    # 2. Publisher Platform (Facebook, Instagram, etc.)
    try:
        params = base_params.copy()
        params['breakdowns'] = 'publisher_platform'
        resp = requests.get(f"{BASE_URL}/{ad_account_id}/insights", params=params)
        if resp.status_code == 200:
            results['platform'] = resp.json().get('data', [])
    except Exception as e:
        print(f"Error fetching platform breakdown: {e}")

    # 3. Region (Cities/States) - 'region' breakdown gives state/province. 'dma' is metro area.
    # We'll use 'region' for now as it's safer.
    try:
        params = base_params.copy()
        params['breakdowns'] = 'region'
        resp = requests.get(f"{BASE_URL}/{ad_account_id}/insights", params=params)
        if resp.status_code == 200:
            results['region'] = resp.json().get('data', [])
    except Exception as e:
        print(f"Error fetching region breakdown: {e}")
        
    _save_to_cache(cache_key, results)
    return results

def get_ad_insights(access_token, ad_ids):
    """Fetches insights for a list of ad IDs."""
    if not ad_ids:
        return {}
        
    insights = {}
    # Batch requests or loop (for MVP loop is fine, but batch is better)
    # For simplicity in MVP, we'll fetch insights for all ads in one go if possible, 
    # but the API endpoint is usually per object or level.
    # Actually, we can query at ad_account level filtering by ad_ids, but let's do it simple:
    # We will fetch insights for ALL ads in the account and map them.
    # This is more efficient than N requests.
    
    # Wait, we can't easily filter by list of IDs in GET params for insights edge on ad account without complex filtering.
    # Better approach: fetch insights at ad_account level with level='ad' and limit.
    pass 

def get_client_ads_with_creatives(access_token, ad_account_id, adset_id=None):
    """Fetches ads with creative details AND insights.
    If adset_id is provided, filters ads to that adset.
    """
    cache_key = f"ads_with_insights_{ad_account_id}_{adset_id}" if adset_id else f"ads_with_insights_{ad_account_id}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached
    
    if not ad_account_id.startswith('act_'):
        ad_account_id = f"act_{ad_account_id}"
        
    # 1. Fetch Ads with Creatives
    url = f"{BASE_URL}/{ad_account_id}/ads"
    params = {
        'access_token': access_token,
        'fields': 'name,status,adset_id,creative{name,image_url,thumbnail_url,body,title,object_story_spec}',
        'limit': 200  # Increase limit to fetch more ads
        # No filtering to include all ads for accurate spend and metrics
    }
    if adset_id:
        import json
        # Filter by specific adset
        params['filtering'] = json.dumps([{'field':'adset.id','operator':'IN','value':[adset_id]}])
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        ads_data = response.json().get('data', [])
        
        # 2. Fetch Insights for these ads specifically
        ad_ids = [ad['id'] for ad in ads_data]
        insights_data = {}
        
        if ad_ids:
            # Chunk IDs if too many (API limit usually ~50-100 for filtering)
            # For MVP, we'll do chunks of 50
            chunk_size = 50
            for i in range(0, len(ad_ids), chunk_size):
                chunk = ad_ids[i:i + chunk_size]
                
                insights_url = f"{BASE_URL}/{ad_account_id}/insights"
                insights_params = {
                    'access_token': access_token,
                    'level': 'ad',
                    'fields': 'ad_id,spend,impressions,clicks,cpc,ctr,actions',
                    'date_preset': 'maximum',
                    'limit': 500,
                    'filtering': json.dumps([{'field':'ad.id','operator':'IN','value':chunk}])
                }
                try:
                    insights_resp = requests.get(insights_url, params=insights_params)
                    if insights_resp.status_code == 200:
                        for item in insights_resp.json().get('data', []):
                            insights_data[item['ad_id']] = item
                except Exception as e:
                    print(f"Error fetching insights chunk: {e}")
        
        processed_ads = []
        for ad in ads_data:
            creative = ad.get('creative', {})
            image_url = creative.get('image_url') or creative.get('thumbnail_url')
            
            if not image_url and 'object_story_spec' in creative:
                try:
                    image_url = creative['object_story_spec']['link_data']['picture']
                except:
                    pass
            
            # Merge Insights
            insight = insights_data.get(ad['id'], {})
            spend = float(insight.get('spend', 0))
            impressions = int(insight.get('impressions', 0))
            clicks = int(insight.get('clicks', 0))
            
            # Calculate ROAS (Purchase Value / Spend)
            purchase_value = 0
            actions = insight.get('actions', [])
            for action in actions:
                if action['action_type'] == 'purchase':
                    # This is count, we need value. Value is in action_values.
                    pass
            
            # Fetch action values for ROAS
            # Note: 'actions' field gives counts. 'action_values' gives value.
            # We need to add 'action_values' to fields above if we want ROAS from FB.
            # For now, let's just use spend/clicks/imp/ctr/cpc
            
            processed_ads.append({
                'id': ad['id'],
                'adset_id': ad.get('adset_id'),
                'name': ad['name'],
                'status': ad['status'],
                'image_url': image_url or 'https://via.placeholder.com/150?text=No+Image',
                'body': creative.get('body', 'Sem texto principal'),
                'title': creative.get('title', 'Sem título'),
                'spend': spend,
                'impressions': impressions,
                'clicks': clicks,
                'cpc': (spend / clicks) if clicks > 0 else 0,
                'ctr': (clicks / impressions * 100) if impressions > 0 else 0,
                'roas': 0 # Placeholder for now, requires action_values
            })
        
        _save_to_cache(cache_key, processed_ads)
        return processed_ads
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ads with creatives: {e}")
        return []
