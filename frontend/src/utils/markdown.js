/**
 * 轻量 Markdown 渲染（零依赖）
 *
 * 为什么不用 marked / markdown-it：本项目前端不希望为此新增运行时依赖，
 * LLM 输出只需要「标题 / 粗体 / 列表 / 行内代码」这几种结构。
 *
 * 安全：先对原文做 HTML 转义，再套用格式替换，因此 v-html 渲染是安全的
 * （LLM 输出中的任何标签都会变成可见文本，不会被当作 HTML 执行）。
 */

function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** 行内格式：粗体、行内代码（在已转义文本上执行） */
function inline(s) {
  return s
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

export function renderMarkdown(text) {
  if (!text) return ''

  const lines = escapeHtml(text).split('\n')
  const out = []
  let listType = null

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')

    if (!line.trim()) {
      closeList()
      continue
    }

    // 标题：### xxx / ## xxx
    let m = line.match(/^\s*#{1,6}\s+(.+)$/)
    if (m) {
      closeList()
      out.push(`<h4>${inline(m[1])}</h4>`)
      continue
    }

    // 无序列表：- xxx / * xxx
    m = line.match(/^\s*[-*]\s+(.+)$/)
    if (m) {
      if (listType !== 'ul') {
        closeList()
        out.push('<ul>')
        listType = 'ul'
      }
      out.push(`<li>${inline(m[1])}</li>`)
      continue
    }

    // 有序列表：1. xxx / 1、xxx
    m = line.match(/^\s*\d+[.、]\s+(.+)$/)
    if (m) {
      if (listType !== 'ol') {
        closeList()
        out.push('<ol>')
        listType = 'ol'
      }
      out.push(`<li>${inline(m[1])}</li>`)
      continue
    }

    closeList()
    out.push(`<p>${inline(line)}</p>`)
  }

  closeList()
  return out.join('')
}
