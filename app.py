import streamlit as st
import openai
import base64
import json
from io import BytesIO
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("📘 MCQ Extractor & Generator")
st.write("Upload image(s) containing multiple choice questions. Get Perseus-formatted output.")

uploaded_files = st.file_uploader("Upload MCQ images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

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
    choices = [
        {
            "content": opt,
            "correct": i == mcq["answer_index"]
        } for i, opt in enumerate(mcq["options"])
    ]

    radio_widget_dynamic = {
        "type": "radio",
        "alignment": "default",
        "static": False,
        "graded": True,
        "options": {
            "choices": choices,
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

    radio_widget_static = {
        "type": "radio",
        "alignment": "default",
        "static": True,
        "graded": True,
        "options": {
            "choices": choices,
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

    return {
        "question": {
            "content": mcq["question"] + "\n\n[[☃ radio 1]]",
            "images": {},
            "widgets": {
                "radio 1": radio_widget_dynamic
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
                "content": "Hint 1: Consider the social system of Hinduism at the time.",
                "images": {},
                "widgets": {}
            },
            {
                "replace": False,
                "content": "Hint 2: Buddhism did not follow a rigid caste structure.",
                "images": {},
                "widgets": {}
            },
            {
                "replace": False,
                "content": "The correct answer is:\n\n[[☃ radio 1]]",
                "images": {},
                "widgets": {
                    "radio 1": radio_widget_static
                }
            }
        ]
    }

if uploaded_files:
    all_mcqs = []

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

    if all_mcqs:
        st.subheader("✅ Perseus-Formatted MCQs")

        perseus_output = [to_perseus_format(q) for q in all_mcqs]
        perseus_json = json.dumps(perseus_output, indent=2)
        st.text_area("📋 Perseus JSON", perseus_json, height=300)

        st.download_button("📘 Download Perseus JSON", data=perseus_json, file_name="perseus_mcqs.json", mime="application/json")

        doc = Document()
        doc.add_heading("MCQs", 0)
        for q in all_mcqs:
            doc.add_paragraph(f"Q: {q['question']}")
            for i, opt in enumerate(q['options']):
                prefix = "✅ " if i == q["answer_index"] else "- "
                doc.add_paragraph(f"{prefix}{opt}")
            doc.add_paragraph()
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        st.download_button("📝 Download Word Doc", data=buf, file_name="mcqs.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        if st.button("✨ Generate Similar Questions"):
            st.subheader("🧠 Similar Questions")
            for q in all_mcqs:
                prompt = (
                    f"Given this MCQ:\nQ: {q['question']}\nOptions: {q['options']}\n\n"
                    "Generate 1-2 new MCQs that assess the same concept. Format:\n"
                    "[{\"question\": \"...\", \"options\": [...], \"answer_index\": ...}]"
                )
                try:
                    res = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=300
                    )
                    output = res.choices[0].message.content.strip()
                    if output.startswith("```json"):
                        output = output.removeprefix("```json").strip().removesuffix("```").strip()
                    new_mcqs = json.loads(output)
                    for nq in new_mcqs:
                        st.markdown(f"**Q: {nq['question']}**")
                        for i, opt in enumerate(nq["options"]):
                            prefix = "✅ " if i == nq["answer_index"] else "- "
                            st.markdown(f"{prefix}{opt}")
                        st.markdown("---")
                except:
                    st.warning(f"❗ Could not generate variation for: {q['question']}")
