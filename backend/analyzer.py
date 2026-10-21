"""CPU-bound HTML analysis. Runs in worker processes, so everything here must be picklable
(module-level functions, plain data in and out)."""
from collections import Counter
from html.parser import HTMLParser
import re

STOPWORDS = {
    "the", "and", "for", "you", "your", "with", "that", "this", "are", "from", "our", "can",
    "all", "not", "but", "have", "has", "was", "will", "more", "about", "into", "its", "it's",
    "they", "their", "what", "when", "how", "use", "any", "out", "who", "one", "also", "may",
}
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{2,}")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.links = 0
        self.images = 0
        self.images_missing_alt = 0
        self.scripts = 0
        self.has_meta_description = False
        self.text_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links += 1
        elif tag == "img":
            self.images += 1
            if not (attrs.get("alt") or "").strip():
                self.images_missing_alt += 1
        elif tag == "script":
            self.scripts += 1
            self._skip_depth += 1
        elif tag == "style":
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and (attrs.get("name") or "").lower() == "description" and attrs.get("content"):
            self.has_meta_description = True

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and self.title is None:
            self.title = data.strip() or None
        elif not self._skip_depth:
            self.text_parts.append(data)


def analyze_html(html: str) -> dict:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    words = [w.lower() for w in WORD_RE.findall(" ".join(parser.text_parts))]
    top = Counter(w for w in words if w not in STOPWORDS).most_common(10)
    return {
        "title": parser.title,
        "page_size_bytes": len(html.encode("utf-8", errors="ignore")),
        "word_count": len(words),
        "link_count": parser.links,
        "image_count": parser.images,
        "images_missing_alt": parser.images_missing_alt,
        "script_count": parser.scripts,
        "has_meta_description": parser.has_meta_description,
        "top_words": top,
    }
