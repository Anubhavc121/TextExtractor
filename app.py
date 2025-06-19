import streamlit as st
import openai
import base64

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("📘 MCQ Extractor from Image")
st.write("Upload an image containing multiple choice questions (MCQs) and extract the questions with options.")

uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

def extract_mcqs_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": "Extract all multiple choice questions (MCQs) from this image. For each question, list the question and all its options clearly." },
                    { "type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" } }
                ]
            }
        ],
        max_tokens=2000
    )

    return response.choices[0].message.content

if uploaded_file:
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)
    with st.spinner("Extracting MCQs..."):
        result = extract_mcqs_from_image(uploaded_file.read())
    st.subheader("📋 Extracted MCQs:")
    st.text_area("Output", result, height=400)