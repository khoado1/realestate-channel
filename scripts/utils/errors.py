"""Shared exception for expected pipeline-flow failures.

Library-style functions (missing input file, invalid selection, unset required
config) raise this instead of calling ``sys.exit`` directly, so a process-fatal
decision is made only at the top-level CLI entrypoint — see
docs/ai-instructions/cloud-architecture.md's failure-handling rule. Each
script's ``if __name__ == "__main__":`` block catches it and exits 1; the
message is already printed by the raiser via ``rprint``/``print`` before
raising, so no message is duplicated here.
"""


class PipelineError(Exception):
    """Raised when a script's inputs or state make it unable to proceed."""
