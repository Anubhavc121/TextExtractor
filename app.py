import streamlit as st
import openai
import base64
import json
import requests
from io import BytesIO
from docx import Document

# API Keys
openai.api_key = st.secrets["OPENAI_API_KEY"]
api_token = st.secrets["AVETI_API_TOKEN"]
api_url = "https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/74995/questions"

st.title("🧠 MCQ Extractor (Perseus Style) from Multiple Images")
st.write("Upload multiple images with MCQs. Get results in structured JSON format and send them to Aveti CMS.")

uploaded_files = st.file_uploader(
    "Upload image(s) with MCQs", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Function to convert simplified MCQ format to Perseus format
def to_perseus_format(q_raw):
    question_text = q_raw["question"]
    options = q_raw["options"]
    answer_index = q_raw["answer_index"]

    def make_radio(correct_index, static=False):
        return {
            "type": "radio",
            "alignment": "default",
            "static": static,
            "graded": True,
            "options": {
                "choices": [
                    {"content": opt, "correct": (i == correct_index)}
                    for i, opt in enumerate(options)
                ],
                "randomize": True,
                "multipleSelect": False,
                "displayCount": None,
                "hasNoneOfTheAbove": False,
                "onePerLine": True,
                "deselectEnabled": False
            },
            "version": {"major": 1, "minor": 0}
        }

    perseus_payload = {
        "question": {
            "content": question_text + "\n\n[[☃ radio 1]]",
            "images": {},
            "widgets": {
                "radio 1": make_radio(answer_index, static=False)
            }
        },
        "answerArea": {
            "calculator": False,
            "chi2Table": False,
            "periodicTable": False,
            "tTable": False,
            "zTable": False
        },
        "itemDataVersion": {
            "major": 0,
            "minor": 1
        },
        "hints": [
            {
                "replace": False,
                "content": "Hint 1: Think carefully.",
                "images": {},
                "widgets": {}
            },
            {
                "replace": False,
                "content": "The correct answer is:\n\n[[☃ radio 1]]",
                "images": {},
                "widgets": {
                    "radio 1": make_radio(answer_index, static=True)
                }
            }
        ]
    }

    return perseus_payload

# Function to send question to Aveti API
def send_to_aveti(question_payload):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    response = requests.post(api_url, headers=headers, json=question_payload)
    return response

# Function to extract JSON from image
def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract **ALL** multiple choice questions (MCQs) from this image, even if they are partially visible or unclear. "
        "Do not skip any question. For each question, if an option or answer is unreadable, include a placeholder such as 'Unclear'. "
        "Respond with ONLY valid JSON in this format (one list of objects):\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "If you find fewer than 4 options, include empty strings ('') as placeholders. "
        "If you are unsure of the correct answer, set answer_index to -1."
    )
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
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
                for mcq in mcqs:
                    perseus_q = to_perseus_format(mcq)
                    res = send_to_aveti(perseus_q)
                    if res.status_code in [200, 201]:
                        st.success(f"✅ Question submitted from {img.name}")
                    else:
                        st.error(f"❌ Submission failed from {img.name}: {res.status_code}")
                        st.json(res.json())
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
