"""Step 10: render a report markdown file to a styled, shareable PDF.
Markdown -> HTML (tables, figures, cover page) -> A4 PDF via headless Chromium (Playwright).

Usage: python 10_export_pdf.py [source.md] [output.pdf]
Defaults: report/results.md -> report/Mispricing_Radar_Report.pdf"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import ANALYSIS_ROOT, REPORT_DIR

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #1f2328; font-size: 10.5pt;
       line-height: 1.5; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4mm; color: #14213d; }
h2 { font-size: 15pt; color: #14213d; border-bottom: 2px solid #cc785c; padding-bottom: 2mm;
     margin: 9mm 0 4mm; break-after: avoid; }
h2.page, h3.page { break-before: page; }
h2.page { margin-top: 0; }
h3 { font-size: 12.5pt; color: #14213d; margin: 7mm 0 3mm; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
strong { color: #111; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f2f2f0; padding: 0 3px; border-radius: 3px; }
blockquote { margin: 4mm 0; padding: 3mm 5mm; background: #faf6f3; border-left: 3px solid #cc785c;
             color: #333; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0 5mm; font-size: 8.6pt; break-inside: avoid; }
th { background: #14213d; color: #fff; text-align: left; padding: 1.6mm 2mm; font-weight: 600; }
td { padding: 1.4mm 2mm; border-bottom: 1px solid #e3e3e0; vertical-align: top; }
tr:nth-child(even) td { background: #f7f7f5; }
img { display: block; max-width: 100%; max-height: 118mm; margin: 4mm auto 2mm; break-inside: avoid; }
p:has(> img) { break-inside: avoid; text-align: center; }
em { color: #555; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: center; break-after: page; }
.cover .kicker { color: #cc785c; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: 10pt; }
.cover h1 { font-size: 30pt; line-height: 1.15; margin: 4mm 0 6mm; }
.cover .sub { font-size: 13pt; color: #444; max-width: 150mm; }
.cover .facts { margin-top: 14mm; display: grid; grid-template-columns: repeat(3, 1fr); gap: 5mm; max-width: 165mm; }
.cover .fact { border-top: 3px solid #cc785c; padding-top: 2mm; }
.cover .fact b { display: block; font-size: 17pt; color: #14213d; }
.cover .fact span { font-size: 9pt; color: #555; }
.cover .meta { margin-top: 18mm; font-size: 9.5pt; color: #666; }
"""


def build_html(md_text: str) -> str:
    title_line, _, body_md = md_text.partition("\n")
    subtitle = re.search(r"^\*(.+?)\*\s*$", body_md, re.M)
    body_md = body_md.replace(subtitle.group(0), "", 1) if subtitle else body_md

    body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"])
    base = ANALYSIS_ROOT.as_uri() + "/"
    body = re.sub(r'src="(?!https?:|file:)([^"]+)"', lambda m: f'src="{base}{m.group(1)}"', body)
    # New page only for major sections and each research question; short sections flow on.
    for h2 in ("Results", "Building blocks used by every RQ", "How the AI system uses these results",
               "AI-generated key findings and company notes", "Limitations", "Revisions since the first version",
               "Appendix A: Financial terms", "How the AI chat uses these results"):
        body = body.replace(f"<h2>{h2}</h2>", f'<h2 class="page">{h2}</h2>', 1)
    body = re.sub(r"<h3>(RQ[2-9][: ])", r'<h3 class="page">\1', body)
    n_rq = len(set(re.findall(r"^### (RQ\d+)[: ]", md_text, re.M)))
    n_fig = len(set(re.findall(r"!\[(Figure\d+)", md_text)))

    cover = f"""
<section class="cover">
  <div class="kicker">FinChat &middot; Equity Research Copilot</div>
  <h1>{title_line.lstrip('# ').strip()}</h1>
  <div class="sub">A point-in-time study of fundamental quality versus market valuation in US technology
  stocks, built from SEC 10-K filings, with an AI analyst layer whose every number is verified.</div>
  <div class="facts">
    <div class="fact"><b>57</b><span>companies, S&amp;P 500 tech</span></div>
    <div class="fact"><b>399</b><span>company-years, FY2018-2024</span></div>
    <div class="fact"><b>{n_fig}</b><span>figures &middot; {n_rq} research questions</span></div>
  </div>
  <div class="meta">{subtitle.group(1) if subtitle else ''}<br>{dt.date.today():%B %Y}</div>
</section>"""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title_line.lstrip('# ')}</title>"
            f"<style>{CSS}</style></head><body>{cover}{body}</body></html>")


def main():
    from playwright.sync_api import sync_playwright

    src = REPORT_DIR / (sys.argv[1] if len(sys.argv) > 1 else "results.md")
    pdf_path = REPORT_DIR / (sys.argv[2] if len(sys.argv) > 2 else "Mispricing_Radar_Report.pdf")
    md_text = src.read_text(encoding="utf-8")
    html_path = src.with_suffix(".html")
    html_path.write_text(build_html(md_text), encoding="utf-8")

    footer = ("<div style='width:100%;font-size:8px;color:#888;padding:0 16mm;display:flex;"
              "justify-content:space-between'><span>Mispricing Radar &middot; FinChat</span>"
              "<span>Page <span class='pageNumber'></span> of <span class='totalPages'></span></span></div>")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="load")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, display_header_footer=True,
                 header_template="<div></div>", footer_template=footer,
                 margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
        browser.close()
    print(f"[saved] {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
