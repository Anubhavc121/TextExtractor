import streamlit as st
import openai
import base64
import json
import requests
import pandas as pd
from io import BytesIO
from typing import Dict

# Load secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
AVETI_API_TOKEN = st.secrets["AVETI_API_TOKEN"]

# UI
st.title("📦 Bulk MCQ Uploader to Aveti")
st.write("Upload a `.csv` with exercise_id and image_filename, and all images.")

csv_file = st.file_uploader("📄 Upload CSV file (exercise_id, image_filename)", type=["csv"])
image_files = st.file_uploader("🖼️ Upload all image files listed in the CSV", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

debug = st.sidebar.checkbox("🔍 Show raw OpenAI JSON")

# Cache images by filename
def map_uploaded_images(files):
    image_map = {}
    for file in files:
        image_map[file.name] = file.read()
    return image_map

# Extract MCQs from image using GPT-4o
def extract_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract ALL multiple choice questions (MCQs) from this image, even if partially visible. "
        "Return valid JSON only, in this format:\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "If the question includes statements, use numbered lines inside the question using newlines. Do not add any explanation or markdown."
    )
    response = openai.chat.completions.create(
        model="gpt-4o",
        temperature=0,
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

    raw_output = response.choices[0].message.content
    if debug:
        st.subheader("🧾 Raw OpenAI Output")
        st.text_area("Raw JSON", raw_output, height=300)

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        st.error(f"❌ JSON parse error: {e}")
        return []

# Smart formatting for question content
def format_question_content(text):
    lines = text.strip().split("\n")
    if any(line.strip().startswith(str(i)) for i, line in enumerate(lines, start=1)):
        return "<br>".join(lines) + "<br><br>[[☃ radio 1]]"
    else:
        return text.strip() + "\n\n[[☃ radio 1]]"

# Submit MCQ to Aveti
def submit_mcq(mcq, exercise_id):
    api_url = f"https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/{exercise_id}/questions"

    question_content = format_question_content(mcq["question"])
    choices = [
        {"content": opt.strip(), "correct": (i == mcq["answer_index"])}
        for i, opt in enumerate(mcq["options"])
    ]

    payload = {
        "question": {
            "content": question_content,
            "images": {},
            "widgets": {
                "radio 1": {
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
                    "version": {"major": 1, "minor": 0}
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
        "itemDataVersion": {"major": 0, "minor": 1},
        "hints": [
            {"replace": False, "content": "Hint 1: Think logically and carefully.", "images": {}, "widgets": {}},
            {"replace": False, "content": "Hint 2: Eliminate clearly wrong answers first.", "images": {}, "widgets": {}},
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
                            "choices": choices,
                            "randomize": False,
                            "multipleSelect": False,
                            "displayCount": None,
                            "hasNoneOfTheAbove": False,
                            "onePerLine": True,
                            "deselectEnabled": False
                        },
                        "version": {"major": 1, "minor": 0}
                    }
                }
            }
        ]
    }

    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {AVETI_API_TOKEN}",
            "Content-Type": "application/json"
        },
        data=json.dumps({"question_json": payload})
    )
    return response.status_code == 200, response

# Bulk processor
if csv_file and image_files:
    df = pd.read_csv(csv_file)
    image_map = map_uploaded_images(image_files)
    results = []

    for _, row in df.iterrows():
        exercise_id = str(row["exercise_id"]).strip()
        image_name = row["image_filename"].strip()

        if image_name not in image_map:
            results.append((exercise_id, image_name, "❌ Image not uploaded"))
            continue

        image_bytes = image_map[image_name]
        mcqs = extract_mcqs_from_image(image_bytes)

        if not isinstance(mcqs, list):
            results.append((exercise_id, image_name, "❌ Extraction failed"))
            continue

        success_all = True
        for mcq in mcqs:
            if len(mcq.get("options", [])) != 4:
                results.append((exercise_id, image_name, "⚠️ Skipped: Invalid MCQ format"))
                success_all = False
                continue
            success, response = submit_mcq(mcq, exercise_id)
            if not success:
                success_all = False
                results.append((exercise_id, image_name, f"❌ API error: {response.status_code}"))
        if success_all:
            results.append((exercise_id, image_name, "✅ All MCQs uploaded"))

    # Show final result
    st.subheader("📊 Upload Summary")
    st.table(pd.DataFrame(results, columns=["Exercise ID", "Image", "Status"]))
