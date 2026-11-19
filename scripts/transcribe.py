# /// script
# requires-python = ">=3.10"
# dependencies = ["faster-whisper>=1.1", "av>=15,<16", "yt-dlp>=2025.1.1"]
# ///
"""Transcribe the opening of your top-scoring posts, on your own computer, for free.

Usage:
  uv run scripts/transcribe.py --file hooks/posts_scored.csv --top 40

For the top posts by score (outliers first) it downloads the audio, transcribes the first
30 seconds with Whisper running locally, and saves:
  hooks/transcripts/<n>.txt          the transcript of the opening
  hooks/hooks_raw.csv                the scored posts plus a spoken_hook column (the first
                                     sentence spoken, word for word)
The first run downloads the Whisper model (about 500 MB for "small"). After that it's
offline and free. Slideshows and silent posts get an empty spoken_hook; their caption
and on-screen text still count.
"""
import argparse
import csv
import pathlib
import re
import tempfile
import urllib.request


def fetch_audio(row, folder):
    out = folder / "clip"
    media = (row.get("media_url") or "").strip()
    if media:
        path = folder / "clip.mp4"
        try:
            urllib.request.urlretrieve(media, path)
            return path
        except Exception:
            pass
    import yt_dlp
    opts = {"format": "bestaudio/best", "outtmpl": str(out) + ".%(ext)s", "quiet": True, "no_warnings": True, "noprogress": True}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(row["url"], download=True)
            return pathlib.Path(y.prepare_filename(info))
    except Exception as e:
        print(f"    couldn't download {row['url']}: {str(e)[:120]}")
        return None


def first_sentence(text):
    text = " ".join(text.split())
    m = re.match(r"(.{12,220}?[.!?])(\s|$)", text)
    return (m.group(1) if m else " ".join(text.split()[:25])).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--model", default="small", help="tiny, base, small, medium or large-v3 (slower, better)")
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    rows = list(csv.DictReader(open(a.file)))
    rows = [r for r in rows if r.get("score")]
    rows.sort(key=lambda r: -float(r["score"]))
    todo = rows[: a.top]
    tdir = pathlib.Path("hooks/transcripts"); tdir.mkdir(parents=True, exist_ok=True)
    print(f"Loading Whisper ({a.model}). The first run downloads it.")
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    for i, r in enumerate(todo, 1):
        r["spoken_hook"] = ""
        if r.get("format") == "slideshow":
            continue
        with tempfile.TemporaryDirectory() as tmp:
            audio = fetch_audio(r, pathlib.Path(tmp))
            if not audio or not audio.exists():
                continue
            segments, _ = model.transcribe(str(audio), clip_timestamps=[0, 30], vad_filter=True)
            text = " ".join(s.text.strip() for s in segments).strip()
        if text and not re.fullmatch(r"[\W\s]*(music|♪)*[\W\s]*", text, re.I):
            (tdir / f"{i:03d}.txt").write_text(f"{r['url']}\n\n{text}\n")
            r["spoken_hook"] = first_sentence(text)
        print(f"  {i}/{len(todo)}  {r.get('score')}  {r['spoken_hook'][:80]}")
    out = pathlib.Path("hooks/hooks_raw.csv")
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(todo[0].keys()) if todo else ["url"])
        w.writeheader(); w.writerows(todo)
    print(f"Saved {out} and {len(list(tdir.glob('*.txt')))} transcripts in {tdir}")


if __name__ == "__main__":
    main()
