# Exploration Charts catalogue

Edit `homotopical-cartography/charts.json`, then run from the site root:

```sh
python3 tools/cartography/build.py
```

Commit the JSON, PDFs and generated HTML together. GitHub Pages serves these
prebuilt files; no framework, package installation or workflow change is needed.
The generator replaces only the catalogue marker block in the main page and
creates individual Chart landing pages. It does not add navigation links.

The catalogue is empty until an actual Chart is ready. To add one, use this shape
(replace all example content and add the actual PDF before building):

```json
{
  "charts": [
    {
      "id": "HC-0001",
      "versions": [
        {
          "version": "v1",
          "title": "Title of the completed Chart",
          "authors": ["Author One", "Author Two"],
          "date": "2026-10-16",
          "abstract": "A short description of its mathematical content.",
          "pdf": "homotopical-cartography/charts/hc-0001/v1/chart.pdf"
        }
      ]
    }
  ]
}
```

Optional fields: `concept_doi` on the Chart, and `doi` and `arxiv` on each version.
Use raw registered identifiers, not URLs; omit fields until they exist. No
identifiers are registered by this script. The highest `vN` is the current
version. Each version carries its own title, authors, date and abstract, so
later authorship changes do not rewrite earlier citations.

## Stable references

- Assign `HC-0001`, `HC-0002`, etc. once; never reuse an ID. This is a local
  project identifier, not a registered persistent identifier.
- The Chart landing page is `/homotopical-cartography/charts/hc-0001/`.
  Exact versions have `/v1/`, `/v2/`, etc. Append versions rather than replacing
  old files. The generator fingerprints the core version metadata and PDF;
  changing an already generated version stops the build. DOI/arXiv links may be
  added later. Template and style changes remain possible.
- To archive a released Chart independently of this homepage, deposit it in
  Zenodo. For the same artefact, supply an existing DOI rather than creating a
  duplicate. Otherwise a DOI can be reserved before publishing and included in
  the PDF. Registration occurs on publication.
- Zenodo's **version DOI** identifies the exact released content; use it in
  precise citations. Its **Concept DOI** represents all versions and currently
  resolves to the latest version. Store these separately.

Official references: [Zenodo DOI reservation](https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/)
and [Zenodo versioning](https://zenodo.org/help/versioning).

PDF paths must be relative to the site root and point to existing local files;
external URLs, traversal and symlinks outside the site are rejected. All text
and link fields are escaped before generating HTML. Missing PDFs, invalid dates,
duplicate IDs or versions stop the build before any generated content changes.
The build intentionally retains old files and does not delete released versions.
Pages remain `noindex, nofollow` while this section is unlisted; remove that
metadata from the main page and generator when public indexing is wanted.
