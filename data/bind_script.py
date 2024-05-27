from PyPDF2 import PdfWriter, PdfReader

pdf_file = PdfReader('482427_ARAF_MAR-2023.pdf')
pdfwriter = PdfWriter()
for i in range(50):
    pdfwriter.add_page(pdf_file.pages[0])
    
pdfwriter.write('binded.pdf')
print(f'pdf file written successfully: {i} pages')
