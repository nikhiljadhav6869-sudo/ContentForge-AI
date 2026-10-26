"""Small, validated rich-text schema with canonical text for evidence offsets."""

import html
import re


def validate_document(document):
    count = 0

    def node(value, allowed, depth=0):
        nonlocal count
        count += 1
        if depth > 10 or count > 5000 or not isinstance(value, dict):
            raise ValueError("Document is too complex or contains an invalid node.")
        kind = value.get("type")
        if not isinstance(kind, str) or kind not in allowed:
            raise ValueError("Use paragraphs, bold, italic, and bullet lists only.")
        keys = {"type", "text", "marks"} if kind == "text" else {"type"} if kind == "hardBreak" else {"type", "content"}
        if set(value) - keys:
            raise ValueError("Unsupported document attributes.")
        if kind == "text":
            text = value.get("text")
            if not isinstance(text, str) or not 1 <= len(text) <= 40000:
                raise ValueError("Document text must be nonempty and bounded.")
            marks = value.get("marks", [])
            if not isinstance(marks, list) or len(marks) > 2:
                raise ValueError("Unsupported text marks.")
            names = []
            for mark in marks:
                if (
                    not isinstance(mark, dict)
                    or set(mark) != {"type"}
                    or not isinstance(mark["type"], str)
                    or mark["type"] not in {"bold", "italic"}
                ):
                    raise ValueError("Only bold and italic text marks are supported.")
                if mark["type"] in names:
                    raise ValueError("Duplicate text marks.")
                names.append(mark["type"])
            return {"type": "text", "text": text, **({"marks": marks} if marks else {})}
        if kind == "hardBreak":
            return {"type": kind}
        content = value.get("content", [])
        if not isinstance(content, list) or (kind != "paragraph" and not content):
            raise ValueError("Invalid document structure.")
        children = (
            {"text", "hardBreak"}
            if kind == "paragraph"
            else {"listItem"}
            if kind == "bulletList"
            else {"paragraph", "bulletList"}
        )
        result = [node(child, children, depth + 1) for child in content]
        if kind == "listItem" and result[0]["type"] != "paragraph":
            raise ValueError("List items must begin with a paragraph.")
        return {"type": kind, **({"content": result} if result else {})}

    result = node(document, {"doc"})
    if len(document_text(result)) > 40000:
        raise ValueError("Document text is too long.")
    return result


def document_text(document):
    """Paragraphs in document order, separated by two newlines; no formatting syntax."""
    paragraphs = []

    def visit(node):
        if node["type"] == "paragraph":
            paragraphs.append("".join(child.get("text", "\n") for child in node.get("content", [])))
        else:
            for child in node.get("content", []):
                visit(child)

    visit(document)
    return "\n\n".join(paragraphs)


def document_markdown(document):
    def inline(node):
        if node["type"] == "hardBreak":
            return "  \n"
        text = re.sub(r"([\\`*_[\]{}!#+.|~\-])", r"\\\1", html.escape(node["text"], quote=False))
        marks = {mark["type"] for mark in node.get("marks", [])}
        if not marks:
            return text
        leading, content, trailing = re.fullmatch(r"(\s*)(.*?)(\s*)", text, re.DOTALL).groups()
        delimiter = ("**" if "bold" in marks else "") + ("*" if "italic" in marks else "")
        return leading + (delimiter + content + delimiter if content else "") + trailing

    def block(node):
        kind = node["type"]
        content = node.get("content", [])
        if kind == "paragraph":
            return "".join(inline(child) for child in content)
        if kind == "bulletList":
            return "\n".join(block(child) for child in content)
        rendered = "\n\n".join(block(child) for child in content)
        return "- " + rendered.replace("\n", "\n  ") if kind == "listItem" else rendered

    return block(document)
