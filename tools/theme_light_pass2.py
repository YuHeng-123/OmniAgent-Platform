"""第二遍：把「深色主题残留」逐处收干净。

第一遍只翻了 token，页面上还剩三类东西跟浅色不搭：
  1. `.tag` 小标签是硬编码的深色胶囊（浅色页里像块脏抹布）
  2. 漏斗的成交卡片是 rose→amber 渐变 + 大投影（营销风）
  3. 胶囊按钮（rounded-full）在数据面板里显得软
"""

from __future__ import annotations

import sys
from pathlib import Path

P_INDEX = Path("templates/index.html")
P_OVERVIEW = Path("templates/partials/tab_overview.html")


def patch(path: Path, pairs: list[tuple[str, str]]) -> None:
    t = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in t:
            print(f"✗ {path.name}: 没找到 {old[:40]}")
            sys.exit(1)
        t = t.replace(old, new, 1)
        print(f"✓ {path.name}: {old[:34]}…")
    path.write_text(t, encoding="utf-8")


# 1) tag 胶囊：深底浅字 → 浅底深字 + 细边
patch(
    P_INDEX,
    [
        (
            """        .tag {
            display: inline-flex; align-items: center;
            padding: 2px 8px; border-radius: 6px;
            font-size: 10px; line-height: 14px; font-family: "JetBrains Mono", Consolas, monospace;
            color: #94A3B8; background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(8px);
        }""",
            """        .tag {
            display: inline-flex; align-items: center;
            padding: 1px 6px; border-radius: 4px;
            font-size: 10px; line-height: 14px; font-family: "JetBrains Mono", Consolas, monospace;
            color: #475467; background: #F2F4F7;
            border: 1px solid #E4E7EC;
            backdrop-filter: none;
        }""",
        ),
    ],
)

# 2) 漏斗成交卡：渐变 + 光晕 → 实色深红块（企业面板里唯一允许的重色）
patch(
    P_OVERVIEW,
    [
        (
            'class="p-3.5 rounded-xl bg-gradient-to-r from-rose-500 to-amber-600 shadow-xl shadow-rose-950/60 border border-rose-400/50 mx-3 text-center"',
            'class="p-3.5 rounded-xl bg-[#B42318] shadow-none border border-[#912018] mx-3 text-center"',
        ),
    ],
)

# 3) 覆盖层补两条：胶囊按钮收敛、标签强调色
extra = """
        /* 胶囊按钮在数据面板里显得软，收敛成 8px；圆形状态点不受影响 */
        button[class*="rounded-full"] { border-radius: 8px !important; }
        .tag-accent { color: #067647 !important; background: #ECFDF3 !important; border-color: #ABEFC6 !important; }
"""
t = P_INDEX.read_text(encoding="utf-8")
t = t.replace("    </style>", extra + "    </style>", 1)
P_INDEX.write_text(t, encoding="utf-8")
print("✓ 覆盖层补充")
