# LLM-audio-processing

TDS GA-3 Q-7 solution

## Steps

1. Make your proejct folder 
2. inside that create a .env file
```
AI_API_TOKEN= Your_api_key (aipipe key)
CHAT_URL=https://aipipe.org/openrouter/v1/chat/completions
RESPONSES_URL=https://aipipe.org/openrouter/v1/responses
```
3. Now put main.py in the same folder 
4. Install requirements
5. Start a server by ``` uvicorn main:app --reload ``` 
(make sure you are in your project directory)
6. Submit that server link. with endpoint /ask

