import streamlit as st
import openai
import base64
import json
from io import BytesIO
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("📘 MCQ Extractor & Generator (Perseus Format)")
st.write("Upload image(s) containing multiple choice questions, or add your own. Get Perseus-formatted output (one JSON per question).")

uploaded_files = st.file_uploader("Upload MCQ images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# --- MANUAL MCQ ENTRY IN SIDEBAR ---
st.sidebar.title("Add MCQ Manually")
if "manual_mcqs" not in st.session_state:
    st.session_state.manual_mcqs = []

with st.sidebar.form("manual_mcq_form"):
    manual_q = st.text_input("Question text")
    n_opt = st.number_input("Number of options", 2, 8, value=4)
    manual_opts = [st.text_input(f"Option {i+1}") for i in range(n_opt)]
    manual_ans = st.number_input("Correct option number (1-based)", 1, n_opt, value=1)
    manual_hint1 = st.text_input("Hint 1 (optional)", "")
    manual_hint2 = st.text_input("Hint 2 (optional)", "")
    add_btn = st.form_submit_button("➕ Add MCQ")
    if add_btn and manual_q and all(manual_opts):
        st.session_state.manual_mcqs.append({
            "question": manual_q,
            "options": manual_opts,
            "answer_index": manual_ans - 1,
            "hint1": manual_hint1,
            "hint2": manual_hint2
        })
        st.sidebar.success("MCQ added!")

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
                            "Respond with ONLY valid JSON in this format:\n\n"
                            "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]"
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

def to_perseus_format(mcq):
    options = [{"content": opt, "correct": i == mcq["answer_index"]} for i, opt in enumerate(mcq["options"])]
    hints = []
    hint1 = mcq.get("hint1", "").strip()
    hint2 = mcq.get("hint2", "").strip()
    if hint1:
        hints.append({"replace": False, "content": hint1, "images": {}, "widgets": {}})
    if hint2:
        hints.append({"replace": False, "content": hint2, "images": {}, "widgets": {}})
    if not hints:
        # default hints
        hints = [
            {
                "replace": False,
                "content": "Hint 1: Consider the social system of Hinduism at the time.",
                "images": {},
                "widgets": {}
            },
            {
                "replace": False,
                "content": "Hint 2: Buddhism did not follow a rigid caste structure.",
                "images": {},
                "widgets": {}
            }
        ]
    # Always add answer reveal hint
    hints.append(
        {
            "replace": False,
            "content": "The correct answer is:\n\n[[☃ radio 1]]",
            "images": {},
            "widgets": {
                "radio 1": {
                    "type": "radio",
                    "alignment": "default",
                    "static": True,
                    "graded": True,
                    "options": {
                        "choices": options,
                        "randomize": False,
                        "multipleSelect": False,
                        "displayCount": None,
                        "hasNoneOfTheAbove": False,
                        "onePerLine": True,
                        "deselectEnabled": False
                    },
                    "version": {
                        "major": 1,
                        "minor": 0
                    }
                }
            }
        }
    )

    return {
        "question": {
            "content": f"{mcq['question']}\n\n[[☃ radio 1]]",
            "images": {},
            "widgets": {
                "radio 1": {
                    "type": "radio",
                    "alignment": "default",
                    "static": False,
                    "graded": True,
                    "options": {
                        "choices": options,
                        "randomize": True,
                        "multipleSelect": False,
                        "displayCount": None,
                        "hasNoneOfTheAbove": False,
                        "onePerLine": True,
                        "deselectEnabled": False
                    },
                    "version": {
                        "major": 1,
                        "minor": 0
                    }
                }
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
        "hints": hints
    }

all_mcqs = []

if uploaded_files:
    for img in uploaded_files:
        st.image(img, caption=img.name, use_container_width=True)
        with st.spinner(f"Extracting MCQs from {img.name}..."):
            raw_json = extract_json_mcqs_from_image(img.read())

            cleaned = raw_json.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").strip()
            if cleaned.endswith("```"):
                cleaned = cleaned.removesuffix("```").strip()

            try:
                mcqs = json.loads(cleaned)
                all_mcqs.extend(mcqs)
            except json.JSONDecodeError:
                st.warning(f"⚠️ Could not parse output from {img.name}")

# Combine image MCQs and manual MCQs
all_combined_mcqs = all_mcqs.copy()
for m in st.session_state.get("manual_mcqs", []):
    all_combined_mcqs.append({
        "question": m["question"],
        "options": m["options"],
        "answer_index": m["answer_index"],
        "hint1": m["hint1"],
        "hint2": m["hint2"]
    })

if all_combined_mcqs:
    st.subheader("✅ Perseus-Formatted MCQs (Individual JSON Objects)")

    perseus_output = [to_perseus_format(q) for q in all_combined_mcqs]

    # Show each as a standalone JSON object (for copy-paste)
    for idx, obj in enumerate(perseus_output, 1):
        st.markdown(f"**MCQ {idx} Perseus JSON:**")
        st.code(json.dumps(obj, indent=2, ensure_ascii=False), language="json")

    # Download all as single text file, with each JSON object separated by two newlines
    perseus_json_text = "\n\n".join(json.dumps(obj, indent=2, ensure_ascii=False) for obj in perseus_output)
    st.download_button(
        "📘 Download All MCQs (each as separate JSON object)",
        data=perseus_json_text,
        file_name="perseus_mcqs.txt",
        mime="text/plain"
    )

    # Optionally, download as docx (for teacher review)
    doc = Document()
    doc.add_heading("MCQs", 0)
    for q in all_combined_mcqs:
        doc.add_paragraph(f"Q: {q['question']}")
        for i, opt in enumerate(q['options']):
            prefix = "✅ " if i == q["answer_index"] else "- "
            doc.add_paragraph(f"{prefix}{opt}")
        doc.add_paragraph()
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    st.download_button(
        "📝 Download Word Doc",
        data=buf,
        file_name="mcqs.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
