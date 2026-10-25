"""Generate Estonian audio with the TartuNLP Neurokõne TTS API.

Usage: python3 gen_audio.py <data_dir> <out_audio_dir>
Writes <out>/<id>.m4a and <data_dir>/audio.json mapping keys -> file names.
WAV chunks are cached in ./tts/cache so reruns only fetch new text.
"""
import glob, hashlib, json, os, re, struct, subprocess, sys, time, urllib.request

DATA, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "tts", "cache")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

FEMALE = ["mari", "liivika", "vesta"]
MALE = ["tambet", "peeter", "kalev"]
MALE_NAMES = {"paul", "andrus", "margus", "mart", "peeter", "jaan", "meelis", "toomas", "bob", "romeo", "juhan", "kalle",
              "martin", "tõnu", "jüri", "mihkel", "rasmus", "ott", "taavi", "andres", "priit", "karl", "sander", "marko",
              "mees", "isa", "vend", "poeg", "vanaisa", "onu", "härra", "jõuluvana", "politseinik", "arst", "ajakirjanik"}
RATE = 22050


def tts(text, speaker, speed=0.9):
    key = hashlib.sha1(f"{speaker}|{speed}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".wav")
    if not os.path.exists(path):
        body = json.dumps({"text": text, "speaker": speaker, "speed": speed}).encode()
        for attempt in range(6):
            try:
                req = urllib.request.Request("https://api.tartunlp.ai/text-to-speech/v2", data=body,
                                             headers={"Content-Type": "application/json"})
                data = urllib.request.urlopen(req, timeout=120).read()
                if data[:4] != b"RIFF":
                    raise ValueError("not wav")
                open(path, "wb").write(data)
                break
            except Exception as e:
                print("  retry", attempt, e, flush=True)
                time.sleep(4 * (attempt + 1))
        else:
            raise RuntimeError("TTS failed: " + text[:60])
        time.sleep(0.3)
    return pcm_of(open(path, "rb").read())


def pcm_of(wav):
    # Minimal RIFF reader: return the raw float32 samples of the 'data' chunk.
    i = 12
    while i < len(wav):
        cid, size = wav[i:i + 4], struct.unpack("<I", wav[i + 4:i + 8])[0]
        if cid == b"data":
            return wav[i + 8:i + 8 + size]
        i += 8 + size + (size & 1)
    raise ValueError("no data chunk")


def silence(sec):
    return b"\x00\x00\x00\x00" * int(RATE * sec)


def write_m4a(pcm, out_path):
    tmp = out_path + ".wav"
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 3, 1, RATE, RATE * 4, 4, 32)
    open(tmp, "wb").write(hdr + b"data" + struct.pack("<I", len(pcm)) + pcm)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "40000", tmp, out_path], check=True)
    os.remove(tmp)


def chunks(text, limit=280):
    # Split into sentence groups under `limit` characters.
    sents = re.split(r"(?<=[.!?…])\s+", text.strip())
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return [c for c in out if re.search(r"\w", c)]


def clean(line):
    line = re.sub(r"\(\s*\d+\s*\)\s*_+", "", line)  # gap markers like (23) ____
    line = re.sub(r"_{2,}|\.{4,}", " ", line)
    return line.strip()


def speak_lines(lines, narrator="mari"):
    """lines: raw text lines; 'Name: text' lines get a voice per speaker."""
    voices, f_i, m_i, pcm = {}, 0, 0, b""
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r"^([A-ZÕÄÖÜŠŽ][\wõäöüšž .'-]{0,24}):\s+(.*)$", raw)
        if m:
            name, text = m.group(1).strip(), m.group(2)
            if name not in voices:
                male = name.lower().split()[0] in MALE_NAMES
                if male:
                    voices[name] = MALE[m_i % len(MALE)]; m_i += 1
                else:
                    voices[name] = FEMALE[f_i % len(FEMALE)]; f_i += 1
            voice = voices[name]
        else:
            text, voice = raw, narrator
        text = clean(text)
        for c in chunks(text):
            pcm += tts(c, voice) + silence(0.35)
        pcm += silence(0.3)
    return pcm


def make(key, lines, narrator="mari", manifest=None):
    fid = hashlib.sha1(key.encode()).hexdigest()[:12]
    out = os.path.join(OUT, fid + ".m4a")
    if not os.path.exists(out):
        pcm = speak_lines(lines, narrator)
        if not pcm:
            return
        write_m4a(silence(0.3) + pcm, out)
    manifest[key] = fid + ".m4a"
    print("ok", key[:70], flush=True)


def main():
    manifest = {}
    exam = json.load(open(os.path.join(DATA, "exam_tasks.json")))
    for t in exam:
        if t.get("section") == "kuulamine" and t.get("text_et"):
            make("lis:" + t["title"], t["text_et"].split("\n"), "liivika", manifest)
    dialogs = json.load(open(os.path.join(DATA, "lesson_dialogs.json")))
    for f in sorted(glob.glob(os.path.join(DATA, "parts", "dialogs_*.json"))):
        dialogs += json.load(open(f))
    for d in dialogs:
        make("dlg:" + d["title"], d["text_et"].split("\n"), "mari", manifest)
    extra = json.load(open(os.path.join(DATA, "extra.json")))
    for i, t in enumerate(extra["speaking_topics"]):
        for q in t["q"]:
            make("q:" + q, [q], MALE[0] if i % 2 else FEMALE[0], manifest)
    for c in json.load(open(os.path.join(DATA, "reader.json"))):
        make("rd:" + c["title"], [c["title"] + "."] + c["text_et"].split("\n"), "mari", manifest)
    if os.environ.get("WITH_WORDS"):
        vocab = json.load(open(os.path.join(DATA, "vocab.json")))
        for f in sorted(glob.glob(os.path.join(DATA, "parts", "vocab_*.json"))):
            vocab += json.load(open(f))
        for i, w in enumerate(vocab):
            make("w:" + w["et"], [w["et"].replace(":", ",")], FEMALE[0] if i % 2 else MALE[0], manifest)
        grammar = json.load(open(os.path.join(DATA, "grammar.json")))
        for f in sorted(glob.glob(os.path.join(DATA, "parts", "grammar_*.json"))):
            grammar += json.load(open(f))
        for t in grammar:
            for x in t.get("examples", []):
                make("g:" + x["et"], [x["et"]], FEMALE[1], manifest)
    json.dump(manifest, open(os.path.join(DATA, "audio.json"), "w"), ensure_ascii=False, indent=1)
    print("done", len(manifest))


main()
