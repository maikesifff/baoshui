#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成软著用「源程序前30页+后30页」HTML，打印为 PDF 即可提交。"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))

# 源文件顺序：仅后端+前端核心代码，不包含 CSS（长行多易导致 PDF 超大）
FILES = [
    os.path.join(ROOT, 'server.py'),
    os.path.join(ROOT, 'app.js'),
]

# 每行最多字符数，超出截断，避免超长行导致 PDF 超过 20MB
MAX_CHARS_PER_LINE = 100

LINES_PER_PAGE = 50
PAGES_FIRST = 30
PAGES_LAST = 30

def read_lines():
    all_lines = []
    for path in FILES:
        if not os.path.isfile(path):
            continue
        name = os.path.basename(path)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                s = line.rstrip()
                if len(s) > MAX_CHARS_PER_LINE:
                    s = s[:MAX_CHARS_PER_LINE] + '...'
                all_lines.append((name, s))
    return all_lines

def main():
    lines = read_lines()
    total = len(lines)
    n_first = LINES_PER_PAGE * PAGES_FIRST   # 1500
    n_last = LINES_PER_PAGE * PAGES_LAST      # 1500

    first_block = lines[:n_first]
    last_block = lines[-n_last:] if total > n_last else lines

    def to_html(block, title, start_num):
        html = ['<div class="section-title">' + title + '</div>']
        for i, (fname, line) in enumerate(block):
            if i > 0 and i % LINES_PER_PAGE == 0:
                html.append('<div class="page-break"></div>')
            line_esc = (line or ' ').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            num = start_num + i
            html.append('<div class="line"><span class="num">%d</span> <span class="code">%s</span></div>' % (num, line_esc))
        return '\n'.join(html)

    first_html = to_html(first_block, '源程序前30页（自报税）', 1)
    last_html = to_html(last_block, '源程序后30页（自报税）', total - len(last_block) + 1)

    out = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>自报税 源程序鉴别材料（前30页+后30页）</title>
<style>
body { font-family: monospace; font-size: 11px; line-height: 1.35; margin: 0; padding: 16px; color: #333; }
.section-title { font-weight: bold; font-size: 14px; margin: 20px 0 12px; }
.line { white-space: pre-wrap; word-break: break-all; }
.line .num { color: #666; margin-right: 12px; display: inline-block; min-width: 5em; text-align: right; }
.line .code { }
@media print {
  body { padding: 12px; }
  .page-break { page-break-after: always; height: 0; }
  .section-title { page-break-before: always; }
  .section-title:first-of-type { page-break-before: avoid; }
}
</style>
</head>
<body>
%s

<div class="page-break"></div>

%s
</body>
</html>
''' % (first_html, last_html)

    outpath = os.path.join(BASE, '源程序-前30页与后30页.html')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(out)
    print('已生成:', outpath)
    print('请用浏览器打开该文件，选择「打印」->「另存为 PDF」，保存为 PDF 后上传至软著系统。')

if __name__ == '__main__':
    main()
