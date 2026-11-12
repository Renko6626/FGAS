import MarkdownIt from 'markdown-it';

export interface HandbookHeading {
  id: string;
  title: string;
  level: number;
  children: HandbookHeading[];
}

const markdown = new MarkdownIt({ html: false, linkify: false }).disable('image');
markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  if (!String(tokens[index]!.attrGet('href') || '').startsWith('#')) {
    tokens[index]!.attrSet('target', '_blank');
    tokens[index]!.attrSet('rel', 'noopener noreferrer');
  }
  return renderer.renderToken(tokens, index, options);
};

export function renderHandbookMarkdown(content: string, prefix = 'handbook') {
  const tokens = markdown.parse(content, {});
  const headings: HandbookHeading[] = [];
  const outline: HandbookHeading[] = [];
  const ancestors: HandbookHeading[] = [];
  const used = new Set<string>();
  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index]!;
    if (token.type !== 'heading_open') continue;
    const inline = tokens[index + 1]!;
    const title = (inline.children || []).map(child => ['text', 'code_inline'].includes(child.type)
      ? child.content : ['softbreak', 'hardbreak'].includes(child.type) ? ' ' : '').join('');
    const slug = title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').trim().replace(/\s+/g, '-') || 'section';
    let id = `${prefix}-${slug}`;
    for (let suffix = 2; used.has(id); suffix++) id = `${prefix}-${slug}-${suffix}`;
    used.add(id);
    token.attrSet('id', id);
    token.attrSet('tabindex', '-1');
    const heading: HandbookHeading = { id, title: title || '未命名章节', level: Number(token.tag.slice(1)), children: [] };
    while (ancestors.length && ancestors[ancestors.length - 1]!.level >= heading.level) ancestors.pop();
    const parent = ancestors[ancestors.length - 1];
    (parent ? parent.children : outline).push(heading);
    ancestors.push(heading);
    headings.push(heading);
  }
  return { html: markdown.renderer.render(tokens, markdown.options, {}), headings, outline };
}
