
import requests

def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    try:
        source = inputs['source']
        api_key = inputs.get('apiKey')

        if not api_key:
            return {"error": "News API key is required. Please provide it in the input as 'apiKey'."}

        url = f"https://newsapi.org/v2/top-headlines?sources={source}&apiKey={api_key}"
        
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        headlines = []
        for article in data.get('articles', []):
            headlines.append({
                'title': article.get('title'),
                'link': article.get('url')
            })

        return {'headlines': headlines}

    except Exception as e:
        return {"error": str(e)}
