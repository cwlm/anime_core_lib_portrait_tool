"""Arguments for single-image processing."""
import argparse
import os
from pathlib import Path
from .config import load_layout


def arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("auto", "manual"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--encoder", required=True, choices=("nvtt", "texconv"))
    parser.add_argument("--encoder-path", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--layout", type=Path, help="JSON canvas and composition settings")
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
                        encoder_path=args.encoder_path, layout=load_layout(args.layout), overwrite=args.overwrite)
        print("已保存" if saved else "需手动处理或已取消")
        return 0 if saved else 2
    except Exception as exc:
        print(f"失败：{exc}")
        return 1
