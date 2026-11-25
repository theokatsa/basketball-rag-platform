| Method | P@6 | R@6 | MRR | nDCG@6 | Success@6 | Median ms | p95 ms |
|---|---|---|---|---|---|---|---|
| keyword | 0.120 | 0.401 | 0.333 | 0.336 | 0.438 | 200 | 255 |
| vector | 0.130 | 0.490 | 0.443 | 0.441 | 0.562 | 464 | 814 |
| hybrid | 0.138 | 0.450 | 0.445 | 0.413 | 0.562 | 482 | 827 |
| rules | 0.688 | 0.875 | 0.896 | 0.870 | 0.938 | 318 | 505 |
| planned | 0.698 | 0.885 | 0.911 | 0.880 | 0.969 | 331 | 507 |

nDCG@6 by question type:

| Type | n | keyword | vector | hybrid | rules | planned |
|---|---|---|---|---|---|---|
| ranking | 4 | 0.048 | 0.048 | 0.076 | 0.920 | 0.920 |
| filter | 5 | 0.000 | 0.059 | 0.149 | 0.971 | 0.971 |
| team | 5 | 0.134 | 0.200 | 0.059 | 1.000 | 1.000 |
| shooting | 3 | 0.710 | 0.877 | 0.877 | 1.000 | 1.000 |
| matchup | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pairs | 2 | 0.500 | 0.815 | 0.500 | 1.000 | 1.000 |
| form | 2 | 0.750 | 1.000 | 0.815 | 1.000 | 1.000 |
| game | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| lookup | 3 | 0.421 | 0.734 | 0.834 | 1.000 | 1.000 |
| paraphrase | 4 | 0.000 | 0.038 | 0.027 | 0.075 | 0.155 |

Unanswerable questions declined: 6 of 6

- declined: Who won the 1998 NBA Finals?
- declined: What is LeBron James's salary?
- declined: How many points did Michael Jordan average in 1990-91?
- declined: Who will win MVP next year?
- declined: What is the capital of France?
- declined: Which WNBA player leads in assists?
