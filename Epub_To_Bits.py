import os
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tempfile
import zipfile
from flask import Flask, request, send_file

app = Flask(__name__)

# Function to extract metadata and cover image
def extract_metadata(epub_file, output_folder):
    book = epub.read_epub(epub_file)
    title = book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else "Unknown Title"
    author = book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else "Unknown Author"
    cover_path = None
    
    for item in book.items:
        if item.get_type() == epub.ITEM_COVER:
            cover_path = os.path.join(output_folder, "cover.jpg")
            with open(cover_path, "wb") as img_file:
                img_file.write(item.get_content())
    
    return {"title": title, "author": author, "cover_image": cover_path}

# Function to extract HTML content and images
def process_epub(epub_file, output_folder):
    book = epub.read_epub(epub_file)
    metadata = extract_metadata(epub_file, output_folder)
    all_html_bits = []
    target_words_per_bit = 1250
    word_count = 0
    formatted_html_accumulated = ""
    image_files = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            
            for img_tag in soup.find_all("img"):
                img_src = img_tag.get("src")
                try:
                    img_data = book.get_item_with_href(img_src)
                    if img_data and img_data.media_type.startswith("image/"):
                        img_name = os.path.basename(img_src)
                        img_path = os.path.join(output_folder, img_name)
                        with open(img_path, "wb") as img_file:
                            img_file.write(img_data.get_content())
                        image_files.append(img_path)
                        img_tag["src"] = img_name
                except:
                    pass
            
            text_blocks = soup.find_all()
            
            for block in text_blocks:
                block_html = str(block)
                block_word_count = len(block.get_text(" ", strip=True).split())
                
                formatted_html_accumulated += block_html + "\n"
                word_count += block_word_count
                
                if word_count >= target_words_per_bit:
                    all_html_bits.append(formatted_html_accumulated)
                    formatted_html_accumulated = ""
                    word_count = 0
    
    if formatted_html_accumulated:
        all_html_bits.append(formatted_html_accumulated)
    
    html_file = os.path.join(output_folder, "all_bits.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write("\n\n<!-- BIT SEPARATOR -->\n\n".join(all_html_bits))
    
    return html_file, metadata, image_files

# API Route to Upload EPUB
@app.route('/upload', methods=['POST'])
def upload_epub():
    if 'file' not in request.files:
        return {"error": "No file uploaded"}, 400
    
    epub_file = request.files['file']
    temp_folder = tempfile.mkdtemp()
    temp_path = os.path.join(temp_folder, "uploaded.epub")
    epub_file.save(temp_path)
    
    html_file, metadata, image_files = process_epub(temp_path, temp_folder)
    
    zip_path = os.path.join(temp_folder, "output.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(html_file, "all_bits.html")
        for img_file in image_files:
            zipf.write(img_file, os.path.basename(img_file))
    
    if os.path.exists(zip_path):
        print("✅ ZIP file successfully created:", zip_path)
        return send_file(zip_path, as_attachment=True, download_name="processed_epub.zip")
    else:
        print("❌ ZIP file was not created. Check file paths.")
        return {"error": "ZIP file was not created"}, 500

# Run Flask App
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
