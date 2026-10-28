"""第三遍：把「深底浅字」的组件类逐个翻过来。

前两遍翻的是 token（tailwind 色阶 + ink 变量），但有一类东西不走 token：
写成 rgba(30,41,59,.4) 的组件类（.btn-ghost / .chip）和直接用 emerald-950 当底色的激活态。
浅色页上它们表现为「灰块 + 看不见的字」——这是用户截图里那一排灰块的来源。
"""

from __future__ import annotations

import sys
from pathlib import Path

P = Path("templates/index.html")
t = P.read_text(encoding="utf-8")


def sub(old: str, new: str, label: str) -> None:
    global t
    if old not in t:
        print(f"✗ 没找到：{label}")
        sys.exit(1)
    t = t.replace(old, new, 1)
    print(f"✓ {label}")


sub(
    """        .btn-ghost {
            background: rgba(30, 41, 59, 0.4);
            color: #94A3B8;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(8px);
            transition: all .18s ease;
        }
        .btn-ghost:hover {
            border-color: rgba(16, 185, 129, 0.5);
            color: #34D399;
            background: rgba(16, 185, 129, 0.1);
        }""",
    """        .btn-ghost {
            background: #FFFFFF;
            color: #475467;
            border: 1px solid #D0D5DD;
            backdrop-filter: none;
            transition: all .18s ease;
        }
        .btn-ghost:hover {
            border-color: #98A2B3;
            color: #101828;
            background: #F9FAFB;
        }""",
    ".btn-ghost",
)

sub(
    """        .chip {
            padding: 4px 13px; border-radius: 999px;
            font-size: 12px; line-height: 18px; color: #94A3B8;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(15, 23, 42, 0.5);
            backdrop-filter: blur(8px);
            transition: all .18s ease;
            white-space: nowrap;
        }
        .chip:hover {
            border-color: rgba(16, 185, 129, 0.5);
            color: #34D399;
            background: rgba(16, 185, 129, 0.1);
        }""",
    """        .chip {
            padding: 3px 10px; border-radius: 6px;
            font-size: 12px; line-height: 18px; color: #475467;
            border: 1px solid #E4E7EC;
            background: #F9FAFB;
            backdrop-filter: none;
            transition: all .18s ease;
            white-space: nowrap;
        }
        .chip:hover {
            border-color: #98A2B3;
            color: #101828;
            background: #F2F4F7;
        }""",
    ".chip",
)

# 直接用深绿色当底色的激活态：换成浅绿底 + 深绿字
overlay = """
        /* ---- 局部深底（emerald-950 / slate-800）在浅色下的替代 ---- */
        [class~="bg-emerald-950/70"], [class~="bg-emerald-950/80"],
        [class~="bg-emerald-900/60"], [class~="bg-emerald-900/40"] {
            background-color: #ECFDF3 !important;
            border-color: #ABEFC6 !important;
            color: #067647 !important;
        }
        [class~="bg-slate-800"], [class~="bg-slate-700"] { background-color: #EAECF0 !important; }
        [class~="bg-slate-600"], [class~="bg-slate-600/70"] { background-color: #E4E7EC !important; }
        [class~="bg-slate-950/90"], [class~="bg-slate-900/80"] { background-color: #F2F4F7 !important; }

        /* 深底上的浅字反过来：这些类只在被上面覆盖的块里出现 */
        [class~="text-emerald-300"], [class~="text-emerald-200"] { color: #067647 !important; }
        [class~="text-slate-300"] { color: #344054 !important; }
"""
t = t.replace("    </style>", overlay + "    </style>", 1)
print("✓ 局部深底覆盖")

P.write_text(t, encoding="utf-8")
