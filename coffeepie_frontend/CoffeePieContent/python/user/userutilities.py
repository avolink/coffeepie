import requests

def get_my_credits(token, base_url):
    url = f"{base_url}/users/me/credits"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers={**headers, "Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}

def get_my_user(token, base_url):
    url = f"{base_url}/users/me"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers={**headers, "Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "detail": str(e)}
