"""scripts/add_chat_to_dashboard_html.py 의 예전 '자료 질문' 코드 제거(strip_legacy_rag) 검사"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("add_chat", ROOT / "scripts" / "add_chat_to_dashboard_html.py")
add_chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(add_chat)

LEGACY = """<html><head><style>
  .panel { color: red; }
  .rag-fab { position: fixed;
    right: 20px; }
  .rag-panel { display: none; }
  @media (max-width: 520px) { .rag-fab { right: 12px; } }
  .keep-style { color: blue; }
</style></head><body>
<script>const DATA = {"courses": []};
readHash();
render();
</script>
<button type="button" class="rag-fab" id="ragFab">자료 질문</button>
<div id="KEEP_ME">남아야 함</div>
<section class="rag-panel" id="ragPanel"><p>패널</p></section>
<script>
const RAG_DOCS = [{"t": "문서"}];
</script>
<script>window.keepThis = 1;</script>
<script>
const RagEngine = (() => ({}))();
</script>
﻿<script>
(() => { const fab = document.getElementById('ragFab'); })();
</script>
</body></html>"""


def test_strip_removes_only_rag_pieces():
    out = add_chat.strip_legacy_rag(LEGACY)
    for gone in ['id="ragFab"', 'id="ragPanel"', "const RAG_DOCS", "const RagEngine", "getElementById('ragFab')", ".rag-fab", ".rag-panel", "﻿"]:
        assert gone not in out, gone
    for kept in ['<div id="KEEP_ME">남아야 함</div>', "window.keepThis = 1", "readHash();", "const DATA = ", ".panel { color: red; }", ".keep-style { color: blue; }"]:
        assert kept in out, kept


def test_strip_stops_when_pieces_missing():
    broken = LEGACY.replace('<section class="rag-panel" id="ragPanel"><p>패널</p></section>', "")
    with pytest.raises(SystemExit):
        add_chat.strip_legacy_rag(broken)
