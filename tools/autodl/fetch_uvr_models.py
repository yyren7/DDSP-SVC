"""
Download the UVR models used by tools/prepare_dataset.py (model files, yaml configs and UVR's
model-data json files) into --model-dir, so the uvr job never needs the network.
audio-separator's own download step fetches exactly what each listed model needs; the models it does
not list (prepare_dataset.EXTRA_MODELS) come from Hugging Face, through hf-mirror.com first. The
weights are never loaded, so this fits in the 2 GB memory limit of a no-GPU instance.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prepare_dataset import DEFAULT_MODELS, EXTRA_MODELS, extra_yaml, register_extra_models  # noqa: E402

HF_HOSTS = ['https://hf-mirror.com', 'https://huggingface.co']


def download(url, dest):
    """url -> dest through dest.part, so an interrupted download never looks finished."""
    import requests
    part = dest.with_name(dest.name + '.part')
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, 'wb') as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    part.replace(dest)
    print(f'   {dest.name}: {dest.stat().st_size / 1e6:.0f} MB from {url}', flush=True)


def fetch_extra(model, model_dir):
    repo, ckpt, yaml = EXTRA_MODELS[model]
    for src, name in ((ckpt, model), (yaml, extra_yaml(model))):
        dest = model_dir / name
        if dest.exists():
            continue
        for host in HF_HOSTS:
            url = f'{host}/{repo}/resolve/main/{src}'
            try:
                download(url, dest)
                break
            except Exception as e:  # network errors and HTTP errors alike: try the next host
                print(f'   {url}: {e}', flush=True)
        else:
            sys.exit(f'could not download {name} from {repo}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('models', nargs='*', help='model filenames (default: the ones prepare_dataset.py uses)')
    args = p.parse_args()
    if importlib.util.find_spec('audio_separator') is None:
        sys.exit('audio-separator is not installed in this environment')
    from audio_separator.separator import Separator
    register_extra_models(Separator)

    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    separator = Separator(model_file_dir=str(model_dir), output_dir=str(model_dir), log_level=30)
    for model in args.models or list(DEFAULT_MODELS.values()):
        print(f'== {model}', flush=True)
        if model in EXTRA_MODELS:
            fetch_extra(model, model_dir)
        _, _, _, model_path, yaml_config = separator.download_model_files(model)
        # what load_model reads before the weights: the yaml config, or UVR's model-data json
        if model_path.lower().endswith('.yaml'):
            yaml_config = model_path
        if yaml_config is not None:
            separator.load_model_data_from_yaml(yaml_config)
        else:
            separator.load_model_data_using_hash(model_path)
    print('all UVR models ready', flush=True)


if __name__ == '__main__':
    main()
