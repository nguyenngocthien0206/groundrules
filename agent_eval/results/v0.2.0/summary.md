# Agent eval: v0.2.0

| | raw_sql | semantic |
| --- | --- | --- |
| Correct | 8% (0% to 18%) | 99% (97% to 100%) |
| Right number | 13% (3% to 27%) | 99% (97% to 100%) |
| Right caveats | 52% (36% to 70%) | 100% (100% to 100%) |
| Correct, tacit_rule | 11% of 21 | 98% of 21 |
| Correct, conflict | 0% of 2 | 100% of 2 |
| Correct, caveat_required | 0% of 5 | 100% of 5 |
| Correct, deprecated | 0% of 2 | 100% of 2 |
| Graded answers | 90 on 30 questions | 90 on 30 questions |
| Open errors | 0 | 0 |
| Median tool calls | 5.0 | 2.5 |
| Median seconds | 31.5 | 42.0 |
| Model | claude-sonnet-5-5 | claude-sonnet-5-5 |
| Tokens in / out | 1,854,547 / 90,722 | 1,104,327 / 37,062 |
| API-equivalent cost | $2.84 | $1.37 |

Rates are means over questions; brackets are 95% bootstrap intervals over questions.
API-equivalent cost is the provider's estimate for the same tokens on the Claude API; a run on a
subscription is not billed per token.
