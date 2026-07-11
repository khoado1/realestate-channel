# CLAUDE.md — Real Estate & Loans Content Channel

This file is retained for project-specific context, but the reusable AI guidance has been split into neutral instruction files. Claude Code only auto-loads `CLAUDE.md` itself, so the files below are pulled in with `@` imports (plain markdown links are not auto-loaded):

@AGENTS.md
@docs/ai-instructions/identity-voice.md
@docs/ai-instructions/project-context.md
@docs/ai-instructions/pipeline-a.md
@docs/ai-instructions/pipeline-b.md
@docs/ai-instructions/software-architecture.md
@docs/ai-instructions/cloud-architecture.md
@docs/ai-instructions/security.md
@docs/ai-instructions/coding-style.md
@docs/python-refactor.md

## Working notes

- Keep the channel voice aligned with the identity and voice guidance.
- Keep the content workflow aligned with the project context and pipeline instructions.
- Keep code changes aligned with the software-architecture, cloud-architecture, security, and
  coding-style instructions — these are always-on because they should shape every diff, not just
  SaaS/infra work. Deeper situational references (e.g. [platform-architecture.md](docs/platform-architecture.md),
  the full target-state SaaS design) are linked from those files rather than imported here, to
  avoid loading their full depth into every session.
- Update the relevant instruction files when new corrections or workflow decisions are learned.
- Future domain guidance (testing, API design, etc.) should default to situational reference docs
  rather than blanket `@` imports, unless it's foundational enough to warrant being always-on like
  the four above.

