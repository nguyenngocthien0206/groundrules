# Actions

A metric answers a question. An action changes something: here, it moves
stock from one store to another. The semantic layer made sure an agent
gives the certified number; an action contract makes sure an agent can
only propose what the business has agreed to, and that a person signs off
before anything moves.

Each file here is the contract for one action. It names:

- **who owns it** (`owner`): the team that must review any change to the
  file, enforced through CODEOWNERS, exactly like a metric's rules;
- **who approves each proposal** (`approver`): the people allowed to turn
  a proposal into a real request;
- **why the rules are what they are** (`decision`): an accepted decision
  record, with a worked example from real rows;
- **what it reads** (`reads`): certified metrics pinned at a version, the
  hidden building blocks inside them it needs, and the marts it joins;
- **the rules as numbers** (`rules`), **what a proposal carries**
  (`proposal`) and **what is written after approval** (`writes`);
- **what an agent must say** (`agent_notes`).

## What the lint guarantees
`make lint` fails when:

- the owner or approver is not a dbt group with a GitHub team;
- the decision record is missing, not accepted, or does not list the
  action under `linked_actions`;
- a pinned metric is no longer certified, or has moved to a new version.
  The rule was checked against the old definition, so someone who owns it
  has to look again before agents act on the new one;
- a building block is not inside one of the pinned metrics, or a model is
  missing or has no enforced contract;
- the rules contradict each other, for example a target allowed to end
  with more cover than a donor needs to start with, so that stock could
  be sent back and forth;
- CODEOWNERS does not give the file to exactly its owner's team, or
  CHANGELOG.md has no entry for the current version.

## Why it is built this way
An agent that can write is a new kind of risk, and the answer is the same
one the repo gives for numbers: the rule lives in one reviewed file, the
reason lives in a decision record, and an independent reference
(`golden/reference/transfer_candidates.sql`) computes the expected
proposals from the raw extracts, so the agent's tool can be checked
against it. Changing a threshold costs one pull request that the owning
team approves. It never takes a code change in the agent.

| Action | Owner | Decision |
| --- | --- | --- |
| [propose_transfer](propose_transfer.yml) | supply_chain_ops | [DR-012](../decisions/DR-012.md) |
