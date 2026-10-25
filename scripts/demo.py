"""Start the offline demo after installing dependencies and building the UI."""

import argparse
import importlib.util
import shutil

import uvicorn
from recon.api.app import create_app
from recon.config import REPO_ROOT, Settings


def prepare(settings: Settings) -> None:
    settings.root.mkdir(parents=True, exist_ok=True)
    target = settings.root / "fixtures"
    target.mkdir(parents=True, exist_ok=True)
    for source in (REPO_ROOT / "tests/fixtures/compiled").iterdir():
        if source.is_file():
            shutil.copyfile(source, target / source.name)
            (target / source.name).chmod(0o600)
    pilot = REPO_ROOT / "models/pilot"
    current = settings.root / "models/current"
    if pilot.is_dir() and not current.exists() and importlib.util.find_spec("torch"):
        destination = settings.root / "models/installed-pilot"
        shutil.copytree(pilot, destination, dirs_exist_ok=True)
        current.symlink_to("installed-pilot", target_is_directory=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    prepare(settings)
    if not args.prepare_only:
        print(
            "RECON is available at http://127.0.0.1:8000. Imported binaries are never executed.",
            flush=True,
        )
        uvicorn.run(create_app(settings), host="127.0.0.1", port=8000)
