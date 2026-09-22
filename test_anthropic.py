from dotenv import load_dotenv
load_dotenv()
import anthropic

client = anthropic.Anthropic()   # finds ANTHROPIC_API_KEY automatically
message = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)
print(message.content[0].text)