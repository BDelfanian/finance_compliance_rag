import type { ReactNode } from "react";

// Renders the generation/summarization agents' plain-text output (see
// src/generation/citation_bound_answer_generation.py's prompt and
// summarization_agent.py) with real structure instead of a single flat <p>.
// The LLM doesn't follow one consistent list style — observed live:
//   - citation_agent's answer: blank-line-separated "- " bullets with
//     indented sub-bullets in some responses, or real newline-separated
//     "1) ... \n2) ..." numbered lines in others;
//   - summarization_agent's answer: the same "1) ... 2) ..." enumeration
//     but with NO newlines at all — the whole list is one physical line,
//     separated only by ". " between items.
// This is a small dedicated parser for that narrow, predictable shape
// rather than a general markdown renderer (which wouldn't handle the
// no-newline enumeration case either, and would still render "[...]"
// citations as plain text without a custom plugin).

const CITATION_PATTERN = /\[[^\]\n]+\]/g;
const LIST_LINE = /^(\s*)(?:[-*]|\d+[.)])\s+(.*)$/;

// "N) "/"N. " markers preceded by whitespace (or start of string) that form
// a strictly sequential 1, 2, 3, ... run — requiring at least two markers in
// sequence (not just one coincidental "2)" in prose) keeps false positives
// on ordinary text negligible.
const INLINE_MARKER = /(?:^|\s)(\d+)[.)]\s+/g;

function withCitationHighlights(line: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = new RegExp(CITATION_PATTERN);
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;

  while ((match = re.exec(line)) !== null) {
    if (match.index > lastIndex) parts.push(line.slice(lastIndex, match.index));
    parts.push(
      <span key={`${keyPrefix}-c${i++}`} className="citation-ref">
        {match[0]}
      </span>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < line.length) parts.push(line.slice(lastIndex));
  return parts.length ? parts : [line];
}

interface ListItem {
  text: string;
  children: string[];
}

type Segment =
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: ListItem[] };

function splitInlineEnumeration(text: string): ListItem[] | null {
  const matches: { start: number; markerEnd: number; num: number }[] = [];
  const re = new RegExp(INLINE_MARKER);
  let m: RegExpExecArray | null;

  while ((m = re.exec(text)) !== null) {
    const leadingSpace = m[0].length - m[0].trimStart().length;
    matches.push({
      start: m.index + leadingSpace,
      markerEnd: m.index + m[0].length,
      num: parseInt(m[1], 10),
    });
  }

  if (matches.length < 2 || matches.some((mm, i) => mm.num !== i + 1)) return null;

  return matches.map((mm, i) => ({
    text: text.slice(mm.markerEnd, i + 1 < matches.length ? matches[i + 1].start : text.length).trim(),
    children: [],
  }));
}

// One list item per physical line — e.g. blank-line-separated "- " bullets,
// or genuinely newline-separated "1) .../2) ..." lines.
function groupMarkerLines(lines: string[]): Segment {
  const items: ListItem[] = [];
  let ordered = false;

  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(LIST_LINE);
    if (!m) continue; // shouldn't happen given the caller's check, but stay defensive
    const [, indent, text] = m;
    if (i === 0) ordered = /^\s*\d+[.)]/.test(lines[i]);
    if (indent.length === 0 || items.length === 0) {
      items.push({ text, children: [] });
    } else {
      items[items.length - 1].children.push(text);
    }
  }

  return { type: "list", ordered, items };
}

function parseBlock(lines: string[]): Segment[] {
  const segments: Segment[] = [];
  let plainRun: string[] = [];

  function flushPlain() {
    if (!plainRun.length) return;
    segments.push({ type: "paragraph", text: plainRun.join(" ") });
    plainRun = [];
  }

  let i = 0;
  while (i < lines.length) {
    if (!LIST_LINE.test(lines[i])) {
      plainRun.push(lines[i].trim());
      i++;
      continue;
    }

    let j = i + 1;
    while (j < lines.length && LIST_LINE.test(lines[j])) j++;
    const markerLines = lines.slice(i, j);
    flushPlain();

    if (markerLines.length === 1) {
      // A lone marker line is ambiguous: it might be one real single-item
      // bullet, or it might be the *entire* no-newline enumeration
      // ("1) ... 2) ... 3) ...") squashed onto one physical line — check
      // for that before assuming it's a single item (which would otherwise
      // swallow the rest of the enumeration into that one item's text).
      const inline = splitInlineEnumeration(markerLines[0]);
      segments.push(inline ? { type: "list", ordered: true, items: inline } : groupMarkerLines(markerLines));
    } else {
      segments.push(groupMarkerLines(markerLines));
    }
    i = j;
  }
  flushPlain();

  return segments;
}

function parseSegments(raw: string): Segment[] {
  const rawBlocks = raw.replace(/\r\n/g, "\n").trim().split(/\n\s*\n/);
  const segments: Segment[] = [];

  for (const rawBlock of rawBlocks) {
    const lines = rawBlock.split("\n").filter((l) => l.trim().length > 0);
    if (lines.length === 0) continue;
    segments.push(...parseBlock(lines));
  }

  return segments;
}

export function FormattedText({ text }: { text: string }) {
  const segments = parseSegments(text);
  if (segments.length === 0) return null;

  return (
    <div className="formatted-text">
      {segments.map((segment, si) => {
        if (segment.type === "paragraph") {
          return (
            <p key={si} className="formatted-text__paragraph">
              {withCitationHighlights(segment.text, `p${si}`)}
            </p>
          );
        }
        const ListTag = segment.ordered ? "ol" : "ul";
        return (
          <ListTag key={si} className="formatted-text__list">
            {segment.items.map((item, ii) => (
              <li key={ii}>
                {withCitationHighlights(item.text, `s${si}-i${ii}`)}
                {item.children.length > 0 && (
                  <ul className="formatted-text__list formatted-text__list--nested">
                    {item.children.map((child, ci) => (
                      <li key={ci}>{withCitationHighlights(child, `s${si}-i${ii}-c${ci}`)}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ListTag>
        );
      })}
    </div>
  );
}
