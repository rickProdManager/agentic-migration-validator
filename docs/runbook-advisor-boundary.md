# Runbook Advisor Boundary

The runbook advisor is allowed to make migration findings easier to understand, but it is not allowed to decide safety. Deterministic detectors, data checks, and gatekeeper results remain the source of truth.

## Boundary Rule

Every advisor claim must be traceable to structured evidence. If the available findings, data checks, or gate results do not support a claim, the advisor must say `insufficient evidence`.

The advisor has three tiers of behavior.

## Tier 1: Restatement

Restatement has no judgment latitude. The advisor may convert structured data into prose, but it must not add causes, impacts, or remediation claims that are not present in the source record.

Allowed:

- Restate a finding summary.
- List a blocking finding key from `gate_results`.
- State whether `can_recommend_cutover` or `can_mark_ready` is allowed.

Required support:

- Finding summaries cite the finding evidence refs.
- Gate status claims cite the gate result evidence ref.

## Tier 2: Recommendation

Recommendations may synthesize next steps, but only from deterministic gate results and finding metadata.

Allowed:

- Recommend not proceeding with cutover when `can_recommend_cutover.allowed` is `false`.
- Recommend not marking ready when `can_mark_ready.allowed` is `false`.
- Recommend resolving or accepting specific blocking finding keys.
- Recommend rerunning validation after remediation.

Not allowed:

- Recommend cutover because the advisor thinks the findings are acceptable.
- Override a blocked gate.
- Treat compatibility advisory findings as PostgreSQL cutover blockers.

Required support:

- Safety recommendations cite the relevant `gate_results` entry.
- Remediation recommendations cite the relevant blocking finding keys and evidence refs.

## Tier 3: Contextualization

Contextualization is the dangerous tier because it is where unsupported causal stories can appear. The advisor may explain why a class of issue matters only when the explanation is templated from known detector semantics or directly supported by finding content.

Allowed:

- Explain that a checksum mismatch means canonical source and target table digests differ.
- Explain that a failed duplicate check means target data contains duplicate values after a unique constraint was relaxed.
- Explain that a blocked gate prevents readiness or cutover in the workflow.

Not allowed:

- Claim the root cause of a mismatch unless a deterministic finding provides that cause.
- Claim business impact that is not present in structured evidence.
- Claim data loss, corruption, or safety unless the relevant finding or gate result supports that exact claim.

Fallback:

- When evidence is missing or too weak, the advisor must say `insufficient evidence`.

## Enforcement

The runbook generator uses these rules before any draft can pass boundary validation:

- It mirrors `gate_results` for cutover/readiness recommendations.
- It cites finding evidence refs for finding summaries.
- It refuses to assert readiness without gate evidence.
- It emits structured claims with claim type and evidence refs.
- It rejects unsupported causal language in contextualization claims.

Model-backed advisors must preserve this contract. Model prose can improve clarity, but deterministic gates remain load-bearing.

## Live Model Boundary

Live model prose is opt-in through `RUNBOOK_MODEL_CALLS=enabled`. The default runbook path remains deterministic and model-disabled.

The live path first builds a deterministic runbook draft, then asks the model for one short narrative paragraph using only that JSON evidence. The returned prose is added as a `contextualization` claim and validated with the same boundary checker before it can pass.

The boundary checker must catch more than missing references. A model paragraph can cite real evidence and still overreach semantically. For example, a checksum mismatch supports "source and target canonical digests differ"; it does not by itself support "data corruption during transfer." Protected causal phrases such as root cause, data corruption, data loss, and transfer failure are rejected unless deterministic evidence already contains that exact support.

This keeps the advisor in tier three from turning a valid evidence reference into an unsupported causal story.
