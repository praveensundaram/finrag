"""API clients, created once and shared by the rest of finrag (and by eval/judge.py)."""
import anthropic
import voyageai
from dotenv import load_dotenv

load_dotenv()   # reads VOYAGE_API_KEY and ANTHROPIC_API_KEY from .env

voyage_client = voyageai.Client()
anthropic_client = anthropic.Anthropic()
