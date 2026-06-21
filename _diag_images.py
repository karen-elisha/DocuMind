# -*- coding: utf-8 -*-
"""Debug image extraction from Docling"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from docling.document_converter import DocumentConverter

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads", "NIPS-2017-attention-is-all-you-need-Paper (1).pdf")
converter = DocumentConverter()
result = converter.convert(pdf_path)
doc = result.document

pictures = list(doc.pictures)
print(f"Total pictures: {len(pictures)}")

pic = pictures[0]
print(f"\nPicture 0 type: {type(pic).__name__}")
print(f"dir(pic): {[x for x in dir(pic) if not x.startswith('__')]}")

# Check get_image carefully
get_img = getattr(pic, "get_image", None)
print(f"\nget_image exists: {callable(get_img)}")
if callable(get_img):
    import inspect
    sig = inspect.signature(get_img)
    print(f"get_image signature: {sig}")
    try:
        result_img = get_img(doc)
        print(f"get_image(doc) returned: {type(result_img)}")
        if result_img is not None:
            print(f"  size: {result_img.size}")
            print(f"  mode: {result_img.mode}")
    except Exception as e:
        print(f"get_image(doc) failed: {e!r}")

# Check if doc has page_images or export_to_images
for attr_name in dir(doc):
    if 'image' in attr_name.lower() or 'export' in attr_name.lower():
        val = getattr(doc, attr_name)
        if callable(val):
            print(f"\ndoc.{attr_name}() - is callable")
        else:
            print(f"\ndoc.{attr_name} - type={type(val).__name__}")

# Check page image
for page_no, page in doc.pages.items():
    print(f"\nPage {page_no} (type={type(page).__name__})")
    print(f"  page.image: {getattr(page, 'image', 'N/A')}")
    # Check if page has an image attribute
    page_image = getattr(page, 'image', None)
    if page_image is not None:
        print(f"  page.image type: {type(page_image).__name__}")
    # Check get_image on page
    page_get_image = getattr(page, 'get_image', None)
    if callable(page_get_image):
        print(f"  page.get_image() is callable - will try")
        try:
            pi = page_get_image(doc) if 'doc' in inspect.signature(page_get_image).parameters else page_get_image()
            print(f"  page.get_image returned: {type(pi)}")
        except Exception as e:
            print(f"  page.get_image failed: {e!r}")
    break
