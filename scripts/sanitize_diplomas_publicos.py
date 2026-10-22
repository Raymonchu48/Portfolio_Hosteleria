#!/usr/bin/env python3
"""Sanea identificadores DNI/NIE válidos en copias públicas de diplomas.

No escribe ni imprime los identificadores. Los PDF originales privados no se tocan:
sólo se sustituyen los ficheros de publicación del repositorio.
"""
from pathlib import Path
import re
import io
import sys
import fitz
from PIL import Image, ImageDraw
import pytesseract
from pytesseract import Output

ROOT = Path("diplomas")
SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
NUMERIC = re.compile(r"(?<![A-Za-z0-9])(?:[0-9]{2}[\s.\-]?[0-9]{3}[\s.\-]?[0-9]{3}[\s.\-]?[A-Za-z]|[XYZxyz][\s.\-]?[0-9]{7}[\s.\-]?[A-Za-z])(?![A-Za-z0-9])")

def valid_id(candidate):
    s = re.sub(r"[\s.\-]", "", candidate).upper()
    if re.fullmatch(r"\d{8}[A-Z]", s):
        return LETTERS[int(s[:8]) % 23] == s[-1]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", s):
        n = {"X":"0","Y":"1","Z":"2"}[s[0]] + s[1:8]
        return LETTERS[int(n) % 23] == s[-1]
    return False

def locate(words):
    """Bounding boxes for standalone/split identifiers in one text line."""
    rows = {}
    for w in words:
        # x0 y0 x1 y1 text block line word
        if len(w) < 7:
            continue
        rows.setdefault((w[5], w[6]), []).append(w)
    boxes = []
    for row in rows.values():
        row = sorted(row, key=lambda w: w[0])
        for i in range(len(row)):
            for n in range(1, min(5, len(row)-i)+1):
                sample = row[i:i+n]
                raw = " ".join(str(w[4]) for w in sample)
                # avoid capturing long surrounding non-DNI content
                if len(raw) > 25:
                    break
                matches = list(NUMERIC.finditer(raw))
                if len(matches) != 1 or not valid_id(matches[0].group()):
                    continue
                if n == 1 and matches[0].start() > 0:
                    # Don't erase surrounding words in a large text object
                    word = str(sample[0][4])
                    if word != matches[0].group():
                        continue
                box = fitz.Rect(min(w[0] for w in sample), min(w[1] for w in sample),
                                max(w[2] for w in sample), max(w[3] for w in sample))
                if not any(box.intersects(old) and box.get_area() <= old.get_area() * 1.5 for old in boxes):
                    boxes.append(box)
                break
    return boxes

def ocr_boxes(image, min_conf=45):
    data = pytesseract.image_to_data(image, config="--psm 11", output_type=Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1
        if confidence < min_conf:
            continue
        x, y = data["left"][i], data["top"][i]
        w, h = data["width"][i], data["height"][i]
        words.append((x, y, x+w, y+h, text, data["block_num"][i], data["line_num"][i]))
    # Reindex block,line into fitz locators
    return locate(words)

def sanitize_pdf(path):
    doc = fitz.open(path)
    changed = False
    hits = 0
    metadata = dict(doc.metadata or {})
    for k, v in metadata.items():
        if not isinstance(v, str):
            continue
        cleared = NUMERIC.sub(lambda m: "[ID RESERVADO]" if valid_id(m.group()) else m.group(), v)
        if cleared != v:
            metadata[k] = cleared
            changed = True
    if changed:
        doc.set_metadata(metadata)
    for page in doc:
        rectangles = locate(page.get_text("words"))
        # OCR raster content to detect IDs also burned into logos/scanned copies.
        zoom = 2
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom,zoom), alpha=False)
        pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        rectangles += [fitz.Rect(x.x0/zoom, x.y0/zoom, x.x1/zoom, x.y1/zoom) for x in ocr_boxes(pil)]
        # De-duplicate, expand slightly for anti-aliased edges
        unique=[]
        for rect in rectangles:
            expanded = fitz.Rect(rect.x0-2,rect.y0-1,rect.x1+2,rect.y1+1) & page.rect
            if expanded.is_empty:
                continue
            if any(expanded.intersects(r) and expanded.get_area()<r.get_area()*1.5 for r in unique):
                continue
            unique.append(expanded)
        for rect in unique:
            page.add_redact_annot(rect, fill=(1,1,1), cross_out=False)
        if unique:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            changed = True
            hits += len(unique)
    if changed:
        tmp = path.with_name(path.name+".private_tmp")
        doc.save(tmp, garbage=4, deflate=True, clean=True)
        doc.close()
        tmp.replace(path)
    else:
        doc.close()
    return changed, hits

def sanitize_image(path):
    img=Image.open(path).convert("RGB")
    boxes=ocr_boxes(img, min_conf=35)
    if not boxes:
        return False,0
    drawer=ImageDraw.Draw(img)
    for r in boxes:
        drawer.rectangle((max(0,r.x0-5),max(0,r.y0-3),min(img.width,r.x1+5),min(img.height,r.y1+3)),fill="white")
    # Re-encode without retaining EXIF/PII metadata.
    img.save(path, quality=95 if path.suffix.lower() in {".jpg",".jpeg"} else None)
    return True,len(boxes)

def main():
    if not ROOT.is_dir():
        raise RuntimeError("Falta la carpeta de diplomas")
    processed=0
    modified=0
    redactions=0
    # Incluye copias antiguas ubicadas fuera de la carpeta diplomas/.
    # Se limita a nombres de certificado existentes, para no reescribir manuales ni CV.
    certificate_names = {p.name.lower() for p in ROOT.rglob("*") if p.is_file()}
    sources = [p for p in Path(".").rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES and
               (str(p).startswith("diplomas/") or
                p.name.lower() in certificate_names or
                re.search(r"diploma|certificado|acreditaci[oó]n",p.name,re.I)) and
               ".git" not in p.parts]
    for path in sorted(set(sources)):
        processed+=1
        if path.suffix.lower()==".pdf":
            did, count=sanitize_pdf(path)
        else:
            did,count=sanitize_image(path)
        if did:
            modified+=1
            redactions+=count
            print(f"Sanitizado: {path.name} ({count} coincidencias)")
    print(f"Revisados: {processed}; archivos corregidos: {modified}; redacciones: {redactions}")
    if not processed:
        raise RuntimeError("No se encontraron archivos para revisar")

if __name__=="__main__":
    main()
