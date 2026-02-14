
import json

class BrowserAgent:
    """
    A mock BrowserAgent for demonstration and testing purposes.
    It simulates interacting with a browser and returning content.
    """
    def __init__(self, goal: str, url: str, cdp_url: str, max_steps: int, use_vision: bool, trace: bool):
        self.goal = goal
        self.url = url
        self.cdp_url = cdp_url
        self.max_steps = max_steps
        self.use_vision = use_vision
        self.trace = trace

    def run(self):
        """
        Simulates running a browser agent task.
        """
        print(f"Mock BrowserAgent running for goal: '{self.goal}' on URL: '{self.url}'", flush=True)
        print(f"  CDP URL: {self.cdp_url}, Use Vision: {self.use_vision}", flush=True)

        # Simulate returning some content
        mock_content = f"""
        <html>
        <head><title>Mock Page for {self.url}</title></head>
        <body>
            <h1>Simulated Content for: {self.goal}</h1>
            <p>This is a mock response from the browser agent for {self.url}.</p>
            <div class="test-element">This is a test paragraph.</div>
            <p>Current simulated temperature: 72F</p>
            <p>Simulated conditions: Sunny</p>
        </body>
        </html>
        """
        
        return {
            "success": True,
            "message": "Mock browser agent successfully ran.",
            "content": mock_content,
            "final_url": self.url,
            "steps_taken": 1,
            "vision_used": self.use_vision
        }

if __name__ == "__main__":
    # Example usage for debugging the mock agent directly
    mock_agent = BrowserAgent(
        goal="Get mock content",
        url="http://example.com/mock",
        cdp_url="http://localhost:9222",
        max_steps=1,
        use_vision=False,
        trace=False
    )
    result = mock_agent.run()
    print(json.dumps(result, indent=2))
