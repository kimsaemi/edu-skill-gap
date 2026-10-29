"""
팀원 검수 결과(분야–과정 검수 시트)를 확정 과정 데이터에 반영하고, 자동 분류 정확도를 계산한다.

입력
  - data/hr/output/recommendation/domain_mapping_review_results.csv        : 검수 탭(183개 과정, 1인 1과정)
  - data/hr/output/recommendation/domain_mapping_cross_review_results.csv  : 교차검수 탭(20개 과정을 다른 팀원이 한 번 더)
  - data/hr/reference/hr_domain_ncs_crosswalk.csv                          : 인사 9개 분야 ID
  (구글 시트 '분야–과정 검수 시트'에서 2026-10-28에 내려받은 값)

반영 규칙 (hr_recommendation_candidates.csv, 같은 과정명은 같은 결과)
  - 인사 9개 분야를 고른 과정 : hr_domain_reviewed = 그 분야, hr_scope = HR_CORE
  - '사무 일반'을 고른 과정    : 인사 분야 없음, hr_scope = COMMON_SUPPORT (공통 업무역량)
  - '인사 업무와 무관'을 고른 과정: recommendation_readiness = EXCLUDED_REVIEW_UNRELATED (추천에서 제외)
  - 검수하지 않은 과정(빈칸 3개): 자동 분류(과정명 키워드)를 그대로 쓰고 domain_review_source에 표시
  - 교차검수에서 두 사람이 다르게 고른 경우: 1차 검수자의 선택을 쓰고 교차 선택은 domain_cross_review에 남긴다

정확도 (data/hr/reports/domain_review_metrics.json, domain_review_report.md)
  - 정밀도: 자동 분류가 분야를 붙인 과정 중 사람이 고른 분야가 그 안에 있는 비율
  - 재현율: 사람이 인사 분야를 고른 과정 중 자동 분류가 그 분야를 붙인 비율
  - 교차검수 일치율과 코헨 카파(11개 선택지 기준)

실행 순서: ... -> apply_hr_scope_and_ncs_crosswalk.py -> 이 스크립트 -> build_customer_platform_data.py
여러 번 실행해도 결과가 같다.
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "data" / "hr" / "output" / "recommendation"
CANDIDATES = REC / "hr_recommendation_candidates.csv"
REVIEW = REC / "domain_mapping_review_results.csv"
CROSS = REC / "domain_mapping_cross_review_results.csv"
CROSSWALK = ROOT / "data" / "hr" / "reference" / "hr_domain_ncs_crosswalk.csv"
METRICS_JSON = ROOT / "data" / "hr" / "reports" / "domain_review_metrics.json"
REPORT_MD = ROOT / "data" / "hr" / "reports" / "domain_review_report.md"

OFFICE = "사무 일반(엑셀·문서·소통)"
UNRELATED = "인사 업무와 무관"
NONE = "(없음)"
PICK, AUTO, MEMO, CID = "가장 맞는 분야 (고르기)", "자동 연결 분야", "메모 (선택)", "과정ID"


def norm_title(t):
    # build_customer_platform_data.py와 같은 기준으로 과정명을 묶는다
    return re.sub(r"\s+", " ", re.sub(r"^(EB24[A-Z0-9]+\s+)", "", str(t))).strip()


def split_auto(s):
    return [] if s in ("", NONE) else [x.strip() for x in s.split(",")]


def compute_metrics(rv, cross, domains):
    done = rv[rv[PICK] != ""]
    auto_has = done[AUTO] != NONE
    pick_hr = done[PICK].isin(domains)
    hit = done.apply(lambda r: r[PICK] in split_auto(r[AUTO]), axis=1)
    none_ok = done[~auto_has][PICK].isin([OFFICE, UNRELATED])

    both = cross[(cross[PICK] != "") & (cross["1차 선택"] != "")]
    labels = sorted(set(both[PICK]) | set(both["1차 선택"]))
    n = len(both)
    po = float((both[PICK] == both["1차 선택"]).mean()) if n else None
    pe = sum((both["1차 선택"] == c).sum() * (both[PICK] == c).sum() for c in labels) / n ** 2 if n else None
    kappa = (po - pe) / (1 - pe) if n and pe < 1 else None

    per_domain = {}
    for d in domains:
        auto_d = done[done[AUTO].map(lambda s: d in split_auto(s))]
        human_d = done[done[PICK] == d]
        per_domain[d] = {
            "auto_linked": int(len(auto_d)),
            "auto_correct": int((auto_d[PICK] == d).sum()),
            "human_picked": int(len(human_d)),
            "human_found_by_auto": sum(d in split_auto(s) for s in human_d[AUTO]),
        }
    return {
        "reviewed_courses": int(len(done)),
        "total_courses": int(len(rv)),
        "blank_courses": rv.loc[rv[PICK] == "", "과정명"].tolist(),
        "precision": {"correct": int(hit[auto_has].sum()), "auto_linked": int(auto_has.sum()),
                      "value": round(float(hit[auto_has].mean()), 4)},
        "recall": {"found": int(hit[pick_hr].sum()), "human_hr": int(pick_hr.sum()),
                   "value": round(float(hit[pick_hr].mean()), 4)},
        "no_domain_correct": {"correct": int(none_ok.sum()), "total": int((~auto_has).sum()),
                              "value": round(float(none_ok.mean()), 4)},
        "missed_by_keywords": done[~auto_has & pick_hr][["과정명", PICK]].values.tolist(),
        "wrong_by_keywords": done[auto_has & ~hit][["과정명", AUTO, PICK]].values.tolist(),
        "pick_counts": done[PICK].value_counts().to_dict(),
        "cross_review": {"pairs": n, "agree": int((both[PICK] == both["1차 선택"]).sum()),
                         "agreement": round(po, 4) if po is not None else None,
                         "pe": round(pe, 4) if pe is not None else None,
                         "kappa": round(kappa, 4) if kappa is not None else None,
                         "disagreements": both[both[PICK] != both["1차 선택"]][["과정명", "1차 선택", PICK]].values.tolist(),
                         "blank": cross.loc[(cross[PICK] == "") | (cross["1차 선택"] == ""), "과정명"].tolist()},
        "per_domain": per_domain,
    }


def apply_to_candidates(rv, cross, dom_id):
    df = pd.read_csv(CANDIDATES, dtype=str)
    df["title_norm"] = df["course_name"].map(norm_title)
    id2title = dict(zip(df["course_id"], df["title_norm"]))
    rv = rv.assign(title_norm=rv[CID].map(id2title))
    cross_by_id = {r[CID]: r for _, r in cross.iterrows()}

    reviewed, source, memo, cross_note = {}, {}, {}, {}
    for _, r in rv.iterrows():
        t = r["title_norm"]
        if r[PICK]:
            reviewed[t], source[t] = r[PICK], "팀원 검수"
        else:
            reviewed[t], source[t] = ", ".join(split_auto(r[AUTO])), "자동 분류(검수 미입력)"
        memo[t] = r[MEMO]
        c = cross_by_id.get(r[CID])
        if c is not None and c[PICK]:
            cross_note[t] = f"교차검수({c['교차 배정']}): {c[PICK]}" + ("" if c[PICK] == r[PICK] else " (불일치, 1차 선택 사용)")

    df["hr_domain_reviewed"] = df["title_norm"].map(reviewed).fillna("")
    df["hr_domain_reviewed_id"] = df["hr_domain_reviewed"].map(
        lambda s: "|".join(dom_id[x.strip()] for x in s.split(",") if x.strip() in dom_id) if s else "")
    df["domain_review_source"] = df["title_norm"].map(source).fillna("")
    df["domain_review_memo"] = df["title_norm"].map(memo).fillna("")
    df["domain_cross_review"] = df["title_norm"].map(cross_note).fillna("")

    active = ~df["recommendation_readiness"].str.startswith("EXCLUDED", na=False)
    human = df["domain_review_source"].eq("팀원 검수")
    df.loc[active & df["hr_domain_reviewed_id"].ne(""), "hr_scope"] = "HR_CORE"
    df.loc[active & human & df["hr_domain_reviewed"].eq(OFFICE), "hr_scope"] = "COMMON_SUPPORT"
    unrelated = active & human & df["hr_domain_reviewed"].eq(UNRELATED)
    df.loc[unrelated, "recommendation_readiness"] = "EXCLUDED_REVIEW_UNRELATED"
    df.loc[unrelated, "hr_scope"] = "OUT_OF_SCOPE"
    df.loc[unrelated, "recommendation_note"] = "팀원 검수에서 '인사 업무와 무관'으로 판정"

    df = df.drop(columns=["title_norm"])
    df.to_csv(CANDIDATES, index=False, encoding="utf-8-sig")
    left = df[~df["recommendation_readiness"].str.startswith("EXCLUDED", na=False)]
    return int(unrelated.sum()), left


def write_report(m):
    p, r, nd, cr = m["precision"], m["recall"], m["no_domain_correct"], m["cross_review"]
    lines = [
        "# 분야–과정 검수 결과와 자동 분류 정확도",
        "",
        f"- 검수: 팀원 4명이 과정명 기준 {m['total_courses']}개 과정 중 {m['reviewed_courses']}개에 '가장 맞는 분야' 하나를 고름 (2026-10-28)",
        f"- 미입력 {len(m['blank_courses'])}개는 자동 분류를 그대로 사용: " + ", ".join(m["blank_courses"]),
        "- 자동 분류: 과정명에 분야 키워드가 들어 있으면 연결 (`scripts/build_customer_platform_data.py`의 `DOMAIN_KEYWORDS`)",
        "",
        "## 자동 분류 정확도",
        "",
        "| 지표 | 값 | 계산 |",
        "| :--- | ---: | :--- |",
        f"| 정밀도 | {p['value']:.1%} | 자동으로 분야가 붙은 {p['auto_linked']}개 중 사람이 고른 분야가 들어 있는 {p['correct']}개 |",
        f"| 재현율 | {r['value']:.1%} | 사람이 인사 분야를 고른 {r['human_hr']}개 중 자동 분류가 찾은 {r['found']}개 |",
        f"| 분야 없음 판정 | {nd['value']:.1%} | 자동으로 분야가 안 붙은 {nd['total']}개 중 사람도 '사무 일반'·'무관'으로 본 {nd['correct']}개 |",
        "",
        "## 팀원 간 일치도 (교차검수)",
        "",
        f"- 두 사람 모두 입력한 {cr['pairs']}쌍 중 {cr['agree']}쌍 일치 ({cr['agreement']:.1%}), 우연 일치 기대값 {cr['pe']:.3f}, **코헨 카파 {cr['kappa']:.2f}**",
        "- 카파 0.8 이상은 '거의 완벽한 일치'로 보지만, 쌍이 적어 참고 수준이다.",
        "- 불일치: " + "; ".join(f"{t} ({a} / {b})" for t, a, b in cr["disagreements"]),
        "",
        "## 자동 분류가 놓친 과정 (사람은 인사 분야로 판정)",
        "",
        "| 과정명 | 사람이 고른 분야 |",
        "| :--- | :--- |",
        *[f"| {t} | {d} |" for t, d in m["missed_by_keywords"]],
        "",
        "## 자동 분류가 틀린 과정 (분야가 붙었지만 사람 판단과 다름)",
        "",
        "| 과정명 | 자동 분류 | 사람이 고른 분야 |",
        "| :--- | :--- | :--- |",
        *[f"| {t} | {a} | {d} |" for t, a, d in m["wrong_by_keywords"]],
        "",
        "## 분야별",
        "",
        "| 분야 | 자동 연결 | 그중 맞음 | 사람이 고름 | 그중 자동이 찾음 |",
        "| :--- | ---: | ---: | ---: | ---: |",
        *[f"| {d} | {v['auto_linked']} | {v['auto_correct']} | {v['human_picked']} | {v['human_found_by_auto']} |"
          for d, v in m["per_domain"].items()],
        "",
        "## 해석 시 주의",
        "",
        "- 정답은 팀원 1인의 판단이며, 교차검수는 20개 과정만 했다.",
        "- 팀원 간 기준 차이: 신입사원이 직접 듣는 온보딩 과정을 '온보딩·직원경험'으로 볼지 '무관'으로 볼지 갈렸다(홍: 무관, 나머지: 온보딩).",
        "- 비즈니스 매너 과정은 시트 안내와 달리 팀원 모두 '무관'으로 판정했다.",
        "- 검수 결과는 `hr_recommendation_candidates.csv`의 `hr_domain_reviewed`·`domain_review_source` 컬럼에 반영했다.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    rv = pd.read_csv(REVIEW, dtype=str).fillna("")
    cross = pd.read_csv(CROSS, dtype=str).fillna("")
    cw = pd.read_csv(CROSSWALK, dtype=str)
    dom_id = dict(zip(cw["domain_name"], cw["domain_id"]))

    m = compute_metrics(rv, cross, list(dom_id))
    METRICS_JSON.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(m)
    n_unrel, left = apply_to_candidates(rv, cross, dom_id)

    print(f"[정확도] 정밀도 {m['precision']['value']:.1%}, 재현율 {m['recall']['value']:.1%}, "
          f"카파 {m['cross_review']['kappa']:.2f} ({m['cross_review']['pairs']}쌍)")
    print(f"[반영] 무관 판정으로 추가 제외 {n_unrel}건 / 남은 확정 과정 {len(left)}건")
    print(left["hr_scope"].value_counts().to_string())
    print(left["domain_review_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
