"""
Converts ENGINEERING_COMPLETION_REPORT.md to a PDF, using Python's
markdown library to render HTML and Edge's headless print-to-pdf to
produce the final file. No Pandoc/LaTeX install needed.

Usage: python md_to_pdf.py
"""
import os
import subprocess

import markdown

HERE = os.path.dirname(__file__)
MD_PATH = os.path.join(HERE, "ENGINEERING_COMPLETION_REPORT.md")
HTML_PATH = os.path.join(HERE, "_report_render.html")
PDF_PATH = os.path.join(HERE, "ENGINEERING_COMPLETION_REPORT.pdf")
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
<style>
  body {
    font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
    color: #1a1a1a;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px 10px;
    line-height: 1.5;
  }
  h1, h2, h3 { color: #111; }
  h1 { border-bottom: 2px solid #333; padding-bottom: 8px; }
  h2 { border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 32px; }
  h3 { margin-top: 22px; }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 0.92em;
  }
  th, td {
    border: 1px solid #999;
    padding: 6px 10px;
    text-align: left;
    vertical-align: top;
  }
  th { background: #eee; }
  pre {
    background: #f4f4f4;
    border: 1px solid #ccc;
    padding: 12px;
    overflow-x: auto;
    font-size: 0.85em;
    line-height: 1.3;
  }
  code {
    font-family: Consolas, Menlo, monospace;
  }
  hr { border: none; border-top: 1px solid #ccc; margin: 24px 0; }
  blockquote {
    border-left: 3px solid #999;
    margin-left: 0;
    padding-left: 14px;
    color: #444;
  }
  @media print {
    body { max-width: 100%; }
  }
</style>
"""


def main():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    body_html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    full_html = f"<!doctype html><html><head><meta charset='utf-8'>{CSS}</head><body>{body_html}</body></html>"

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    subprocess.run(
        [
            EDGE_EXE,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={PDF_PATH}",
            "--no-margins",
            f"file:///{HTML_PATH.replace(os.sep, '/')}",
        ],
        check=True,
    )
    os.remove(HTML_PATH)
    print(f"PDF written to {PDF_PATH}")


if __name__ == "__main__":
    main()
