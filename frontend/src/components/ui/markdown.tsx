import MarkdownIt from "markdown-it";
import { useMemo } from "react";

const md = new MarkdownIt({
  html: false, // 转义一切 HTML，防注入
  linkify: false,
  breaks: true,
  typographer: false,
});

// 只放行 http/https 链接（报告内容含社区原文，需防 javascript: 等协议注入）
md.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
  const hrefRaw = tokens[idx].attrGet("href");
  const href = typeof hrefRaw === "string" ? hrefRaw : "";
  if (!/^https?:\/\//i.test(href)) {
    tokens[idx].attrSet("href", "#");
    tokens[idx].attrSet("data-unsafe", "1");
  }
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noopener noreferrer");
  return self.renderToken(tokens, idx, options);
};

// 给 H2/H3 注入顺序锚点 id（sec-1、sec-2…），供报告页目录树滚动定位
let headingSeq = 0;
md.renderer.rules.heading_open = (tokens, idx, options, _env, self) => {
  const tag = tokens[idx].tag;
  if (tag === "h2" || tag === "h3") {
    headingSeq += 1;
    tokens[idx].attrSet("id", `sec-${headingSeq}`);
  }
  return self.renderToken(tokens, idx, options);
};

/** Markdown 渲染（白卡内排版见 .md-report 样式） */
export function MarkdownView({ content }: { content: string }) {
  const html = useMemo(() => {
    headingSeq = 0; // 每次渲染重置序号，保证锚点与目录树一致
    return md.render(content);
  }, [content]);
  return <div className="md-report" dangerouslySetInnerHTML={{ __html: html }} />;
}
