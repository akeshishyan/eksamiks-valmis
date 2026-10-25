import json, sys, os, glob
d = sys.argv[1]; names = ["vocab","grammar","lesson_dialogs","reader","exam_tasks","exam_format","research","extra"] + (["audio"] if os.path.exists(os.path.join(d,"audio.json")) else [])
data = {n: json.load(open(os.path.join(d, n + ".json"))) for n in names}
for key, pre in [("vocab","vocab"),("grammar","grammar"),("lesson_dialogs","dialogs")]:
    for f in sorted(glob.glob(os.path.join(d, "parts", pre + "_*.json"))):
        add = json.load(open(f)); data[key] += add; print("merged", os.path.basename(f), len(add))
ids = [g["id"] for g in data["grammar"]]; assert len(ids) == len(set(ids)), "duplicate grammar ids"
seen=set(); data["vocab"]=[w for w in data["vocab"] if not ((w["lesson"],w["et"]) in seen or seen.add((w["lesson"],w["et"])))]
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
t = open(sys.argv[2]).read().replace("/*__DATA__*/", blob)
open(sys.argv[3], "w").write(t); print(len(t)//1024, "KB;", len(data["vocab"]), "words;", len(data["grammar"]), "grammar topics;", len(data["lesson_dialogs"]), "dialogs")
