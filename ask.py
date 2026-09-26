"""Ask finrag a question from the command line.

Usage:  python3 ask.py "What are Apple's main risk factors?"
With no question given, it asks the original FX smoke-test question.
"""
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from finrag.generate import answer

DEFAULT_QUESTION = "What are the risks from foreign exchange rates?"

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    response = answer(question)
    console = Console()
    console.print(Panel(question, title="Question", border_style="cyan"))
    console.print(Panel(Markdown(response), title="Answer", border_style="green"))
