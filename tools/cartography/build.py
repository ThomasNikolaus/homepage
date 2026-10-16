#!/usr/bin/env python3
"""Build the Exploration Charts catalogue and static landing pages (stdlib only)."""

import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from urllib.parse import quote

START = "<!-- CHART-CATALOGUE:START -->"
END = "<!-- CHART-CATALOGUE:END -->"
SITE_ORIGIN = "https://thomasnikolaus.de"
ID_RE = re.compile(r"HC-(?:[0-9]{4}|[1-9][0-9]{4,})")
VERSION_RE = re.compile(r"v[1-9][0-9]*")
DOI_RE = re.compile(r"10\.[0-9]{4,9}/[^\s<>\"']+")
ARXIV_RE = re.compile(r"(?:[0-9]{4}\.[0-9]{4,5}|[a-z][a-z.\-]+/[0-9]{7})(?:v[1-9][0-9]*)?")
FINGERPRINT_RE = re.compile(r"<!-- CHART-VERSION-FINGERPRINT:([0-9a-f]{64}) -->")


def escape(value):
    return html.escape(str(value), quote=True)


def required_text(record, name, context):
    value = record.get(name)
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"{context}: {name} must be a nonempty, single-line string")
    return value.strip()


def optional_identifier(record, name, pattern, context):
    value = record.get(name)
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{context}: invalid {name}; supply the identifier, not a URL")
    return value


def local_pdf(site_root, value, context):
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or "\\" in value
            or any(c in value for c in "?#%:") or path.suffix.lower() != ".pdf"):
        raise ValueError(f"{context}: pdf must be a plain site-relative PDF path")
    resolved = (site_root / path).resolve()
    if not resolved.is_relative_to(site_root):
        raise ValueError(f"{context}: pdf path escapes the site root")
    if not resolved.is_file():
        raise ValueError(f"{context}: local PDF is missing: {value}")
    return "/" + quote(path.as_posix(), safe="/"), hashlib.sha256(resolved.read_bytes()).hexdigest()


def load_charts(site_root):
    data = json.loads((site_root / "homotopical-cartography/charts.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("charts"), list):
        raise ValueError("charts.json must contain an object with a charts list")
    charts = []
    seen_ids = set()
    for raw in data["charts"]:
        if not isinstance(raw, dict):
            raise ValueError("Each chart must be an object")
        chart_id = required_text(raw, "id", "Chart")
        if not ID_RE.fullmatch(chart_id) or int(chart_id[3:]) == 0:
            raise ValueError(f"Invalid chart ID: {chart_id}; use HC-0001, HC-0002, …")
        if chart_id in seen_ids:
            raise ValueError(f"Duplicate chart ID: {chart_id}")
        seen_ids.add(chart_id)
        chart = {"id": chart_id, "slug": chart_id.lower(), "versions": []}
        chart["concept_doi"] = optional_identifier(raw, "concept_doi", DOI_RE, chart_id)
        versions = raw.get("versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError(f"{chart_id}: versions must be a nonempty list")
        seen_versions = set()
        for raw_version in versions:
            if not isinstance(raw_version, dict):
                raise ValueError(f"{chart_id}: each version must be an object")
            version = required_text(raw_version, "version", chart_id)
            context = f"{chart_id} {version}"
            if not VERSION_RE.fullmatch(version):
                raise ValueError(f"{context}: version must be v1, v2, …")
            if version in seen_versions:
                raise ValueError(f"{context}: duplicate version")
            seen_versions.add(version)
            record = {"version": version}
            for field in ("title", "date", "abstract", "pdf", "status", "human_review"):
                record[field] = required_text(raw_version, field, context)
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", record["date"]):
                raise ValueError(f"{context}: date must use YYYY-MM-DD")
            datetime.date.fromisoformat(record["date"])
            authors = raw_version.get("authors")
            if not isinstance(authors, list) or not authors:
                raise ValueError(f"{context}: authors must be a nonempty list")
            record["authors"] = [required_text({"name": author}, "name", context) for author in authors]
            record["pdf_url"], record["pdf_hash"] = local_pdf(site_root, record["pdf"], context)
            record["doi"] = optional_identifier(raw_version, "doi", DOI_RE, context)
            record["arxiv"] = optional_identifier(raw_version, "arxiv", ARXIV_RE, context)
            frozen = {key: record[key] for key in ("version", "title", "authors", "date", "abstract", "pdf", "pdf_hash")}
            frozen["id"] = chart_id
            record["fingerprint"] = hashlib.sha256(json.dumps(frozen, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            chart["versions"].append(record)
        chart["versions"].sort(key=lambda record: int(record["version"][1:]), reverse=True)
        charts.append(chart)
    return sorted(charts, key=lambda chart: chart["id"])


def chart_url(chart, version=None):
    base = f"/homotopical-cartography/charts/{chart['slug']}/"
    return base + (version + "/" if version else "")


def links(record):
    values = [f'<a href="{escape(record["pdf_url"])}">PDF</a>']
    if record["doi"]:
        doi = record["doi"]
        values.append(f'<a href="https://doi.org/{escape(quote(doi, safe="/"))}">DOI: {escape(doi)}</a>')
    if record["arxiv"]:
        arxiv = record["arxiv"]
        values.append(f'<a href="https://arxiv.org/abs/{escape(quote(arxiv, safe="/"))}">arXiv: {escape(arxiv)}</a>')
    return '<p class="chart-links">' + " · ".join(values) + "</p>"


def metadata(chart, record):
    return (f'<p class="chart-meta">{escape("; ".join(record["authors"]))}<br>'
            f'{escape(chart["id"])} · {escape(record["version"])} · '
            f'<time datetime="{escape(record["date"])}">{escape(record["date"])}</time><br>'
            f'<strong>Status:</strong> {escape(record["status"])}</p>')


def catalogue(charts):
    if not charts:
        placeholders = (
            ("Group completion commutes with infinite products", "group-completion-commutes-with-infinite-products.pdf"),
            ("There is no infinite Künneth", "there-is-no-infinite-kunneth.pdf"),
        )
        entries = []
        for title, filename in placeholders:
            href = "/homotopical-cartography/placeholders/" + filename
            entries.append('<article class="chart-record chart-placeholder-record">\n'
                           f'<h3><a href="{escape(href)}">{escape(title)}</a></h3>\n'
                           f'<p class="chart-links"><a href="{escape(href)}">PDF</a> · Placeholder</p>\n'
                           '</article>')
        return "\n".join(entries)
    entries = []
    for chart in charts:
        record = chart["versions"][0]
        entries.append(f'<article class="chart-record">\n'
                       f'<h3><a href="{chart_url(chart)}">{escape(record["title"])}</a></h3>\n'
                       + metadata(chart, record) + '\n'
                       + f'<p class="chart-abstract">{escape(record["abstract"])}</p>\n'
                       + links(record) + '\n</article>')
    return "\n".join(entries)


def landing_page(chart, record, current):
    title = escape(record["title"])
    body = (f'<h1>{title}</h1>\n' + metadata(chart, record) + '\n'
            + f'<p class="chart-abstract">{escape(record["abstract"])}</p>\n' + links(record)
            + '\n<h2>Human verification and understanding</h2>\n'
            + f'<p class="chart-human-review">{escape(record["human_review"])}</p>')
    if current:
        if chart["concept_doi"]:
            doi = chart["concept_doi"]
            body += (f'\n<p class="chart-links">All versions: '
                     f'<a href="https://doi.org/{escape(quote(doi, safe="/"))}">{escape(doi)}</a></p>')
        body += '\n<h2>Versions</h2>\n<ul class="chart-version-list">'
        for item in chart["versions"]:
            body += (f'\n<li><a href="{chart_url(chart, item["version"])}">{escape(item["version"])} — '
                     f'{escape(item["title"])}</a> ({escape(item["date"])})<br>'
                     f'{escape("; ".join(item["authors"]))}</li>')
        body += '\n</ul>'
    else:
        citation = (f'{"; ".join(record["authors"])}. {record["title"]}. '
                    f'Exploration Chart {chart["id"]}, {record["version"]}, {record["date"]}.')
        if record["doi"]:
            citation += f' https://doi.org/{record["doi"]}'
        else:
            citation += f' {SITE_ORIGIN}{chart_url(chart, record["version"])}'
        body += f'\n<h2>Citation</h2>\n<p class="chart-citation">{escape(citation)}</p>'
        body += f'\n<p><a href="{chart_url(chart)}">View all versions of {escape(chart["id"])}</a></p>'
    fingerprint = "" if current else f'<!-- CHART-VERSION-FINGERPRINT:{record["fingerprint"]} -->\n'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · {escape(chart["id"])} · Homotopical Cartography</title>
  <meta name="description" content="{escape(record["abstract"])}">
  <meta name="robots" content="noindex, nofollow">
  <link rel="canonical" href="{SITE_ORIGIN}{chart_url(chart, None if current else record["version"])}">
  <link rel="icon" type="image/png" href="/favicon-mm.png">
  <link rel="stylesheet" href="/Style.css">
  <link rel="stylesheet" href="/Cartography.css">
</head>
<body class="cartography-page chart-page">
{fingerprint}<header class="site-header">
  <a class="wordmark" href="/homotopical-cartography.html">Homotopical Cartography</a>
  <nav aria-label="Page navigation"><a href="/index.html">Homepage</a></nav>
</header>
<main class="cartography-main">
{body}
</main>
</body>
</html>
'''


def build(site_root):
    site_root = site_root.resolve()
    charts = load_charts(site_root)
    main_path = site_root / "homotopical-cartography.html"
    if not main_path.resolve().is_relative_to(site_root):
        raise ValueError("Main HTML path escapes the site root")
    main_html = main_path.read_text(encoding="utf-8")
    if main_html.count(START) != 1 or main_html.count(END) != 1 or main_html.index(START) > main_html.index(END):
        raise ValueError("Main HTML must contain exactly one correctly ordered catalogue marker pair")
    before, rest = main_html.split(START, 1)
    _, after = rest.split(END, 1)
    pending = [(main_path, before + START + "\n" + catalogue(charts) + "\n" + END + after)]
    for chart in charts:
        base = site_root / "homotopical-cartography/charts" / chart["slug"]
        if not base.resolve().is_relative_to(site_root):
            raise ValueError(f"{chart['id']}: output path escapes the site root")
        pending.append((base / "index.html", landing_page(chart, chart["versions"][0], True)))
        for record in chart["versions"]:
            path = base / record["version"] / "index.html"
            if not path.resolve().is_relative_to(site_root):
                raise ValueError(f"{chart['id']}: version output path escapes the site root")
            if path.exists():
                previous = FINGERPRINT_RE.search(path.read_text(encoding="utf-8"))
                if not previous or previous.group(1) != record["fingerprint"]:
                    raise ValueError(f"{chart['id']} {record['version']}: published version changed; create a new version")
            pending.append((path, landing_page(chart, record, False)))
    # Validate every record and existing version before touching any output.
    for path, contents in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == contents:
            continue
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".chart-build-", delete=False) as stream:
            stream.write(contents)
            temporary = Path(stream.name)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return len(charts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        count = build(args.site_root)
    except (ValueError, OSError) as error:
        print(f"Catalogue not built: {error}", file=sys.stderr)
        return 1
    print(f"Built catalogue: {count} chart(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
