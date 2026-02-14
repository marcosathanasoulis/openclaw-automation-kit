
from openclaw_automation.browser_agent_adapter import run_browser_agent_goal, browser_agent_enabled
from bs4 import BeautifulSoup

def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    if not browser_agent_enabled():
        return {"error": "Browser agent is not enabled. Please set OPENCLAW_USE_BROWSER_AGENT=true."}

    try:
        url = inputs['url']
        
        # Use the browser agent to get the rendered page content
        agent_result = run_browser_agent_goal(
            goal="Get the HTML content of the page after it has fully loaded.",
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

        headlines = []
        for h3 in soup.find_all('h3'):
            title = h3.get_text(strip=True)
            if len(title) > 15: # Filter out short text
                link_tag = h3.find_parent('a')
                if link_tag:
                    link = link_tag.get('href')
                    if link and not link.startswith('http'):
                        link = f"https://www.bbc.com{link}"
                    if title and link:
                        headlines.append({'title': title, 'link': link})

        # Remove duplicates
        unique_headlines = []
        seen_links = set()
        for headline in headlines:
            if headline['link'] not in seen_links:
                unique_headlines.append(headline)
                seen_links.add(headline['link'])

        return {'headlines': unique_headlines}

    except Exception as e:
        return {"error": str(e)}
