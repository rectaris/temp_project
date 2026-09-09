# Let the verification helper accept the remote _src_path every real downstream project records, and check a release candidate against those recorded baselines before it is tagged

status: checked
primary_invariant: A downstream project whose recorded template source is a remote address is verified against its real baseline rather than refused, and a release candidate is checked against every recorded downstream baseline before it is tagged.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"All three downstream projects record _src_path as an https URL. The helper treats that value as a relative path, so Path(value).is_absolute() is false, the value is joined under the target clone, and the run stops as source_path_overlap before any update is attempted. The shipped skill therefore refuses every real downstream project it was written for.","kind":"reproduced_defect"}
  - {"evidence":"The helper already resolves the isolated source through one recorded path value and already runs every escape, overlap and scratch check against it, so substituting one fixed workspace-relative path for a remote value reuses those checks unchanged instead of adding a second path model.","kind":"existing_mechanism"}
  - {"evidence":"The helper already writes one machine-readable manifest and the committed triage table already resolves that manifest to one owner and next action, so an aggregate runner over several projects needs no new judgment, only a loop and a non-zero exit.","kind":"existing_mechanism"}
  - {"evidence":"Running the new aggregate runner against a real baseline reported source_dirty with owner project, although the dirty repository was this template repository. Every source-side suffix carried the target-side owner, so a template-side fault was routed to the downstream project that merely observed it.","kind":"reproduced_defect"}
completion_conditions:
  - A baseline whose recorded _src_path is a URL or an scp-style address is verified against the isolated source checkout, and the manifest records both the recorded remote value and the substituted isolated path.
  - A baseline whose recorded _src_path is a local relative path keeps its original baseline commit and its existing escape, overlap and scratch refusals.
  - A reason code shared by both repositories under comparison resolves to the repository the subject names, so a source-side fault reports the template and a target-side fault reports the project.
  - The committed baseline record names every downstream project with its own validation commands, and the aggregate runner reports each one and exits non-zero unless all of them verify.
  - A baseline record that cannot be acted on, an unrecorded project name, an occupied output directory or an absent checkout stops the runner with a named reason instead of a silently skipped project.
completion_witness_map:
  - {"condition_sha256":"sha256:f791c74f3e69f8052ea0769d35d2d497d8c304870b7db6376486df4ef4e1fa62","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:20e02ce55bd400593599a8f4083bbd2c051a2ef62895e76adbd6a16c689c79ee","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:2edc7ffe73ce06079bec0264d3beaefa8be37589c2b19ec487677c67ac5241b1","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:d57f66e070ac6b3bfc683f18e2edb925b9f676f7b079f174b74561029d7ef3de","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:3fbd468160fa593e1c6630c90f621f09904eb8b659ffda9b991f89fafa3d6cf5","witness":"python3 tests/test-verify-copier-update.py"}
write_scope:
  - .codex/skills/verify-copier-update/scripts/verify-copier-update.py
  - .codex/skills/verify-copier-update/references/verification-contract.md
  - .codex/skills/verify-copier-update/references/update-triage.yaml
  - .codex/skills/verify-copier-update/scripts/triage-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/references/verification-contract.md
  - template/.project-agent-workflow/skills/verify-copier-update/references/update-triage.yaml
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/triage-copier-update.py
  - docs/downstream-baselines.yaml
  - scripts/verify-downstream-baselines.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/lint-project-workflow.sh
  - tests/test-verify-copier-update.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/external-services.yaml
  - scripts/check-copier-template.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - references/validation.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The three downstream projects this repository serves can be verified as they are actually recorded, without editing their answer files first.
  - A release candidate is checked against every recorded downstream baseline from one command whose exit status decides whether the tag may be created, and each reported outcome names the party who can act on it.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:312031507c07bf0b906d9da283743c8b5f980cd09d919a5061a446ad3787bf3d","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
  - {"acceptance_sha256":"sha256:4bd2e1fea37b4945131860f3752d759b4e18bd675c42b1e855d247482470890f","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
checked_summary_ja: 実在の下流プロジェクトが記録している遠隔 _src_path を検証ツールが扱えるようにし、公開前に記録済みの基線へ候補を当てて確かめる

## Decisions

- Place the isolated source at one fixed path beside the target clone and commit that path into the clone's answer file, rather than teaching the helper to fetch the remote, because the verification must describe the source commit this repository is about to publish and a fetch would describe whatever the remote already holds.
- Commit the substituted path inside the clone rather than leaving it uncommitted, because Copier refuses to update a dirty repository, and then compare the post-update head against that commit rather than against the downstream baseline, so the substitution cannot be mistaken for a change the update made.
- Record both the remote value and the substituted path in the manifest, so a reader can tell that the verified relationship is not the one the project records and can judge the difference instead of inheriting it silently.
- Keep the existing refusals for local values unchanged, because a local path that escapes the workspace is still a real hazard and remote support must not widen what a local value may do.
- Give every subject in the triage table its own owner and let a shared suffix take the owner from its subject, because the same fault means different things on the two sides of the comparison and reporting a template fault to a downstream project sends the report to someone who cannot act on it.
- Keep an explicit per-subject override for the suffixes that describe a path the caller supplied, so a bad command-line argument is still reported to the caller rather than to either repository.
- Record the downstream baselines in committed data rather than in the runner, because the set of served projects changes without the verification logic changing.
- Resolve a recorded relative path against the main worktree's parent rather than against the current directory, because this repository's own work happens in linked worktrees that sit nowhere near the downstream checkouts.
- Report every baseline and exit non-zero unless all of them verify, rather than stopping at the first failure, because a release decision needs the whole picture and a partially checked candidate must not look checked.
- Keep the runner and the baseline record out of the template, because they name real projects that this repository serves and a generated project must not inherit another project's facts.

## Tasks

- [x] Accept a remote _src_path by verifying against an isolated source checkout placed beside the target clone, and record both the recorded and the substituted value.
- [x] Compare the post-update and post-validation head against the clone's own baseline, so the committed substitution is not read as an update effect.
- [x] Give each triage subject its own owner, resolve a shared suffix through its subject, and keep a per-subject override for caller-supplied paths.
- [x] Record the downstream baselines and add an aggregate runner that reports every one of them and exits non-zero unless all verify.
- [x] Register the new files, run the skill tests from the repository lint, and run the authoritative suite once.

## Validation Notes

`python3 tests/test-verify-copier-update.py` は73件すべて成功し、`scripts/lint-project-workflow.sh` も通過した。lint の出力に現れる `root agent policy check failed:` は否定試験が期待する出力である。

遠隔判定は Copier 本体の規則を写した。`copier._vcs.get_repo` の別名書き換え、接頭辞、接尾辞をそのまま実装し、そのうえで網を経由する住所だけを置換対象とした。この二段構えにより、`/srv/template.git` や `file:///srv/template.git` のようにこの計算機の中にあるリポジトリは経路として扱われ、絶対・逸脱・重複の拒否を従来どおり受ける。

記録の各項目は検証前に実物と突き合わせる。走らせた結果、記録していた origin が3件とも誤りで、`supportcard-status` の追跡先が `calc-sapo` という別名であることが判明したため、実測値に直した。`baseline_ref` は一度だけ commit に解決し、以後の読み取りと `--target-ref` の両方でその commit を使う。動く枝が検査と検証の間にずれることはない。

`v1.4.5` を候補として3件すべてに対して実行した。記録検査は3件とも通過し、残る阻害は本作業木の未コミット変更による `source_dirty`（所有者はテンプレート）と、`gakumasu-timeline` の作業木汚れによる `target_dirty`（所有者はプロジェクト）である。同じ接尾辞が主語に応じて別の責任主体を指すことを実データで確認した。

読み取り専用の独立レビューを2巡使った。1巡目の指摘3件、2巡目の指摘5件をすべて受け入れて修正したが、2巡目の修正自体は独立レビューを経ていない。
