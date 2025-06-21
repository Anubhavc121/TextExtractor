import streamlit as st
import openai
import base64
import json
from io import BytesIO
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("🧠 MCQ Extractor (Perseus Style) from Multiple Images")
st.write("Upload multiple images with MCQs. Get results in structured JSON format like Perseus uses.")

uploaded_files = st.file_uploader(
    "Upload image(s) with MCQs", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract all multiple choice questions (MCQs) from this image. "
                            "Respond with ONLY valid JSON in the format below and nothing else:\n\n"
                            "[\n  {\n    \"question\": \"...\",\n    "
                            "\"options\": [\"...\", \"...\", \"...\", \"...\"],\n    "
                            "\"answer_index\": 1\n  }\n]"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content

if uploaded_files:
    all_mcqs = []
    raw_outputs = []

    for img in uploaded_files:
        st.image(img, caption=img.name, use_container_width=True)
        with st.spinner(f"Extracting MCQs from {img.name}..."):
            raw_json = extract_json_mcqs_from_image(img.read())
            raw_outputs.append((img.name, raw_json))
            try:
                mcqs = json.loads(raw_json)
                all_mcqs.extend(mcqs)
            except json.JSONDecodeError:
                st.warning(f"⚠️ {img.name} returned non-JSON output. It will be shown below.")

    st.subheader("🧾 Final Output (Combined from All Images)")

    if all_mcqs:
        formatted = json.dumps(all_mcqs, indent=2)
        st.text_area("📋 Structured Perseus JSON", formatted, height=400)

        st.download_button(
            label="📄 Download JSON",
            data=formatted,
            file_name="perseus_mcqs.json",
            mime="application/json"
        )

        doc = Document()
        doc.add_heading("MCQs Extracted in Perseus Format", 0)
        for q in all_mcqs:
            doc.add_paragraph(f"Q: {q['question']}")
            for i, opt in enumerate(q["options"]):
                prefix = " ✅" if i == q["answer_index"] else ""
                doc.add_paragraph(f"  - {opt}{prefix}")
            doc.add_paragraph("")
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        st.download_button(
            label="📄 Download as Word Document",
            data=buffer,
            file_name="mcqs_perseus.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        st.warning("❗ No structured MCQs could be parsed. Check raw output below.")

    st.subheader("🧾 Raw Outputs (Unparsed)")
    for filename, raw in raw_outputs:
        st.text_area(f"🖼 Raw output from {filename}", raw, height=200)
