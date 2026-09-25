import json
from explore import client     # reuse the Anthropic client you already set up

JUDGE_MODEL = "claude-sonnet-5"
VERDICT_SCORES = {"CORRECT": 1.0, "PARTIAL": 0.5, "INCORRECT": 0.0}

JUDGE_SYSTEM_PROMPT = """You are grading answers produced by a question-answering system
about Apple's fiscal 2025 SEC 10-K filing. You will receive the question type,
the question, a reference answer written by a human expert, the context the
system was given (retrieved excerpts from the filing), and the system's answer.

You perform two separate checks.

CHECK 1 — CORRECTNESS. Compare the system's answer to the reference answer only.

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

CHECK 2 — FAITHFULNESS. Ignore the reference answer for this check. Is every
factual claim in the system's answer supported by the context?
- A claim is supported if the context states it, or it follows directly from
  figures in the context. Check any comparisons, rankings, or calculations
  yourself using the numbers in the context.
- Citation labels, and statements that information is not available, are not
  factual claims.
- List each unsupported claim as a short phrase. If all claims are supported,
  the list is empty.

Respond with ONLY a JSON object, no other text and no markdown code fences:
{"verdict": "CORRECT" | "PARTIAL" | "INCORRECT", "reason": "<one sentence>",
 "faithful": true | false, "unsupported_claims": ["<claim>", ...]}"""


def judge(question, qtype, reference, system_answer, context):
    """Ask the judge to grade one answer. Returns a dict with
    verdict, reason, faithful, unsupported_claims."""
    user_message = (
        f"Question type: {qtype}\n"
        f"Question: {question}\n"
        f"Reference answer: {reference}\n"
        f"Context the system was given:\n{context}\n"
        f"System answer: {system_answer}"
    )

    client_response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=2000,   # thinking counts toward this, so leave plenty of room
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

        if client_response.stop_reason == "max_tokens":
        return {"verdict": "ERROR", "reason": "Judge output truncated (hit max_tokens)",
                "faithful": None, "unsupported_claims": []}

    # The response holds a list of content blocks; the text is in the first one.
    text = next(block.text for block in client_response.content if block.type == "text").strip()

    # Safety net: strip markdown code fences if the model added them anyway.
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Judge failure, not a finrag failure — label it separately so it can't
        # silently lower finrag's score. Keep a snippet of the raw output for debugging.
        result = {
            "verdict": "ERROR",
            "reason": f"Could not parse judge output: {text[:200]}",
            "faithful": None,
            "unsupported_claims": [],
        }

    return result


if __name__ == "__main__":
    # --- Refusal tests (same as before, now with a context) ---
    ref = ("The 10-K does not contain real-time stock price data. Correct behavior "
           "is to decline, stating the information is not available.")
    ctx = ("[Source 1 — Item 5]\nShare repurchase activity... August 31, 2025 to "
           "September 27, 2025: 27,247 shares at an average price of $238.56.")

    clean = "The filing does not contain Apple's current stock price."
    trap  = ("The filing does not give a current price, but Apple repurchased shares "
             "at an average of $238.56 in September 2025.")
    wrong = "Apple's current stock price is $238.56."

    for label, ans in [("clean", clean), ("trap", trap), ("wrong", wrong)]:
        result = judge("What is Apple's current stock price?", "unanswerable", ref, ans, ctx)
        print(label, "->", result)

    # --- Faithfulness test: the q03 mistake ---
    ref2 = "Services grew 14% and iPhone grew 4%."
    ctx2 = ("[Source 1 — Item 7]\niPhone $209,586 (2025) vs $201,183 (2024). "
            "Services $109,158 (2025) vs $96,169 (2024).")
    ans2 = ("Services grew 14% and iPhone grew 4%, "
            "with iPhone contributing the largest dollar increase.")

    result = judge("How did Apple's sales change?", "answerable", ref2, ans2, ctx2)
    print("faithfulness ->", result)