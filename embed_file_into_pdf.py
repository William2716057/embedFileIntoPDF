#!/usr/bin/env python3
import sys
import zlib
from pathlib import Path

def pdf_literal_string(s: str) -> str:
    """Return PDF literal string with parentheses and backslashes escaped."""
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"

def make_pdf_with_attachment(file_path: Path, out_pdf: Path):
    filename = file_path.name
    data = file_path.read_bytes()
    compressed = zlib.compress(data)

    # PDF objects we will write:
    # 1 0 obj - Catalog (references /Names)
    # 2 0 obj - Names dict with EmbeddedFiles pointing to object 3
    # 3 0 obj - Name tree for EmbeddedFiles: << /Names [ (filename) 4 0 R ] >>
    # 4 0 obj - Filespec pointing to EF << /F 5 0 R >> and F (filename)
    # 5 0 obj - EmbeddedFile stream (FlateDecode) containing compressed bytes

    objects = []

    # Object 1: Catalog
    obj1 = b"""1 0 obj
<< /Type /Catalog /Names 2 0 R >>
endobj
"""
    objects.append(obj1)

    # Object 2: Names dictionary
    obj2 = b"""2 0 obj
<< /EmbeddedFiles 3 0 R >>
endobj
"""
    objects.append(obj2)

    # Object 3: Name tree with Names array
    obj3 = ("3 0 obj\n<< /Names [ %s 4 0 R ] >>\nendobj\n" % pdf_literal_string(filename)).encode('utf-8')
    objects.append(obj3)

    # Object 4: Filespec: /F (filename) and /EF << /F 5 0 R >>
    obj4 = ("4 0 obj\n<< /Type /Filespec /F %s /EF << /F 5 0 R >> >>\nendobj\n" % pdf_literal_string(filename)).encode('utf-8')
    objects.append(obj4)

    # Object 5: EmbeddedFile stream (compressed)
    # We include Filter /FlateDecode and put Length of compressed data.
    stream_header = ("5 0 obj\n<< /Type /EmbeddedFile /Filter /FlateDecode /Length %d >>\nstream\n" % len(compressed)).encode('utf-8')
    stream_footer = b"\nendstream\nendobj\n"
    obj5 = stream_header + compressed + stream_footer
    objects.append(obj5)

    # Build file bytes, tracking offsets for xref
    header = b"%PDF-1.7\n%\xE2\xE3\xCF\xD3\n"  # pdf header + binary comment line
    out_bytes = bytearray()
    out_bytes.extend(header)

    offsets = []
    for obj in objects:
        offsets.append(len(out_bytes))
        out_bytes.extend(obj)

    # xref table
    xref_start = len(out_bytes)
    out_bytes.extend(b"xref\n")
    # number of objects + 1 (object 0)
    out_bytes.extend(f"0 {len(objects)+1}\n".encode('utf-8'))
    # object 0
    out_bytes.extend(b"0000000000 65535 f \n")
    # entries for each object
    for off in offsets:
        out_bytes.extend(f"{off:010d} 00000 n \n".encode('utf-8'))

    # trailer
    trailer = (
        "trailer\n"
        "<< /Size %d /Root 1 0 R >>\n" % (len(objects)+1)
    ).encode('utf-8')
    out_bytes.extend(trailer)
    out_bytes.extend(b"startxref\n")
    out_bytes.extend(f"{xref_start}\n".encode('utf-8'))
    out_bytes.extend(b"%%EOF\n")

    out_pdf.write_bytes(out_bytes)
    print(f"Created {out_pdf} with embedded file '{filename}' ({len(data)} bytes).")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Missing input: python3 embed_file_into_pdf.py file_to_embed output.pdf")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    if not src.exists():
        print("Embed file does not exist:", src)
        sys.exit(2)
    make_pdf_with_attachment(src, dst)
