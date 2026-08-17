from pathlib import Path

import pdfplumber

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed/extracted_text")

OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_pdf_text(pdf_path: Path) -> str:
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    return "\n\n".join(full_text)


def clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if len(line.strip()) < 3:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def main():
    for pdf_file in RAW_DIR.glob("*.pdf"):
        print(f"Extracting: {pdf_file.name}")
        raw_text = extract_pdf_text(pdf_file)
        text = clean_text(raw_text)
        out_file = OUT_DIR / (pdf_file.stem + ".txt")
        out_file.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
