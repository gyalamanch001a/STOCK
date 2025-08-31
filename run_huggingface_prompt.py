import requests

def run_huggingface_prompt(prompt: str, model: str = "gpt2") -> str:
    """
    Run a prompt using Hugging Face Inference API (public model, no API key required).
    """
    url = f"https://api-inference.huggingface.co/models/{model}"
    response = requests.post(url, json={"inputs": prompt})
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
            return result[0]["generated_text"]
        return str(result)
    else:
        return f"Error: {response.status_code} - {response.text}"

if __name__ == "__main__":
    prompt = "What is the weather in New York today?"
    print(run_huggingface_prompt(prompt))
