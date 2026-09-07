# Independent Natural-Japanese Comparison

Evaluate one frozen scenario with its baseline and adapted outputs.

Report every scenario requirement as `pass`, `fail`, `partial`, or `not_applicable`.
Check facts, quotations, uncertainty, code blocks, requested format, and project terms separately.
Treat invented experience, motive, emotion, preference, or certainty as a critical failure.
For the code-only holdout, any added Japanese prose or prose-rewriting workflow is a critical failure.

Choose `adapted_better` only when the adapted output is materially clearer or more natural without protected-content drift.
Choose `equivalent` when neither output is materially worse.
Reject the comparison if the outputs use different models, the evaluator shares either generation session, or the holdout was used for tuning.

Record the evaluator identity, evaluator session identity, unclear points, discretionary assumptions, retries, and tool or time notes.
