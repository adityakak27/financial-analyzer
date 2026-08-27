from __future__ import annotations

from finchat.collect.text_pipeline import chunk_text
from finchat.nlp.sections import extract_sections, html_to_text

FILLER_RISK = ("Our business faces supply chain disruption and component shortage risks. "
               "Competition in our industry is intense. ") * 60
FILLER_MDA = ("Gross margins improved due to pricing actions and cost discipline. "
              "We continue to invest in research and development. ") * 60
TAIL = ("We are exposed to interest rate risk. " * 40)

SAMPLE_HTML = f"""<html><body>
<p>Item 1A. Risk Factors</p>
<p>{FILLER_RISK}</p>
<p>Item 1B. Unresolved Staff Comments</p>
<p>None.</p>
<p>Item 7. Management's Discussion and Analysis of Financial Condition</p>
<p>{FILLER_MDA}</p>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</p>
<p>{TAIL}</p>
<p>Item 8. Financial Statements and Supplementary Data</p>
</body></html>"""

SPLIT_HTML = f"""<html><body><table>
<tr><td>Part I</td></tr>
<tr><td>Item</td><td>1A.</td><td>Risk Factors</td></tr>
<tr><td colspan="3">{FILLER_RISK}</td></tr>
<tr><td>Item</td><td>1B.</td><td>Unresolved Staff Comments</td></tr>
<tr><td>None</td></tr>
<tr><td>Item</td><td>7.</td><td>Management's Discussion and Analysis</td></tr>
<tr><td colspan="3">{FILLER_MDA}</td></tr>
<tr><td>Item</td><td>7A.</td><td>Market Risk</td></tr>
<tr><td colspan="3">{TAIL}</td></tr>
<tr><td>Item</td><td>8.</td><td>Financial Statements</td></tr>
</table></body></html>"""


def test_html_to_text_strips_tags():
    text = html_to_text(SAMPLE_HTML)
    assert "supply chain" in text
    assert "<p>" not in text


def test_extract_sections_finds_mda_and_risk():
    text = html_to_text(SAMPLE_HTML)
    sections = extract_sections(text)
    assert "mda" in sections and "risk" in sections
    assert "Gross margins improved" in sections["mda"]
    assert "supply chain" in sections["risk"]
    assert "Financial Statements" not in sections["mda"]
    assert "Unresolved" not in sections["risk"]


def test_extract_sections_survives_table_split_headings():
    text = html_to_text(SPLIT_HTML)
    sections = extract_sections(text)
    assert "mda" in sections, f"sections={list(sections)}"
    assert "Gross margins improved" in sections["mda"]
    assert "risk" in sections
    assert "supply chain" in sections["risk"]


def test_chunking():
    long_para = " ".join(f"sentence {i} with some filler words to pad length" for i in range(200))
    chunks = chunk_text(long_para, size=1200, overlap=150)
    assert len(chunks) > 1
    assert all(len(c) <= 1400 for c in chunks)
