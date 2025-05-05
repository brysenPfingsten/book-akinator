from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
import os
import re


def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_')


def extract_epub_to_txt(epub_path, output_dir):
    book = epub.read_epub(epub_path)
    os.makedirs(output_dir, exist_ok=True)

    file_count = 0

    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # Use <h1>, <h2>, or title fallback
            title_tag = soup.find(['h1', 'h2']) or soup.title
            title = title_tag.get_text(strip=True) if title_tag else f'section_{file_count}'
            filename = f"{slugify(title)}.txt"

            # Extract plain text from the HTML
            text = soup.get_text(separator="\n")

            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(text.strip())

            print(f"Saved: {filename}")
            file_count += 1