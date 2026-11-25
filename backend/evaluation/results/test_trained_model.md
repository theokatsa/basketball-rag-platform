| Method | P@6 | R@6 | MRR | nDCG@6 | Success@6 | Median ms | p95 ms |
|---|---|---|---|---|---|---|---|
| keyword | 0.120 | 0.401 | 0.333 | 0.336 | 0.438 | 204 | 244 |
| vector | 0.117 | 0.427 | 0.414 | 0.410 | 0.469 | 468 | 788 |
| hybrid | 0.126 | 0.464 | 0.423 | 0.411 | 0.531 | 474 | 854 |
| rules | 0.682 | 0.870 | 0.891 | 0.866 | 0.906 | 340 | 471 |
| planned | 0.714 | 0.901 | 0.922 | 0.898 | 0.938 | 352 | 476 |

nDCG@6 by question type:

| Type | n | keyword | vector | hybrid | rules | planned |
|---|---|---|---|---|---|---|
| ranking | 4 | 0.048 | 0.000 | 0.076 | 0.920 | 0.920 |
| filter | 5 | 0.000 | 0.000 | 0.000 | 0.971 | 0.971 |
| team | 5 | 0.134 | 0.300 | 0.106 | 1.000 | 1.000 |
| shooting | 3 | 0.710 | 1.000 | 1.000 | 1.000 | 1.000 |
| matchup | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pairs | 2 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 |
| form | 2 | 0.750 | 1.000 | 1.000 | 1.000 | 1.000 |
| game | 2 | 1.000 | 0.991 | 1.000 | 1.000 | 1.000 |
| lookup | 3 | 0.421 | 0.217 | 0.440 | 1.000 | 1.000 |
| paraphrase | 4 | 0.000 | 0.000 | 0.000 | 0.048 | 0.298 |

Unanswerable questions declined: 6 of 6

- declined: Who won the 1998 NBA Finals?
- declined: What is LeBron James's salary?
- declined: How many points did Michael Jordan average in 1990-91?
- declined: Who will win MVP next year?
- declined: What is the capital of France?
- declined: Which WNBA player leads in assists?
