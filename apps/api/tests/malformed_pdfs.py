"""Synthetic unreadable PDFs, shared by the adapter and API tests."""


def one_page_pdf(page_entries: bytes) -> bytes:
    """A minimal one-page PDF with a correct xref; `page_entries` go into the /Page dict."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R " + page_entries + b" >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref_at
    return bytes(out)


VALID_PAGE_PDF = one_page_pdf(b"/MediaBox [0 0 612 792]")

# Shapes a user can upload by accident. The first three fail when pdfplumber opens the file;
# the last three open fine and fail while pdfplumber reads the page's MediaBox.
MALFORMED_PDFS = {
    "empty": b"",
    "garbage": b"not a pdf at all",
    "truncated_header": b"%PDF-1.4\n1 0 obj",
    "mediabox_three_numbers": one_page_pdf(b"/MediaBox [0 0 612]"),  # IndexError
    "mediabox_missing": one_page_pdf(b""),  # TypeError
    "mediabox_control_byte": one_page_pdf(b"/MediaBox [0 0 \x1f12 792]"),  # MalformedPDFException
}
