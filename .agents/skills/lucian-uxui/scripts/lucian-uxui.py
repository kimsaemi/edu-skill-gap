#!/usr/bin/env python3
"""
Python port of lucian-uxui CLI for environments without Node.js.
Supports: search, list, get, tokens, info.
"""

import sys
import os
import re
import json
import time
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

VERSION = "1.1.0"
SOURCES = [
    s.strip().rstrip("/")
    for s in os.environ.get(
        "LUCIAN_UXUI_BASE",
        "https://lucianlabs.dev/uxui-prompt/api/v1,https://raw.githubusercontent.com/Seokwoooo/lucian-uxui-prompt/main/api/v1",
    ).split(",")
    if s.strip()
]
TTL = int(os.environ.get("LUCIAN_UXUI_TTL", 6 * 3600))
USER_AGENT = f"lucian-uxui-skill/{VERSION} (+https://github.com/Seokwoooo/lucian-uxui)"
HANGUL = re.compile(r"[\uac00-\ud7a3\u3131-\u318e]")

CACHE_DIR = Path(os.environ.get("LUCIAN_UXUI_CACHE") or (Path.home() / ".cache" / "lucian-uxui"))
try:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    CACHE_DIR = None

def read_cache(name):
    if not CACHE_DIR:
        return None, None
    file_path = CACHE_DIR / name
    meta_path = CACHE_DIR / (name + ".meta.json")
    if file_path.exists():
        try:
            text = file_path.read_text(encoding="utf-8")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            return text, meta
        except Exception:
            pass
    return None, None

def write_cache(name, text, meta=None):
    if not CACHE_DIR:
        return
    try:
        file_path = CACHE_DIR / name
        meta_path = CACHE_DIR / (name + ".meta.json")
        file_path.write_text(text, encoding="utf-8")
        if meta:
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
    except Exception:
        pass

def fetch_url(url, etag=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            text = resp.read().decode("utf-8")
            return 200, text, resp.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        raise
    except Exception as e:
        raise

def download(rel, etag=None, source=None):
    preferred = [source] + [s for s in SOURCES if s != source] if source in SOURCES else SOURCES
    for base in preferred:
        url = f"{base}/{rel}"
        try:
            status, text, new_etag = fetch_url(url, etag=etag if base == source else None)
            return status, text, new_etag, base
        except Exception:
            continue
    raise RuntimeError(f"Could not reach any source for {rel}")

def cached_text(rel, refresh=False):
    name = rel.replace("/", "_")
    cached, meta = read_cache(name)
    now = time.time()
    if cached and meta and not refresh and (now - meta.get("fetchedAt", 0)) < TTL:
        return cached, meta

    status, text, new_etag, base = download(rel, etag=meta.get("etag") if meta else None, source=meta.get("source") if meta else None)
    if status == 304 and cached:
        meta["fetchedAt"] = now
        write_cache(name, cached, meta)
        return cached, meta

    meta = {"etag": new_etag, "source": base, "fetchedAt": now}
    write_cache(name, text, meta)
    return text, meta

def load_catalog(lang="en", refresh=False):
    text, meta = cached_text(f"{lang}/catalog.tsv", refresh=refresh)
    lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    header = lines[0].split("\t")
    items = []
    for line in lines[1:]:
        cells = line.split("\t")
        item = dict(zip(header, cells))
        item["tags"] = item.get("tags", "").split() if item.get("tags") else []
        items.append(item)
    by_id = {it["id"]: it for it in items}
    ver_match = re.search(r"version=(\w+)", text)
    version = ver_match.group(1) if ver_match else ""
    return items, by_id, version, meta.get("source")

SYNONYMS = {
    "switch": ["toggle"], "toggle": ["switch"], "modal": ["dialog", "sheet"], "dialog": ["modal"], "popup": ["dialog", "popover"],
    "spinner": ["loading", "loader"], "loader": ["loading", "progress"], "progress": ["loading"], "skeleton": ["loading"],
    "login": ["sign-in", "signin", "auth"], "signin": ["login", "auth"], "signup": ["sign-up", "register", "auth"], "register": ["signup"],
    "password": ["auth", "login"], "otp": ["code", "verification"], "toast": ["notification", "alert", "snackbar"],
    "notification": ["toast", "alert"], "alert": ["toast", "notification"], "snackbar": ["toast"],
    "dropdown": ["menu", "select"], "select": ["dropdown", "picker"], "picker": ["select"], "nav": ["menu", "tabs", "navigation"],
    "navigation": ["nav", "menu", "tabs"], "navbar": ["nav", "menu"], "sidebar": ["nav", "menu"], "tabs": ["tab"], "tab": ["tabs"],
    "cta": ["button"], "btn": ["button"], "chart": ["graph", "analytics"], "graph": ["chart"], "stats": ["chart", "analytics", "metric"],
    "dashboard": ["chart", "analytics", "widget", "metric"], "kpi": ["metric", "chart"], "kanban": ["board", "task"],
    "todo": ["task", "checklist"], "calendar": ["schedule", "date"], "date": ["calendar"], "schedule": ["calendar"],
    "upload": ["file", "drop"], "search": ["input", "filter"], "form": ["input"], "textarea": ["input", "editor"],
    "slider": ["range"], "range": ["slider"], "rating": ["star"], "pricing": ["price", "plan", "billing", "toggle"],
    "price": ["pricing"], "cart": ["checkout", "shop"], "checkout": ["payment", "cart"], "empty": ["empty-state", "no-results"],
    "error": ["404", "empty"], "404": ["error"], "card": ["cards"], "editor": ["document", "text"], "table": ["data", "grid"],
    "chat": ["message"], "message": ["chat"], "accordion": ["faq", "collapse", "disclosure"], "faq": ["accordion"],
    "tooltip": ["hint", "popover"], "copy": ["clipboard"], "share": ["social"], "like": ["heart", "favorite"], "theme": ["dark", "night", "day"],
    "dark": ["night", "theme"], "light": ["day", "theme"], "mode": ["theme"], "hero": ["button", "card"], "landing": ["button", "card"],
    "newsletter": ["subscribe", "email"], "subscribe": ["newsletter"], "testimonial": ["card", "quote"], "profile": ["card", "avatar"]
}

KO_SYNONYMS = [
    ("회원가입", ["signup", "sign-up", "register", "onboarding"]), ("가입", ["signup", "sign-up"]), ("로그인", ["login", "sign-in", "auth"]),
    ("비밀번호", ["password"]), ("인증", ["otp", "verification", "auth"]), ("버튼", ["button"]), ("토글", ["toggle", "switch"]),
    ("스위치", ["switch", "toggle"]), ("체크박스", ["checkbox"]), ("요금", ["pricing", "price", "plan"]), ("가격", ["pricing", "price"]),
    ("결제", ["checkout", "payment", "billing"]), ("장바구니", ["cart"]), ("메뉴", ["menu", "nav"]), ("탭", ["tabs", "tab"]),
    ("드롭다운", ["dropdown", "select", "menu"]), ("검색", ["search"]), ("입력", ["input", "field"]), ("태그", ["tags", "chips"]),
    ("슬라이더", ["slider", "range"]), ("별점", ["rating", "star"]), ("카드", ["card"]), ("모달", ["dialog", "modal"]),
    ("팝업", ["dialog", "popover"]), ("툴팁", ["tooltip"]), ("알림", ["toast", "notification", "alert"]), ("토스트", ["toast"]),
    ("로딩", ["loading", "spinner", "skeleton"]), ("진행", ["progress", "loading"]), ("빈 화면", ["empty-state", "empty"]),
    ("오류", ["error", "404"]), ("에러", ["error", "404"]), ("차트", ["chart", "graph"]), ("그래프", ["chart", "graph"]),
    ("대시보드", ["dashboard", "kpi", "chart", "widget"]), ("위젯", ["widget"]), ("칸반", ["kanban", "board", "task"]),
    ("할 일", ["todo", "task", "checklist"]), ("할일", ["todo", "task", "checklist"]), ("투두", ["todo", "checklist"]),
    ("달력", ["calendar", "date"]), ("캘린더", ["calendar", "date"]), ("일정", ["calendar", "schedule", "gantt"]), ("날짜", ["date", "calendar"]),
    ("다크", ["dark", "theme", "night"]), ("테마", ["theme", "dark"]), ("설정", ["settings", "toggle"]), ("업로드", ["upload", "file"]),
    ("파일", ["file", "upload"]), ("복사", ["copy", "clipboard"]), ("공유", ["share"]), ("좋아요", ["like", "heart"]),
    ("뉴스레터", ["newsletter", "subscribe", "email"]), ("구독", ["subscribe", "newsletter"]), ("자주 묻는", ["faq", "accordion"]),
    ("아코디언", ["accordion"]), ("단계", ["stepper", "wizard", "steps"]), ("온보딩", ["onboarding"]), ("에디터", ["editor"]),
    ("편집", ["editor", "edit"]), ("테이블", ["table"]), ("채팅", ["chat", "message"]), ("메시지", ["message", "chat"]),
    ("프로필", ["profile", "avatar"]), ("지도", ["map"]), ("타임라인", ["timeline"])
]

def extract_terms(text):
    words = re.findall(r"[\w]+(?:-[\w]+)*", str(text).lower())
    out = []
    for w in words:
        out.append(w)
        if "-" in w:
            out.extend(w.split("-"))
    return out

def hit(t, word):
    if t == word:
        return 1.0
    if HANGUL.search(word):
        return 0.8 if len(word) >= 2 and word in t else 0.0
    return 0.6 if len(word) >= 3 and t.startswith(word) else 0.0

def score_item(item, words, extra=None):
    t_titles = extract_terms(item["title"]) + (extract_terms(extra["title"]) if extra else [])
    t_tags = [w for tag in item.get("tags", []) for w in extract_terms(tag)]
    t_cat = extract_terms(item.get("category", "") + " " + item.get("cat", "")) + (extract_terms(extra["category"]) if extra else [])
    t_sum = extract_terms(item.get("summary", "")) + (extract_terms(extra["summary"]) if extra else [])
    fields = [
        (t_titles, 4),
        (t_tags, 4),
        (t_cat, 3),
        (t_sum, 1)
    ]
    score = 0.0
    matched = 0
    for w_entry in words:
        word = w_entry["word"]
        weight = w_entry["weight"]
        best = 0.0
        for flist, fweight in fields:
            for term in flist:
                best = max(best, hit(term, word) * fweight)
        if best > 0:
            score += best * weight
            if weight == 1.0:
                matched += 1
    return score + matched * 2, matched

def normalize_id(raw):
    m = re.search(r"(?:^|#)(\d{1,6})$", str(raw).strip())
    if not m:
        raise ValueError(f"'{raw}' is not an element ID (use numbers like 050)")
    return m.group(1).lstrip("0").zfill(3) or "000"

def cmd_search(query_words, lang="en", category=None, limit=10, refresh=False):
    query = " ".join(query_words).strip()
    if not query:
        print("search needs keywords, e.g. search 'pricing toggle'")
        return
    items, by_id, _, _ = load_catalog(lang, refresh=refresh)
    try:
        _, other_by_id, _, _ = load_catalog("en" if lang == "ko" else "ko", refresh=refresh)
    except Exception:
        other_by_id = {}

    base = extract_terms(query)
    words = [{"word": w, "weight": 1.0} for w in base]
    def add(w, wt):
        if not any(x["word"] == w for x in words):
            words.append({"word": w, "weight": wt})

    q_lower = query.lower()
    for ko, ens in KO_SYNONYMS:
        if ko in q_lower:
            for en in ens:
                add(en, 0.8)
    for b in base:
        for alt in SYNONYMS.get(b, []):
            add(alt, 0.5)

    results = []
    for item in items:
        if category and item.get("cat") != category:
            continue
        extra = other_by_id.get(item["id"])
        sc, matched = score_item(item, words, extra)
        if sc > 0:
            results.append((item, sc, matched))

    results.sort(key=lambda x: (x[2], x[1], -int(x[0]["id"])), reverse=True)
    results = results[:limit]

    if not results:
        print(f"No match for '{query}'. Try broader words, or browse: list")
        return

    print(f"# {len(results)} of {len(items)} elements for '{query}' (lang={lang}) · get <id> for code")
    for item, sc, _ in results:
        summary = item.get("summary", "")
        if len(summary) > 140:
            summary = summary[:139] + "…"
        print(f"{item['id']}  {item.get('title')}  [{item.get('cat')} · {item.get('shape')}]  {summary}")

def cmd_list(category=None, lang="en", refresh=False):
    items, _, _, _ = load_catalog(lang, refresh=refresh)
    if not category:
        counts = {}
        for item in items:
            cat = item.get("cat", "other")
            counts[cat] = counts.get(cat, 0) + 1
        print(f"# {len(items)} elements in {len(counts)} categories (lang={lang}) · list --category <slug>")
        for cat, cnt in counts.items():
            print(f"{cat.ljust(28)} {str(cnt).rjust(4)}")
        return

    filtered = [it for it in items if it.get("cat") == category]
    if not filtered:
        print(f"No category '{category}'. Run list to see available categories.")
        return
    print(f"# {len(filtered)} elements in {category} (lang={lang}) · get <id> for code")
    for it in filtered:
        summary = it.get("summary", "")
        if len(summary) > 120:
            summary = summary[:119] + "…"
        print(f"{it['id']}  {it.get('title')}  [{it.get('cat')}]  {summary}")

def cmd_get(raw_ids, lang="en", out_dir=None, refresh=False):
    ids = [normalize_id(r) for r in raw_ids if r.strip()]
    if not ids:
        print("get needs element IDs, e.g. get 050 112")
        return
    items, by_id, _, src = load_catalog(lang, refresh=refresh)
    for el_id in ids:
        item = by_id.get(el_id)
        if not item:
            print(f"No element {el_id}.")
            continue
        rel = f"{lang}/e/{el_id}.txt"
        status, text, _, _ = download(rel, source=src)
        if out_dir:
            out_p = Path(out_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            f_path = out_p / f"lucian-{el_id}.html"
            f_path.write_text(text, encoding="utf-8")
            print(f"Saved: {f_path}")
        else:
            print(text)

def cmd_tokens(lang="en", out=None, refresh=False):
    text, _ = cached_text(f"{lang}/tokens.css", refresh=refresh)
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"Saved tokens to {out}")
    else:
        print(text)

def cmd_info(lang="en"):
    items, _, ver, src = load_catalog(lang)
    print(f"lucian-uxui {VERSION} (Python CLI)")
    print(f"elements: {len(items)} (catalog {ver}, lang={lang})")
    print(f"source: {src or 'cache'}")
    print(f"sources: {', '.join(SOURCES)}")
    print(f"cache: {CACHE_DIR or 'off'}")
    print("gallery: https://lucianlabs.dev/uxui-prompt/")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(f"lucian-uxui {VERSION} (Python)\nCommands: search <query>, list [--category slug], get <ids...>, tokens, info")
        sys.exit(0)

    cmd = args[0]
    lang = "ko" if "--lang" in args and args[args.index("--lang") + 1] == "ko" else "en"
    if "--lang=ko" in args:
        lang = "ko"
    category = None
    if "-c" in args:
        category = args[args.index("-c") + 1]
    elif "--category" in args:
        category = args[args.index("--category") + 1]

    refresh = "--refresh" in args
    out_arg = None
    if "--out" in args:
        out_arg = args[args.index("--out") + 1]

    rest = [a for a in args[1:] if not a.startswith("-") and a != category and a != out_arg and a != lang]

    if cmd in ("search", "find"):
        cmd_search(rest, lang=lang, category=category, refresh=refresh)
    elif cmd in ("list", "ls"):
        cmd_list(category=category, lang=lang, refresh=refresh)
    elif cmd == "get":
        cmd_get(rest, lang=lang, out_dir=out_arg, refresh=refresh)
    elif cmd == "tokens":
        cmd_tokens(lang=lang, out=out_arg, refresh=refresh)
    elif cmd == "info":
        cmd_info(lang=lang)
    else:
        print(f"Unknown command: {cmd}")
