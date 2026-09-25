# End-to-end answer scoring: finrag answers every golden question,
# the judge grades each answer, and we report scores by question type.
import json
from explore import answer
from eval.judge import judge, VERDICT_SCORES
from eval.recall import load_golden, GOLDEN_PATH

RESULTS_PATH = "eval/results.json"


def main():
    golden = load_golden(GOLDEN_PATH)

    scores = {"answerable": [], "unanswerable": []}   # one list of scores per type
    errors = []                                       # ids where the judge failed
    records = []                                      # full details, saved to disk

    for q in golden:
        system_answer = answer(q["question"])

        result = judge(q["question"], q["type"], q["reference_answer"], system_answer) 
        verdict = result.get("verdict", "ERROR")

        # TODO: if verdict is "ERROR" (or not in VERDICT_SCORES), add q["id"] to errors
        #       otherwise, add VERDICT_SCORES[verdict] to the right list in scores
        #       (hint: q["type"] is exactly "answerable" or "unanswerable")
        if verdict == "ERROR" or verdict not in VERDICT_SCORES:
            errors.append(q["id"])
        else:
            scores[q["type"]].append(VERDICT_SCORES[verdict])

        # TODO: print one line: id, type, verdict, reason
        print(f"Question ID: {q['id']} | Type: {q['type']} | Verdict: {verdict} | Reason: {result.get('reason', '')}")

        records.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "reference_answer": q["reference_answer"],
            "system_answer": system_answer,
            "verdict": verdict,
            "reason": result.get("reason", ""),
        })

    # TODO: for each type in scores, print its average and count, e.g.
    #       answerable:   0.87 (15 questions)
    #       unanswerable: 0.75 (4 questions)
    #       (guard against an empty list, like you did in recall.py)
    for qtype, score_list in scores.items():
        avg_score = sum(score_list) / len(score_list) if score_list else 0.0
        print(f"{qtype}: {avg_score:.2f} ({len(score_list)} questions)")

    # TODO: print how many errors there were, and which ids
    print(f"\nErrors: {len(errors)} question(s) failed to be judged.")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"\nFull results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()