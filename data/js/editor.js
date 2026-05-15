'use strict';

// ── Markdown → HTML ───────────────────────────────────────────────────────────

function _escHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function _inlineToHtml(raw) {
  // Cross-references [[name]] — before HTML escaping so names are plain strings
  let out = raw.replace(/\[\[([^\]]+)\]\]/g, (_, name) => {
    const safe = name.replace(/"/g, '&quot;');
    return `\x00CR\x00${safe}\x00`;   // placeholder survives _escHtml
  });

  let t = _escHtml(out);

  // Restore cross-reference placeholders as anchor elements
  t = t.replace(/\x00CR\x00([^\x00]*)\x00/g, (_, name) =>
    `<a class="crossref" href="#" data-ref="${name}">${name}</a>`
  );

  // Bold (**text** or __text__) — process before italic
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/__(.+?)__/g, '<strong>$1</strong>');
  // Italic (*text* or _text_)
  t = t.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
  t = t.replace(/_([^_\n]+?)_/g, '<em>$1</em>');
  // Code inline
  t = t.replace(/`([^`\n]+?)`/g, '<code>$1</code>');
  // Standard link [text](url)
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  return t;
}

function markdownToHtml(md) {
  if (!md || !md.trim()) return '<p><br></p>';

  const lines = md.split('\n');
  const out   = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Headings
    const hm = line.match(/^(#{1,3}) (.+)/);
    if (hm) {
      const lvl = hm[1].length;
      out.push(`<h${lvl}>${_inlineToHtml(hm[2])}</h${lvl}>`);
      i++; continue;
    }

    // Unordered list (- or *)
    if (/^[*-] /.test(line)) {
      const items = [];
      while (i < lines.length && /^[*-] /.test(lines[i])) {
        items.push(`<li>${_inlineToHtml(lines[i].slice(2))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join('')}</ul>`);
      continue;
    }

    // Ordered list
    if (/^\d+\. /.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(`<li>${_inlineToHtml(lines[i].replace(/^\d+\. /, ''))}</li>`);
        i++;
      }
      out.push(`<ol>${items.join('')}</ol>`);
      continue;
    }

    // Blank line — skip (paragraphs handle their own spacing)
    if (!line.trim()) { i++; continue; }

    // Regular paragraph
    out.push(`<p>${_inlineToHtml(line)}</p>`);
    i++;
  }

  return out.length ? out.join('') : '<p><br></p>';
}

// ── HTML → Markdown ───────────────────────────────────────────────────────────

function _nodeToMd(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const tag  = node.tagName.toLowerCase();
  const kids = () => Array.from(node.childNodes).map(_nodeToMd).join('');

  switch (tag) {
    case 'h1': return `# ${kids().trim()}\n\n`;
    case 'h2': return `## ${kids().trim()}\n\n`;
    case 'h3': return `### ${kids().trim()}\n\n`;
    case 'strong': case 'b': return `**${kids()}**`;
    case 'em':     case 'i': return `*${kids()}*`;
    case 'code':             return `\`${kids()}\``;
    case 'a': {
      // Cross-reference anchor → [[name]]
      if (node.classList && node.classList.contains('crossref')) {
        return `[[${node.dataset.ref || kids()}]]`;
      }
      return `[${kids()}](${node.getAttribute('href') || ''})`;
    }
    case 'ul': {
      const rows = Array.from(node.children)
        .map(li => `- ${_nodeToMd(li).trim()}`).join('\n');
      return `${rows}\n\n`;
    }
    case 'ol': {
      const rows = Array.from(node.children)
        .map((li, n) => `${n + 1}. ${_nodeToMd(li).trim()}`).join('\n');
      return `${rows}\n\n`;
    }
    case 'li':  return kids();
    case 'p': {
      const t = kids().trim();
      return t ? `${t}\n\n` : '';
    }
    case 'br':  return '\n';
    case 'div': { const t = kids(); return t ? `${t}\n` : ''; }
    default:    return kids();
  }
}

function htmlToMarkdown(html) {
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  return Array.from(wrap.childNodes)
    .map(_nodeToMd)
    .join('')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── CodexEditor class ─────────────────────────────────────────────────────────

class CodexEditor {
  constructor(el) {
    this._el         = el;
    this._dirty      = false;
    this._savedRange = null;   // cursor position saved when [[ is detected
    this._init();
  }

  /** Load markdown string into the editable area. */
  load(markdown) {
    this._el.innerHTML = markdownToHtml(markdown);
    this._dirty = false;
    this._savedRange = null;
    this._el.focus();
  }

  /** Return current content as standard Markdown. */
  getMarkdown() {
    return htmlToMarkdown(this._el.innerHTML);
  }

  get isDirty() { return this._dirty; }

  /** Wrap current selection in a <code> span. */
  insertCode() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    const code  = document.createElement('code');
    code.appendChild(sel.isCollapsed
      ? document.createTextNode('código')
      : range.extractContents());
    range.deleteContents();
    range.insertNode(code);
    range.selectNodeContents(code);
    sel.removeAllRanges();
    sel.addRange(range);
    this._el.focus();
  }

  /** Execute a document.execCommand formatting command. */
  format(cmd, value) {
    document.execCommand(cmd, false, value || null);
    this._el.focus();
  }

  _init() {
    // Mark dirty, notify Python, detect [[, and debounce word count
    this._wcTimer = null;
    this._el.addEventListener('input', () => {
      this._dirty = true;
      _py('editor', 'dirty');

      // Debounced word count: fires 1 s after the user stops typing
      clearTimeout(this._wcTimer);
      this._wcTimer = setTimeout(() => {
        const text  = this._el.innerText || '';
        const trimmed = text.trim();
        const count = trimmed === '' ? 0 : trimmed.split(/\s+/).length;
        _py('wordcount', String(count));
      }, 1000);

      const sel = window.getSelection();
      if (!sel || !sel.rangeCount) return;
      const range = sel.getRangeAt(0);
      const node  = range.startContainer;
      if (node.nodeType !== Node.TEXT_NODE) return;
      const before = node.textContent.substring(0, range.startOffset);
      if (before.endsWith('[[')) {
        this._savedRange = range.cloneRange();
        _py('crossref', '');
      }
    });

    // Click on cross-reference links → navigate to referenced document
    this._el.addEventListener('click', e => {
      const a = e.target.closest('a.crossref');
      if (a) {
        e.preventDefault();
        _py('navigate', a.dataset.ref || '');
      }
    });

    // After pressing Enter inside a heading, start a plain paragraph
    this._el.addEventListener('keydown', e => {
      if (e.key !== 'Enter' || e.shiftKey) return;
      const block = _currentBlock(this._el);
      if (block && /^H[1-6]$/.test(block.tagName)) {
        e.preventDefault();
        const p = document.createElement('p');
        p.innerHTML = '<br>';
        block.after(p);
        _setCursor(p, 0);
      }
    });
  }
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function _currentBlock(root) {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return null;
  const BLOCKS = ['P','H1','H2','H3','H4','H5','H6','LI','DIV','BLOCKQUOTE'];
  let el = sel.getRangeAt(0).startContainer;
  if (el.nodeType === Node.TEXT_NODE) el = el.parentElement;
  while (el && el !== root) {
    if (BLOCKS.includes(el.tagName)) return el;
    el = el.parentElement;
  }
  return null;
}

function _setCursor(el, offset) {
  const sel   = window.getSelection();
  const range = document.createRange();
  range.setStart(el, offset);
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
}

/** Send a simple string message to a Python WebKit message handler. */
function _py(handler, msg) {
  if (window.webkit && window.webkit.messageHandlers[handler]) {
    window.webkit.messageHandlers[handler].postMessage(String(msg));
  }
}

// ── Python-facing public API ──────────────────────────────────────────────────

/** Called from Python: load content into editor. */
function codexLoad(markdown) {
  window._editor && window._editor.load(markdown);
}

/** Called from Python: collect content and post it back via 'save' handler. */
function codexSave() {
  if (!window._editor) return;
  _py('save', window._editor.getMarkdown());
}

/** Called from Python: toggle dark/light color scheme. */
function codexSetDark(isDark) {
  document.documentElement.classList.toggle('dark', !!isDark);
}

/**
 * Called from Python after the user picks a document in the cross-reference
 * dialog. Replaces the [[ immediately before the saved cursor with a proper
 * crossref anchor element.
 */
function codexInsertRef(name) {
  const editor = window._editor;
  if (!editor || !editor._savedRange) return;

  const range  = editor._savedRange;
  editor._savedRange = null;

  const node = range.startContainer;
  if (node.nodeType !== Node.TEXT_NODE) return;

  const offset = range.startOffset;
  const text   = node.textContent;
  const before = text.substring(0, offset);
  const idx    = before.lastIndexOf('[[');
  if (idx === -1) return;

  // Build the crossref anchor
  const a = document.createElement('a');
  a.className  = 'crossref';
  a.href       = '#';
  a.dataset.ref = name;
  a.textContent = name;

  // Split the text node around the anchor
  const afterNode = document.createTextNode(text.substring(offset));
  node.textContent = before.substring(0, idx);
  const parent = node.parentNode;
  parent.insertBefore(afterNode, node.nextSibling);
  parent.insertBefore(a, afterNode);

  // Place cursor right after the inserted anchor
  const sel      = window.getSelection();
  const newRange = document.createRange();
  newRange.setStartAfter(a);
  newRange.collapse(true);
  sel.removeAllRanges();
  sel.addRange(newRange);

  editor._el.focus();
  _py('editor', 'dirty');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  window._editor = new CodexEditor(document.getElementById('editor'));
});
