"""Generate test PDFs for parser strategy validation."""
import os
from fpdf import FPDF

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(DATA_DIR, exist_ok=True)


def make_pdf(filename: str, num_pages: int):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for i in range(1, num_pages + 1):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 15, f"Page {i} of {num_pages}", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 11)
        body = (
            f"This is the body text on page {i}. It contains sample content for "
            f"testing parser strategy, text extraction, and page counting. "
            f"DocuMind Graph KG-RAG system validates multimodal document parsing. "
            f"The quick brown fox jumps over the lazy dog near the bank of the river. " * 3
        )
        pdf.multi_cell(0, 6, body)
        pdf.ln(3)

        # Add a heading on every page
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"Section {i}: Analysis Results", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, "Additional paragraph content follows the section heading. This text provides more context for the document analysis pipeline.")
        pdf.ln(2)

        # Table every 3 pages
        if i % 3 == 0:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, f"Table {i//3}: Experimental Data", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            col_w = 40
            for h in ["Sample", "Value", "Unit", "Status"]:
                pdf.cell(col_w, 7, h, border=1)
            pdf.ln()
            for r in range(3):
                for c in range(4):
                    pdf.cell(col_w, 6, f"{chr(65+r)}{c+1}", border=1)
                pdf.ln()

        # Figure caption every 5 pages
        if i % 5 == 0:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, f"Figure {i//5}: Concentration vs. Time Plot", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, "Caption: This figure shows the relationship between inhibitor concentration and surface coverage over time.", new_x="LMARGIN", new_y="NEXT")

    filepath = os.path.join(DATA_DIR, filename)
    pdf.output(filepath)
    print(f"Created {filepath} ({num_pages} pages)")
    return filepath


if __name__ == "__main__":
    make_pdf("parser-test-11p.pdf", 11)
    make_pdf("parser-test-50p.pdf", 50)
    print("Done.")
