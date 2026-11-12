import assert from 'node:assert/strict';
import test from 'node:test';
import { renderHandbookMarkdown } from '../src/lib/handbookMarkdown.ts';

test('heading hierarchy handles skipped levels and repeated titles with distinct rendered targets', () => {
  const result = renderHandbookMarkdown('## 发票 **报销**\n#### 办理\n## 发票 **报销**\n#### 办理\n\n```md\n# 代码中的标题\n```', 'reading');
  assert.deepEqual(result.outline.map(heading => ({ title: heading.title, level: heading.level, children: heading.children.map(child => child.title) })), [
    { title: '发票 报销', level: 2, children: ['办理'] },
    { title: '发票 报销', level: 2, children: ['办理'] },
  ]);
  assert.deepEqual(result.headings.map(heading => heading.id), ['reading-发票-报销', 'reading-办理', 'reading-发票-报销-2', 'reading-办理-2']);
  for (const heading of result.headings) assert.ok(result.html.includes(`id="${heading.id}"`));
});

test('handbook renders text and tables while keeping embedded HTML and unsafe links inert', () => {
  const result = renderHandbookMarkdown('<script>alert(1)</script>\n\n[危险](javascript:alert(1))\n\n[流程](https://example.com)\n\n| 项目 | 说明 |\n| --- | --- |\n| 发票 | 保留 |');
  assert.ok(result.html.includes('&lt;script&gt;'));
  assert.ok(!result.html.includes('<script>'));
  assert.ok(!result.html.includes('href="javascript:'));
  assert.ok(result.html.includes('rel="noopener noreferrer"'));
  assert.ok(result.html.includes('<table>'));
  assert.deepEqual(result.outline, []);
});
