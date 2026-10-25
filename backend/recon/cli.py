import argparse
import json
import logging
from pathlib import Path

from recon.config import Settings
from recon.errors import ReconError
from recon.storage.artifacts import atomic_json, read_json


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="recon", description="Local static binary analysis. Targets are never executed."
    )
    parser.add_argument("--data-dir", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve the local API and built interface")
    serve.add_argument("--port", type=int, default=8000)
    analyze = commands.add_parser(
        "analyze", help="Analyze a binary in the constrained parser process"
    )
    analyze.add_argument("file", type=Path)
    analyze.add_argument("--output", type=Path)
    dataset = commands.add_parser("dataset", help="Build the pinned, licensed source dataset")
    dataset.add_argument("action", choices=["build", "audit"])
    dataset.add_argument("--offline", action="store_true")
    train_parser = commands.add_parser(
        "train", help="Train the CPU pilot model using project-disjoint data"
    )
    train_parser.add_argument("--epochs", type=int, default=30)
    train_parser.add_argument("--seed", type=int, default=42)
    train_parser.add_argument("--resume", action="store_true")
    eval_parser = commands.add_parser(
        "evaluate", help="Evaluate frozen test projects after model selection"
    )
    eval_parser.add_argument("--baseline-only", action="store_true")
    eval_parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings(**({"data_dir": args.data_dir} if args.data_dir else {}))
    try:
        if args.command == "serve":
            import uvicorn

            from recon.api.app import create_app

            logging.basicConfig(
                level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
            )
            uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, workers=1)
        elif args.command == "analyze":
            from recon.security.process import run_analysis

            result = run_analysis(args.file, settings).model_dump()
            if args.output:
                atomic_json(args.output, result)
            else:
                print(json.dumps(result, indent=2))
        elif args.command == "dataset":
            from recon.ml.dataset import build_dataset, validate_dataset

            if args.action == "build":
                print(build_dataset(settings, offline=args.offline))
            else:
                print(
                    json.dumps(
                        validate_dataset(read_json(settings.root / "research/dataset.json")),
                        indent=2,
                    )
                )
        elif args.command == "train":
            from recon.ml.research import train

            if not 1 <= args.epochs <= 200 or not 0 <= args.seed <= 2147483647:
                parser.error("Use 1–200 epochs and a nonnegative 32-bit seed")
            result = train(
                read_json(settings.root / "research/dataset.json"),
                settings.root,
                args.epochs,
                args.seed,
                resume=args.resume,
            )
            atomic_json(settings.root / "research/training-report.json", result)
            print(json.dumps(result, indent=2))
        elif args.command == "evaluate":
            from recon.ml.dataset import validate_dataset
            from recon.ml.model import load_model
            from recon.ml.research import evaluate

            data = read_json(settings.root / "research/dataset.json")
            audit = validate_dataset(data)
            model = None if args.baseline_only else settings.root / "models/current"
            if model and load_model(model)[2]["dataset_hash"] != data["dataset_hash"]:
                raise ReconError(
                    "MODEL_DATASET_MISMATCH", "Use the model's original frozen dataset."
                )
            result = evaluate(data["samples"], model_package=model)
            result.update(
                {
                    "dataset_hash": data["dataset_hash"],
                    "audit": audit,
                    "environment": data["environment"],
                    "missing_toolchains": data["missing_toolchains"],
                    "dataset_limitations": data["limitations"],
                }
            )
            target = args.output or settings.root / "research/evaluation-report.json"
            atomic_json(target, result)
            print(
                json.dumps(
                    {
                        "report": str(target),
                        "metrics": {
                            k: {n: v for n, v in m.items() if n != "subgroups"}
                            for k, m in result["methods"].items()
                        },
                    },
                    indent=2,
                )
            )
    except (ReconError, FileNotFoundError) as exc:
        parser.exit(1, f"{getattr(exc, 'code', 'FILE_MISSING')}: {exc}\n")


if __name__ == "__main__":
    main()
