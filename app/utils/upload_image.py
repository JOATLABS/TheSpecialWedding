import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from app.services.media_storage import MediaStorage, StorageTarget


def upload_image(local_path: str, folder: str = "gallery") -> str:
    storage = MediaStorage()
    filename = os.path.basename(local_path)
    key = f"{folder}/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{filename}"

    with open(local_path, "rb") as file_handle:
        storage.upload_fileobj(file_handle, StorageTarget.PRIMARY, key)

    return storage.build_public_url(StorageTarget.PRIMARY, key)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload an image to the primary gallery media bucket."
    )
    parser.add_argument("local_path", help="Path to the image file to upload.")
    parser.add_argument(
        "--folder",
        default="gallery",
        help="Storage folder prefix inside the primary media bucket.",
    )
    args = parser.parse_args()

    local_path = Path(args.local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File does not exist: {local_path}")

    public_url = upload_image(str(local_path), folder=args.folder)
    print(public_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
