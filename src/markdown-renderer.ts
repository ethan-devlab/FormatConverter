import mermaid from "mermaid";
import katex from "katex";
import "katex/dist/katex.min.css";

declare global {
  interface Window {
    __FC_STATUS?: { ready?: boolean; error?: string };
  }
}

async function render() {
  // Source HTML is disabled by the parser. Mermaid cannot relax these settings.
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral",
    suppressErrorRendering: true, maxTextSize: 100000,
    secure: ["securityLevel", "startOnLoad", "maxTextSize", "secure"],
    flowchart: { htmlLabels: false } });
  for (const element of document.querySelectorAll<HTMLElement>(".math")) {
    katex.render(element.textContent || "", element, { displayMode: element.classList.contains("block"),
      throwOnError: true, trust: false, maxExpand: 1000, strict: "error" });
  }
  for (const [index, element] of [...document.querySelectorAll<HTMLElement>("code.language-mermaid")].entries()) {
    const source = element.textContent || "";
    if (/%%\s*\{|^\s*---/m.test(source)) throw new Error("Mermaid configuration directives are not supported.");
    const result = await mermaid.render(`diagram-${index}`, source);
    const container = document.createElement("div");
    container.className = "mermaid-output";
    container.innerHTML = result.svg;
    element.closest("pre")!.replaceWith(container);
  }
  await document.fonts.ready;
  await Promise.all([...document.images].map(async (image) => {
    await image.decode();
  }));
  window.__FC_STATUS = { ready: true };
}

void render().catch((error: unknown) => {
  window.__FC_STATUS = { error: error instanceof Error ? error.message : String(error) };
});
