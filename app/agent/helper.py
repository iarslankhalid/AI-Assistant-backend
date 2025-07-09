import requests


def get_timezone_from_ip(ip: str) -> dict:
    try:
        # Get timezone name
        timezone_response = requests.get(f"https://ipapi.co/{ip}/timezone/")
        # Get UTC offset
        utc_offset_response = requests.get(f"https://ipapi.co/{ip}/utc_offset/")
        
        timezone = "Unknown"
        utc_offset = "Unknown"
        
        if timezone_response.status_code == 200:
            timezone = timezone_response.text.strip()
        
        if utc_offset_response.status_code == 200:
            utc_offset = utc_offset_response.text.strip()
            
        return {
            "timezone": timezone,
            "utc_offset": utc_offset
        }
    except Exception as e:
        return {
            "timezone": "Unknown",
            "utc_offset": "Unknown",
            "error": str(e)
        }