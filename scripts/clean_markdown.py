import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
files = [
    ROOT / 'SOLUCAO_DATABASE_LOCKED.md',
    ROOT / 'BACKTEST_INSIGHTS_FEATURE.md',
    ROOT / 'BACKTEST_INSIGHTS_IMPLEMENTATION.md'
]

lang_whitelist = ('bash','python','sql','text','sh','json','yaml','ini')

for f in files:
    if not f.exists():
        print(f"Skipping {f}: not found")
        continue
    s = f.read_text(encoding='utf-8')
    original = s
    # Remove outer fences if file starts with a fence and ends with a matching fence
    lines = s.splitlines()
    if lines and lines[0].strip().startswith('```') and lines[-1].strip().startswith('```'):
        # remove first fence line and last fence line
        # but ensure we don't remove valid fenced blocks inside
        # If the first fence includes a language (like ```markdown) and the second is a plain fence, remove both
        # We'll only remove if the first fence appears immediately before a heading
        if len(lines) > 1 and lines[1].lstrip().startswith('#'):
            print(f"Cleaning outer fence in {f.name}")
            lines = lines[1:-1]
            s = '\n'.join(lines)

    # Add language tag 'text' to code fences that have no language
    # Replace occurrences of ```\n that are not followed by a known language
    def repl(match):
        nxt = match.group(1)
        # if next token looks like a language, keep as-is
        token = nxt.split('\n',1)[0].strip()
        if token.split()[0] in lang_whitelist:
            return match.group(0)
        return '```text\n' + nxt

    s = re.sub(r'```\n([\s\S]*?)', lambda m: ('```text\n'+m.group(1)) if not m.group(0).startswith('```') else m.group(0), s)
    # The above is conservative; now also fix isolated fences like lines starting with ``` followed by newline
    s = re.sub(r'```\n', '```text\n', s)

    # Write back if changed
    if s != original:
        f.write_text(s, encoding='utf-8')
        print(f"Updated {f.name}")
    else:
        print(f"No changes for {f.name}")

print('Done')
