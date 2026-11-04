"""
발표 '대시보드 업무·강좌 매핑' 섹션(data.json의 dashboard_mapping) 회귀 테스트.

- 집계 스크립트를 다시 돌린 값 = 커밋된 data.json 값
- build_presentation_data.py가 data.json을 새로 써도 dashboard_mapping이 남는지
- 슬롯 수(270 = 90 × 3), 부족 슬롯(3개 미만) 및 목록이 리랭커 CSV와 일치하는지
- 빈 칸 재계산, 최신 대시보드 파일 이름 형식
- 발표 페이지(presentation/index.html)에 같은 값이 들어가 있는지
실행: python scripts/test_dashboard_mapping.py   (모델·API 필요 없음, 파일을 고치지 않음)
"""
import collections
import json
import re
import sys
import tempfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT / "scripts"))
sys.argv = sys.argv[:1]  # build_presentation_data가 sys.argv 옵션을 읽으므로 비워 둔다

import build_dashboard_mapping_stats as dms  # noqa: E402
import build_presentation_data as bpd  # noqa: E402

DATA = ROOT / "presentation" / "src" / "data.json"
PAGE = ROOT / "presentation" / "index.html"
RERANK_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"

committed = json.loads(DATA.read_text(encoding="utf-8")).get("dashboard_mapping")
assert committed, "data.json에 dashboard_mapping이 없음 → python scripts/build_dashboard_mapping_stats.py"

# 1) 재현
src = dms.latest_dashboard()
assert re.fullmatch(r"hr_career_platform_v2_\d{4}-\d{2}-\d{2}\.html", src.name), f"대시보드 파일 이름 형식이 다름: {src.name}"
fresh = dms.dashboard_mapping()
assert fresh == committed, "data.json의 dashboard_mapping이 최신 대시보드와 다름 → 집계 스크립트를 다시 실행"
print(f"[PASS] 재현: {src.name} → 강좌 {fresh['courses']:,}, 부족 슬롯 {fresh['thin_slots']}/{fresh['slots_total']} (업무 {fresh['thin_tasks']}개), 빈 칸 {len(fresh['empty_cells'])}")

# 2) build_presentation_data.py가 이 섹션을 함께 써야 한다
assert bpd.dashboard_mapping_section() == fresh, "build_presentation_data.py가 dashboard_mapping을 다르게 계산함"
code = (ROOT / "scripts" / "build_presentation_data.py").read_text(encoding="utf-8")
assert '"dashboard_mapping": dashboard_mapping_section()' in code, "build_presentation_data.py의 data에 dashboard_mapping 키가 빠짐"
# 대시보드 파일이 없을 때는 이전 data.json 값을 쓴다
with tempfile.TemporaryDirectory() as empty:
    bpd.ROOT = Path(empty)  # 대시보드 파일이 없는 폴더
    try:
        assert bpd.dashboard_mapping_section() == committed, "대시보드 파일이 없을 때 이전 값을 쓰지 않음"
    finally:
        bpd.ROOT = ROOT
print("[PASS] build_presentation_data.py가 dashboard_mapping을 유지 (대시보드 파일이 없으면 이전 값)")

# 3) 슬롯 수와 리랭커 CSV 직접 비교
m = fresh
assert m["tasks_total"] == 90, f"tasks_total 기대 90, 실제 {m['tasks_total']}"
assert m["slots_total"] == 90 * 3, f"slots_total 기대 270, 실제 {m['slots_total']}"
assert m["slot_min"] == 3, f"slot_min 기대 3, 실제 {m['slot_min']}"
assert m["thin_slots"] == len(m["thin_slot_list"]), "thin_slots와 thin_slot_list 길이가 다름"
assert m["thin_tasks"] == len(set(s["task"] for s in m["thin_slot_list"])), "thin_tasks와 고유 업무 수가 다름"

# 리랭커 CSV에서 직접 집계하여 검증
df_rerank = pd.read_csv(RERANK_CSV)
counts = df_rerank.groupby(["domain_id", "task_id", "task_name", "level"]).size().reset_index(name="n")
thin_in_csv = counts[counts["n"] < m["slot_min"]]

assert m["thin_slots"] == len(thin_in_csv), f"thin_slots ({m['thin_slots']}) != CSV 부족 슬롯 ({len(thin_in_csv)})"
assert m["thin_tasks"] == thin_in_csv["task_id"].nunique(), f"thin_tasks ({m['thin_tasks']}) != CSV 고유 업무 ({thin_in_csv['task_id'].nunique()})"

csv_slots = sorted([(r["task_name"], r["level"], r["n"]) for _, r in thin_in_csv.iterrows()])
json_slots = sorted([(r["task"], r["level"], r["n"]) for r in m["thin_slot_list"]])
assert csv_slots == json_slots, f"thin_slot_list 불일치:\n  CSV:  {csv_slots}\n  JSON: {json_slots}"
assert [d["n"] for d in m["domains"]] == sorted(d["n"] for d in m["domains"]), "분야 막대가 오름차순이 아님"
print(f"[PASS] 슬롯 검증: 270개 중 {m['thin_slots']}개 부족 슬롯 (리랭커 CSV와 100% 일치)")

# 4) 빈 칸을 원본에서 다시 센다
text = src.read_text(encoding="utf-8")
D, _ = json.JSONDecoder().raw_decode(text[re.search(r"const DATA = ", text).end():])
name = {d["id"]: d["short"] for d in D["domains"]}
cross = collections.Counter((name[i], D["cats"][c["cat"]]) for c in D["courses"] for i in c["doms"] if i in name)
for g in m["empty_cells"]:
    assert cross[(g["domain"], g["category"])] == 0, f"빈 칸이 아님: {g}"
n_cells = len(name) * len(D["cats"])
assert sum(1 for k in cross if cross[k] > 0) + len(m["empty_cells"]) == n_cells, "분야×카테고리 칸 수가 맞지 않음"
print(f"[PASS] 빈 칸 {len(m['empty_cells'])}개 모두 강좌 0개 (전체 {n_cells}칸)")

# 5) 발표 페이지에 같은 값과 엘리먼트 존재 확인
page = PAGE.read_text(encoding="utf-8")
P, _ = json.JSONDecoder().raw_decode(page[re.search(r"const D = ", page).end():])
assert P.get("dashboard_mapping") == committed, "presentation/index.html이 data.json과 다름 → python scripts/build_presentation.py"
for el in ("ch-map-domain", "ch-map-thin", "map-domain-summary", "map-slots-summary", "map-gaps"):
    assert f'id="{el}"' in page, f"발표 페이지에 #{el} 자리가 없음"
print("[PASS] 발표 페이지(index.html)에 같은 값과 표시 자리가 있음")

print("\n🎉 대시보드 매핑 섹션 회귀 테스트 통과")
