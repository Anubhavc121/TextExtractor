import streamlit as st
import openai
import base64
import json
import requests

# Load API keys from secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
AVETI_API_TOKEN = st.secrets["AVETI_API_TOKEN"]

# UI Setup
st.title("🧠 MCQ Extractor (Perseus Format for Aveti)")
st.write("Upload image(s) containing MCQs and send them to Aveti in the correct CMS format.")

debug = st.sidebar.checkbox("🔍 Show raw and final JSON")

# Exercise ID input
exercise_id = st.text_input("Enter Exercise ID:", value="74995")
if not exercise_id.strip().isdigit():
    st.error("❌ Please enter a valid numeric Exercise ID.")
    st.stop()

# Construct API URL
api_url = f"https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/{exercise_id}/questions"

# Upload image(s)
uploaded_files = st.file_uploader(
    "📷 Upload MCQ image(s)", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Step 1: Extract JSON from image
def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract ALL multiple choice questions (MCQs) from this image, even if partially visible. "
        "Use this exact JSON format:\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "Return plain JSON only. No markdown, no explanation, no ```json block."
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
        st.text_area("Raw JSON from OpenAI", raw_output, height=300)

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        st.error(f"❌ Failed to parse JSON: {e}")
        return []

# Step 2: Send one MCQ to Aveti API
def send_mcq_to_api(mcq):
    try:
        # Ensure 4 options
        if len(mcq["options"]) != 4:
            st.warning("⚠️ Skipped: MCQ must have exactly 4 options.")
            return

        # Format choices
        choices = [
            {"content": opt.strip(), "correct": (i == mcq["answer_index"])}
            for i, opt in enumerate(mcq["options"])
        ]

        # Prepare Perseus-style payload
        payload = {
            "question": {
                "content": mcq["question"].strip() + "\n\n[[☃ radio 1]]",
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

        # Show JSON if debug is on
        if debug:
            st.subheader("📦 Final JSON Sent to API")
            st.json({"question_json": payload})

        # Send to Aveti API
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
            st.error(f"❌ Upload failed: Status {response.status_code}")
            try:
                st.json(response.json())
            except:
                st.text(response.text)

    except Exception as e:
        st.error(f"⚠️ Error while sending: {e}")

# Step 3: Main image processing loop
if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"📷 Processing: {file.name}")
        image_bytes = file.read()
        mcqs = extract_json_mcqs_from_image(image_bytes)

        if isinstance(mcqs, list):
            for idx, mcq in enumerate(mcqs):
                st.markdown(f"### Q{idx + 1}")
                st.write(mcq["question"])
                for i, opt in enumerate(mcq["options"]):
                    prefix = "✅" if i == mcq["answer_index"] else "🔘"
                    st.write(f"{prefix} {opt}")
                send_mcq_to_api(mcq)
        else:
            st.warning("⚠️ No MCQs extracted or format invalid.")
