# AGENTS.md — Real Estate & Loans Content Channel

Use this file as the shared entrypoint for AI guidance.

## Project guidance
- Keep the repository organized around content pipeline scripts and reusable utilities.
- Prefer small, composable functions over large script-only functions.

## Environment notes
The following environment variables are used by the content workflow:

- BASE_CHANNEL
- BASE_CODE_DIR
- BASE_CONTENT_DIR
- VIDEO_DIR
- LONGFORM_DIR
- SHORTS_DIR
- AUDIO_DIR

## Python refactor guidance
See [docs/python-refactor.md](docs/python-refactor.md) for the Python-specific refactor pattern for making scripts reusable and composable.
