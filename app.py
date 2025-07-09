import streamlit as st
import openai
import base64
import json
import requests
import pandas as pd

# Load secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
AVETI_API_TOKEN = st.secrets["AVETI_API_TOKEN"]

# UI setup
st.title("📦 Bulk MCQ Uploader with Preview")
st.write("Upload a `.csv` with `exercise_id,image_filename` and matching image files.")

csv_file = st.file_uploader("📄 Upload CSV", type=["csv"])
image_files = st.file_uploader("🖼️ Upload images listed in the CSV", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
debug = st.sidebar.checkbox("🔍 Show raw OpenAI JSON")

# Map filenames to bytes
def map_uploaded_images(files):
    return {file.name: file.read() for file in files}

# Extract MCQs from image
def extract_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract ALL multiple choice questions (MCQs) from this image. "
        "Return a plain JSON list like:\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]"
    )
    response = openai.chat.completions.create(
        model="gpt-4o", temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }],
        max_tokens=2000
    )
    raw = response.choices[0].message.content
    if debug:
        st.subheader("🧾 Raw Output")
        st.text_area("Raw JSON", raw, height=300)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []

# Format question (uses <br> if numbered)
def format_question(text):
    lines = text.strip().split("\n")
    if any(line.strip().startswith(str(i)) for i, line in enumerate(lines, start=1)):
        return "<br>".join(lines) + "<br><br>[[☃ radio 1]]"
    return text.strip() + "\n\n[[☃ radio 1]]"

# Build full payload
def build_payload(mcq, formatted_question):
    choices = [{"content": opt.strip(), "correct": (i == mcq["answer_index"])} for i, opt in enumerate(mcq["options"])]
    return {
        "question": {
            "content": formatted_question,
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
            "calculator": False, "chi2Table": False,
            "periodicTable": False, "tTable": False, "zTable": False
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

# Submit to Aveti
def submit_to_api(payload, exercise_id):
    url = f"https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/{exercise_id}/questions"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {AVETI_API_TOKEN}", "Content-Type": "application/json"},
        data=json.dumps({"question_json": payload})
    )
    if response.status_code == 200:
        st.success(f"✅ Uploaded to {exercise_id}")
    else:
        st.error(f"❌ Failed for {exercise_id}: {response.status_code}")
    return response.status_code == 200, response.status_code

# === Main Logic ===
if csv_file and image_files:
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    st.write("📋 Columns Detected:", df.columns.tolist())

    image_map = map_uploaded_images(image_files)
    preview_data = []

    for _, row in df.iterrows():
        ex_id = str(row.get("exercise_id", "")).strip()
        img_name = row.get("image_filename", "").strip()

        if not ex_id or not img_name:
            preview_data.append({"exercise_id": ex_id, "image": img_name, "status": "❌ Missing fields", "mcqs": []})
            continue
        if img_name not in image_map:
            preview_data.append({"exercise_id": ex_id, "image": img_name, "status": "❌ Image not uploaded", "mcqs": []})
            continue

        image_bytes = image_map[img_name]
        mcqs = extract_mcqs_from_image(image_bytes)
        st.write(f"📘 {len(mcqs)} question(s) extracted from {img_name}")

        if not isinstance(mcqs, list) or not mcqs:
            preview_data.append({"exercise_id": ex_id, "image": img_name, "status": "❌ Extraction failed", "mcqs": []})
            continue

        preview_data.append({"exercise_id": ex_id, "image": img_name, "status": "🕵️ Ready", "mcqs": mcqs})

    st.subheader("👁️ Preview Extracted MCQs")
    for entry in preview_data:
        st.markdown(f"---\n#### 📘 Exercise: {entry['exercise_id']} | 🖼️ Image: {entry['image']}")
        st.write(f"**Status:** {entry['status']}")
        for idx, mcq in enumerate(entry["mcqs"]):
            st.markdown(f"**Q{idx+1}:** {mcq['question']}")
            for i, opt in enumerate(mcq["options"]):
                prefix = "✅" if i == mcq["answer_index"] else "🔘"
                st.markdown(f"- {prefix} {opt}")

    if st.button("🚀 Upload All to CMS"):
        st.info("Uploading... Please wait.")
        results = []
        for entry in preview_data:
            if not entry["mcqs"]:
                results.append((entry["exercise_id"], entry["image"], entry["status"]))
                continue
            for mcq in entry["mcqs"]:
                if len(mcq.get("options", [])) != 4:
                    results.append((entry["exercise_id"], entry["image"], "⚠️ Invalid MCQ format"))
                    continue
                payload = build_payload(mcq, format_question(mcq["question"]))
                success, code = submit_to_api(payload, entry["exercise_id"])
                status = "✅ Uploaded" if success else f"❌ Failed ({code})"
                results.append((entry["exercise_id"], entry["image"], status))

        st.subheader("📊 Upload Summary")
        st.table(pd.DataFrame(results, columns=["Exercise ID", "Image", "Status"]))
