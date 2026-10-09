"""
Download the UVR models used by tools/prepare_dataset.py (model files, yaml configs and UVR's
model-data json files) into --model-dir, so the uvr job never needs the network.
Loading each model once through audio-separator makes it fetch exactly what it needs.
"""
import argparse
import importlib.util
import sys
from pathlib import Path


def default_models():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from prepare_dataset import DEFAULT_MODELS
    return list(DEFAULT_MODELS.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('models', nargs='*', help='model filenames (default: the ones prepare_dataset.py uses)')
    args = p.parse_args()
    if importlib.util.find_spec('audio_separator') is None:
        sys.exit('audio-separator is not installed in this environment')
    from audio_separator.separator import Separator

    Path(args.model_dir).mkdir(parents=True, exist_ok=True)
    separator = Separator(model_file_dir=args.model_dir, output_dir=args.model_dir, log_level=30)
    for model in args.models or default_models():
        print(f'== {model}', flush=True)
        separator.load_model(model_filename=model)
    print('all UVR models ready', flush=True)


if __name__ == '__main__':
    main()
