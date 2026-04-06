#!/usr/bin/env python3
"""Strip comments and unnecessary whitespace from C source."""
import subprocess, sys, os

def is_ident(c):
    return c.isalnum() or c == '_'

def minify_line(line):
    out = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == '"':
            out.append(c)
            i += 1
            while i < n and line[i] != '"':
                if line[i] == '\\' and i + 1 < n:
                    out.append(line[i])
                    i += 1
                out.append(line[i])
                i += 1
            if i < n:
                out.append(line[i])
                i += 1
            continue
        if c == "'":
            out.append(c)
            i += 1
            while i < n and line[i] != "'":
                if line[i] == '\\' and i + 1 < n:
                    out.append(line[i])
                    i += 1
                out.append(line[i])
                i += 1
            if i < n:
                out.append(line[i])
                i += 1
            continue
        if c in (' ', '\t'):
            j = i + 1
            while j < n and line[j] in (' ', '\t'):
                j += 1
            if out and j < n and is_ident(out[-1]) and is_ident(line[j]):
                out.append(' ')
            i = j
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def _join_code(parts):
    """Join code fragments, inserting a space only where two identifier chars would merge."""
    if not parts:
        return ''
    result = parts[0]
    for p in parts[1:]:
        if result and p and is_ident(result[-1]) and is_ident(p[0]):
            result += ' '
        result += p
    return result

def minify(src, dst):
    result = subprocess.run(
        ['gcc', '-fpreprocessed', '-dD', '-E', src],
        capture_output=True, text=True
    )
    lines = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line or line.startswith('# ') and line.split()[1].isdigit():
            continue
        stripped = line.lstrip()
        if stripped.startswith('#include'):
            lines.append(stripped)
        elif stripped.startswith('#define'):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                lines.append(parts[0] + ' ' + parts[1] + ' ' + minify_line(parts[2]))
            else:
                lines.append(stripped)
        elif stripped.startswith('#'):
            lines.append(stripped)
        else:
            r = minify_line(line)
            if r:
                lines.append(r)
    # Concatenate non-preprocessor lines, inserting a space when needed between identifier chars
    out = []
    buf = []
    for line in lines:
        if line.startswith('#'):
            if buf:
                out.append(_join_code(buf))
                buf = []
            out.append(line)
        else:
            buf.append(line)
    if buf:
        out.append(_join_code(buf))
    with open(dst, 'w') as f:
        f.write('\n'.join(out) + '\n')
    print(f"{src}: {os.path.getsize(src)} -> {dst}: {os.path.getsize(dst)}")

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'chal/src/chal.c'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'chal/src/chal_mini.c'
    minify(src, dst)
