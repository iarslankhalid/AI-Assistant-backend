import json
import requests


def get_timezone_from_ip(ip: str) -> dict:
    try:
        print(ip)
        ip_info = requests.get(f"https://ipinfo.io/{ip}/json")
        
        print(ip_info.content)
        return json.loads(ip_info.content)
    except Exception as e:
        print(e)
        return {
            "error": str(e)
        }