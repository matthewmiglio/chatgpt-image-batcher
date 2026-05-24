import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from prompts import load_prompts, slugify

out = r"C:\Users\matt\Downloads\wow_fishbot"
prompts_path = r"C:\My_Files\my_programs\wow_fishbot\ads\prompts\wow-girls-fishing-rods-revealing-feet.json"

imgs = [f for f in os.listdir(out) if f.lower().endswith(".png") and f != "download.png"]
all_prompts = load_prompts(prompts_path)
slug_map = {slugify(p): p for p in all_prompts}

for f in sorted(imgs):
    base = f.rsplit(".", 1)[0]
    img_slug = re.sub(
        r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", "", base
    )
    match = slug_map.get(img_slug, "<<no match>>")
    print("-" * 60)
    print("FILE  :", f)
    print("PROMPT:", match)
