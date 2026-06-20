#!/usr/bin/env python3
"""
Post-process HTML chapter files to style code block comments.
Wraps // comments inside <pre><code> blocks with <span class="code-comment">.
"""
import os, re, sys

def style_comments(html):
    """Within <pre><code>...</code></pre> blocks, wrap // comments."""
    def process_code(match):
        code = match.group(1)
        # Wrap // comments (to end of line)
        code = re.sub(r'(//[^\n]*)', r'<span class="code-comment">\1</span>', code)
        return f'<pre><code>{code}</code></pre>'

    return re.sub(r'<pre><code>(.*?)</code></pre>', process_code, html, flags=re.DOTALL)

if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    count = 0
    for fname in os.listdir(chapters_dir):
        if not fname.endswith('.html'):
            continue
        path = os.path.join(chapters_dir, fname)
        with open(path, 'r') as f:
            original = f.read()
        if '<pre><code>' not in original:
            continue
        result = style_comments(original)
        if result != original:
            with open(path, 'w') as f:
                f.write(result)
            count += 1
    print(f" done ({count} file{'s' if count != 1 else ''} transformed)")
