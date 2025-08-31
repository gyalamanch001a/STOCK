# Example for LangChain (multi-agent, open-source)
# Requires: pip install langchain openai
from langchain_openai import OpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType

# Dummy tool for demonstration

def weather_tool(query: str) -> str:
    return "The weather in New York is sunny and 75°F."

tools = [
    Tool(
        name="Weather",
        func=weather_tool,
        description="Get the weather for a city."
    )
]

openai_api_key = "YOUR_OPENAI_API_KEY"  # Replace with your actual key
llm = OpenAI(temperature=0, openai_api_key=openai_api_key)
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

if __name__ == "__main__":
    prompt = "What is the weather in New York today?"
    print(agent.run(prompt))
