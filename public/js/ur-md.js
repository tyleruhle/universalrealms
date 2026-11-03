/**
 * ur-md.js — a small, safe Markdown renderer for lore text written by Claude or
 * pasted by users. Everything is HTML-escaped FIRST, then a fixed set of
 * Markdown forms is turned into tags, so no input can inject markup or script.
 * Links are kept only for http(s) URLs and open in a new tab.
 *
 *   urMarkdown(text) -> HTML string
 *   urMarkdownInto(element, text)
 */
(function () {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  function inline(s) {
    // s is already escaped
    return s
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*\w])\*([^*\n]+)\*(?=[^*\w]|$)/g, '$1<em>$2</em>')
      .replace(/(^|[^_\w])_([^_\n]+)_(?=[^_\w]|$)/g, '$1<em>$2</em>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
               (m, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  }

  function render(src) {
    const lines = esc(String(src || '').replace(/\r\n?/g, '\n')).split('\n');
    const out = [];
    let para = [], list = null;
    const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
    const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map(i => `<li>${inline(i)}</li>`).join('')}</${list.tag}>`); list = null; } };
    for (const raw of lines) {
      const line = raw.trimEnd();
      let m;
      if (!line.trim()) { flushPara(); flushList(); continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
        flushPara(); flushList();
        const level = Math.min(6, m[1].length + 2);              // # -> h3: pages own h1/h2
        out.push(`<h${level}>${inline(m[2])}</h${level}>`); continue;
      }
      if (/^(-{3,}|\*{3,})$/.test(line.trim())) { flushPara(); flushList(); out.push('<hr>'); continue; }
      if ((m = line.match(/^&gt;\s?(.*)$/))) { flushPara(); flushList(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
      if ((m = line.match(/^\s*[-*+]\s+(?:\[( |x)\]\s+)?(.*)$/))) {
        flushPara();
        if (!list || list.tag !== 'ul') { flushList(); list = { tag: 'ul', items: [] }; }
        list.items.push((m[1] === 'x' ? '☑ ' : m[1] === ' ' ? '☐ ' : '') + m[2]); continue;
      }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
        flushPara();
        if (!list || list.tag !== 'ol') { flushList(); list = { tag: 'ol', items: [] }; }
        list.items.push(m[1]); continue;
      }
      if (list && /^\s{2,}\S/.test(raw)) { list.items[list.items.length - 1] += ' ' + line.trim(); continue; }
      flushList();
      para.push(line.trim());
    }
    flushPara(); flushList();
    return out.join('\n');
  }

  window.urMarkdown = render;
  window.urMarkdownInto = (el, text) => { el.innerHTML = render(text); };
})();
