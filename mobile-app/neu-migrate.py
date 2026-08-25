"""一次性迁移脚本：把 mobile-app 各页面 <style> 里残留的「边框 + 平铺底色」旧语言
改写为 tokens.css 里既定的拟物化（Neumorphism）词汇。跑完即可删除。

词汇表（与 theme/neumorphism.css、theme/publishing.css 保持一致）：
  凸起表面  border: 0 + background: var(--neu-surface) + box-shadow: var(--neu-raise|-sm)
  凹陷表面  border: 0 + background: var(--paper)       + box-shadow: var(--neu-inset)
  品牌实体  background: var(--neu-surface-brand) + 双向阴影，按下转 --neu-inset-brand
  禁用      background: var(--paper-deep) + box-shadow: none
  分隔线    1px var(--neu-light) + 0 1px 0 var(--neu-shade-soft)（浮雕棱线）
"""

from __future__ import annotations

import glob
import re
import sys

BRAND_RAISE = "-4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade)"
FOCUS_RING = "var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26)"
INVALID_RING = "var(--neu-inset), 0 0 0 2px rgba(163, 59, 50, 0.34)"

SMALL_HINTS = (
    "badge", "chip", "pill", "count", "dot", "marker", "icon", "thumb", "cell",
    "tag", "stat", "file", "tab", "option", "avatar", "orb", "legend", "action",
    "button", "btn", "trigger", "toggle", "step", "bubble",
    ".primary", ".secondary", ".danger", ".apply", ".confirm", ".cancel",
    "submit", "send", "follow", "login", "register", "logout", "retry",
    "remove", "close", "edit-materials", "load-more",
)
BAR_HINTS = ("footer", "-bar", "bar ", "toolbar", "shell", "composer-", "input-bar")
INPUT_HINTS = (
    "input", "textarea", "select", "-field", "notes-field", "text-field",
    "tag-input", "search-results",
)
GRID_CELL_HINTS = ("grid", "facts", "benefits", "readonly-list", "contact-list",
                   "rule-item", "month-stats", "fact-item")
MEDIA_HINTS = ("media", "cover", "thumb", "placeholder", "preview", "frame", "map")

BORDER_RE = re.compile(
    r"^(1px|2px|3px|4px)\s+(solid|dashed)\s+(.+)$", re.S)
NUM_RADIUS_RE = re.compile(r"(?<![\w-])(\d+)px")
OLD_SHADOW_RE = re.compile(r"^0\s+(-?\d+)px\s+(\d+)px", re.S)
RING_SHADOW_RE = re.compile(r"^0\s+0\s+0\s+(\d+)px")


def is_neutral_border(value: str) -> bool:
    v = value.replace(" ", "")
    return any(
        k in v
        for k in ("var(--border)", "var(--divider)", "var(--border-light)",
                  "rgba(26,26,26,0.08)", "rgba(98,91,78,")
    )


def radius_token(px: int) -> str:
    if px >= 99:
        return "var(--radius-pill)"
    if px <= 7:
        return "var(--radius-sm)"
    if px <= 15:
        return "var(--radius-md)"
    return "var(--radius-lg)"


class Decls:
    """按顺序保存声明，支持按属性名读写，序列化时保留原缩进。"""

    def __init__(self, body: str) -> None:
        self.indent = "  "
        self.inline = "\n" not in body.strip()
        m = re.search(r"\n([ \t]+)\S", body)
        if m:
            self.indent = m.group(1)
        self.items: list[list[str] | str] = []
        buf = ""
        for chunk in re.split(r"(;)", body):
            if chunk == ";":
                self._push(buf)
                buf = ""
            else:
                buf += chunk
        self._push(buf)

    def _push(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return
        if ":" in text and not text.startswith("/*"):
            prop, _, value = text.partition(":")
            self.items.append([prop.strip(), value.strip()])
        else:
            self.items.append(text)

    def get(self, prop: str) -> str | None:
        for item in self.items:
            if isinstance(item, list) and item[0] == prop:
                return item[1]
        return None

    def has(self, prop: str) -> bool:
        return self.get(prop) is not None

    def set(self, prop: str, value: str, after: str | None = None) -> None:
        for item in self.items:
            if isinstance(item, list) and item[0] == prop:
                item[1] = value
                return
        index = len(self.items)
        if after:
            for i, item in enumerate(self.items):
                if isinstance(item, list) and item[0] == after:
                    index = i + 1
                    break
        self.items.insert(index, [prop, value])

    def drop(self, prop: str) -> None:
        self.items = [
            item for item in self.items
            if not (isinstance(item, list) and item[0] == prop)
        ]

    def rename(self, old: str, new: str) -> None:
        for item in self.items:
            if isinstance(item, list) and item[0] == old:
                item[0] = new

    def render(self) -> str:
        if self.inline:
            return " " + " ".join(
                f"{item[0]}: {item[1]};" if isinstance(item, list) else item
                for item in self.items
            ) + " "
        lines = []
        for item in self.items:
            if isinstance(item, list):
                lines.append(f"{self.indent}{item[0]}: {item[1]};")
            else:
                lines.append(f"{self.indent}{item}")
        return "\n" + "\n".join(lines) + "\n" + self.indent[:-2]


def rewrite(selector: str, body: str) -> str:
    if "{" in body or "}" in body:
        return body
    sel = " ".join(selector.split()).lower()
    d = Decls(body)
    touched = False

    def hint(hints) -> bool:
        return any(h in sel for h in hints)

    is_disabled = ":disabled" in sel or "[disabled]" in sel or ".disabled" in sel
    is_focus = ":focus" in sel
    is_active = ":active" in sel
    is_input = hint(INPUT_HINTS)
    small = hint(SMALL_HINTS)
    raise_shadow = "var(--neu-raise-sm)" if small else "var(--neu-raise)"

    border = d.get("border")
    border_color = d.get("border-color")
    bg = (d.get("background") or d.get("background-color") or "").strip()
    shadow = d.get("box-shadow")

    def set_raise(surface: str = "var(--neu-surface)") -> None:
        d.set("border", "0")
        if d.has("background-color"):
            d.rename("background-color", "background")
        d.set("background", surface, after="border-radius")
        d.set("box-shadow", raise_shadow, after="background")

    def set_inset(surface: str = "var(--paper)") -> None:
        d.set("border", "0")
        if d.has("background-color"):
            d.rename("background-color", "background")
        d.set("background", surface, after="border-radius")
        d.set("box-shadow", "var(--neu-inset)", after="background")

    # ── 品牌实体（主行动） ────────────────────────────────
    if bg in ("var(--brand)", "var(--brand-strong)"):
        if border or border_color:
            d.set("border", "0")
            d.drop("border-color")
        d.set("background", "var(--neu-surface-brand)")
        d.set("box-shadow", BRAND_RAISE if not is_active else "var(--neu-inset-brand)",
              after="background")
        touched = True

    # ── 禁用：压平 ────────────────────────────────────────
    elif is_disabled and (border or border_color or bg or shadow):
        d.drop("border-color")
        if border and is_neutral_border(border):
            d.set("border", "0")
        if bg:
            d.set("background", "var(--paper-deep)")
        d.set("box-shadow", "none", after="background")
        touched = True

    # ── 焦点环：凹陷加深 + 品牌描边 ─────────────────────────
    elif is_focus and (border_color or (shadow and RING_SHADOW_RE.match(shadow))):
        if border_color == "var(--brand)":
            d.drop("border-color")
        if shadow and RING_SHADOW_RE.match(shadow):
            d.set("box-shadow", FOCUS_RING)
        elif border_color == "var(--brand)":
            d.set("box-shadow", FOCUS_RING)
        touched = True

    # ── 输入控件：一律凹陷 ────────────────────────────────
    elif is_input and (border or bg) and "results" not in sel:
        set_inset()
        touched = True

    # ── 有完整边框的块：按底色判断凸 / 凹 ──────────────────
    elif border and BORDER_RE.match(border):
        m = BORDER_RE.match(border)
        width, style, color = m.group(1), m.group(2), m.group(3).strip()
        if style == "dashed":
            set_inset()
            touched = True
        elif color == "var(--brand)":
            # 品牌描边 + 浅底：视为次要按钮 / 强调卡片
            set_raise()
            touched = True
        elif is_neutral_border(color):
            if bg == "var(--divider)":
                set_inset()          # 1px 网格线容器 → 凹槽
            elif bg == "var(--paper)":
                set_inset()
            elif bg == "var(--brand-soft)":
                d.set("border", "0")
                d.set("box-shadow", raise_shadow, after="background")
            elif bg.startswith("var(--ink") or bg.startswith("rgba"):
                d.set("border", "0")
                d.set("box-shadow", raise_shadow, after="background")
            elif bg in ("var(--paper-light)", "var(--paper-deep)", "transparent", ""):
                if hint(MEDIA_HINTS):
                    set_inset()
                else:
                    set_raise()
            else:
                d.set("border", "0")
                d.set("box-shadow", raise_shadow, after="background")
            touched = True
        elif width in ("2px", "3px", "4px") and "paper" in color:
            d.set("border", f"{width} {style} var(--paper)")
            touched = True

    # ── 只有底色的块 ──────────────────────────────────────
    if not touched and bg:
        if bg == "var(--paper-light)":
            if hint(BAR_HINTS):
                d.set("background", "var(--paper)")
            elif hint(GRID_CELL_HINTS):
                d.set("background", "transparent")
            elif not shadow:
                d.set("background", "var(--neu-surface)")
                d.set("box-shadow", raise_shadow, after="background")
            else:
                d.set("background", "var(--neu-surface)")
            touched = True
        elif bg == "var(--paper-deep)" and "skeleton" not in sel:
            d.set("background", "var(--paper)")
            if not shadow:
                d.set("box-shadow", "var(--neu-inset)", after="background")
            touched = True

    # ── 方向性分隔线 → 浮雕棱线（受光侧高光，背光侧暗影） ───
    for side, offset in (("bottom", "0 1px 0"), ("right", "1px 0 0"),
                         ("top", "inset 0 1px 0"), ("left", "inset 1px 0 0")):
        prop = f"border-{side}"
        value = d.get(prop)
        if not value or not BORDER_RE.match(value):
            continue
        m = BORDER_RE.match(value)
        if m.group(1) != "1px" or not is_neutral_border(m.group(3)):
            continue
        d.set(prop, "1px solid var(--neu-light)")
        if not d.has("box-shadow"):
            d.set("box-shadow", f"{offset} var(--neu-shade-soft)", after=prop)
        touched = True

    # ── ion 自定义属性底色 ────────────────────────────────
    for prop in ("--background", "--border-color"):
        value = d.get(prop)
        if value in ("var(--paper-light)", "var(--paper-deep)"):
            d.set(prop, "var(--paper)")
            touched = True

    # ── 圆角统一到令牌（拟物化要求一致的大圆角） ────────────
    radius = d.get("border-radius")
    if radius and "var(" not in radius and "%" not in radius:
        parts = radius.split()
        if all(NUM_RADIUS_RE.fullmatch(p) for p in parts):
            d.set("border-radius",
                  " ".join(radius_token(int(p[:-2])) for p in parts))
            touched = True

    # ── 旧投影 → 浮雕令牌 ────────────────────────────────
    shadow = d.get("box-shadow")
    if shadow and "neu-" not in shadow and "rgba" in shadow and not is_active:
        m = OLD_SHADOW_RE.match(shadow)
        if m and not RING_SHADOW_RE.match(shadow):
            blur = int(m.group(2))
            token = ("var(--neu-raise-sm)" if blur <= 8
                     else "var(--neu-raise)" if blur < 20
                     else "var(--neu-raise-lg)")
            d.set("box-shadow", token)
            touched = True

    # ── 交互元素补上 box-shadow 过渡 ───────────────────────
    transition = d.get("transition")
    if touched and transition and "box-shadow" not in transition:
        if "border-color" in transition:
            transition = re.sub(r"border-color(\s+[^,]+)?", r"box-shadow\1", transition)
        else:
            transition = f"{transition}, box-shadow var(--motion-fast) ease"
        d.set("transition", transition)

    if not touched:
        return body
    return d.render()


def process(path: str) -> bool:
    text = open(path, encoding="utf-8").read()
    out = []
    cursor = 0
    changed = False
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S):
        css = m.group(1)
        new_css = []
        pos = 0
        for rule in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
            body = rule.group(2)
            new_body = rewrite(rule.group(1), body)
            if new_body != body:
                changed = True
            new_css.append(css[pos:rule.start(2)])
            new_css.append(new_body)
            pos = rule.end(2)
        new_css.append(css[pos:])
        out.append(text[cursor:m.start(1)])
        out.append("".join(new_css))
        cursor = m.end(1)
    out.append(text[cursor:])
    if changed:
        open(path, "w", encoding="utf-8", newline="").write("".join(out))
    return changed


if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(glob.glob("src/**/*.vue", recursive=True))
    for f in targets:
        if process(f):
            print("updated", f)
