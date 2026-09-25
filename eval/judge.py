import json
from explore import client     # reuse the Anthropic client you already set up

JUDGE_MODEL = "claude-sonnet-5"
VERDICT_SCORES = {"CORRECT": 1.0, "PARTIAL": 0.5, "INCORRECT": 0.0}

JUDGE_SYSTEM_PROMPT = """You are grading answers produced by a question-answering system
about Apple's fiscal 2025 SEC 10-K filing. You will receive the question type,
the question, a reference answer written by a human expert, and the system's answer.

Grade the system's answer with exactly one verdict: CORRECT, PARTIAL, or INCORRECT.

If the question type is "answerable":
- CORRECT: the answer contains the key facts from the reference answer, and nothing
  in it contradicts the reference. Wording may differ. Extra accurate detail is fine.
  For questions whose reference is a long list, the answer is CORRECT if it covers
  most of the list and adds nothing false.
- PARTIAL: the answer gets some key facts right but misses important ones,
  or contains a minor error.
- INCORRECT: the answer misses the main point, gets a key fact wrong,
  or states things that are not supported by the reference.

If the question type is "unanswerable":
- CORRECT: the answer clearly says the information is not available in the filing
  and does not guess.
- PARTIAL: the answer says the information is not available, but also speculates
  or presents a related figure as if it might be the answer.
- Any specific figure, name, or estimate mentioned alongside the refusal counts as
  PARTIAL, even if it is labeled as something other than the requested answer
  (for example, a historical buyback price mentioned in reply to a question about
  the current stock price). A CORRECT answer declines without offering such figures.
- INCORRECT: the answer provides an answer (for example a price, a name, or a number)
  instead of declining.

Numbers are equivalent if they express the same value in different units
(for example, $112,010 million and $112.0 billion).

Respond with ONLY a JSON object, no other text and no markdown code fences:
{"verdict": "CORRECT" | "PARTIAL" | "INCORRECT", "reason": "<one sentence>"}"""


def judge(question, qtype, reference, system_answer):
    """Ask the judge to grade one answer. Returns a dict: {"verdict": ..., "reason": ...}"""
    user_message = (
        f"Question type: {qtype}\n"
        f"Question: {question}\n"
        f"Reference answer: {reference}\n"
        f"System answer: {system_answer}"
    )

    client_response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # The response holds a list of content blocks; the text is in the first one.
    text = client_response.content[0].text.strip()

    # Safety net: strip markdown code fences if the model added them anyway.
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Judge failure, not a finrag failure — label it separately so it can't
        # silently lower finrag's score. Keep a snippet of the raw output for debugging.
        result = {"verdict": "ERROR", "reason": f"Could not parse judge output: {text[:200]}"}

    return result


if __name__ == "__main__":
    ref = ("The 10-K does not contain real-time stock price data. Correct behavior "
           "is to decline, stating the information is not available.")

    clean = "The filing does not contain Apple's current stock price."
    trap  = ("The filing does not give a current price, but Apple repurchased shares "
             "at an average of $238.56 in September 2025.")
    wrong = "Apple's current stock price is $238.56."

    for label, ans in [("clean", clean), ("trap", trap), ("wrong", wrong)]:
        result = judge("What is Apple's current stock price?", "unanswerable", ref, ans)
        print(label, "->", result)