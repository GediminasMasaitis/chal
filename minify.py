#!/usr/bin/env python3
"""Strip comments, whitespace, and rename identifiers in C source."""
import subprocess, sys, os, re, itertools, string

# --- Preprocessor ifdef evaluation ---

def eval_ifdefs(source, defines):
    """Evaluate #ifdef/#ifndef/#else/#endif, keeping only active branches."""
    out = []
    stack = []  # stack of (active, seen_true)
    for line in source.splitlines(True):
        stripped = line.strip()
        if stripped.startswith('#ifdef '):
            sym = stripped.split()[1]
            active = all(a for a, _ in stack)  # parent must be active
            matches = sym in defines
            stack.append((active and matches, active and matches))
            continue
        elif stripped.startswith('#ifndef '):
            sym = stripped.split()[1]
            active = all(a for a, _ in stack)
            matches = sym not in defines
            stack.append((active and matches, active and matches))
            continue
        elif stripped == '#else':
            if stack:
                prev_active, seen_true = stack[-1]
                parent_active = all(a for a, _ in stack[:-1])
                now_active = parent_active and not seen_true
                stack[-1] = (now_active, seen_true or now_active)
            continue
        elif stripped == '#endif':
            if stack:
                stack.pop()
            continue
        # Include line only if all levels are active
        if all(a for a, _ in stack):
            out.append(line)
    return ''.join(out)

# --- Whitespace minification ---

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
    if not parts:
        return ''
    result = parts[0]
    for p in parts[1:]:
        if result and p and is_ident(result[-1]) and is_ident(p[0]):
            result += ' '
        result += p
    return result

# --- Identifier renaming ---

DO_NOT_RENAME = frozenset(
    # C keywords
    'auto break case char const continue default do double else enum extern '
    'float for goto if inline int long register return short signed sizeof '
    'static struct switch typedef typeof union unsigned void volatile while '
    # C alternative tokens
    'and or not and_eq or_eq not_eq xor xor_eq bitand bitor compl '
    # Standard library functions used in chal.c
    'printf fprintf sscanf sprintf snprintf scanf '
    'strlen strstr strncmp strcmp strcpy strcat memset memcpy memmove '
    'calloc malloc realloc free atoi atol atof strtol strtod setbuf setvbuf '
    'clock exit abort atexit '
    'tolower toupper isupper islower isalpha isdigit isalnum isspace isxdigit '
    'putchar getchar '
    'abs fabs log log2 log10 round ceil floor sqrt pow exp fmax fmin '
    'fgets fputs puts getchar putchar fflush fopen fclose fread fwrite '
    # Standard types
    'size_t int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t '
    'clock_t FILE '
    # Standard macros/constants
    'NULL CLOCKS_PER_SEC EOF '
    'stdin stdout stderr '
    'PRId64 PRIu64 PRIx64 SCNd64 SCNu64 '
    'INT64_MAX INT64_MIN UINT64_MAX '
    'true false bool _Bool '
    # Entry point
    'main '
    # Preprocessor directive keywords
    'define undef ifdef ifndef endif elif include pragma error warning line '
    # GCC builtins
    '__builtin_expect __attribute__ __inline __restrict '
    .split()
)

TOKEN_RE = re.compile(
    r'(?P<string>"(?:[^"\\]|\\.)*")'
    r"|(?P<char>'(?:[^'\\]|\\.)*')"
    r'|(?P<number>0[xX][0-9a-fA-F]+[uUlL]*'
    r'|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?[uUlLfF]*'
    r'|\.\d+(?:[eE][+-]?\d+)?[fFlL]*)'
    r'|(?P<ident>[a-zA-Z_][a-zA-Z0-9_]*)'
    r'|(?P<punct>->|<<|>>|<=|>=|==|!=|&&|\|\||[+\-*/%&|^~!<>=.,;:?{}()\[\]#])'
    r'|(?P<ws>\s+)'
)

def tokenize_c(source):
    tokens = []
    pos = 0
    for line in source.split('\n'):
        # Handle #include <...> specially — don't tokenize the header path
        if line.lstrip().startswith('#include'):
            tokens.append(('pp_include', line))
            tokens.append(('newline', '\n'))
            continue
        for m in TOKEN_RE.finditer(line):
            kind = m.lastgroup
            text = m.group()
            tokens.append((kind, text))
        tokens.append(('newline', '\n'))
    return tokens

def short_name_gen(skip):
    chars = string.ascii_lowercase + string.ascii_uppercase
    length = 1
    while True:
        for combo in itertools.product(chars, repeat=length):
            name = ''.join(combo)
            if name not in skip:
                yield name
        length += 1

def rename_identifiers(source):
    tokens = tokenize_c(source)
    # Count identifier frequencies
    freq = {}
    for kind, text in tokens:
        if kind == 'ident' and text not in DO_NOT_RENAME:
            freq[text] = freq.get(text, 0) + 1
    # Sort by frequency descending, then alphabetically for stability
    sorted_idents = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    # Generate rename map
    gen = short_name_gen(DO_NOT_RENAME)
    rename_map = {}
    for ident in sorted_idents:
        rename_map[ident] = next(gen)
    # Apply renames
    out = []
    for kind, text in tokens:
        if kind == 'ident' and text in rename_map:
            out.append(rename_map[text])
        elif kind == 'pp_include':
            out.append(text)
        elif kind == 'newline':
            out.append(text)
        else:
            out.append(text)
    return ''.join(out)

# --- Main pipeline ---

def minify(src, dst, defines=None):
    # Evaluate #ifdef/#endif before gcc preprocessing
    with open(src) as f:
        source = f.read()
    source = eval_ifdefs(source, defines or set())
    # Write to temp file for gcc
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False)
    tmp.write(source)
    tmp.close()
    result = subprocess.run(
        ['gcc', '-fpreprocessed', '-dD', '-E', tmp.name],
        capture_output=True, text=True
    )
    os.unlink(tmp.name)
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
    # Concatenate non-preprocessor lines
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
    content = '\n'.join(out) + '\n'
    # Rename identifiers
    content = rename_identifiers(content)
    # Re-minify whitespace after renaming (shorter names may allow removing spaces)
    final_lines = []
    for line in content.split('\n'):
        if not line:
            continue
        if line.startswith('#'):
            final_lines.append(line)
        else:
            r = minify_line(line)
            if r:
                final_lines.append(r)
    out2 = []
    buf2 = []
    for line in final_lines:
        if line.startswith('#'):
            if buf2:
                out2.append(_join_code(buf2))
                buf2 = []
            out2.append(line)
        else:
            buf2.append(line)
    if buf2:
        out2.append(_join_code(buf2))
    content = '\n'.join(out2) + '\n'
    with open(dst, 'w') as f:
        f.write(content)
    print(f"{src}: {os.path.getsize(src)} -> {dst}: {os.path.getsize(dst)}")

if __name__ == '__main__':
    # Parse -DFOO flags and positional args
    defines = set()
    args = []
    for a in sys.argv[1:]:
        if a.startswith('-D'):
            defines.add(a[2:])
        else:
            args.append(a)
    src = args[0] if len(args) > 0 else 'chal/src/chal.c'
    dst = args[1] if len(args) > 1 else 'chal/src/chal_mini.c'
    minify(src, dst, defines)
