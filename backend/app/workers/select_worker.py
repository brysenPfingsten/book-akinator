import re

# Priority order: lower is better
ext_priority = {
    # '.txt': 0,
    '.epub': 1,
    '.pdf': 2,
    '.zip': 3,
    '.rar': 4,
}

# Build regex to match only the allowed extensions at the end
ext_regex = re.compile(
    r'^!(\w+)\s+(.*?)\s*(?:::\s*INFO::.*)?\s*$', re.IGNORECASE
)

# Only accept entries that end with the correct extension
valid_extensions = tuple(ext_priority.keys())

def extract_extension(filename):
    # Match extension at the end
    match = re.search(r'\.(' + '|'.join(e[1:] for e in ext_priority) + r')$', filename, re.IGNORECASE)
    if match:
        return '.' + match.group(1).lower()
    return None

def parse_and_sort(file_path):
    entries = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            m = ext_regex.match(line)
            if m:
                filename = m.group(2)
                ext = extract_extension(filename)
                if ext in ext_priority:
                    entries.append({
                        'original_line': line,
                        'filename': filename,
                        'extension': ext,
                        'priority': ext_priority[ext]
                    })

    return sorted(entries, key=lambda e: e['priority'])

