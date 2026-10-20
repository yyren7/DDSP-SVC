"""
Download a large file in parallel byte ranges. A single connection from AutoDL to hf-mirror.com / the
Hugging Face xet storage gives about 0.3 MB/s; many ranges at once add up. Standard library only.

    python tools/autodl/fetch_parallel.py <url> <dest> [parts]

The redirect (hf-mirror -> signed xet URL) is resolved once; every part is retried until complete; the
file appears under <dest> only when all bytes are there.
"""
import sys
import threading
import time
import urllib.request
from pathlib import Path


def resolve(url):
    """(final url, size) after redirects, from a 1-byte range request."""
    req = urllib.request.Request(url, headers={'Range': 'bytes=0-0', 'User-Agent': 'fetch_parallel'})
    with urllib.request.urlopen(req, timeout=60) as r:
        size = int(r.headers['Content-Range'].rsplit('/', 1)[1])
        return r.geturl(), size


def fetch_part(url, path, start, end, done, lock):
    have = path.stat().st_size if path.exists() else 0
    while start + have <= end:
        req = urllib.request.Request(url, headers={'Range': f'bytes={start + have}-{end}',
                                                   'User-Agent': 'fetch_parallel'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(path, 'ab') as fp:
                while True:
                    buf = r.read(1 << 16)
                    if not buf:
                        break
                    fp.write(buf)
                    have += len(buf)
                    with lock:
                        done[0] += len(buf)
        except OSError:
            time.sleep(2)  # the signed URL stays valid for an hour; reconnect and go on from `have`


def main():
    url, dest = sys.argv[1], Path(sys.argv[2])
    parts = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    final, size = resolve(url)
    step = -(-size // parts)
    tmp = [dest.with_name(f'{dest.name}.part{i}') for i in range(parts)]
    done, lock, t0 = [sum(p.stat().st_size for p in tmp if p.exists())], threading.Lock(), time.time()
    threads = [threading.Thread(target=fetch_part, args=(final, p, i * step, min(size, (i + 1) * step) - 1, done, lock),
                                daemon=True) for i, p in enumerate(tmp)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(10)
        print(f'{dest.name}: {done[0] / 1e6:.0f} / {size / 1e6:.0f} MB, {done[0] / 1e6 / (time.time() - t0):.1f} MB/s',
              flush=True)
    got = sum(p.stat().st_size for p in tmp)
    if got != size:
        sys.exit(f'{dest.name}: {got} of {size} bytes')
    with open(dest.with_name(dest.name + '.download'), 'wb') as out:
        for p in tmp:
            out.write(p.read_bytes())
    dest.with_name(dest.name + '.download').replace(dest)
    for p in tmp:
        p.unlink()
    print(f'{dest}: {size} bytes in {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    main()
