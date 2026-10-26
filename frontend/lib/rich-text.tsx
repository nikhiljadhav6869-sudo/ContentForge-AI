import type { ReactNode } from "react";

export type RichDocument = {
  type: string;
  text?: string;
  marks?: { type: string }[];
  content?: RichDocument[];
};

export function plainDocument(body: string): RichDocument {
  return {
    type: "doc",
    content: body
      .split("\n\n")
      .map((text) => ({
        type: "paragraph",
        ...(text ? { content: [{ type: "text", text }] } : {}),
      })),
  };
}

export function documentText(document: RichDocument): string {
  const paragraphs: string[] = [];
  function visit(node: RichDocument) {
    if (node.type === "paragraph")
      paragraphs.push(
        (node.content || []).map((child) => child.text ?? "\n").join(""),
      );
    else node.content?.forEach(visit);
  }
  visit(document);
  return paragraphs.join("\n\n");
}

export function RichDocumentView({ document }: { document: RichDocument }) {
  function render(node: RichDocument, key: number): ReactNode {
    if (node.type === "text") {
      let content: ReactNode = node.text;
      for (const mark of node.marks || []) {
        if (mark.type === "bold") content = <strong>{content}</strong>;
        if (mark.type === "italic") content = <em>{content}</em>;
      }
      return <span key={key}>{content}</span>;
    }
    const children = node.content?.map(render);
    switch (node.type) {
      case "doc":
        return (
          <div key={key} className="formatted-document">
            {children}
          </div>
        );
      case "paragraph":
        return <p key={key}>{children?.length ? children : <br />}</p>;
      case "bulletList":
        return <ul key={key}>{children}</ul>;
      case "listItem":
        return <li key={key}>{children}</li>;
      case "hardBreak":
        return <br key={key} />;
      default:
        return null;
    }
  }
  return render(document, 0);
}
