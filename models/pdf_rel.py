import os
import shutil
import time

from PyPDF2 import PdfReader, PdfWriter

if not os.path.exists('data'):
    os.makedirs('data')

base_dir = os.path.abspath('data')
progress = dict()


def detail_extract(file_page):
    try:
        contents = file_page.extract_text().split('\n')
        content = contents[3:6]

        dates = content[0].strip().split('-')
        d_mon = dates[0]
        d_year = dates[-1]
        sur_name = content[1].split(':')[1].split(',')[0].strip()
        if ':' in content[-1]:
            ippis = content[-1].split(':')[-1].strip()
        else:
            ippis = content[6].split(':')[-1].strip()
        new_name = [ippis, sur_name, d_mon, d_year]
        return new_name
    except Exception:
        return None


def splitter(file, file_path, task_id):
    try:
        if os.path.exists(file_path):
            shutil.rmtree(file_path)

        os.makedirs(file_path)
        
        pdf_reader = PdfReader(file)
        pages = len(pdf_reader.pages)

        for i in range(pages):
            name = detail_extract(pdf_reader.pages[i])
            
            # Update progress
            progress[task_id] = (i + 1) / pages * 100
            time.sleep(0.1)  # Simulate time taken for processing each page
            
            if not name:
                continue
            
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[i])
            
            if name[0] == '482427':
                name[0] = str(int(name[0]) + i)

            pswd = f'{name[1][:2]}{name[0][-2:]}'
            pdf_writer.encrypt(pswd)

            name = f'{name[0]}_{name[1]}_{name[2]}-{name[3]}.pdf'

            file_name = str(os.path.join(file_path, name))
            with open(file_name, 'wb') as f:
                pdf_writer.write(f)

        progress[task_id] = 100  # Ensure progress is marked complete
        return True
    except Exception as e:
        progress[task_id] = 100  # Indicate error
        print('error:', e)
        return False