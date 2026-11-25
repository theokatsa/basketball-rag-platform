"""Fine-tune the embedding model on basketball language and measure what it gains.

    python training/train_embeddings.py              train, compare, save to models/basketball-minilm
    python training/train_embeddings.py --epochs 1   quicker

Two kinds of pairs are learned together with a contrastive loss (the right partner must be closer
than every other one in the batch):
  phrase   -> another phrase or the plain name of the same statistic
  question -> the document that answers it (questions are made from templates)
A quarter of the phrases and two templates of every kind are held out and only measured.
"""

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from training.phrases import NONE, PHRASES, split  # noqa: E402

BASE = "all-MiniLM-L6-v2"
OUT = Path(__file__).resolve().parent.parent / "models" / "basketball-minilm"
SEED = 7
CHECKPOINT = OUT.parent / "checkpoint.pt"

# {n} is the name in the title. The last two of each kind are held out.
TEMPLATES = {
    "player_season": ["What were {n}'s averages?", "How good was {n} this season?", "Tell me about {n}", "{n} stats", "What kind of player is {n}?", "Describe the season of {n}", "Give me a scouting report on {n}", "What does {n} bring to a team?"],
    "shot_profile": ["Where does {n} shoot from?", "{n} shot chart", "How does {n} shoot from each zone?", "Is {n} efficient at the rim?", "{n} corner three shooting", "From which areas does {n} score?", "What are the favourite spots of {n}?", "Break down where {n} gets shots"],
    "matchups": ["Who guards {n} best?", "Which defenders bother {n}?", "Toughest matchups for {n}", "Who does {n} defend well?", "Who can {n} score on easily?", "Which opponents struggle against {n}?", "Who gives {n} a hard time?", "Who has the answer for {n} on defense?"],
    "form": ["How is {n} playing lately?", "{n} last 10 games", "Is {n} in good form?", "Did {n} finish the season well?", "Recent performances of {n}", "Is {n} hot or cold?", "How did things end for {n} this year?", "Has {n} been improving?"],
    "team_season": ["How good were the {n}?", "{n} record and ratings", "Describe the {n} season", "What is the style of the {n}?", "Are the {n} good on defense?", "{n} strengths and weaknesses", "Give me an overview of the {n}", "What kind of team are the {n}?"],
    "pairs": ["Best duo on the {n}", "{n} two-man combinations", "Who plays well together on the {n}?", "Chemistry on the {n}", "Which {n} teammates fit best?", "{n} partnerships", "Which pairing works for the {n}?", "Who should share the court for the {n}?"],
    "game": ["What happened in {n}?", "{n} result", "Who won {n}?", "Best player in {n}", "{n} final score", "Recap of {n}", "Summary of the game {n}", "How did {n} end?"],
}
CUT = {"player_season": " 2024-25 season", "shot_profile": " shot locations", "matchups": " defensive matchups", "form": " recent form", "team_season": " team season", "pairs": " duos", "game": "\0"}


def load_documents():
    with SessionLocal() as db:
        found = db.execute(text("select doc_key, kind, title, content, entity from rag_documents order by id")).mappings().all()
    return [{**d, "name": d["title"].split(CUT[d["kind"]])[0]} for d in found]


def phrase_accuracy(model, train, test):
    """Nearest-class accuracy on held-out phrases, and the share of unrelated questions recognised."""
    labels = list(PHRASES)
    x, y = model.encode([p for p, _ in train], normalize_embeddings=True), [c for _, c in train]
    xt, yt = model.encode([p for p, _ in test], normalize_embeddings=True), [c for _, c in test]
    names = model.encode([PHRASES[c][0] or "not a basketball statistic" for c in labels], normalize_embeddings=True)
    knn = (xt @ x.T).argmax(axis=1)
    clf = LogisticRegression(C=20, max_iter=2000).fit(x, y)
    return {
        "names only": float(np.mean([labels[i] == c for i, c in zip((xt @ names.T).argmax(axis=1), yt)])),
        "nearest phrase": float(np.mean([y[i] == c for i, c in zip(knn, yt)])),
        "classifier": float(np.mean(clf.predict(xt) == np.array(yt))),
    }


def retrieval_accuracy(model, documents, rng):
    """Held-out question templates: is the right document first among all of them?"""
    vectors = model.encode([f"{d['title']}. {d['content']}" for d in documents], normalize_embeddings=True, batch_size=64)
    picked = rng.sample(range(len(documents)), 600)
    questions = [TEMPLATES[documents[i]["kind"]][6 + j % 2].format(n=documents[i]["name"]) for j, i in enumerate(picked)]
    ranks = ((q := model.encode(questions, normalize_embeddings=True, batch_size=64)) @ vectors.T).argsort(axis=1)[:, ::-1]
    place = [int(np.where(r == i)[0][0]) for r, i in zip(ranks, picked)]
    by_kind = defaultdict(list)
    for i, p in zip(picked, place):
        by_kind[documents[i]["kind"]].append(p == 0)
    return {"top1": float(np.mean([p == 0 for p in place])), "top6": float(np.mean([p < 6 for p in place])), "mrr": float(np.mean([1 / (p + 1) for p in place])), "by_kind": {k: float(np.mean(v)) for k, v in by_kind.items()}}


def embed(model, texts):
    features = model.tokenize(texts)
    out = model(features)["sentence_embedding"]
    return torch.nn.functional.normalize(out, dim=1)


def contrastive(a, b, same):
    """Cross-entropy over the batch; other rows that are also correct are not counted as wrong."""
    scores = a @ b.T * 20
    mask = same.clone()
    mask.fill_diagonal_(False)
    scores = scores.masked_fill(mask, -1e4)
    target = torch.arange(len(a))
    return (torch.nn.functional.cross_entropy(scores, target) + torch.nn.functional.cross_entropy(scores.T, target)) / 2


def train(model, phrases, documents, epochs):
    rng = random.Random(SEED)
    torch.manual_seed(SEED)
    optimiser = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    by_class = defaultdict(list)
    for phrase, label in phrases:
        by_class[label].append(phrase)
    by_entity = defaultdict(list)
    for i, d in enumerate(documents):
        by_entity[d["entity"]].append(i)
    batch = 24
    steps = epochs * len(documents) // batch
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimiser, max_lr=3e-5, total_steps=steps + 1, pct_start=0.1)
    model.train()
    started, first = time.time(), 0
    if CHECKPOINT.exists():
        saved = torch.load(CHECKPOINT)
        model.load_state_dict(saved["model"])
        optimiser.load_state_dict(saved["optimiser"])
        scheduler.load_state_dict(saved["scheduler"])
        first = saved["step"] + 1
        print(f"continuing at step {first}", flush=True)
    for step in range(first, steps):
        # Half the batch comes from whole entities, so documents about the same player compete.
        chosen = []
        while len(chosen) < batch // 2:
            chosen += by_entity[rng.choice(list(by_entity))]
        chosen = list(dict.fromkeys(chosen))[: batch // 2]
        chosen += [i for i in rng.sample(range(len(documents)), batch) if i not in chosen][: batch - len(chosen)]
        docs = [documents[i] for i in chosen]
        questions = [rng.choice(TEMPLATES[d["kind"]][:6]).format(n=d["name"]) for d in docs]
        loss = contrastive(embed(model, questions), embed(model, [f"{d['title']}. {d['content']}" for d in docs]), torch.eye(len(docs), dtype=torch.bool))
        # A phrase and another phrase of the same class (or the statistic's own name).
        labels = rng.sample(list(by_class), min(28, len(by_class)))
        left, right = [], []
        for label in labels:
            a = rng.choice(by_class[label])
            others = [p for p in by_class[label] if p != a]
            left.append(a)
            right.append(PHRASES[label][0] if PHRASES[label][0] and rng.random() < 0.4 else rng.choice(others))
        loss = loss + contrastive(embed(model, left), embed(model, right), torch.eye(len(labels), dtype=torch.bool))
        optimiser.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimiser.step()
        scheduler.step()
        if step and step % 50 == 0:  # a crash then costs at most 50 steps
            torch.save({"step": step, "model": model.state_dict(), "optimiser": optimiser.state_dict(), "scheduler": scheduler.state_dict()}, CHECKPOINT)
        if step % 25 == 0:
            print(f"step {step}/{steps} loss {loss.item():.3f} {time.time() - started:.0f}s", flush=True)
    model.eval()
    CHECKPOINT.unlink(missing_ok=True)
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=2)
    args = parser.parse_args()
    phrases, test = split()
    documents = load_documents()
    OUT.parent.mkdir(exist_ok=True)
    print(f"{len(phrases)} training phrases, {len(test)} held out, {len(PHRASES)} classes; {len(documents)} documents", flush=True)
    results = {}
    model = SentenceTransformer(BASE)
    results["base"] = {"phrases": phrase_accuracy(model, phrases, test), "retrieval": retrieval_accuracy(model, documents, random.Random(1))}
    print("base", json.dumps(results["base"]), flush=True)
    train(model, phrases, documents, args.epochs)
    results["tuned"] = {"phrases": phrase_accuracy(model, phrases, test), "retrieval": retrieval_accuracy(model, documents, random.Random(1))}
    print("tuned", json.dumps(results["tuned"]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    model.save(str(OUT))
    (Path(__file__).resolve().parent.parent / "evaluation" / "results" / "training.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
