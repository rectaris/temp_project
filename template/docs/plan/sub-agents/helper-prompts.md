# Helper Prompt Templates

Use these templates for repeatable helper prompts. Keep each request bounded and task-specific.

## Read-Only Exploration

```md
Objective:
Read scope:
Questions:
Return:
- concise findings
- relevant paths or symbols
- risks or open questions
```

## Scoped Implementation

```md
Objective:
Write scope:
Read scope:
Constraints:
Validation:
Return:
- changed paths
- implementation summary
- validation run or blocked
- risks
```

## Change Review

```md
Objective:
Changed paths:
Review focus:
Validation context:
Return:
- findings ordered by severity
- missing validation
- residual risk
```
