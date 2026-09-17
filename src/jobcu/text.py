"""Turning job ad HTML into clean plain text."""

import re

from lxml import html as lxml_html
from lxml.etree import ParserError

_BLOCK_TAGS = ("p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
               "section", "article", "header", "footer", "table")


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    if "<" not in markup:
        return tidy(markup)
    try:
        root = lxml_html.fragment_fromstring(markup, create_parent="div")
    except (ParserError, ValueError):
        return tidy(re.sub(r"<[^>]+>", " ", markup))
    for bad in root.xpath("//script|//style|//noscript"):
        bad.drop_tree()
    for element in root.iter(*_BLOCK_TAGS):
        element.tail = "\n" + (element.tail or "")
        if element.tag == "li":
            element.text = "• " + (element.text or "")
    return tidy(root.text_content())


def tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
