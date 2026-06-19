# -*- coding: utf-8 -*-
"""Debug image extraction from Docling - round 2"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from docling.document_converter import DocumentConverter

pdf_path = r"C:\Users\tharu\OneDrive\Desktop\Dell\data\uploads\NIPS-2017-attention-is-all-you-need-Paper (1).pdf"
converter = DocumentConverter()
result = converter.convert(pdf_path)
doc = result.document

pictures = list(doc.pictures)
print(f"Total pictures: {len(pictures)}")

for i, pic in enumerate(pictures):
    print(f"\n=== Picture {i} ===")
    
    # Check image attribute
    img_attr = getattr(pic, 'image', None)
    print(f"pic.image: type={type(img_attr).__name__ if img_attr is not None else 'None'}")
    if img_attr is not None:
        print(f"pic.image dir: {[x for x in dir(img_attr) if not x.startswith('_')]}")
    
    # Check captions
    caps = getattr(pic, 'captions', None)
    if caps:
        print(f"pic.captions: {list(caps)}")
    
    ct = getattr(pic, 'caption_text', None)
    if ct:
        print(f"pic.caption_text: {ct}")
    
    # Check prov
    prov = getattr(pic, 'prov', None) or []
    print(f"pic.prov: {len(prov)} items")
    for p in prov:
        print(f"  prov: page_no={p.page_no}, bbox={p.bbox}")
    
    # Try get_image with different prov_index
    get_img = getattr(pic, 'get_image', None)
    for prov_idx in range(len(prov)):
        try:
            result_img = get_img(doc, prov_index=prov_idx)
            if result_img is not None:
                print(f"get_image(doc, prov_index={prov_idx}) returned: {type(result_img).__name__} size={result_img.size}")
        except Exception as e:
            print(f"get_image(doc, prov_index={prov_idx}) failed: {e!r}")

# Check doc.pages page image rendering
print("\n\n=== Trying to render page images ===")
doc2 = converter.convert(pdf_path).document
for page_no in [3, 4]:
    page = doc2.pages[page_no]
    page_image = getattr(page, 'image', None)
    if page_image is not None:
        print(f"Page {page_no} has image: type={type(page_image).__name__}")

# Check if page has get_image
page = doc2.pages[3]
page_get_image = getattr(page, 'get_image', None)
if callable(page_get_image):
    import inspect
    print(f"page.get_image sig: {inspect.signature(page_get_image)}")
    result = page_get_image(doc2)
    print(f"page.get_image(doc) returned: {type(result)}")

# Try export_to_images if it exists on doc
export_images = getattr(doc2, 'export_to_images', None)
if callable(export_images):
    print(f"\ndoc.export_to_images() exists and is callable")

# Check _list_images_on_disk
list_images = getattr(doc2, '_list_images_on_disk', None)
if callable(list_images):
    imgs = list_images()
    print(f"\ndoc._list_images_on_disk() returned: {imgs}")

# Check if PictureItem has an image reference we can use differently
print("\n=== Trying to find image data ===")
# Let's look at the raw PictureItem data
pic0 = pictures[0]
print(f"\nPicture 0 attributes with 'image' in name:")
for attr in dir(pic0):
    if 'image' in attr.lower():
        val = getattr(pic0, attr)
        print(f"  {attr}: callable={callable(val)}, type={type(val).__name__ if not callable(val) else 'callable'}")

# Check if image attribute is a PIL Image
if not callable(img_attr) and img_attr is not None:
    import PIL.Image
    if isinstance(img_attr, PIL.Image.Image):
        print(f"pic.image IS a PIL Image! size={img_attr.size}")

# One more approach: check if the conversion result has page_images
print("\n=== Checking ConversionResult ===")
print(f"dir(result): {[x for x in dir(result) if not x.startswith('_')]}")
