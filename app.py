import streamlit as st
import openai
import base64
import json
import requests

# Setup API keys from secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
AVETI_API_TOKEN = st.secrets["AVETI_API_TOKEN"]

# API configuration
api_url = "https://production.mobile.avetilearning.com/service/cms/api/v1/exercise/74995/questions"
headers = {
    "Authorization": f"Bearer {AVETI_API_TOKEN}",
    "Content-Type": "application/json"
}

st.title("🧠 MCQ Extractor (Perseus Style) from Multiple Images")
st.write("Upload multiple images with MCQs. Get results in structured JSON format like Perseus uses.")
debug = st.sidebar.checkbox("🔍 Show raw JSON from OpenAI")

uploaded_files = st.file_uploader(
    "Upload image(s) with MCQs", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Function to extract JSON from image
def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract **ALL** multiple choice questions (MCQs) from this image, even if they are partially visible or unclear. "
        "Do not skip any question. For each question, if an option or answer is unreadable, include a placeholder such as 'Unclear'. "
        "Respond with ONLY valid JSON in this format (one list of objects):\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "Do NOT include markdown, explanation, or any extra text. No ```json blocks. Only plain JSON."
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
        st.text_area("🧾 Raw OpenAI Output", raw_output, height=300)

    try:
        parsed_json = json.loads(raw_output)
        return parsed_json
    except json.JSONDecodeError as e:
        st.error(f"❌ JSON decoding failed: {e}")
        st.text_area("⚠️ Raw output", raw_output)
        return []

# Function to send each MCQ to Aveti API
def send_mcq_to_api(mcq):
    try:
        choices = [
            {"content": opt, "correct": (i == mcq["answer_index"])}
            for i, opt in enumerate(mcq["options"])
        ]

        payload = {
            "question": {
                "content": mcq["question"] + "\n\n[[☃ radio 1]]",  # <-- FIXED
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
                    "content": "Hint 1: Think carefully.",
                    "images": {},
                    "widgets": {}
                },
                {
                    "replace": False,
                    "content": "The correct answer is:\n\n[[☃ radio 1]]",  # <-- FIXED
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

        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            st.success(f"✅ Uploaded: {mcq['question'][:60]}...")
        else:
            st.error(f"❌ Failed. Status code: {response.status_code}")
            st.json(response.json())
    except Exception as e:
        st.error(f"⚠️ Error sending question: {e}")

# Main logic
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
            st.error("⚠️ No MCQs extracted from this image.")
