#!/usr/bin/env python3
"""
Reverse geocoding example to get address from coordinates
Coordinates: 72.9855854, 19.2291751
"""

# Method 1: Using geopy with Nominatim (OpenStreetMap - Free, no API key required)
def reverse_geocode_nominatim():
    from geopy.geocoders import Nominatim
    
    # Initialize geocoder
    geolocator = Nominatim(user_agent="youtility_app")
    
    # Note: latitude comes first, then longitude
    location = geolocator.reverse("19.2291751, 72.9855854")
    
    print("Address from Nominatim (OpenStreetMap):")
    print(location.address)
    print("\nRaw data:")
    print(location.raw)
    return location


# Method 2: Using Google Maps Geocoding API (requires API key)
def reverse_geocode_google(api_key):
    import requests
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'latlng': '19.2291751,72.9855854',
        'key': api_key
    }

    response = requests.get(url, params=params, timeout=(5, 15))
    data = response.json()

    if data['status'] == 'OK':
        print("Address from Google Maps:")
        print(data['results'][0]['formatted_address'])
        print("\nAddress components:")
        for component in data['results'][0]['address_components']:
            print(f"  {component['types'][0]}: {component['long_name']}")
    return data


# Method 3: Using requests with OpenStreetMap Nominatim API directly
def reverse_geocode_osm_api():
    import requests
    
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': 19.2291751,
        'lon': 72.9855854,
        'format': 'json',
        'addressdetails': 1
    }
    headers = {
        'User-Agent': 'YoutilityApp/1.0'
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=(5, 15))
    data = response.json()
    
    print("Address from OpenStreetMap API:")
    print(data.get('display_name', 'Not found'))
    
    if 'address' in data:
        print("\nAddress details:")
        for key, value in data['address'].items():
            print(f"  {key}: {value}")
    
    return data


# Method 4: For Django project - using existing Google Maps key from settings
def reverse_geocode_django():
    """
    Use this method within your Django project
    """
    import requests
    from django.conf import settings
    
    # Your project already has GOOGLE_MAP_SECRET_KEY in settings
    api_key = settings.GOOGLE_MAP_SECRET_KEY
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'latlng': '19.2291751,72.9855854',
        'key': api_key
    }

    response = requests.get(url, params=params, timeout=(5, 15))
    data = response.json()

    if data['status'] == 'OK':
        return data['results'][0]['formatted_address']
    else:
        return f"Error: {data.get('status', 'Unknown error')}"


if __name__ == "__main__":
    print("="*60)
    print("Reverse Geocoding for coordinates: 19.2291751, 72.9855854")
    print("="*60)
    
    # Method 1: Using geopy (install with: pip install geopy)
    try:
        print("\n--- Method 1: Using geopy ---")
        reverse_geocode_nominatim()
    except ImportError:
        print("Please install geopy: pip install geopy")
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 3: Using requests with OpenStreetMap
    try:
        print("\n--- Method 2: Using OpenStreetMap API ---")
        reverse_geocode_osm_api()
    except ImportError:
        print("Please install requests: pip install requests")
    except Exception as e:
        print(f"Error: {e}")
    
    # For Google Maps API (requires API key)
    # Uncomment and add your API key to test
    # print("\n--- Method 3: Using Google Maps ---")
    # reverse_geocode_google("YOUR_API_KEY_HERE")
    
    print("\n" + "="*60)
    print("Note: These coordinates appear to be in Thane, Maharashtra, India")
    print("Near Hiranandani Estate area based on the coordinates")