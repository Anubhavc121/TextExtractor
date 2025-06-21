import streamlit as st
import openai
import base64
import json
from io import BytesIO
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("🧠 MCQ Extractor (Perseus Style) from Multiple Images")
st.write("Upload multiple images with MCQs. Get results in structured JSON format like Perseus uses.")

uploaded_files = st.file_uploader("Upload image(s) with MCQs", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

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
                        "text": "Extract all multiple choice questions (MCQs) from this image in the following JSON format:\n\n[\n  {\n    \"question\": \"...\",\n    \"options\": [\"...\", \"...\", \"...\", \"...\"],\n    \"answer_index\": 1\n  },\n  ...\n]"
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

    for img in uploaded_files:
        st.image(img, caption=img.name, use_container_width=True)
        with st.spinner(f"Extracting MCQs from {img.name}..."):
            raw_json = extract_json_mcqs_from_image(img.read())
            try:
                mcqs = json.loads(raw_json)
                all_mcqs.extend(mcqs)
            except:
                st.error(f"Could not parse output from {img.name} as JSON.")
                st.text_area("Raw Output", raw_json)

    if all_mcqs:
        st.subheader("🧾 Extracted MCQs in Perseus JSON Format")
        formatted = json.dumps(all_mcqs, indent=2)
        st.text_area("Structured Output", formatted, height=400)

        st.download_button(
            label="📄 Download JSON",
            data=formatted,
            file_name="perseus_mcqs.json",
            mime="application/json"
        )

        # Optional Word document too
        doc = Document()
        doc.add_heading("MCQs Extracted in Perseus Format", 0)
        for q in all_mcqs:
            doc.add_paragraph(f"Q: {q['question']}")
            for i, opt in enumerate(q["options"]):
                prefix = "(Correct)" if i == q["answer_index"] else ""
                doc.add_paragraph(f"  - {opt} {prefix}")
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
