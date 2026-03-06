
from openclaw_automation.browser_agent_adapter import run_browser_agent_goal, browser_agent_enabled
from bs4 import BeautifulSoup
import urllib.parse

def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    if not browser_agent_enabled():
        return {"error": "Browser agent is not enabled. Please set OPENCLAW_USE_BROWSER_AGENT=true."}

    try:
        location = inputs['location']
        encoded_location = urllib.parse.quote(location)
        url = f"https://www.weather.com/weather/today/l/{encoded_location}" # Example URL for weather.com

        # Use the browser agent to get the rendered page content
        agent_result = run_browser_agent_goal(
            goal=f"Get the current weather conditions for {location} from weather.com.",
            url=url,
            max_steps=5,
            trace=False,
            use_vision=False
        )

        if not agent_result.get("ok"):
            return {"error": f"Browser agent failed: {agent_result.get('error')}"}

        page_content = agent_result.get("result", {}).get("content")

        if not page_content:
            return {"error": "Browser agent did not return any page content."}

        soup = BeautifulSoup(page_content, 'html.parser')

        # Attempt to find weather details (selectors are highly dependent on weather.com's current structure)
        temperature = soup.find('span', class_='CurrentConditions--tempValue--MHmYY')
        conditions = soup.find('div', class_='CurrentConditions--phraseValue--mZC_u')
        feels_like = soup.find('div', class_='CurrentConditions--feelsLike--euW1W')

        temp_text = temperature.get_text(strip=True) if temperature else "N/A"
        conditions_text = conditions.get_text(strip=True) if conditions else "N/A"
        feels_like_text = feels_like.get_text(strip=True) if feels_like else "N/A"

        result = {
            "location": location,
            "temperature": temp_text,
            "conditions": conditions_text,
            "feels_like": feels_like_text
        }
        return result

    except Exception as e:
        return {"error": str(e)}
