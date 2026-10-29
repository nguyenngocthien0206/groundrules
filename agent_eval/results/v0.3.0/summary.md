# Agent eval: v0.3.0

| | actions | raw_actions |
| --- | --- | --- |
| Correct (the right transfer, or none) | 100% (100% to 100%) | 88% (62% to 100%) |
| Safe (nothing filed that breaks DR-012) | 100% (100% to 100%) | 100% (100% to 100%) |
| Right reason, when none is due | 100% (100% to 100%) | 75% (25% to 100%) |
| Runs that filed an unsafe transfer | 0 of 24 | 0 of 24 |
| Correct, proposal | 100% of 4 | 75% of 4 |
| Correct, no_proposal | 100% of 4 | 100% of 4 |
| Graded answers | 24 on 8 questions | 24 on 8 questions |
| Open errors | 0 | 0 |
| Median tool calls | 2.0 | 13.0 |
| Median seconds | 26.5 | 23.8 |
| Model | claude-sonnet-5-5 | claude-sonnet-5-5 |
| Tokens in / out | 255,627 / 10,534 | 1,094,717 / 49,854 |
| API-equivalent cost | $0.31 | $1.87 |

Rates are means over questions; brackets are 95% bootstrap intervals over questions.
API-equivalent cost is the provider's estimate for the same tokens on the Claude API; a run on a
subscription is not billed per token.
