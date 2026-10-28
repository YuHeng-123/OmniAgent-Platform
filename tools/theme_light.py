"""把 OmniAgent 控制台从「深空霓虹」换成「企业浅色」。

只动 token 与几处硬编码颜色，不碰结构：
  - tailwind 的 dark.* 色阶整体翻成浅色表面
  - --ink-* 文字色阶从「暗底浅字」翻成「浅底深字」
  - body 底色、玻璃卡片、hover 光效收掉
最后追加一层覆盖样式做细节收敛（圆角、边框、滚动条、强调色对比度）。
"""
from __future__ import annotations

import sys
from pathlib import Path

p = Path("templates/index.html")
t = p.read_text(encoding="utf-8")
orig_len = len(t)


def sub(old: str, new: str, label: str) -> None:
    global t
    if old not in t:
        print(f"✗ 没找到：{label}")
        sys.exit(1)
    t = t.replace(old, new, 1)
    print(f"✓ {label}")


# 1) 表面色阶：dark.* 从深空翻成浅色（名字保留，避免改 500 多处 class）
sub(
    """                        dark: {
                            900: 'rgb(11 15 25 / <alpha-value>)',
                            800: 'rgb(15 23 42 / <alpha-value>)',
                            700: 'rgb(22 30 49 / <alpha-value>)',
                            600: 'rgb(30 41 59 / <alpha-value>)',
                            border: 'rgba(255, 255, 255, 0.08)'
                        },""",
    """                        dark: {
                            // 浅色企业主题：名字沿用 dark.*，值换成表面色，
                            // 这样 500 多处 bg-dark-900 不用一个个改。
                            950: 'rgb(248 250 252 / <alpha-value>)',
                            900: 'rgb(255 255 255 / <alpha-value>)',
                            800: 'rgb(255 255 255 / <alpha-value>)',
                            700: 'rgb(249 250 251 / <alpha-value>)',
                            600: 'rgb(243 244 246 / <alpha-value>)',
                            border: 'rgba(16, 24, 40, 0.09)'
                        },""",
    "tailwind dark 色阶",
)

# 2) 文字色阶：浅底深字。--ink-white 从纯白改成近黑，text-white 自动变成标题色
INK_LIGHT = """            --ink-white: #FFFFFF;
            --ink-strong: #F8FAFC;
            --ink-body: #E2E8F0;
            --ink-soft: #CBD5E1;
            --ink-mute: #94A3B8;
            --ink-faint: #64748B;
            --ink-ghost: #475569;
            --ink-whisper: #334155;"""

INK_DARK = """            --ink-white: #101828;
            --ink-strong: #101828;
            --ink-body: #1D2939;
            --ink-soft: #344054;
            --ink-mute: #475467;
            --ink-faint: #667085;
            --ink-ghost: #98A2B3;
            --ink-whisper: #D0D5DD;"""

sub(INK_LIGHT, INK_DARK, ":root 文字色阶")
# aside/header 里又重复声明了一遍，同样翻转
assert INK_LIGHT in t, "aside/header 的第二份墨色块没找到"
t = t.replace(INK_LIGHT, INK_DARK, 1)
print("✓ aside/header 文字色阶")

# 3) body 底色：去掉三层辉光渐变，换中性浅灰
sub(
    """        body {
            background:
                radial-gradient(1200px 520px at 50% -10%, rgba(16, 185, 129, 0.12), transparent 68%),
                radial-gradient(900px 420px at 85% 15%, rgba(6, 182, 212, 0.08), transparent 60%),
                radial-gradient(800px 500px at 15% 85%, rgba(16, 185, 129, 0.06), transparent 65%),
                #0B0F19;
            color: #E2E8F0;
        }
        ::selection { background: rgba(16, 185, 129, 0.35); color: #FFFFFF; }""",
    """        body {
            background: #F4F6F9;
            color: #1D2939;
        }
        ::selection { background: #D6E4FF; color: #101828; }""",
    "body 底色",
)

# 4) 玻璃卡片 → 白卡 + 细边 + 极轻投影
sub(
    """            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4), inset 0 1px 0 0 rgba(255, 255, 255, 0.05);""",
    """            backdrop-filter: none;
            -webkit-backdrop-filter: none;
            background: #FFFFFF;
            border: 1px solid #E4E7EC;
            border-radius: 10px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);""",
    "glass-card 底色",
)

# 5) 卡片上的「鼠标跟随辉光」在企业浅色主题里是噪音，关掉
sub(
    """            background: radial-gradient(circle, rgba(16, 185, 129, 0.14) 0%, rgba(6, 182, 212, 0.04) 50%, transparent 75%);""",
    """            background: none;""",
    "卡片辉光层",
)

# 6) 覆盖层：细节收敛
overlay = """
        /* ==================================================================
         * 企业浅色主题覆盖层（2026-10 重做）
         * 目标：去掉霓虹/玻璃/大圆角，回到「白底、细边、深字、一处强调」的数据面板观感。
         * ================================================================== */
        body { background: #F4F6F9 !important; color: #1D2939 !important; }

        /* 去磨砂：浅色下毛玻璃会把字压灰 */
        [class*="backdrop-blur"] { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }

        /* 顶栏与侧栏：实心白 + 一条分隔线，不要发光边框 */
        header, aside, nav {
            background: #FFFFFF !important;
            box-shadow: none !important;
            border-color: #E4E7EC !important;
        }

        /* 圆角收敛：3xl/2xl 在数据面板里显得软 */
        .rounded-3xl { border-radius: 12px !important; }
        .rounded-2xl { border-radius: 10px !important; }

        /* 悬停抬升改成轻微阴影，不做位移缩放 */
        .card-perspective:hover { transform: none !important; box-shadow: 0 2px 8px rgba(16, 24, 40, 0.08) !important; }

        /* 强调色在浅底上要压深一档才够对比度 */
        [class*="text-accent-emerald"], [class*="text-emerald-3"], [class*="text-emerald-4"] { color: #067647 !important; }
        [class*="text-accent-cyan"], [class*="text-cyan-3"], [class*="text-cyan-4"] { color: #0E7090 !important; }
        [class*="text-accent-amber"], [class*="text-amber-3"], [class*="text-amber-4"] { color: #B54708 !important; }
        [class*="text-accent-rose"], [class*="text-rose-3"], [class*="text-rose-4"] { color: #B42318 !important; }
        [class*="text-accent-steel"], [class*="text-slate-4"] { color: #475467 !important; }

        /* 分隔线：浅底上统一成灰 */
        [class*="border-dark-border"], .border-dark-border { border-color: #E4E7EC !important; }
        hr { border-color: #E4E7EC !important; }

        /* 滚动条 */
        ::-webkit-scrollbar-thumb { background: #D0D5DD !important; }

        /* 表格/列表行高亮 */
        tbody tr:hover { background: #F9FAFB !important; }

        /* 深色代码块（事件流 / SQL）保留黑底，但把字色钉住，别被主题翻成深灰 */
        pre, .font-mono code { color: inherit; }
        #failover-log-box, #event-stream, #sql-display { color: #E4E7EC !important; }
"""
sub("    </style>", overlay + "    </style>", "覆盖层")

p.write_text(t, encoding="utf-8")
print(f"完成：{orig_len} → {len(t)} 字符")
