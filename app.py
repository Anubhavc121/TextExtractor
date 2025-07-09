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
st.title("🧠 MCQ Extractor (CMS-Ready Format from CSV)")
st.write("Upload a CSV with Exercise IDs and filenames + the image files themselves.")

debug = st.sidebar.checkbox("🔍 Show raw and final JSON")

# CSV Upload
csv_file = st.file_uploader("📄 Upload CSV (exercise_id, image_filename)", type=["csv"])
uploaded_images = st.file_uploader("📷 Upload all image files", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if not csv_file or not uploaded_images:
    st.stop()

df = pd.read_csv(csv_file)
image_map = {img.name: img for img in uploaded_images}

# Extract MCQs from image
def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract ALL multiple choice questions (MCQs) from this image, even if partially visible. "
        "Format in JSON as:\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "If the question includes statements (like 'Consider the following...'), number them inside the `question` using newlines. "
        "Do not include explanations, markdown, or ```json."
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

# Send to Aveti API
def send_mcq_to_api(mcq, exercise_id):
    api_url = f"https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/{exercise_id}/questions"

    try:
        if len(mcq["options"]) != 4:
            st.warning("⚠️ Skipped: MCQ must have exactly 4 options.")
            return

        question_text = mcq["question"].strip()

        has_numbered_statements = any(
            line.strip().startswith(str(i)) for i, line in enumerate(question_text.split("\n"), start=1)
        )

        if has_numbered_statements:
            formatted_question = question_text.replace("\n", "<br>") + "<br><br>[[☃ radio 1]]"
        else:
            formatted_question = question_text + "\n\n[[☃ radio 1]]"

        choices = [
            {"content": opt.strip(), "correct": (i == mcq["answer_index"])}
            for i, opt in enumerate(mcq["options"])
        ]

        payload = {
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
                    "content": "Hint 1: Think logically and carefully.",
                    "images": {},
                    "widgets": {}
                },
                {
                    "replace": False,
                    "content": "Hint 2: Eliminate clearly wrong answers first.",
                    "images": {},
                    "widgets": {}
                },
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

        if debug:
            st.subheader("📦 Final Payload Sent to API")
            st.json({"question_json": payload})

        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {AVETI_API_TOKEN}",
                "Content-Type": "application/json"
            },
            data=json.dumps({"question_json": payload})
        )

        if response.status_code == 200:
            st.success(f"✅ Uploaded: {mcq['question'][:60]}...")
        else:
            st.error(f"❌ Upload failed: {response.status_code}")
            try:
                st.json(response.json())
            except:
                st.text(response.text)

    except Exception as e:
        st.error(f"⚠️ Error while sending: {e}")

# Main loop through CSV
for _, row in df.iterrows():
    exercise_id = str(row["exercise_id"]).strip()
    image_filename = row["image_filename"].strip()

    if not exercise_id.isdigit():
        st.warning(f"❌ Skipped invalid exercise ID: {exercise_id}")
        continue

    if image_filename not in image_map:
        st.warning(f"⚠️ Missing image file: {image_filename}")
        continue

    st.subheader(f"📷 Processing: {image_filename} → Exercise ID {exercise_id}")
    image_bytes = image_map[image_filename].read()
    mcqs = extract_json_mcqs_from_image(image_bytes)

    if isinstance(mcqs, list):
        for idx, mcq in enumerate(mcqs):
            st.markdown(f"### Q{idx + 1}")
            st.write(mcq["question"])
            for i, opt in enumerate(mcq["options"]):
                prefix = "✅" if i == mcq["answer_index"] else "🔘"
                st.write(f"{prefix} {opt}")
            send_mcq_to_api(mcq, exercise_id)
    else:
        st.warning("⚠️ No MCQs extracted or format invalid.")
