
import requests

def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    try:
        url = inputs['url']
        response = requests.head(url, allow_redirects=True, timeout=10) # Using HEAD request for efficiency
        
        is_online = response.status_code == 200
        status_text = "Online" if is_online else "Offline"

        result = {
            "url": url,
            "status": status_text,
            "status_code": response.status_code
        }
        return result

    except requests.exceptions.RequestException as e:
        return {
            "url": inputs['url'],
            "status": "Offline",
            "status_code": 0, # Use 0 to indicate connection error
            "error": str(e)
        }
    except Exception as e:
        return {"error": str(e)}
