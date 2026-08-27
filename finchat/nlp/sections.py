from __future__ import annotations

import re
from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


_HEADING = re.compile(r"(?im)^[\s\-_]*(item\s+\d{1,2}[A-B]?)\b[\s\.\:\-_]*(.{0,90})$")

WANTED = {"1A", "1B", "7", "7A", "8"}

MAX_SECTION_CHARS = 900_000
MIN_SECTION_CHARS = 3000

MDA_MARKERS = [
    "results of operations", "liquidity", "capital resources", "critical accounting",
    "gross margin", "operating expenses", "cash flows", "fiscal year",
]
RISK_MARKERS = [
    "could adversely", "material adverse", "risk factors", "competition",
    "litigation", "regulatory", "our business", "may be harmed",
]
DENSITY_MIN = {"mda": 1.5, "risk": 2.0}


def _headings(text: str) -> list[tuple[int, str, str]]:
    out = []
    for m in _HEADING.finditer(text):
        num = m.group(1).upper().replace(" ", "").replace("ITEM", "")
        num = re.sub(r"[^0-9A-B]", "", num)
        if num in WANTED:
            out.append((m.start(), num, m.group(2)[:60]))
    return out


def _last_paired(headings: list[tuple[int, str, str]], start_tag: str,
                 end_tags: set[str], min_len: int) -> tuple[int, int] | None:
    best = None
    for i, (pos, num, _) in enumerate(headings):
        if num != start_tag:
            continue
        for pos2, num2, _ in headings[i + 1:]:
            if num2 in end_tags and pos2 - pos <= MAX_SECTION_CHARS:
                if pos2 - pos >= min_len:
                    best = (pos, pos2)
                break
    return best


def _extract_line_based(text: str) -> dict[str, str]:
    hs = _headings(text)
    out: dict[str, str] = {}
    pair = _last_paired(hs, "7", {"7A", "8"}, MIN_SECTION_CHARS)
    if pair:
        out["mda"] = text[pair[0]:pair[1]]
    pair = _last_paired(hs, "1A", {"1B", "7"}, MIN_SECTION_CHARS)
    if pair:
        out["risk"] = text[pair[0]:pair[1]]
    return out


_FLAT_HEADING = re.compile(r"(?i)\bitem\s+(\d{1,2}[A-B]?)\b[\s\.\:\-_]")


def _flat_candidates(flat: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(1).upper()) for m in _FLAT_HEADING.finditer(flat)
            if m.group(1).upper() in WANTED]


def _candidate_pairs(cands: list[tuple[int, str]], start_tag: str,
                     end_tags: set[str]) -> list[tuple[int, int]]:
    pairs = []
    for i, (pos, num) in enumerate(cands):
        if num != start_tag:
            continue
        for pos2, num2 in cands[i + 1:]:
            if pos2 - pos > MAX_SECTION_CHARS:
                break
            if num2 in end_tags:
                span = pos2 - pos
                if span >= MIN_SECTION_CHARS:
                    pairs.append((pos, pos2))
                break
    return pairs


def _pick_best(flat: str, pairs: list[tuple[int, int]], markers: list[str],
               max_pairs: int = 80) -> tuple[int, int] | None:
    best, best_score = None, -1.0
    for s, e in pairs[:max_pairs]:
        density = _density(flat[s:e].lower(), markers)
        if density > best_score:
            best, best_score = (s, e), density
    return best


_MDA_TITLE = re.compile(r"(?i)(?<![a-z])management'?s discussion and analysis(?![a-z])")
_MDA_TITLE_END = re.compile(
    r"(?i)quantitative and qualitative disclosures|financial statements and supplementary data")
_RISK_TITLE = re.compile(r"(?i)(?<![a-z])risk factors(?![a-z])")
_RISK_TITLE_END = re.compile(
    r"(?i)unresolved staff comments|item\s*1b(?![0-9a-b])|market for registrant")


def _normalize(text: str) -> str:
    return text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')


def _density(seg: str, markers: list[str]) -> float:
    n = max(len(seg), 1)
    return sum(seg.count(m) for m in markers) * 10000.0 / n


def _title_anchor(flat: str, title_re, end_re, markers: list[str],
                  density_min: float) -> tuple[int, int] | None:
    titles = [m.start() for m in title_re.finditer(flat)]
    for start in reversed(titles[-60:]):
        end_m = end_re.search(flat, start + MIN_SECTION_CHARS)
        if not end_m or (end_m.start() - start) > MAX_SECTION_CHARS:
            continue
        seg = flat[start:end_m.start()].lower()
        if len(seg) >= MIN_SECTION_CHARS and _density(seg, markers) >= density_min:
            return start, end_m.start()
    return None


def extract_sections(text: str) -> dict[str, str]:
    text = _normalize(text)
    flat = re.sub(r"\s+", " ", text)
    line = _extract_line_based(text)
    cands = _flat_candidates(flat)

    result: dict[str, str] = {}

    def collect(sec: str) -> list[tuple[float, int, str]]:
        collected: list[tuple[float, int, str]] = []
        markers = MDA_MARKERS if sec == "mda" else RISK_MARKERS
        thresh = DENSITY_MIN[sec]
        v = line.get(sec)
        if v:
            d = _density(v.lower(), markers)
            if d >= thresh:
                collected.append((d, len(v), v))
        if sec == "mda":
            pair = _title_anchor(flat, _MDA_TITLE, _MDA_TITLE_END, markers, thresh)
        else:
            pair = _title_anchor(flat, _RISK_TITLE, _RISK_TITLE_END, markers, thresh)
        if pair:
            seg = flat[pair[0]:pair[1]]
            collected.append((_density(seg.lower(), markers), len(seg), seg))
        start_tag, end_tags = ("7", {"7A", "8"}) if sec == "mda" else ("1A", {"1B", "7"})
        pairs = _candidate_pairs(cands, start_tag, end_tags)
        best = _pick_best(flat, pairs, markers)
        if best:
            seg = flat[best[0]:best[1]]
            d = _density(seg.lower(), markers)
            if d >= thresh:
                collected.append((d, len(seg), seg))
        return collected

    for sec in ("mda", "risk"):
        options = collect(sec)
        if options:
            options.sort(key=lambda x: (x[0] * (x[1] ** 0.5), x[0], x[1]), reverse=True)
            result[sec] = options[0][2]

    return {k: v for k, v in result.items() if len(v) >= MIN_SECTION_CHARS}
