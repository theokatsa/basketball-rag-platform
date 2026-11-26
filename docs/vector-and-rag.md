# Vector store and RAG pipeline

How the system turns statistics into searchable evidence, answers questions from it, and how
well that works. Results are for the 2024-25 regular season, the only one in the database.

## 1. The idea

A language model does not know this database and invents numbers when asked. Retrieval-Augmented
Generation (RAG) finds the relevant facts first and lets the model write only from them.

```text
question (English, or Greek put into English words; follow-ups made complete)
  -> fact engine         a number nobody wrote down is calculated (part 8)
  -> query planner       exact parts: names, teams, ages, thresholds, "best"
  -> retrieval           SQL filters and rankings / pgvector / full-text search
  -> numbered sources
  -> language model      writes an answer with [1] [2] citations (or sources are quoted)
  -> grounding check     every number must exist in a source
```

## 2. What is stored

Separate vector spaces, because "what is this text about" and "who plays like this" are
different questions.

| Table | Vector | Rows | Distance | Answers |
|---|---|---|---|---|
| `rag_documents` | 384 (MiniLM text embedding) | 3,127 | cosine | meaning of a question |
| `player_stat_vectors` | 12 (z-scores) | 569 | Euclidean | similar averages ("production") |
| `player_style_vectors` | 24 + 24 (learned) | 569 | Euclidean | similar overall, similar playing style (part 9) |

**Documents.** One document answers one kind of question about one entity.

| Kind | Count | Content |
|---|---|---|
| player_season | 569 | averages, shooting, advanced statistics, strengths |
| shot_profile | 447 | makes and attempts per court zone, against the league |
| matchups | 429 | who guarded the player best, who was guarded well |
| form | 392 | last 10 games against the earlier ones |
| team_season | 30 | record, ratings and ranks |
| pairs | 30 | best and weakest duos by net rating |
| game | 1,230 | result and best performers |

Each row holds the text, its embedding, a full-text index (`tsv`) and the same facts as numbers
(`meta`). MiniLM ignores everything after 256 tokens, so documents are kept below that; all are.

**Statistical vectors.** A z-score says how many standard deviations a player is from the league
mean, which makes 10 rebounds and 40% shooting comparable. With d the Euclidean distance,
similarity = exp(-d^2 / 24). Moving this search from memory into pgvector changed no result: 120
comparisons with and without filters gave the same players in the same order.

**Index.** HNSW is an approximate index: a layered graph that is walked towards the query.

| Search | Recall@10 | Median ms |
|---|---|---|
| exact scan | 1.000 | 13.62 |
| HNSW ef_search=10 | 0.751 | 0.32 |
| HNSW ef_search=40 | 0.904 | 0.56 |
| HNSW ef_search=100 (used) | 0.943 | 0.87 |
| HNSW ef_search=200 | 0.980 | 1.27 |

49 queries over 3,127 vectors, time inside the server without the network. At this size an exact
scan is fast enough; the index matters as seasons are added. Filters can leave an HNSW search
short of results, so pgvector's iterative scan is on.

## 3. Retrieval

- **keyword**: PostgreSQL full-text search. `ts_rank_cd` has no inverse document frequency, so it
  is a weaker baseline than BM25.
- **vector**: nearest text embeddings.
- **hybrid**: both, merged by Reciprocal Rank Fusion, score = sum of 1 / (60 + rank). It uses ranks
  because the two scores are on different scales.
- **rules**: the planner decides. Filters and rankings are SQL, "like X" is a statistical vector
  search, a lookup fetches the right kind of document, anything else is hybrid search.
- **planned**: rules plus the semantic skill router. `/ask` uses the fact engine first and this for the rest, without the skill router: it asks back instead (part 10).

## 4. Retrieval evaluation

44 questions were written before the planner, with answers computed by SQL on the raw tables.
Five paraphrases were later added to the development set. Development: 17, test: 32. The test set
was run once, with the code frozen. Top 6 results are scored.

| Method | P@6 | R@6 | MRR | nDCG@6 | 95% interval of nDCG | Median ms |
|---|---|---|---|---|---|---|
| keyword | 0.120 | 0.401 | 0.339 | 0.340 | 0.20-0.49 | 214 |
| vector | 0.130 | 0.490 | 0.458 | 0.448 | 0.29-0.61 | 502 |
| hybrid | 0.133 | 0.444 | 0.441 | 0.414 | 0.26-0.57 | 476 |
| rules | 0.703 | 0.875 | 0.896 | 0.874 | 0.76-0.97 | 349 |
| planned | 0.714 | 0.885 | 0.911 | 0.884 | 0.78-0.97 | 348 |

Intervals are bootstrapped over questions. Times include the network to Supabase.

| Type (nDCG@6) | n | keyword | vector | hybrid | planned |
|---|---|---|---|---|---|
| ranking | 4 | 0.048 | 0.048 | 0.076 | 0.920 |
| filter | 5 | 0.000 | 0.047 | 0.079 | 1.000 |
| team | 5 | 0.134 | 0.200 | 0.059 | 1.000 |
| shooting | 3 | 0.710 | 0.877 | 1.000 | 1.000 |
| matchup | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| pairs | 2 | 0.500 | 0.815 | 0.500 | 1.000 |
| form | 2 | 0.815 | 1.000 | 0.815 | 1.000 |
| game | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| lookup | 3 | 0.421 | 0.836 | 0.834 | 1.000 |
| paraphrase | 4 | 0.000 | 0.038 | 0.027 | 0.155 |

**Findings**

1. Embeddings find the right *document* but cannot rank or filter. No document says "I am the
   league's best", and "under 25" sits next to "over 25". Planning improves nDCG over vector
   search by 0.44 (95% interval 0.29 to 0.59).
2. Hybrid search did not beat vector search (difference -0.035, interval -0.13 to 0.05).
3. The router does not generalise: paraphrases scored 0.957 in development and 0.155 on the test
   set. It handles plain descriptions, but MiniLM does not know basketball slang. Its overall gain
   over rules is 0.010 (interval 0.00 to 0.03).

**Limits of this evaluation**

- One person's tool wrote the questions, the rules and the answer key, and several test types have
  only 2 to 4 questions. Independent questions from real users are needed.
- Rankings are judged by the same statistic the planner sorts by, which favours it.
- The test set was used; a further change needs new questions to be reported fairly.
- Precision counts extra context as wrong: a lookup also returns the season line on purpose.
- All 6 unanswerable questions were declined, but the refusal word list was written after those
  questions, so this is not an independent result. One answerable question was also declined
  ("Guys who clean the glass").
- Generation has not been evaluated, because no language model key was configured.
- These are the numbers of the first run. Documents later switched to the age during the season,
  like the pages; a rerun gives vector 0.441, hybrid 0.413, planned 0.880 (the key still uses the
  current age for three questions).

## 5. Grounding

`grounding.py` reads every number in an answer and looks for it in the sources (rounding allowed,
added precision not), and checks that citations exist. It catches invented statistics. It does not
catch a real number attached to the wrong player, or a false claim without numbers.

## 6. Run it

```text
cd backend
python scripts/build_rag_index.py                    build or refresh (only changes are embedded)
python -m unittest discover -s tests -t .            planner and grounding tests
python evaluation/run_eval.py --split dev            retrieval comparison
python evaluation/bench_index.py                     exact scan against HNSW
```

Run the first command again after any ingestion script.

| File (backend/) | Role |
|---|---|
| scripts/schema_rag.sql | tables and indexes |
| app/services/corpus.py | statistics -> documents |
| app/services/query_planner.py | question -> plan |
| app/services/skill_router.py | paraphrase -> statistic |
| app/services/retrieval.py | the five retrieval methods |
| app/services/rag_service.py | prompt, answer, fallback |
| app/services/grounding.py | number and citation check |

## 8. Fact engine

Most questions about statistics ask for a number that no document contains ("points at home in
January", "most 40-point games"). The engine reads a question into subject, statistic, slice of
games and operation, and calculates over the season held in memory (28 MB, loaded at startup). The
result goes to the model as source [1], or is shown as it is when there is no model.

It covers the data of every page: averages, totals and ranks; splits by place, result, month,
opponent and last games; season highs; counts of games; double- and triple-doubles; size, age and
experience; comparisons; records, standings, streaks, quarters, overtime; shot types and areas;
pairs; one-on-one matchups; lineups; ideal teammates; players who would help a team; changes in
form; league averages. Follow-ups ("what about Jokic?", "and at home?") are rewritten into complete
questions. Greek questions are handled by replacing basketball words, not by translation.

**Evaluation.** 107 questions with answers computed by SQL on the raw tables were written before the
engine. The baseline is the retrieval system of part 3 on the same questions.

| Split | Questions | Baseline | Fact engine |
|---|---|---|---|
| development | 40 | 20.0% | 100.0% |
| test (held out) | 67 | 29.9% | 98.5% |

The one wrong test answer is a four-way tie in which the key names one player and the answer lists
all four. The test was rerun after later changes and gave the same result.

Limits: the questions and the engine have the same author, so this shows that the data is covered
more than that any wording is understood. A number counts as correct if it appears in the answer,
which is lenient, for the baseline too. Words are matched, so some sentences are read wrongly:
"jump into passing lanes" is taken as passing, and "the weather in Miami" returns the Miami Heat.
Bench scoring and clutch player statistics are not in the data.

## 9. Learned similarity and suggestions

**Features.** 42 per player: role, scoring, touch, shot selection (9 areas, 12 shot types), passing,
rebounding, defense. Percentages are pulled toward the league average when attempts are few.

**Learning.** Each player is described twice, from odd and from even games. Differences between a
player's two halves are noise, differences between players are signal. The projection whitens the
noise and keeps the directions with most signal, weighted by reliability (linear discriminant
analysis with shrinkage). Similarity is exp(-(d / s)^2), where the median pair of players gets 10%.

**How it is tested.** There is no answer key for "similar". A measure is good when the closest match
of a player's one half is his own other half among 384 players (5 folds; never tested on players it
was trained on). Position agreement of the five nearest is not trained on.

| Method | Odd/even: own half first | First/second half of season | Same position |
|---|---|---|---|
| 12 averages, Euclidean (before) | 0.388 | 0.247 | 0.588 |
| 42 features, Euclidean | 0.826 | 0.681 | 0.613 |
| learned, 24 dimensions (used) | 0.948 | 0.743 | 0.639 |
| learned, style only, 24 dimensions (used) | 0.876 | 0.764 | 0.654 |

Most of the gain comes from the features; learning adds less on the harder test, where roles change.
The last column comes from the odd/even table. The size 24 was chosen from this table, so its numbers
are slightly optimistic. Minutes are the most important overall feature, which is why "playing style"
leaves them out. Recognising a player is not the same as a scout's idea of similarity.

**Archetypes** are k-means groups in the learned space (8, chosen by silhouette). The silhouette is
0.17: roles overlap, and the labels are loose. Each group is labelled by its three most distinctive
features ("Shoots mostly threes, shoots from far, wing threes"); pages show a short role name instead
("Floor spacer", ROLE_NAMES in similarity_service.py). These describe the group, not the player.

**Suggestions** compare candidates with each player someone shortlisted, compared or viewed (not with
their average, since a person can have several interests), add what was viewed together, and spread
the list out. **Team targets** look for players strong where a squad is weak. Neither has been tested
with users; the platform has too few for that.

## 10. Two training experiments, one negative

**Fine-tuning the embeddings.** MiniLM was trained with a contrastive loss on question and document
pairs made from templates, and on phrase pairs (3 epochs, 390 steps, about an hour on a CPU).

| Measure | Original | Trained |
|---|---|---|
| Right document first, unseen templates | 0.697 | 0.962 |
| Right statistic, unseen phrases (33 classes) | 0.419 | 0.409 |
| Retrieval test, vector nDCG@6 | 0.441 | 0.410 |

The trained model looks much better on questions made the way its training questions were made, and
no better on independent ones (difference -0.03, interval -0.12 to 0.05). It learned the templates.
The original model is used. The loss fell from 3.8 to 0.02 and said nothing about this.

**Paraphrase router.** A classifier on the embeddings, 33 classes, about 300 phrases. On held-out
phrases the first guess is right 35% of the time and one of the first three 65%. Acting on the first
guess would answer most paraphrases wrongly, so it is used to ask back: "did you mean ...?" with
three questions to choose from. An unrelated question is recognised as such only 55% of the time.
A first version chose its confidence threshold by cross-validation on phrases that the embedding
model had been tuned on; it looked precise (85%) and was not (39% on held-out phrases).

## 11. Audience: simulated users, most viewed and "also viewed"

The platform had one real user, so 600 users were **simulated** (scripts/simulate_users.py): 14,394
views over 60 days. They are flagged (`app_users.is_simulated`), cannot sign in, are named on every
page that uses them, and are removed with `--remove`. Their behaviour mixes reasons to open a page:
a favourite team (35%), one of 25 **random** groups of players such as a draft class or a podcast
(20%), popularity that is partly chance (20%), a position and age (13%), the site's own similar-players
list (12%), and a few players suddenly in the news. Random groups and chance popularity cannot be
found from statistics, only from behaviour, so the simulation can show whether a method learns
from people rather than repeating the statistics.

**Task A, next to a player:** for each visit after a date, which other players were opened in it.
Views are split by time (70% to learn, 15% to choose settings, 15% to test). The method was then
fixed and confirmed on two new simulations with other users, groups and popularity (seeds 101 and 202),
never seen while developing. nDCG@6:

| Method | Development | Fresh 1 | Fresh 2 |
|---|---|---|---|
| popularity | 0.065 | 0.069 | 0.088 |
| similar players (no audience) | 0.072 | 0.070 | 0.059 |
| same team | 0.133 | 0.135 | 0.162 |
| the platform so far | 0.121 | 0.116 | 0.119 |
| cosine | 0.131 | 0.127 | 0.124 |
| Jaccard | 0.141 | 0.141 | 0.139 |
| item2vec (PPMI + SVD) | 0.124 | 0.115 | 0.118 |
| graph walk | 0.160 | 0.155 | 0.161 |
| cosine, shrunk | 0.169 | 0.166 | 0.176 |
| EASE | 0.169 | 0.167 | 0.176 |
| learned blend | 0.173 | 0.172 | 0.187 |
| equal blend | 0.176 | 0.171 | 0.187 |
| EASE with prior (used) | 0.173 | 0.171 | 0.182 |

"The platform so far" is the formula the site used before. EASE (Steck 2019) predicts every player
from all the others with a ridge regression, so two players who only share a popular third one are
not linked. "With prior" leans on statistical similarity and team when a player has few visits:
trust = visits / (visits + k), k chosen on the validation period. It ties with the best blends
(within 0.005, a rule fixed before the confirmation) and is used because it relies on what people did.
A weight-learning blend was tried first as a classifier of opened against random pairs: it learned
popularity and ranked worse than equal weights (0.135 against 0.173); fitting the ranking directly
fixed it but did not beat equal weights.

Share of the random groups found in the top 6 (only behaviour can reveal them):

| | Development | Fresh 1 | Fresh 2 |
|---|---|---|---|
| similar players (no audience) | 0.01 | 0.02 | 0.02 |
| the platform so far | 0.49 | 0.42 | 0.41 |
| EASE | 0.57 | 0.51 | 0.50 |
| EASE with prior (used) | 0.56 | 0.49 | 0.45 |
| learned blend | 0.40 | 0.41 | 0.32 |
| equal blend | 0.48 | 0.42 | 0.40 |

Blends add team and popularity and find fewer of the groups. Lists only show pairs opened together
by at least two people, so that no list reveals what one person looked at.

**Task B, for a person:** which players someone opens for the first time later. nDCG@6:

| Method | Development | Fresh 1 | Fresh 2 |
|---|---|---|---|
| popularity | 0.081 | 0.080 | 0.100 |
| similar players | 0.037 | 0.027 | 0.033 |
| also viewed lists | 0.137 | 0.130 | 0.150 |
| people like you | 0.140 | 0.140 | 0.146 |
| EASE over people | 0.146 | 0.147 | 0.158 |
| EASE + similar players (used) | 0.137 | 0.147 | 0.157 |

Suggestions mix behaviour (45%) and similarity (45%) with quality (10%). The share is a judgement,
not a measurement: in the simulation behaviour wins easily, but only 12% of simulated clicks follow
similarity, a number that was chosen, not observed. Real users decide this.

Fixed on 2026-11-26: the two parts were not on the same scale. Behaviour was rescaled so the best ten
score about 1, but similarity was left raw, and for a rare player like Jokić the closest match is only
0.36. The intended 45/45 was in effect about 25/75 for behaviour, so popular players crowded out
similar ones. Similarity is now rescaled the same way. Two more changes came from reading the Home
page: with nothing known about a person, the list took the best player of each of the eight groups,
which brought in bench players with good per-minute numbers (Ty Jerome, Moritz Wagner after 30 games).
It now takes regular starters (40 games, 24 minutes) by quality and 30-day views, at most two per
group. And each suggestion is described by the player's own strengths, not his group's label.

**Most viewed** counts different users per period, with the place in the period before. **Trending**
compares the views of the last 5 days with the player's usual share of traffic, in standard
deviations of a count; with hundreds of players it needs 3 to avoid chance. It found all 4 players
planted in the news as its top 4. **Hidden gems** are players whose place by overall score is far
above their place by viewers.

**Limits.** Everything here is measured on simulated behaviour; the numbers show that the methods
recover planted structure, not how real scouts behave. The lists are retrained with
`python training/train_also_viewed.py --store`, not live; erased views leave the lists until then.
The simulated views age: run the simulation again before a demonstration.

## 12. More similarity

**Younger and better versions.** Similar players can be limited to three or more years younger, or to
a higher overall score ("a younger Lillard": Maxey, Mitchell, White).

**Teams that play alike.** 21 features: pace, three-point and free-throw rates, assists, rebounding,
turnovers, steals, blocks, what opponents are allowed, and 9 shot areas. Tested like players: is a
team's closest match among 30 its own other half of games (chance: 3%)?

| Features | Odd and even games | First and second half of season |
|---|---|---|
| 8 team averages | 0.78 | 0.47 |
| style features (used) | 0.98 | 0.73 |

## 13. Training and evaluation commands (backend/)

```text
python training/train_similarity.py                  similarity table, models/similarity.npz
python training/train_router.py                      models/router.npz
python training/train_embeddings.py                  the experiment of part 10 (resumes after a crash)
python evaluation/run_facts.py --split dev --show    fact questions
python scripts/simulate_users.py                     600 simulated users (--remove to delete them)
python training/train_also_viewed.py                 compare methods, store also viewed lists
python training/train_also_viewed.py --confirm 303   compare on a fresh simulation
```

After train_similarity.py run scripts/build_rag_index.py. To use another embedding model set
EMBEDDING_MODEL and rebuild; a mismatch is refused.

## 14. Questions written by other people

The two earlier test sets were written alongside the system, so a third set was taken from outside:
246 questions from three public sources, kept in their original wording
(backend/evaluation/external_questions.py).

| Source | Questions | What it is |
|---|---|---|
| Hugging Face text-to-SQL NBA set | 50 | stats questions written by an unknown author |
| Stathead sample searches | 145 | example searches from Basketball-Reference's search tool (college ones left out) |
| Scouting guides (3 sites) | 51 | questions scouts ask about a player |

The rules were fixed before any answer was computed: "a season" means 2024-25, the only season stored;
questions about careers, other seasons, playoffs, awards, the draft, WNBA/ABA or data that is not stored
should be declined; per-game leaders without a stated minimum use the NBA.com minimums (58 games). The
scouting questions name no player, so each was given one, taken in a fixed order from regular players.
The file was frozen (its sha256 is in the report) and run once, with no change to the system.

| Source | Answerable: correct | Should decline: declined |
|---|---|---|
| Hugging Face | 3 of 35 (9%) | 2 of 15 (13%) |
| Stathead | 14 of 56 (25%) | 34 of 87 (39%) |
| Scouting | - | 2 of 35 (6%) |
| All | 17 of 91 (19%) | 38 of 137 (28%) |

The earlier sets gave 98.5% correct and 6 of 6 declined. Against outside wording the system is far weaker.
That is the most important result of the evaluation. The failures fall into a few patterns:

1. **One wrong fallback.** 34 of the wrong answers are the same "best duo by net rating" list: questions
   of the form "who has the highest X among players who ..." are taken as a question about pairs.
2. **Conditions dropped.** Teenager, 7-footer, rookie, last-place team, "fewer than 20 minutes" and
   overtime are ignored, and the plain leader is returned instead.
3. **Wrong statistic or direction.** Totals are answered with per-game numbers, some "highest" questions
   get the lowest, and every player streak becomes the team winning streak.
4. **Declining only on known words.** A question with a player's name almost always gets that player's
   profile, even "Was he coachable?" or "Would you let your daughter marry him?". The system declines only
   when it sees a word it knows is missing ("draft", "coachable").

The 16 scouting questions that can partly be answered from statistics ("Can he guard multiple positions?")
are not scored automatically; their answers are in results/external_to_read.md for a person to judge.

Limits: the answer keys were still written here, by SQL on the raw tables; the "lead" check passes any
tied leader, so a few team questions with many ties are easy; one number was failed only by rounding
(true value 23.25, key 23.3, answer 23.2). This set has now been used too: a fix found by reading these
failures must be reported as "after seeing the set".

```text
python evaluation/run_external.py --name external    results/external.md, .json, _to_read.md
python evaluation/run_external.py --set web --reader llm   the fourth set (part 17) with the reader of part 16
python evaluation/selective.py results/external_rules.json  risk against coverage (part 19)
```

**Correction (2026-11-26).** Failure pattern 1 is not caused by "among players who": all 34 "best duo"
answers come from one alternative of a regular expression in `fact_engine._shared`, `play\w* with`,
meant for "played with" but also matching "player**s with** the highest…". None of the 34 questions is
about duos. The pattern now only takes the verb (`play(?:s|ed|ing)? with`). After seeing the set:

| Run | Answerable: correct | Should decline: declined |
|---|---|---|
| frozen run | 17 of 91 (19%) | 38 of 137 (28%) |
| after the duo fix (after seeing the set) | 20 of 91 (22%) | 38 of 137 (28%) |

The duo answers disappeared, but of the 20 answerable questions that got one, only three became right;
the other 17 now fail at the next rule (a dropped condition, the wrong statistic or direction), and the
14 that should be declined now get another answer instead. Fixing rules one by one does not generalise;
part 16 changes the reader instead.

## 15. Questions and feedback from people

The Scout page keeps every question (`ask_log`) with what the system did, unless the person switches it
off; the page says so under the question box. Under each answer: "Was this answer right?" and, for no, a
reason (wrong statistic, wrong player or team, a wrong number, should have declined) and what it should
have said (`answer_feedback`). Beside each similar player: "Is X a good match?" (`similar_feedback`).
No row names a person: no account, no address. A random number kept by the browser (`visitor`) groups
one person's answers; `ASK_LOG_SOURCE` (an environment setting, default `local`) separates a study
from development. Tables: `scripts/schema_feedback.sql`, created at startup.

```text
ASK_LOG_SOURCE=study                                   while other people use the site
python evaluation/export_asked.py --source study       their questions, for a test set with answer keys
python evaluation/judge_similarity.py --source study   the blind test of part 20
```

The questions people type are the test set that part 14 asked for, and the only one that can measure
real wording; they still need answer keys written by SQL, like the other sets, before being run.

## 16. A language model reads the question

Parts 8 and 14 show that the calculation is right when the question is understood, and that the
word-matching reader is what fails on outside wording. A language model now reads the question into a
small structured query (`stat_query.py`, a StatQuery): who is asked about (players or teams, by name, or
a group: positions, rookies, conference, a team's roster), which games (home or away, wins or losses,
months, last games, opponents), conditions ("at least 50 games", "averaging 20 points", "40 points in a
game"), what to measure (a statistic per game, in total or per 36 minutes, a sum of statistics, or a
ratio of totals such as blocks per foul) and what to do with it (rank, value, compare, count, average,
sum, list). Three kinds: season numbers, single games, and counts of games. A fourth, "other", hands
shot zones, matchups, duos, lineups, streaks, standings and similar players to the old reader, and the
model can say that a question cannot be answered, with a reason (another season or a career, playoffs,
awards or the draft, not a statistic, not recorded).

```text
question -> language model -> StatQuery (JSON that must fit a schema) -> checks -> calculation -> answer
                      \-> not answerable: declined with the reason
                      \-> "other", invalid twice, or no model: the word-matching reader (part 8)
```

The model never writes a number. `query_executor.py` checks everything in the query (names against the
season's players and teams, by surname so that "Michael Jordan" does not become Michael Porter Jr.,
statistics against the metric tables) and calculates over the same in-memory season as the fact engine.
Rates and averages use the NBA.com leaderboard minimums (58 games; FG% 300 made, 3P% 82 made, FT% 125
made), scaled to a slice of games, unless the question states a minimum of games, minutes or attempts.

The prompt (`llm_reader.py`) holds the contract, the list of statistics and ten examples written for it,
none taken from a test set. The answer must be JSON fitting the schema (structured output); a reply that
does not validate is sent back once with the error, then the old reader answers. Answers can be cached
by model, prompt version and question (`READER_CACHE`), so an evaluation can be repeated exactly.

**The chips.** On the Scout page the query is shown as chips that can be changed: kind, players or
teams, who counts, which games, conditions, measure, calculation, order and how many. "Recalculate"
sends the changed query to the executor without reading the question again. When the model declined, a
person can ask to calculate anyway. An edited answer is logged as `edited`, which also records where
readings were wrong.

**Protocol.** The StatQuery contract was written before the fourth test set was collected (part 17).
The prompt was written from the contract and tried on new questions of my own. The third set (part 14)
has been seen, so it is now development data for this reader: its numbers will be reported as such.
Results: to be filled in after the runs (they need a language model with credit).

## 17. A fourth test set, from the web

Collected on 2026-11-26 after the contract of part 16 was fixed, frozen at 21:05 UTC
(`evaluation/web_questions.py`, sha256 `260c7dc74469f27d431268c37389c5e4fb11915d7d1f6498bc6a90579c0de661`).
No system was run on it while it was collected or keyed.

| Source | Questions | What it is |
|---|---|---|
| USC text-to-SQL test file (Hugging Face) | 50 | every third of 150 questions about team games, written for another NBA database |
| StatMuse | 54 | what users typed into StatMuse, as its pages show it; every result of 12 recorded searches with one answer |
| Quizzes (Sporcle, Yardbarker) | 34 | all clues of a 2024-25 almanac and an advanced-stats quiz, and three list questions |

70 are answerable (51 checked by the first name, 13 by a number, 4 by one of several accepted numbers,
2 by every name), 64 should be declined (other seasons, playoffs, awards, data that is not kept) and 4
are left to a person. StatMuse results that ask for a whole table ("NBA player stats 2024-25"), garbled
text and near-duplicates were left out and are listed in the file. Rules were fixed before any key was
computed (in the file): no season means 2024-25, "2025" alone means 2024-25, other seasons are declined,
and an "average percentage" may be the mean of games or the season ratio.

The keys are SQL on the raw tables, as before, but several can be checked against numbers printed on
the quiz pages, which this project did not write: rebounds leader 13.9, blocks leader 2.4, FG% 70.6%,
FT% 93.3%, 3P% 45.6%, steals 3.0, most wins 68, most losses 65. All agree with the keys, including the
blocks leader, which only holds with the 58-game minimum (Wembanyama averaged more in 46 games).

Results: to be run once, with both readers, after the reader is final.

## 18. Checking who a number belongs to

Part 5's check passes a real number given to the wrong player. `grounding.misattributed` pairs every
number with the player or team named last before it, in the answer and in the sources, and flags a
number that the sources give to someone else and never to the one the answer names ("Jokić averaged
30.4" when the sources say "Giannis Antetokounmpo 30.4, Nikola Jokić 29.6"). Numbers a source states
without a name, and small whole numbers (ranks, counts below 10), are not judged, to keep false alarms
rare. The page shows "the sources give these to someone else: …".

`evaluation/run_generation.py` measures the writer (the language model that turns sources into prose):
every number in a source, no number given to the wrong owner, citations present and valid, whether the
written answer is still right when the calculated sentence it was written from was right ("broke"),
time, tokens and cost, and a sample sheet for a person to score (faithful, complete, clear, 0-2 each).
Results: to be filled in after the runs.

## 19. When to answer

Every answer now carries a confidence from 0 to 1 and the signals it was made from. The strongest is
agreement: the model's query and the old reader are asked the same question; when both name the same
leader or give the same number, they rarely share the mistake. Hand-set values (`rag_service.confidence`):
model calculated and readers agree 0.95, model calculated with nothing to compare 0.8, readers disagree
0.6, old reader calculated 0.5 (0.45 after a fallback), documents only 0.3, declined or asked back 0.
The page warns when the readers disagree, after a fallback, and for answers assembled from documents.

`evaluation/selective.py` draws risk against coverage: answering only above a confidence, how many
questions are answered (coverage) and how many of those answers are wrong (risk); AURC is the area under
that curve, lower is better. Answering a question that should be declined is wrong. It can also learn
the weight of each signal (logistic regression) on a seen set and report it on a held-out one.

The old reader on the third set (after seeing it):

| Answer when confidence is at least | Coverage | Risk |
|---|---|---|
| 0.50 (calculated answers only) | 60% | 86% |
| 0.30 (everything it answered) | 81% | 89% |

AURC 0.705. Its confidence hardly separates right from wrong: the old reader is confidently wrong on
outside wording, which is what the language-model reader has to improve. Results for it: after the runs.

## 20. Two pages for the defence

**How it works** shows the pipeline, runs one question through both readers and the four retrieval
methods side by side (part 4's finding, live: embeddings find the right document but cannot rank or
filter), and shows the headline results read from `evaluation/results`.

**Judge similar players** is a blind test of part 9. A regular player (40 games, 20 minutes) is shown
with two lists of five similar players: the learned measure and the twelve averages used before, in
random order; the page never learns which is which. People choose the list that is more alike, or "about
the same". `evaluation/judge_similarity.py` reports how often each method wins and a sign test; since
one person's answers are not independent, also per person. 10 to 15 people judging 10 players each is
enough to detect a clear preference.

## 21. Next

1. Run the language-model reader on the third set (development), then once on the fourth set, with the
   old reader alongside; fit the confidence weights on the third set and report them on the fourth.
2. Measure the writer with `run_generation.py`, and have a person score the sample.
3. Run a short study (`ASK_LOG_SOURCE=study`): questions, verdicts and blind judgments from other people.
4. Compare a larger or multilingual embedding model for paraphrases.
5. Add seasons.
