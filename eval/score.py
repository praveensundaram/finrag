# End-to-end answer scoring: finrag answers every golden question,
# the judge grades each answer, and we report scores by question type.
import json
from finrag.generate import answer_with_context
from eval.judge import judge, VERDICT_SCORES
from eval.recall import load_golden, GOLDEN_PATH
from eval.history import log_run

RESULTS_PATH = "eval/results.json"


def main():
    golden = load_golden(GOLDEN_PATH)

    scores = {"answerable": [], "unanswerable": []}   # one list of scores per type
    errors = []                                       # ids where the judge failed
    unfaithful = []                                   # ids with unsupported claims
    records = []                                      # full details, saved to disk

    for q in golden:
        system_answer, context = answer_with_context(q["question"])

        result = judge(q["question"], q["type"], q["reference_answer"], system_answer, context)
        verdict = result.get("verdict", "ERROR")
        faithful = result.get("faithful")

        # Correctness score (judge failures are kept out of the averages).
        if verdict == "ERROR" or verdict not in VERDICT_SCORES:
            errors.append(q["id"])
        else:
            scores[q["type"]].append(VERDICT_SCORES[verdict])

        # Faithfulness: `is False` so a judge ERROR (faithful=None) isn't blamed on finrag.
        if faithful is False:
            unfaithful.append(q["id"])

        print(f"Question ID: {q['id']} | Type: {q['type']} | Verdict: {verdict} "
              f"| Faithful: {faithful} | Reason: {result.get('reason', '')}")

        records.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "reference_answer": q["reference_answer"],
            "system_answer": system_answer,
            "verdict": verdict,
            "reason": result.get("reason", ""),
            "faithful": faithful,
            "unsupported_claims": result.get("unsupported_claims", []),
            "context": context,
        })

    # Correctness, reported separately per question type.
    print()
    for qtype, score_list in scores.items():
        avg_score = sum(score_list) / len(score_list) if score_list else 0.0
        print(f"{qtype}: {avg_score:.2f} ({len(score_list)} questions)")

    # Faithfulness across all questions the judge could grade.
    judged = len(golden) - len(errors)
    print(f"faithfulness: {judged - len(unfaithful)}/{judged} answers fully supported by context")
    if unfaithful:
        print(f"  unfaithful: {', '.join(unfaithful)}")

    # Judge failures.
    print(f"\nErrors: {len(errors)} question(s) failed to be judged.")
    if errors:
        print(f"  ids: {', '.join(errors)}")
    
    log_run("answers", {
    "answerable": round(sum(scores["answerable"]) / len(scores["answerable"]), 4) if scores["answerable"] else 0.0,
    "unanswerable": round(sum(scores["unanswerable"]) / len(scores["unanswerable"]), 4) if scores["unanswerable"] else 0.0,
    "faithful": judged - len(unfaithful),
    "judged": judged,
    "errors": len(errors),
    })

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"\nFull results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()