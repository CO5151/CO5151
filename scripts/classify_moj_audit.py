"""Phan loai ket qua audit thanh 3 nhom va in bao cao."""
import json
from collections import defaultdict
from pathlib import Path

AUDIT = Path("/Users/tungdl/Documents/CO5151/CO5151/data/processed/moj_status_audit.json")
rows = json.load(open(AUDIT, encoding="utf-8"))

buckets = defaultdict(list)
for r in rows:
    m = r.get("moj") or {}
    if not m or m.get("doc_num_matches") is False:
        buckets["khong_kiem_chung_duoc"].append(r["doc_id"])
        continue
    code = m.get("eff_code")
    if code == "CHL":
        key = "trung" if r["graph_status"] == "in_force" else "moj_con_hieu_luc__graph_noi_het"
    elif code == "HHL1P":
        key = "het_hieu_luc_mot_phan"
    elif code == "HHL":
        key = "het_hieu_luc_toan_bo"
    elif code == "CCHL":
        key = "chua_co_hieu_luc"
    else:
        key = "khac"
    buckets[key].append((r["doc_id"], m.get("eff_from"), m.get("eff_to")))

print(f"tong {len(rows)} van ban\n")
for k in ["trung", "het_hieu_luc_mot_phan", "het_hieu_luc_toan_bo",
          "moj_con_hieu_luc__graph_noi_het", "chua_co_hieu_luc", "khac",
          "khong_kiem_chung_duoc"]:
    items = buckets.get(k) or []
    if not items:
        continue
    print(f"[{k}]  {len(items)}")
    for it in items:
        if isinstance(it, tuple):
            print(f"    {it[0]:<18} eff {it[1]} -> {it[2]}")
        else:
            print(f"    {it}")
    print()
