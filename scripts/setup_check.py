from scripts.utils.verification import (
    check_doppler_auth,
    check_doppler_cli,
    check_env_var,
    check_python_module,
    render_statuses,
)


def run() -> int:
    print("Checking Python deps...")
    statuses = [
        check_python_module("dotenv", "python-dotenv"),
        check_python_module("requests"),
        check_python_module("rich"),
        check_python_module("youtube_transcript_api", "youtube-transcript-api"),
        check_python_module("dateutil", "python-dateutil"),
    ]
    render_statuses(statuses)

    print("")
    print("Checking Doppler...")
    render_statuses([check_doppler_cli(), check_doppler_auth()])

    print("")
    print("Checking paths...")
    render_statuses([check_env_var("BASE_CONTENT_DIR"), check_env_var("SCRIPTS_DIR")])

    print("")
    print("Setup complete. Run 'make dirs' to create content folders, then 'make help'.")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
