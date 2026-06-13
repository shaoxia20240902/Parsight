export function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case '&': return '&amp;'
      case '<': return '&lt;'
      case '>': return '&gt;'
      case '"': return '&quot;'
      case "'": return '&#39;'
      default: return ch
    }
  })
}

export function renderMarkdown(content: string): string {
  if (!content) return ''
  const lines = content.trim().split('\n')
  if (lines.length >= 2 && lines[0].includes('|') && lines[1].includes('---')) {
    const headers = lines[0].split('|').map((s) => s.trim()).filter(Boolean)
    const rows = lines.slice(2).map((line) => line.split('|').map((s) => s.trim()).filter(Boolean))
    return `<table class="builder-md-table"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  }
  return escapeHtml(content).replace(/\n/g, '<br>')
}
