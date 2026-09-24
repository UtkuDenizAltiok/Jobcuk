"""Turning job ad HTML into clean plain text."""

import html
import re
import unicodedata

from lxml import html as lxml_html
from lxml.etree import ParserError

_BLOCK_TAGS = ("p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
               "section", "article", "header", "footer", "table")


# A tag left in the text after converting: the site sent its HTML escaped ("&lt;p&gt;").
_LEFTOVER_TAG = re.compile(
    r"</?(?:p|div|br|li|ul|ol|h[1-6]|strong|b|em|i|u|span|a|table|tr|td|section)\b[^<>]*>",
    re.IGNORECASE,
)


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    if "<" not in markup and "&lt;" in markup:
        markup = html.unescape(markup)
    text = _to_text(markup)
    # HTML escaped inside HTML (Arbeitnow sometimes): the first pass leaves the inner tags.
    return _to_text(text) if _LEFTOVER_TAG.search(text) else text


def _to_text(markup: str) -> str:
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


def normalise(text: str | None) -> str:
    """For comparing words: lower case, accents removed ("München" → "munchen"), punctuation as
    spaces."""
    text = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss"))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())
