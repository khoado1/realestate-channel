import os


def run() -> int:
    vars_to_check = {
        "BASE_CONTENT_DIR": os.getenv("BASE_CONTENT_DIR"),
        "CHANNEL_NAME": os.getenv("CHANNEL_NAME"),
        "CHANNEL_ID": os.getenv("CHANNEL_ID"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY"),
        "POSTIZ_API_KEY": os.getenv("POSTIZ_API_KEY"),
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY"),
        "HEYGEN_API_KEY": os.getenv("HEYGEN_API_KEY"),
    }

    for key, value in vars_to_check.items():
        if not value:
            print(f"  ✗ {key}: MISSING")
        elif "KEY" in key:
            print(f"  ✓ {key}: set")
        else:
            print(f"  ✓ {key}: {value}")

    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
