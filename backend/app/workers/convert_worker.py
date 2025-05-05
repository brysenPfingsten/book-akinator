import zipfile
import rarfile
import tempfile
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod
import os
import re
import mobi
from io import StringIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
import PyPDF2


class Converter(ABC):
    @abstractmethod
    def convert(self, input_path, output_dir):
        pass


def slugify(text):
    """Convert text to a safe filename."""
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()


class EpubConverter(Converter):
    def convert(self, input_path, output_dir):
        """Convert EPUB file to individual text files per section."""
        book = epub.read_epub(input_path)
        os.makedirs(output_dir, exist_ok=True)

        file_count = 0

        for item in book.get_items():
            if item.get_type() == ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')

                # Use <h1>, <h2>, or title fallback
                title_tag = soup.find(['h1', 'h2']) or soup.title
                title = title_tag.get_text(strip=True) if title_tag else f'section_{file_count}'
                filename = f"{file_count:03d}_{slugify(title)}.txt"

                # Extract plain text from the HTML
                text = soup.get_text(separator="\n")

                with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(text.strip())

                file_count += 1


class MobiConverter(Converter):
    def convert(self, input_path, output_dir):
        """Convert MOBI file to individual text files per section."""
        # Extract MOBI content
        temp_dir, filepath = mobi.extract(input_path)

        # MOBI files are often converted to HTML during extraction
        # So we'll treat them similarly to EPUBs
        try:
            # Try to find the HTML file in the extracted directory
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.html') or file.endswith('.htm'):
                        html_path = os.path.join(root, file)
                        with open(html_path, 'r', encoding='utf-8') as f:
                            soup = BeautifulSoup(f.read(), 'html.parser')

                        sections = self._split_into_sections(soup)
                        os.makedirs(output_dir, exist_ok=True)

                        for i, (title, content) in enumerate(sections):
                            filename = f"{i:03d}_{slugify(title)}.txt"
                            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                                f.write(content.strip())
        finally:
            mobi.cleanup(temp_dir)

    def _split_into_sections(self, soup):
        """Split HTML content into sections based on headings."""
        sections = []
        current_title = "Section"
        current_content = []

        for element in soup.find_all(True):
            if element.name in ['h1', 'h2', 'h3']:
                if current_content:
                    sections.append((current_title, '\n'.join(current_content)))
                    current_content = []
                current_title = element.get_text(strip=True)
            else:
                text = element.get_text(separator='\n', strip=True)
                if text:
                    current_content.append(text)

        if current_content:
            sections.append((current_title, '\n'.join(current_content)))

        return sections if sections else [("content", soup.get_text(separator='\n'))]


class PdfConverter(Converter):
    def convert(self, input_path, output_dir):
        """Convert PDF file to individual text files per section."""
        os.makedirs(output_dir, exist_ok=True)

        # First approach: Try to extract text with structure
        try:
            with open(input_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        filename = f"{i:03d}_page_{i + 1}.txt"
                        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f_out:
                            f_out.write(text.strip())
            return
        except Exception:
            pass

        # Fallback: Use pdfminer for more complex PDFs
        output_string = StringIO()
        laparams = LAParams()

        with open(input_path, 'rb') as f:
            extract_text_to_fp(f, output_string, laparams=laparams)

        full_text = output_string.getvalue()
        sections = self._split_pdf_into_sections(full_text)

        for i, (title, content) in enumerate(sections):
            filename = f"{i:03d}_{slugify(title)}.txt"
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content.strip())

    def _split_pdf_into_sections(self, text):
        """Attempt to split PDF text into sections based on common patterns."""
        lines = text.split('\n')
        sections = []
        current_section = []
        current_title = "Section 1"

        for line in lines:
            # Simple heuristic for section headings
            if (line.isupper() or
                (len(line) < 50 and line.strip() and not line[0].islower() and
                 not line.endswith('.') and not line.endswith(','))):
                if current_section:
                    sections.append((current_title, '\n'.join(current_section)))
                    current_section = []
                current_title = line.strip()
            else:
                current_section.append(line)

        if current_section:
            sections.append((current_title, '\n'.join(current_section)))

        return sections if sections else [("content", text)]


class TextConverter(Converter):
    def convert(self, input_path, output_dir):
        """Convert plain text file to individual files based on sections."""
        os.makedirs(output_dir, exist_ok=True)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split on multiple newlines or common chapter markers
        sections = re.split(r'\n\s*\n|\nCHAPTER [IVXLCDM0-9]+\n', content)

        for i, section in enumerate(sections):
            if section.strip():
                # Try to extract title from first line
                first_line = section.strip().split('\n')[0]
                if len(first_line) < 100 and not first_line[0].islower():
                    title = first_line.strip()
                    content = '\n'.join(section.strip().split('\n')[1:])
                else:
                    title = f"Section {i + 1}"
                    content = section.strip()

                filename = f"{i:03d}_{slugify(title)}.txt"
                with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f_out:
                    f_out.write(content.strip())


class ArchiveConverter(Converter):
    def convert(self, input_path, output_dir):
        """Base class for archive converters."""
        raise NotImplementedError("Use specific archive converter (Zip/Rar)")


class ZipConverter(ArchiveConverter):
    def convert(self, input_path, output_dir):
        """Extract and convert contents of ZIP archives."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            self._process_extracted(temp_dir, output_dir)

    def _process_extracted(self, temp_dir, output_dir):
        """Process all files in extracted directory."""
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    base_name = os.path.splitext(file)[0]
                    sub_output = os.path.join(output_dir, base_name)
                    convert_ebook(file_path, sub_output)


class RarConverter(ArchiveConverter):
    def convert(self, input_path, output_dir):
        """Extract and convert contents of RAR archives."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with rarfile.RarFile(input_path) as rf:
                rf.extractall(temp_dir)
            self._process_extracted(temp_dir, output_dir)

    def _process_extracted(self, temp_dir, output_dir):
        """Process all files in extracted directory (same as ZIP)."""
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path: str = os.path.join(root, file)
                if os.path.isfile(file_path):
                    base_name: str = os.path.splitext(file)[0]
                    sub_output: str = os.path.join(output_dir, base_name)
                    convert_ebook(file_path, sub_output)


# [Keep all existing converters (EpubConverter, MobiConverter, etc.) here]

def get_converter(input_path):
    """Get the appropriate converter based on file extension."""
    ext = os.path.splitext(input_path)[1].lower()

    converters = {
        '.epub': EpubConverter,
        '.mobi': MobiConverter,
        '.azw3': MobiConverter,
        '.pdf': PdfConverter,
        '.txt': TextConverter,
        '.zip': ZipConverter,
        '.rar': RarConverter
    }

    if ext in converters:
        return converters[ext]()
    raise ValueError(f"Unsupported file format: {ext}")


def convert_ebook(input_path, output_dir):
    """
    Convert an ebook file or archive to individual text files in the output directory.

    Args:
        input_path (str): Path to the input file/archive
        output_dir (str): Directory where text files will be saved
    """
    # Check if input exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    converter = get_converter(input_path)
    converter.convert(input_path, output_dir)
    print(f"Conversion complete. Files saved to {output_dir}")

# Example usage:
# convert_ebook('book.epub', 'output_directory')