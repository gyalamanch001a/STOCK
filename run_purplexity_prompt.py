import requests

def run_purplexity_prompt(prompt: str, api_key: str) -> str:
    """
    Run a prompt using the Purplexity API and return the response.
    """
    url = "https://api.purplexity.ai/v1/chat"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json().get("response", "No response field in API result.")
    else:
        return f"Error: {response.status_code} - {response.text}"

if __name__ == "__main__":
    # Example usage
    api_key = "YOUR_PURPLEXITY_API_KEY"
    prompt = "What is the weather in New York today?"
    result = run_purplexity_prompt(prompt, api_key)
    print(result)
