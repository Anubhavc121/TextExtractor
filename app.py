import streamlit as st
import openai
import base64
from io import BytesIO
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("🧠 MCQ Extractor + Practice Generator")
st.write("Upload an image of MCQs. We'll extract them and generate practice exercises using GPT-4o.")

uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

def extract_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all multiple choice questions (MCQs) from this image. For each question, list the question and all its options clearly."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content

def generate_practice_questions(mcq_text):
    prompt = f"""
You're an educational assistant. Given the following MCQs, generate:
1. Two similar MCQs per original question.
2. One fill-in-the-blank per question.

MCQs:
{mcq_text}
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    return response.choices[0].message.content

if uploaded_file:
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
    with st.spinner("Extracting MCQs..."):
        image_bytes = uploaded_file.read()
        extracted_mcqs = extract_mcqs_from_image(image_bytes)

    st.subheader("📋 Extracted MCQs")
    st.text_area("Extracted Questions", extracted_mcqs, height=300)

    # Download only extracted MCQs
    mcq_only_doc = Document()
    mcq_only_doc.add_heading("Extracted MCQs", level=1)
    for line in extracted_mcqs.split("\n"):
        mcq_only_doc.add_paragraph(line)
    mcq_only_buffer = BytesIO()
    mcq_only_doc.save(mcq_only_buffer)
    mcq_only_buffer.seek(0)
    st.download_button(
        label="📄 Download Extracted Questions Only",
        data=mcq_only_buffer,
        file_name="extracted_mcqs.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    if st.button("🧪 Generate Practice Questions"):
        with st.spinner("Generating..."):
            exercises = generate_practice_questions(extracted_mcqs)
        st.subheader("🎯 Practice Questions")
        st.text_area("Generated Practice", exercises, height=400)

        # Word document with everything
        doc = Document()
        doc.add_heading("Extracted MCQs", level=1)
        for line in extracted_mcqs.split("\n"):
            doc.add_paragraph(line)
        doc.add_heading("Generated Practice Questions", level=1)
        for line in exercises.split("\n"):
            doc.add_paragraph(line)
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        st.download_button(
            label="📄 Download All as Word Document",
            data=buffer,
            file_name="mcq_exercises.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
