#!/usr/bin/env python3
import sys
import zlib
from pathlib import Path
import re

def pdf_literal_string(s: str) -> str:
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"

def make_pdf_with_attachment(file_path: Path, out_pdf: Path):
    filename = file_path.name
    data = file_path.read_bytes()
    compressed = zlib.compress(data)

    if out_pdf.exists():
        # Read existing PDF and try to preserve objects
        pdf_bytes = out_pdf.read_bytes()
        existing_objects = re.findall(rb'(\d+ 0 obj.*?endobj\n)', pdf_bytes, re.S)
        objects = existing_objects
        # Find the highest object number
        obj_nums = [int(re.match(rb'(\d+)', obj).group(1)) for obj in existing_objects]
        next_obj_num = max(obj_nums) + 1 if obj_nums else 1
        # Find existing Names array
        names_match = re.search(rb'/Names\s*\[\s*(.*?)\s*\d+ 0 R\s*\]', pdf_bytes, re.S)
        if names_match:
            names_list = names_match.group(1).decode('utf-8').split()
        else:
            names_list = []
        names_list.append(pdf_literal_string(filename))
    else:
        objects = []

        # Object 1: Catalog
        obj1 = b"1 0 obj\n<< /Type /Catalog /Names 2 0 R >>\nendobj\n"
        objects.append(obj1)

        # Object 2: Names dictionary
        obj2 = b"2 0 obj\n<< /EmbeddedFiles 3 0 R >>\nendobj\n"
        objects.append(obj2)

        names_list = [pdf_literal_string(filename)]
        next_obj_num = 4  # start for first file

    # Object for new file
    file_obj_num = next_obj_num
    stream_obj_num = next_obj_num + 1

    # Object N: Name tree
    obj_names = f"{file_obj_num} 0 obj\n<< /Names [ {' '.join(names_list)} {stream_obj_num} 0 R ] >>\nendobj\n".encode('utf-8')
    objects.append(obj_names)

    # Object N+1: Filespec
    obj_filespec = f"{stream_obj_num} 0 obj\n<< /Type /Filespec /F {pdf_literal_string(filename)} /EF << /F {stream_obj_num + 1} 0 R >> >>\nendobj\n".encode('utf-8')
    objects.append(obj_filespec)

    # Object N+2: EmbeddedFile
    obj_embedded = f"{stream_obj_num + 1} 0 obj\n<< /Type /EmbeddedFile /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n".encode('utf-8') \
                   + compressed + b"\nendstream\nendobj\n"
    objects.append(obj_embedded)

    # Rebuild PDF
    header = b"%PDF-1.7\n%\xE2\xE3\xCF\xD3\n"
    out_bytes = bytearray(header)
    offsets = []
    for obj in objects:
        offsets.append(len(out_bytes))
        out_bytes.extend(obj)

    xref_start = len(out_bytes)
    out_bytes.extend(b"xref\n")
    out_bytes.extend(f"0 {len(objects)+1}\n".encode('utf-8'))
    out_bytes.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out_bytes.extend(f"{off:010d} 00000 n \n".encode('utf-8'))

    trailer = f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n".encode('utf-8')
    out_bytes.extend(trailer)
    out_bytes.extend(b"startxref\n")
    out_bytes.extend(f"{xref_start}\n".encode('utf-8'))
    out_bytes.extend(b"%%EOF\n")

    out_pdf.write_bytes(out_bytes)
    print(f"Embedded '{filename}' into {out_pdf} ({len(data)} bytes).")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 embed_file_into_pdf.py file_to_embed output.pdf")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    if not src.exists():
        print("Embed file does not exist:", src)
        sys.exit(2)
    make_pdf_with_attachment(src, dst)

