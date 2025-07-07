import streamlit as st
import openai
import base64
import json
import requests

# Load secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
AVETI_API_TOKEN = st.secrets["AVETI_API_TOKEN"]

# UI setup
st.title("🧠 MCQ Extractor (Perseus Format for Aveti)")
st.write("Upload image(s) with MCQs and send them to Aveti CMS in proper format.")

debug = st.sidebar.checkbox("🔍 Show raw and final JSON")

# Get exercise ID input
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

# Extract JSON from image
def extract_json_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract ALL multiple choice questions (MCQs) from this image, even if partially visible. "
        "Use this exact JSON format:\n\n"
        "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer_index\": 1}]\n\n"
        "If the question says 'Which of the above...', move the factual statements into the `question` field as numbered lines. "
        "The options should then be generic like '1 and 3', '1, 2 and 3', etc. "
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

# Fix and send to API
def send_mcq_to_api(mcq):
    try:
        # Patch if question implies numbered statements and options are actually statements
        if (
            len(mcq["options"]) == 3 and
            "which of the above" in mcq["question"].lower() and
            all(opt[0].islower() or opt[0].isupper() for opt in mcq["options"])
        ):
            # Inject the options as numbered statements
            statements = [f"{i+1}. {opt.strip()}" for i, opt in enumerate(mcq["options"])]
            mcq["question"] = mcq["question"].strip().rstrip(":") + ":\n\n" + "\n".join(statements) + "\n\nWhich of the above statements is/are correct?"

            # Replace options with standard multiple statement format
            mcq["options"] = [
                "1 alone",
                "1 and 3",
                "2 and 3",
                "1, 2 and 3"
            ]

            # Default to index 2 (can be improved if ground truth exists)
            mcq["answer_index"] = 2

        if len(mcq["options"]) != 4:
            st.warning("⚠️ Skipped: MCQ must have exactly 4 options.")
            return

        choices = [
            {"content": opt.strip(), "correct": (i == mcq["answer_index"])}
            for i, opt in enumerate(mcq["options"])
        ]

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

        if debug:
            st.subheader("📦 Final Payload Sent to API")
            st.json({"question_json": payload})

        # Wrap in question_json field as required
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

# Main loop
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
            st.warning("⚠️ No MCQs extracted or invalid format.")
