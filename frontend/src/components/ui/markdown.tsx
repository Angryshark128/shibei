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

/** Markdown 渲染（白卡内排版见 .md-report 样式） */
export function MarkdownView({ content }: { content: string }) {
  const html = useMemo(() => md.render(content), [content]);
  return <div className="md-report" dangerouslySetInnerHTML={{ __html: html }} />;
}
