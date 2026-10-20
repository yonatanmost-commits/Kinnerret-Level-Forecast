"""
coach.py - a speaking coach for the talk: teleprompter, microphone, and Claude listening.

Serves the prompter (prompter_template.html, the same script as the show) on localhost, where the
browser may use the microphone. Practise one slide at a time, or the whole talk: each take is
saved, transcribed on this machine (faster-whisper), measured against the script and the
narrated pace, and handed to Claude (the `claude` command line, headless) for a few warm,
specific tips. Recordings stay on this machine; only the transcript and the numbers go to Claude.

Every take is logged to coach/log.jsonl (time, slide, numbers, tips), so progress can be read
back later, by you or by a Claude session.

Run:  python docs/talk/coach.py            # then open http://localhost:8765
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
from flask import Flask, Response, jsonify, request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_prompter as P                                            # noqa: E402

COACH = HERE / "coach"
TAKES = COACH / "takes"
LOG = COACH / "log.jsonl"
PORT = 8765
WHISPER = "small.en"
FILLERS = ("um", "uh", "er", "erm", "ah", "hmm", "you know", "kind of", "sort of", "i mean", "basically")
PAUSE_S = 1.2                    # a silence this long between words counts as a pause
NAMES = "Kinneret, Degania, Copernicus, Adnan, Tzemach, Jordan, GBR, GRU, Claude Code, Kasparov, centaur"

app = Flask(__name__)
_model = None
_talk = None


def talk() -> list[dict]:
    global _talk
    if _talk is None:
        _talk = P.talk()
    return _talk


def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER, device="cpu", compute_type="int8")
    return _model


def words_of(text: str) -> list[str]:
    text = text.replace("–", " ").replace("—", " ")
    return re.findall(r"[a-z0-9']+", text.lower())


def coverage(script: str, said: list[str]) -> tuple[float, list[str], list[str]]:
    """Share of the script said, the script runs skipped and the runs added (4+ words each)."""
    ref = words_of(script)
    sm = difflib.SequenceMatcher(a=ref, b=said, autojunk=False)
    hit = sum(b.size for b in sm.get_matching_blocks())
    missed, added = [], []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op in ("delete", "replace") and a1 - a0 >= 4:
            missed.append(" ".join(ref[a0:a1]))
        if op in ("insert", "replace") and b1 - b0 >= 4:
            added.append(" ".join(said[b0:b1]))
    return (hit / len(ref) if ref else 1.0), missed, added


def energy_range(wav: Path) -> float:
    """Spread of the voice's loudness (dB, 10th to 90th percentile of voiced 0.25 s windows):
    small means a flat delivery, larger means light and shade."""
    with wave.open(str(wav)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
        n = w.getframerate() // 4
    if len(x) < n * 4:
        return 0.0
    rms = np.sqrt(np.mean(x[: len(x) // n * n].reshape(-1, n) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    voiced = db[db > np.percentile(db, 30)]
    return float(np.percentile(voiced, 90) - np.percentile(voiced, 10)) if len(voiced) > 4 else 0.0


def measure(wav: Path, script: str, target: float) -> dict:
    with wave.open(str(wav)) as w:                                  # 16 kHz mono from ffmpeg; handing Whisper
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768  # samples
    segs, _ = model().transcribe(audio, word_timestamps=True, initial_prompt=NAMES, vad_filter=True)  # skips its av decoder
    ws = [w for s in segs for w in (s.words or [])]
    said_text = "".join(w.word for w in ws).strip()
    said = words_of(said_text)
    if not ws:
        return {"heard": False}
    spoken = ws[-1].end - ws[0].start
    gaps = [b.start - a.end for a, b in zip(ws, ws[1:])]
    pauses = [g for g in gaps if g >= PAUSE_S]
    low = sorted({w.word.strip(" ,.?!").lower() for w in ws if w.probability < 0.45 and len(w.word.strip()) > 3})
    lowered = " " + said_text.lower() + " "
    fillers = {f: len(re.findall(rf"\b{re.escape(f)}\b", lowered)) for f in FILLERS}
    cov, missed, added = coverage(script, said)
    return {"heard": True, "transcript": said_text, "seconds": round(spoken, 1), "target": round(target, 1),
            "wpm": round(len(said) / spoken * 60) if spoken > 0 else 0,
            "script_wpm": round(len(words_of(script)) / target * 60) if target else 0,
            "pauses": len(pauses), "longest_pause": round(max(pauses), 1) if pauses else 0.0,
            "fillers": {k: v for k, v in fillers.items() if v}, "coverage": round(cov, 2),
            "missed": missed[:6], "added": added[:6], "unclear": low[:8],
            "energy_db": round(energy_range(wav), 1)}


COACH_PROMPT = """You are a warm, encouraging speaking coach. The speaker is rehearsing a 15-minute
conference talk in English (not their first language) about forecasting the level of Lake Kinneret
with machine learning; their style is storytelling first, calm and light on the ear. They just
practised {where}. Below are the script, what the transcriber heard, and measurements.

Give feedback that makes them want to do one more take:
- Start with one thing that genuinely went well, tied to a number or a line they said.
- Then at most two concrete tips, each one small enough to try on the very next take, each
  pointing at a real line or number from this take (never generic advice).
- If they paraphrased the script but kept the meaning, that is fine and worth praising; only flag
  skipped content if it carried a fact or the story's thread.
- "unclear" words are ones the transcriber was unsure of: suggest slowing or opening those words
  only if it is a pattern, and say it kindly.
- The narrated target pace is a calm reference, not a rule; about 120-150 words a minute is
  comfortable for a conference hall.
- energy_db is the spread of loudness: under about 6 dB can sound flat, 8-14 dB is lively.
Reply with JSON only: {{"praise": "...", "tips": ["...", "..."], "next_take": "one short line to keep in mind"}}
Keep each string under 45 words. Plain, friendly words; no exclamation marks overload.

SCRIPT:
{script}

HEARD:
{heard}

MEASUREMENTS:
{numbers}
"""


def tips(where: str, script: str, m: dict) -> dict:
    numbers = {k: v for k, v in m.items() if k not in ("transcript", "heard")}
    prompt = COACH_PROMPT.format(where=where, script=script, heard=m["transcript"],
                                 numbers=json.dumps(numbers, ensure_ascii=False))
    try:
        r = subprocess.run(["claude", "-p", "--output-format", "text"], input=prompt, capture_output=True,
                           text=True, encoding="utf-8", timeout=180)
        out = r.stdout
        j = json.loads(out[out.index("{"): out.rindex("}") + 1])
        return {"praise": str(j.get("praise", "")), "tips": [str(t) for t in j.get("tips", [])][:2],
                "next_take": str(j.get("next_take", ""))}
    except Exception as e:                                          # the numbers still stand without tips
        return {"praise": "", "tips": [], "next_take": "", "error": f"Claude did not answer ({type(e).__name__})."}


@app.get("/")
def index() -> Response:
    page = P.TEMPLATE.read_text(encoding="utf-8").replace("/*__TALK__*/[]", json.dumps(talk(), ensure_ascii=False))
    return Response("<!doctype html><html><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width,initial-scale=1'></head><body>"
                    + page + "</body></html>", mimetype="text/html")


@app.get("/api/ping")
def ping():
    return jsonify(ok=True, history=history())


def history() -> dict:
    """Per slide ("0" = the whole talk): the takes so far, oldest first, numbers only."""
    out: dict = {}
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            t = json.loads(line)
            m = t.get("metrics", {})
            out.setdefault(str(t["slide"]), []).append(
                {"at": t["at"], "seconds": m.get("seconds"), "wpm": m.get("wpm"), "coverage": m.get("coverage")})
    return out


@app.post("/api/take")
def take():
    slide = int(request.args.get("slide", "0"))
    T = talk()
    if slide:
        s = next(x for x in T if int(x["n"]) == slide)
        script = "\n\n".join(c["text"] for c in s["clicks"])
        target = sum(c["secs"] for c in s["clicks"])
        where = f"slide {slide} of 12, \"{s['title'] or s['q']}\""
    else:
        script = "\n\n".join(c["text"] for s in T for c in s["clicks"])
        target = sum(c["secs"] for s in T for c in s["clicks"])
        where = "the whole talk, start to finish"
    TAKES.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw = TAKES / f"{stamp}_s{slide:02d}.webm"
    raw.write_bytes(request.get_data())
    wav = raw.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ac", "1", "-ar", "16000", str(wav)],
                   check=True)
    m = measure(wav, script, target)
    if not m.get("heard"):
        return jsonify(metrics=m, coach={"praise": "", "tips": [], "next_take": "",
                                         "error": "I couldn't hear any speech. Check the microphone and try again."})
    c = tips(where, script, m)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": stamp, "slide": slide, "file": raw.name, "metrics": m, "coach": c},
                           ensure_ascii=False) + "\n")
    return jsonify(metrics=m, coach=c, history=history())


if __name__ == "__main__":
    print(f"coach on http://localhost:{PORT}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
