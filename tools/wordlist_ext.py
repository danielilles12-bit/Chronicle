"""Optional: fetch a community crossword wordlist with quality scores.

Tries known URLs for freely distributed constructor wordlists (format
"WORD;score" per line). Returns {WORD: score} or None if unavailable.
Cached under tools/cache/.
"""
import os
import urllib.request
import zipfile
import io

CACHE = os.path.join(os.path.dirname(__file__), "cache")
TXT = os.path.join(CACHE, "ext_wordlist.txt")

URLS = [
    "https://www.spreadthewordlist.com/files/spreadthewordlist.txt",
    "https://www.spreadthewordlist.com/wordlist/spreadthewordlist.txt",
    "https://peterbroda.me/crosswords/wordlist/files/wordlist.zip",
    "https://peterbroda.me/crosswords/wordlist/wordlist.zip",
]


def _parse(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ";" not in line:
            continue
        word, _, score = line.partition(";")
        word = word.strip().upper()
        try:
            sc = int(score.strip())
        except ValueError:
            continue
        if word.isalpha():
            out[word] = sc
    return out or None


def get_external_words():
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(TXT):
        with open(TXT) as f:
            return _parse(f.read())
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if url.endswith(".zip"):
                zf = zipfile.ZipFile(io.BytesIO(data))
                name = next(n for n in zf.namelist() if n.endswith(".txt"))
                data = zf.read(name)
            text = data.decode("utf-8", "ignore")
            parsed = _parse(text)
            if parsed and len(parsed) > 50_000:
                with open(TXT, "w") as f:
                    f.write(text)
                print("external wordlist cached:", url, len(parsed), "words")
                return parsed
        except Exception as e:  # noqa: BLE001
            print("wordlist fetch failed:", url, e)
    return None


if __name__ == "__main__":
    words = get_external_words()
    if words:
        good = sum(1 for s in words.values() if s >= 50)
        print("total:", len(words), "score>=50:", good)
    else:
        print("no external wordlist available")
