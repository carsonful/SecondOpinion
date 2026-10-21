"""Private, bounded subprocess used for PDF text extraction."""
import io
import json
import sys


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    except ImportError:  # Parent timeout still applies on Windows.
        pass
    from pypdf import PdfReader
    raw = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError('size')
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
        raise ValueError('encrypted or page limit')
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or '')
        if sum(map(len, pages)) > 60_000:
            # Let the parent report its normal text-budget error, without more work.
            break
    text = '\n\n'.join(f'[Page {i}]\n{page}' for i, page in enumerate(pages, 1))
    print(json.dumps({'identity_text': '\n'.join(pages[:2]), 'text': text}))


if __name__ == '__main__':
    main()
