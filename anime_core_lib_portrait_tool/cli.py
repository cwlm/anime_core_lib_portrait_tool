"""Arguments for the single-image and CSV scripts."""
import argparse
import os
from pathlib import Path


def arguments(batch=False, argv=None):
    parser = argparse.ArgumentParser()
    if batch:
        parser.add_argument("csv", type=Path)
    else:
        parser.add_argument("mode", choices=("auto", "manual"))
        parser.add_argument("--input", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--encoder", required=True, choices=("nvtt", "texconv"))
    parser.add_argument("--encoder-path", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model-cache", type=Path)
    args = parser.parse_args(argv)
    if args.model_cache:
        os.environ["HF_HUB_CACHE"] = str(args.model_cache.resolve())
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    return args


def main(argv=None):
    args = arguments(argv=argv)
    if args.mode == "auto":
        from .auto import prepare
    else:
        from .manual import prepare
    try:
        saved = prepare(args.input, args.output, encoder=args.encoder,
                        encoder_path=args.encoder_path, overwrite=args.overwrite)
        print("已保存" if saved else "需手动处理或已取消")
        return 0 if saved else 2
    except Exception as exc:
        print(f"失败：{exc}")
        return 1


def batch_main(argv=None):
    from .batch import run_batch
    args = arguments(batch=True, argv=argv)
    try:
        return 0 if run_batch(args.csv, encoder=args.encoder,
                             encoder_path=args.encoder_path, overwrite=args.overwrite) else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"失败：{exc}")
        return 1
