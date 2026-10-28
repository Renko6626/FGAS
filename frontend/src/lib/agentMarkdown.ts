import MarkdownIt from 'markdown-it';

// Model text is untrusted: render Markdown syntax, never embedded HTML or remote images.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false }).disable('image');

markdown.core.ruler.after('inline', 'fgas_business_links', state => {
  for (const inline of state.tokens) {
    if (inline.type !== 'inline' || !inline.children) continue;
    const children = [];
    let linkDepth = 0;
    for (const token of inline.children) {
      if (token.type === 'link_open') linkDepth++;
      if (token.type === 'link_close') linkDepth--;
      if (token.type !== 'text' || linkDepth > 0) { children.push(token); continue; }
      let offset = 0;
      for (const match of token.content.matchAll(/\b(?:FT|ST)-\d{6}\b/g)) {
        const start = match.index!;
        if (start > offset) {
          const text = new state.Token('text', '', 0);
          text.content = token.content.slice(offset, start);
          children.push(text);
        }
        const open = new state.Token('link_open', 'a', 1);
        open.attrSet('href', '#' + (match[0].startsWith('FT') ? 'transfers' : 'stock') + '?code=' + match[0]);
        const text = new state.Token('text', '', 0);
        text.content = match[0];
        children.push(open, text, new state.Token('link_close', 'a', -1));
        offset = start + match[0].length;
      }
      if (!offset) children.push(token);
      else if (offset < token.content.length) {
        const text = new state.Token('text', '', 0);
        text.content = token.content.slice(offset);
        children.push(text);
      }
    }
    inline.children = children;
  }
});

markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  const token = tokens[index]!;
  let href = String(token.attrGet('href') || '');
  // Keep the current page query and live chat request when opening a workbench record.
  if (href.startsWith('/#')) { href = href.slice(1); token.attrSet('href', href); }
  if (!href.startsWith('#')) {
    token.attrSet('target', '_blank');
    token.attrSet('rel', 'noopener noreferrer');
  }
  return renderer.renderToken(tokens, index, options);
};

export function renderAgentMarkdown(content: string): string {
  return markdown.render(content);
}
