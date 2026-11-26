"""Results of the blind test of similar players (page "Judge similar players", table similarity_judgments).

    python evaluation/judge_similarity.py --source study

Each judgment compares the learned method ("overall": 42 features, weights learned from odd and even
games) with the twelve averages used before ("production"), shown in random order. A sign test asks
whether the learned lists win more often than chance (half) when people prefer one; "about the same"
is left out of the test and reported. Answers from one person are not independent, so the result is
also given per person.
"""

import argparse
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402


def sign_test(wins: int, losses: int) -> float:
    """Two-sided p-value of wins out of wins + losses under a fair coin."""
    n = wins + losses
    if not n:
        return 1.0
    tail = sum(comb(n, k) for k in range(max(wins, losses), n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="study")
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = db.execute(text("select visitor::text, left_method, right_method, choice from similarity_judgments where source = :s"), {"s": args.source}).all()
    winner = Counter()
    people = defaultdict(Counter)
    for visitor, left, right, choice in rows:
        chosen = "same" if choice == "same" else (left if choice == "left" else right)
        winner[chosen] += 1
        people[visitor][chosen] += 1
    learned, averages, same = winner["overall"], winner["production"], winner["same"]
    print(f"{len(rows)} judgments from {len(people)} browsers (source '{args.source}').")
    print(f"Learned lists preferred {learned} times, the twelve averages {averages} times, about the same {same} times.")
    if learned + averages:
        print(f"Share preferring the learned lists: {learned / (learned + averages):.0%}; sign test p = {sign_test(learned, averages):.3f}.")
    by_person = Counter("learned" if c["overall"] > c["production"] else "averages" if c["production"] > c["overall"] else "tie" for c in people.values())
    print(f"Per person, the method preferred more often: learned {by_person['learned']}, averages {by_person['averages']}, tie {by_person['tie']}; "
          f"sign test over people p = {sign_test(by_person['learned'], by_person['averages']):.3f}.")


if __name__ == "__main__":
    main()
