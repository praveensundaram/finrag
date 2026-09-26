import json
from finrag.clients import anthropic_client as client

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
- A refusal (saying the information is not available or not in the context) is
  INCORRECT for an answerable question, even if it does not guess.

If the question type is "unanswerable":
- CORRECT: the answer clearly says the requested information is not available in the
  filing. It may mention a related figure that the filing does report, as long as the
  answer clearly labels it as a different metric from the one asked for (for example,
  "unit sales are not reported; iPhone net sales were $209.6 billion").
- PARTIAL: the answer says the information is not available, but also offers an
  estimate, approximation, or calculation of the requested figure, or presents a
  related figure as if it could stand in for the answer.
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
    # Each case: (label, question, type, reference, context, answer, expected)
    # "expected" lists what must hold: a verdict, and/or a faithful value.

    # --- Shared setup for the stock-price (unanswerable) cases ---
    q_price = "What is Apple's current stock price?"
    ref_price = ("The 10-K does not contain real-time stock price data. Correct behavior "
                 "is to decline, stating the information is not available.")
    ctx_price = ("[Source 1 — Item 5]\nShare repurchase activity... August 31, 2025 to "
                 "September 27, 2025: 27,247 shares at an average price of $238.56.")

    cases = [
        # Unanswerable: clean refusal
        ("clean refusal", q_price, "unanswerable", ref_price, ctx_price,
         "The filing does not contain Apple's current stock price.",
         {"verdict": "CORRECT"}),

        # Unanswerable: refusal + clearly labeled related figure (allowed under the new policy)
        ("labeled related figure", q_price, "unanswerable", ref_price, ctx_price,
         "The filing does not give a current stock price. For reference, Apple repurchased "
         "shares at an average price of $238.56 in September 2025, which is a historical "
         "buyback price, not the current price.",
         {"verdict": "CORRECT"}),

        # Unanswerable: refusal + estimate of the requested figure (still penalized)
        ("estimate", q_price, "unanswerable", ref_price, ctx_price,
         "The filing does not state the current stock price, but based on recent buyback "
         "prices it is probably around $240.",
         {"verdict": "PARTIAL"}),

        # Unanswerable: gives a number as the answer
        ("answers instead of declining", q_price, "unanswerable", ref_price, ctx_price,
         "Apple's current stock price is $238.56.",
         {"verdict": "INCORRECT"}),

        # Faithfulness: the q03 mistake (wrong comparison not stated in the context)
        ("unsupported comparison", "How did Apple's sales change?", "answerable",
         "Services grew 14% and iPhone grew 4%.",
         "[Source 1 — Item 7]\niPhone $209,586 (2025) vs $201,183 (2024). "
         "Services $109,158 (2025) vs $96,169 (2024).",
         "Services grew 14% and iPhone grew 4%, with iPhone contributing the largest dollar increase.",
         {"faithful": False}),

        # Answerable question, but the system refuses: must be INCORRECT
        ("refusal on answerable", "Who is Apple's Chief Financial Officer?", "answerable",
         "Kevan Parekh is Apple's Chief Financial Officer.",
         "[Source 1 — Item 16]\n| /s/ Kevan Parekh | Senior Vice President, Chief Financial Officer |",
         "The provided context does not name Apple's Chief Financial Officer.",
         {"verdict": "INCORRECT"}),
    ]

    failures = 0
    for label, question, qtype, ref, ctx, answer, expected in cases:
        result = judge(question, qtype, ref, answer, ctx)
        ok = all(result.get(key) == value for key, value in expected.items())
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label:30} expected {expected}  "
              f"got verdict={result.get('verdict')} faithful={result.get('faithful')}")
        if not ok:
            print(f"      reason: {result.get('reason')}")

    print(f"\n{len(cases) - failures}/{len(cases)} judge checks passed")
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
        # --- Refusal on an answerable question: must be INCORRECT ---
    result = judge("How did Apple's sales change?", "answerable", ref2, ans2, ctx2)
    print("faithfulness ->", result)


    ref3 = "Kevan Parekh is Apple's Chief Financial Officer."
    ctx3 = "[Source 1 — Item 16]\n| /s/ Kevan Parekh | Senior Vice President, Chief Financial Officer |"
    ans3 = "The provided context does not name Apple's Chief Financial Officer."

    result = judge("Who is Apple's Chief Financial Officer?", "answerable", ref3, ans3, ctx3)
    print("refusal on answerable ->", result)
