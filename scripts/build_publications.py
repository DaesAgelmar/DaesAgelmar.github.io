from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIB_PATH = ROOT / "bibliography" / "KY-Publications.bib"
OUTPUT_DIR = ROOT / "generated"
OUTPUT_PATH = OUTPUT_DIR / "publications.md"


def split_bibtex_entries(text: str) -> list[str]:
    """Split a BibTeX file into complete entries, respecting nested braces."""
    entries: list[str] = []
    start: int | None = None
    depth = 0

    for index, char in enumerate(text):
        if char == "@" and depth == 0:
            if start is not None:
                entries.append(text[start:index].strip())
            start = index

        if start is None:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

    if start is not None:
        entries.append(text[start:].strip())

    return [entry for entry in entries if entry]


def extract_field(entry: str, field: str) -> str | None:
    """Extract a BibTeX field with braced, quoted, or bare values."""
    braced_match = re.search(
        rf"(?im)^\s*{re.escape(field)}\s*=\s*\{{",
        entry,
    )

    if braced_match is not None:
        start = braced_match.end()
        depth = 1
        index = start

        while index < len(entry) and depth:
            char = entry[index]

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

            index += 1

        if depth == 0:
            return entry[start:index - 1].strip()

    quoted_match = re.search(
        rf'(?im)^\s*{re.escape(field)}\s*=\s*"([^"]*)"',
        entry,
    )

    if quoted_match is not None:
        return quoted_match.group(1).strip()

    bare_match = re.search(
        rf"(?im)^\s*{re.escape(field)}\s*=\s*([^,\n]+)",
        entry,
    )

    if bare_match is not None:
        return bare_match.group(1).strip()

    return None


def clean_bibtex_text(value: str | None) -> str:
    """Remove BibTeX protection syntax while preserving Unicode text."""
    if not value:
        return ""

    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\_": "_",
        r"\#": "#",
        r"\:": ":",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    # In this bibliography, braces mainly protect capitalization.
    value = value.replace("{", "").replace("}", "")

    # Normalize whitespace.
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_entry_type(entry: str) -> str:
    """Return the BibTeX entry type."""
    match = re.match(r"@(\w+)", entry)
    return match.group(1).lower() if match else ""


def parse_authors(value: str | None) -> list[str]:
    """Convert BibTeX author strings to readable names."""
    if not value:
        return []

    authors: list[str] = []

    for author in value.split(" and "):
        author = clean_bibtex_text(author)

        if "," in author:
            surname, given = [
                part.strip()
                for part in author.split(",", 1)
            ]
            display = f"{given} {surname}"
        else:
            display = author

        authors.append(display)

    return authors


def format_authors(authors: list[str]) -> str:
    """Format author list and emphasize Kemal Yayla."""
    formatted: list[str] = []

    for author in authors:
        if author.casefold() == "kemal yayla".casefold():
            author = "**Kemal Yayla**"

        formatted.append(author)

    if not formatted:
        return ""

    if len(formatted) == 1:
        return formatted[0]

    if len(formatted) == 2:
        return f"{formatted[0]} & {formatted[1]}"

    return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


def is_preprint(
    entry_type: str,
    doi: str,
    url: str,
    publisher: str,
) -> bool:
    """Identify public preprints without relying only on @misc."""
    doi_lower = doi.casefold()
    url_lower = url.casefold()
    publisher_lower = publisher.casefold()

    known_preprint_signals = (
        "10.21203/rs.3" in doi_lower
        or "10.2139/ssrn" in doi_lower
        or "researchsquare.com" in url_lower
        or "ssrn.com" in url_lower
        or publisher_lower == "ssrn"
    )

    return entry_type == "misc" and known_preprint_signals


def preprint_platform(doi: str, url: str, publisher: str) -> str:
    """Infer the public preprint platform."""
    doi_lower = doi.casefold()
    url_lower = url.casefold()
    publisher_lower = publisher.casefold()

    if (
        "10.21203/rs.3" in doi_lower
        or "researchsquare.com" in url_lower
    ):
        return "Research Square"

    if (
        "10.2139/ssrn" in doi_lower
        or "ssrn.com" in url_lower
        or publisher_lower == "ssrn"
    ):
        return "SSRN"

    return publisher or "Preprint"


def format_article_source(entry: str) -> str:
    journal = clean_bibtex_text(extract_field(entry, "journal"))
    volume = clean_bibtex_text(extract_field(entry, "volume"))
    number = clean_bibtex_text(extract_field(entry, "number"))
    pages = clean_bibtex_text(extract_field(entry, "pages"))

    source = f"*{journal}*" if journal else ""

    if volume:
        source += f", *{volume}*"

    if number:
        source += f"({number})"

    if pages:
        source += f", {pages}"

    return source


def format_source(
    entry: str,
    entry_type: str,
    preprint: bool,
    doi: str,
    url: str,
    publisher: str,
) -> str:
    """Format the publication venue or repository."""
    if preprint:
        return f"*{preprint_platform(doi, url, publisher)}*"

    if entry_type == "article":
        return format_article_source(entry)

    if entry_type == "incollection":
        booktitle = clean_bibtex_text(
            extract_field(entry, "booktitle")
        )
        pages = clean_bibtex_text(
            extract_field(entry, "pages")
        )

        source = f"In *{booktitle}*" if booktitle else "Book chapter"

        if pages:
            source += f", {pages}"

        return source

    if entry_type == "inproceedings":
        booktitle = clean_bibtex_text(
            extract_field(entry, "booktitle")
        )

        return (
            f"*{booktitle}*"
            if booktitle
            else "Conference contribution"
        )

    if entry_type == "phdthesis":
        school = clean_bibtex_text(
            extract_field(entry, "school")
        )

        return (
            f"Doctoral dissertation, {school}"
            if school
            else "Doctoral dissertation"
        )

    return publisher


def type_label(entry_type: str, preprint: bool) -> str:
    """Return a human-readable scholarly-output type."""
    if preprint:
        return "Preprint"

    labels = {
        "article": "Journal article",
        "incollection": "Book chapter",
        "inproceedings": "Conference contribution",
        "phdthesis": "Doctoral dissertation",
    }

    return labels.get(entry_type, "Scholarly output")


def parse_entry(entry: str) -> dict[str, str | int | bool]:
    """Convert one BibTeX entry to a normalized publication record."""
    entry_type = get_entry_type(entry)

    year_text = clean_bibtex_text(
        extract_field(entry, "year")
    )

    year = int(year_text) if year_text.isdigit() else 0

    title = clean_bibtex_text(
        extract_field(entry, "title")
    )

    authors = parse_authors(
        extract_field(entry, "author")
    )

    doi = clean_bibtex_text(
        extract_field(entry, "doi")
    )

    url = clean_bibtex_text(
        extract_field(entry, "url")
    )

    publisher = clean_bibtex_text(
        extract_field(entry, "publisher")
    )

    preprint = is_preprint(
        entry_type=entry_type,
        doi=doi,
        url=url,
        publisher=publisher,
    )

    source = format_source(
        entry=entry,
        entry_type=entry_type,
        preprint=preprint,
        doi=doi,
        url=url,
        publisher=publisher,
    )

    return {
        "year": year,
        "title": title,
        "authors": format_authors(authors),
        "source": source,
        "doi": doi,
        "url": url,
        "type": type_label(entry_type, preprint),
        "preprint": preprint,
    }


def render_publication(
    record: dict[str, str | int | bool],
) -> str:
    """Render one publication as Quarto-compatible Markdown."""
    title = str(record["title"])
    authors = str(record["authors"])
    source = str(record["source"])
    doi = str(record["doi"])
    url = str(record["url"])
    publication_type = str(record["type"])

    lines = [
        '::: {.publication-entry}',
        f"**{title}**",
        "",
        authors,
        "",
    ]

    if source:
        lines.extend(
            [
                source,
                "",
            ]
        )

    links: list[str] = []

    if doi:
        links.append(
            f"[DOI](https://doi.org/{doi})"
        )
    elif url:
        links.append(
            f"[View]({url})"
        )

    links.append(
        f'<span class="pub-type">{publication_type}</span>'
    )

    lines.extend(
        [
            " · ".join(links),
            ":::",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Generate the publication page fragment from the BibTeX file."""
    if not BIB_PATH.exists():
        raise FileNotFoundError(
            f"Bibliography not found: {BIB_PATH}"
        )

    text = BIB_PATH.read_text(encoding="utf-8")
    entries = split_bibtex_entries(text)

    publications = [
        parse_entry(entry)
        for entry in entries
    ]

    publications = [
        publication
        for publication in publications
        if publication["year"]
    ]

    by_year: dict[
        int,
        list[dict[str, str | int | bool]],
    ] = defaultdict(list)

    for publication in publications:
        year = int(publication["year"])
        by_year[year].append(publication)

    output = [
        "<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->",
        "",
    ]

    for year in sorted(by_year, reverse=True):
        records = by_year[year]

        regular_records = [
            record
            for record in records
            if not bool(record["preprint"])
        ]

        preprint_records = [
            record
            for record in records
            if bool(record["preprint"])
        ]

        output.extend(
            [
                f"## {year}",
                "",
            ]
        )

        if regular_records:
            if preprint_records:
                output.extend(
                    [
                        "### Publications and other scholarly outputs",
                        "",
                    ]
                )

            regular_records = sorted(
                regular_records,
                key=lambda record: str(
                    record["title"]
                ).casefold(),
            )

            for record in regular_records:
                output.append(
                    render_publication(record)
                )

        if preprint_records:
            output.extend(
                [
                    "### Preprints",
                    "",
                    (
                        "Publicly available manuscripts are listed "
                        "separately from formally published outputs."
                    ),
                    "",
                ]
            )

            preprint_records = sorted(
                preprint_records,
                key=lambda record: str(
                    record["title"]
                ).casefold(),
            )

            for record in preprint_records:
                output.append(
                    render_publication(record)
                )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        "\n".join(output).rstrip() + "\n",
        encoding="utf-8",
    )

    preprint_count = sum(
        bool(publication["preprint"])
        for publication in publications
    )

    print(
        f"Generated {OUTPUT_PATH.relative_to(ROOT)} "
        f"from {len(publications)} records "
        f"({preprint_count} preprints)."
    )


if __name__ == "__main__":
    main()