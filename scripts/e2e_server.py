"""Isolated browser-test server. It only removes its own generated test data."""

import shutil

import uvicorn
from build_fixtures import ROOT, build
from recon.api.app import create_app
from recon.config import Settings

root = ROOT / ".recon/e2e"
if root.is_symlink():
    raise RuntimeError("Refusing a symlink at the browser-test data directory")
if root.exists():
    shutil.rmtree(root)
build(root / "fixtures")
uvicorn.run(create_app(Settings(data_dir=root)), host="127.0.0.1", port=8001)
