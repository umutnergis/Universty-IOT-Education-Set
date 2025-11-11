import requests

API_KEY = "8E4579A1-C3C6-4223-90FE-FBE59B7DDFE6"
BASE_URL = "http://gaunmes.pkeylabs.io/api/v1/session/currentSessionId"

def get_current_session_id(wc_id):
    """
    Belirtilen wc_id için currentSessionId bilgisini döndürür.
    """
    headers = {
        "Accept": "application/json",
        "apiKey": API_KEY
    }

    params = {
        "wcId": wc_id
    }

    try:
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # HTTP hatası varsa hata fırlatır
        return response.json()  # JSON cevabı döndür
    except requests.exceptions.RequestException as e:
        print(f"❌ Hata: {e}")
        return None


if __name__ == "__main__":
    wc_id = 5
    result = get_current_session_id(wc_id)
    print(result)