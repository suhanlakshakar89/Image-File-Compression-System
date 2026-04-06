import streamlit as st
import numpy as np
import cv2
from PIL import Image
import fitz  # PyMuPDF
import zipfile
import os
import io
import base64
import shutil

# ─────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="File Compressor",
    page_icon="🗜️",
    layout="centered"
)

st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stButton>button {
            background-color: #28a745;
            color: white;
            font-size: 16px;
            padding: 10px 28px;
            border-radius: 8px;
            border: none;
        }
        .stButton>button:hover { background-color: #218838; }
        .stat-box {
            background: #ffffff;
            border-radius: 10px;
            padding: 16px 24px;
            margin: 8px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .big-pct { font-size: 2rem; font-weight: 700; }
    </style>
""", unsafe_allow_html=True) 

# st.markdown("""
#     <style>
#         .main {
#             background-color: #f8f9fa;
#             color: #000000;   /* FIX: force dark text */
#         }

#         /* Make all text visible */
#         body, p, div, span {
#             color: #000000 !important;
#         }

#         .stButton>button {
#             background-color: #28a745;
#             color: white;
#             font-size: 16px;
#             padding: 10px 28px;
#             border-radius: 8px;
#             border: none;
#         }

#         .stButton>button:hover {
#             background-color: #218838;
#         }

#         .stat-box {
#             background: #ffffff;
#             color: #000000;   /* FIX: text visible */
#             border-radius: 10px;
#             padding: 16px 24px;
#             margin: 8px 0;
#             box-shadow: 0 2px 8px rgba(0,0,0,0.08);
#         }

#         .big-pct {
#             font-size: 2rem;
#             font-weight: 700;
#             color: #000000;  /* FIX */
#         }

#         /* FIX: Streamlit markdown text visibility */
#         .stMarkdown, .stText {
#             color: #000000 !important;
#         }
#     </style>
# """, unsafe_allow_html=True)


# ─────────────────────────────────────────
#  COMPRESSION FUNCTIONS
# ─────────────────────────────────────────

def analyze_image_complexity(image: Image.Image) -> float:
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return np.sum(edges) / edges.size


def compress_image(content: bytes) -> tuple[bytes, str]:
    image = Image.open(io.BytesIO(content)).convert("RGB")

    # Resize to 50% dimensions
    new_size = (int(image.width * 0.5), int(image.height * 0.5))
    image = image.resize(new_size, Image.LANCZOS)

    complexity = analyze_image_complexity(image)
    quality = 15 if complexity > 0.15 else (12 if complexity > 0.08 else 8)

    buf = io.BytesIO()
    image.save(buf, "JPEG", optimize=True, quality=quality)
    msg = f"Image | Complexity: {complexity:.4f} | Quality: {quality} | Resized 50%"
    return buf.getvalue(), msg


def compress_pdf(content: bytes) -> tuple[bytes, str]:
    # Write to temp, process, read back
    tmp_in = "/tmp/input.pdf"
    tmp_out = "/tmp/compressed.pdf"
    with open(tmp_in, "wb") as f:
        f.write(content)

    doc = fitz.open(tmp_in)
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
                img_pil = Image.open(io.BytesIO(base["image"])).convert("RGB")
                new_size = (int(img_pil.width * 0.4), int(img_pil.height * 0.4))
                img_pil = img_pil.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                img_pil.save(buf, "JPEG", quality=15)
                doc.update_stream(xref, buf.getvalue())
            except Exception:
                pass

    doc.save(tmp_out, garbage=4, deflate=True, clean=True)
    doc.close()

    with open(tmp_out, "rb") as f:
        return f.read(), "PDF compressed aggressively"


def compress_docx(content: bytes) -> tuple[bytes, str]:
    tmp_in  = "/tmp/input.docx"
    tmp_out = "/tmp/compressed.docx"
    extract_dir = "/tmp/temp_docx"

    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    with open(tmp_in, "wb") as f:
        f.write(content)

    with zipfile.ZipFile(tmp_in, "r") as z:
        z.extractall(extract_dir)

    media_path = os.path.join(extract_dir, "word", "media")
    if os.path.exists(media_path):
        for img_file in os.listdir(media_path):
            img_path = os.path.join(media_path, img_file)
            try:
                img = Image.open(img_path).convert("RGB")
                new_size = (int(img.width * 0.4), int(img.height * 0.4))
                img = img.resize(new_size, Image.LANCZOS)
                img.save(img_path, "JPEG", optimize=True, quality=15)
            except Exception:
                pass

    with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder, _, files in os.walk(extract_dir):
            for file in files:
                path = os.path.join(folder, file)
                z.write(path, os.path.relpath(path, extract_dir))

    with open(tmp_out, "rb") as f:
        return f.read(), "DOCX compressed aggressively"


# ─────────────────────────────────────────
#  MIME HELPER
# ─────────────────────────────────────────
MIME_MAP = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/jpeg",   # output is always JPEG after compression
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ─────────────────────────────────────────
#  UI
# ─────────────────────────────────────────
st.title("🗜️ File Compressor")
st.markdown("Compress **Images, PDFs, and DOCX** files by up to **80–90%** in size.")
st.divider()

uploaded = st.file_uploader(
    "📁 Upload your file",
    type=["jpg", "jpeg", "png", "pdf", "docx"],
    help="Supported: JPG, PNG, PDF, DOCX"
)

if uploaded:
    filename   = uploaded.name
    base_name, ext_with_dot = os.path.splitext(filename)   # "xyz", ".pdf"
    ext        = ext_with_dot.lstrip(".").lower()           # "pdf"
    content    = uploaded.read()
    orig_size  = len(content) / 1024                        # KB

    # st.markdown(f"""
    # <div class="stat-box">
    #     📂 <b>File:</b> {filename}<br>
    #     📏 <b>Original size:</b> {orig_size:.1f} KB<br>
    #     🔍 <b>Type:</b> {ext.upper()}
    # </div>
    # """, unsafe_allow_html=True) 

    st.markdown(f"""
<div class="stat-box" style="color:#000000 !important;">
    <p style="color:#000000; margin:0;">📂 <b>File:</b> {filename}</p>
    <p style="color:#000000; margin:0;">📏 <b>Original size:</b> {orig_size:.1f} KB</p>
    <p style="color:#000000; margin:0;">🔍 <b>Type:</b> {ext.upper()}</p>
</div>
""", unsafe_allow_html=True)

    if st.button("🚀 Compress Now"):
        with st.spinner("⏳ Compressing..."):
            try:
                if ext in ["jpg", "jpeg", "png"]:
                    out_bytes, msg = compress_image(content)
                    out_ext = "jpg"
                elif ext == "pdf":
                    out_bytes, msg = compress_pdf(content)
                    out_ext = "pdf"
                elif ext == "docx":
                    out_bytes, msg = compress_docx(content)
                    out_ext = "docx"
                else:
                    st.error(f"❌ Unsupported file type: .{ext}")
                    st.stop()

                comp_size = len(out_bytes) / 1024
                saved     = orig_size - comp_size
                pct       = (saved / orig_size * 100) if orig_size > 0 else 0

                # ── Stats ──
                color = "#28a745" if pct >= 70 else ("#ffc107" if pct >= 40 else "#dc3545")
                st.success(f"✅ {msg}")
                col1, col2, col3 = st.columns(3)
                col1.metric("📦 Original",   f"{orig_size:.1f} KB")
                col2.metric("📉 Compressed", f"{comp_size:.1f} KB")
                col3.metric("💾 Saved",      f"{saved:.1f} KB")

                st.markdown(
                    f'<div class="stat-box" style="text-align:center">'
                    f'<span class="big-pct" style="color:{color}">🎯 {pct:.1f}% smaller</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # ── Image preview ──
                if ext in ["jpg", "jpeg", "png"]:
                    st.image(out_bytes, caption="🖼️ Compressed Preview", use_column_width=True)

                # ── Download button — xyz_compressed.pdf ──
                download_name = f"{base_name}_compressed.{out_ext}"
                st.download_button(
                    label=f"⬇️ Download  {download_name}",
                    data=out_bytes,
                    file_name=download_name,
                    mime=MIME_MAP.get(out_ext, "application/octet-stream"),
                    use_container_width=True
                )

            except Exception as e:
                st.error(f"❌ Compression failed: {e}")
                import traceback
                st.code(traceback.format_exc())

else:
    st.info("👆 Upload a file above to get started.")
