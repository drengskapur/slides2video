import base64
import json
import os
import tempfile
from io import BytesIO
import subprocess
from pathlib import Path
import shutil

import openai
import pycountry
from gtts import gTTS
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image
from google.cloud import texttospeech
import streamlit as st

# --- Constants ---
DEFAULT_SLIDE_DURATION = 3
DEFAULT_OUTPUT_FILENAME = "output_video.mp4"
DEFAULT_GAP_BETWEEN_SLIDES = 1  # seconds

# --- Helper Functions ---
def slide_to_image(slide, slide_index, temp_dir):
    image_path = os.path.join(temp_dir, f"slide_{slide_index}.png")
    slide.save(image_path, format="png")
    return image_path


def make_chunks(size, chunk_size):
    return [size[i : i + chunk_size] for i in range(0, len(size), chunk_size)]


def convert_pptx_to_pdf(input_pptx: Path):
    output_pdf_path: Path = Path("downloads") / f"{input_pptx.stem}.pdf"
    try:
        Path("downloads").mkdir(parents=True, exist_ok=True)
        if shutil.which("libreoffice") is None:
            raise FileNotFoundError("LibreOffice is not installed or not in the PATH. Please install LibreOffice.")

        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", str(input_pptx), "--outdir", str(output_pdf_path.parent)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_pdf_path

    except Exception as e:
        raise RuntimeError(f"Error converting {input_pptx} to PDF: {e}") from e


# --- TTS Functions ---
@st.cache_data
def synthesize_speech_gtts(text, temp_dir, slide_index, language="en"):
    tts = gTTS(text=text, lang=language)
    audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")
    tts.save(audio_path)
    return audio_path


@st.cache_data
def synthesize_speech_google(text, voice_name, language_code, speaking_rate, pitch, temp_dir, slide_index, credentials_content):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(name=voice_name, language_code=language_code)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=speaking_rate, pitch=pitch)
    client = texttospeech.TextToSpeechClient.from_service_account_json(credentials_content)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")

    with open(audio_path, "wb") as out:
        out.write(response.audio_content)
    return audio_path


@st.cache_data
def synthesize_speech_openai(text, voice_name, api_key, model="tts-1-hd"):
    openai.api_key = api_key
    response = openai.audio.speech.create(input=text, voice=voice_name, model=model)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_file.write(response.content)
    return temp_file.name


@st.cache_data
def get_google_tts_voices(credentials_content, language_code="en-US"):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
        creds_file.write(credentials_content)
        creds_file.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
        try:
            client = texttospeech.TextToSpeechClient()
            voices = client.list_voices().voices
            voice_options = [
                (f"{voice.name} ({pycountry.languages.get(alpha_2=voice.language_codes[0].split('-')[0]).name}, {texttospeech.SsmlVoiceGender(voice.ssml_gender).name})", voice.name)
                for voice in voices
                if voice.language_codes and voice.name and voice.ssml_gender and voice.language_codes[0] == language_code
            ]
            return voice_options

        except Exception as e:
            st.error(f"Error initializing Google TTS: {e}")
            return []

        finally:
            os.remove(creds_file.name)


def get_language_options(credentials_content):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
        creds_file.write(credentials_content)
        creds_file.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
        try:
            client = texttospeech.TextToSpeechClient()
            voices = client.list_voices().voices
            language_codes = sorted({voice.language_codes[0] for voice in voices})
            return language_codes

        except Exception as e:
            st.error(f"Error fetching languages: {e}")
            return []
        finally:
            os.remove(creds_file.name)


def get_language_code_from_name(language_name):
    try:
        return pycountry.languages.get(name=language_name).alpha_2 + "-" + pycountry.countries.get(name=language_name.split(" (")[0]).alpha_2
    except KeyError:
        return None


def get_language_name_from_code(language_code):
    try:
        return pycountry.languages.get(alpha_2=language_code.split("-")[0]).name
    except KeyError:
        return "Unknown Language"


# --- Video Generation Function ---
@st.cache_data
def generate_video(slides_data, slide_duration, gap_duration, output_filename, voice_name, credentials_content, tts_engine, end_slide_index=None):
    try:
        slide_duration = int(slide_duration)
        gap_duration = int(gap_duration)
    except ValueError:
        st.error("Slide duration and gap duration must be valid numbers.")
        return
    if tts_engine == "Google Cloud":
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
            creds_file.write(credentials_content)
            creds_file.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
            try:
                client = texttospeech.TextToSpeechClient.from_service_account_json(creds_file.name)
            except Exception as e:
                st.error(f"Error initializing Google TTS: {e}")
                return
            with tempfile.TemporaryDirectory() as temp_dir:
                return _create_video_from_data(client, slides_data, slide_duration, gap_duration, output_filename, voice_name, temp_dir, tts_engine, credentials_content, end_slide_index)
            os.remove(creds_file.name)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            return _create_video_from_data(None, slides_data, slide_duration, gap_duration, output_filename, voice_name, temp_dir, tts_engine, credentials_content, end_slide_index)


def _create_video_from_data(client, slides_data, slide_duration, gap_duration, output_filename, voice_name, temp_dir, tts_engine, credentials_content, end_slide_index=None):
    image_clips = []
    audio_clips = []
    slides_to_process = slides_data if end_slide_index is None else slides_data[: end_slide_index + 1]
    for i, slide_data in enumerate(slides_to_process):
        slide = slide_data["slide"]
        image_path = slide_to_image(slide, i, temp_dir)
        image_clips.append(ImageClip(image_path))
        text = slide_data.get("voiceover", "")
        audio_path = create_audio(text, voice_name, temp_dir, i, tts_engine, credentials_content)
        audio_clip = AudioFileClip(audio_path)
        audio_clips.append(audio_clip)
        actual_slide_duration = max(slide_duration, audio_clip.duration)
        image_clips[-1] = image_clips[-1].set_duration(actual_slide_duration)
        if i < len(slides_to_process) - 1:
            image_clips.append(ImageClip(image_path).set_duration(gap_duration))
    combined_audio = CompositeAudioClip(audio_clips)
    final_clips = [img.set_audio(combined_audio) for img in image_clips]
    final_video = concatenate_videoclips(final_clips)
    video_path = os.path.join(temp_dir, output_filename)
    final_video.write_videofile(video_path, fps=24)
    return video_path


# --- UI Functions ---
def display_slide_preview(slide, slide_index):
    st.write(f"**Slide {slide_index + 1}**")
    image_stream = BytesIO()
    slide.save(image_stream, format="png")
    image_stream.seek(0)
    st.image(Image.open(image_stream), width=300)
    if st.session_state["slides_data"][slide_index]["audio_path"]:
        st.audio(st.session_state["slides_data"][slide_index]["audio_path"], format="audio/mp3")
    else:
        st.warning("No voiceover generated for this slide yet.")


def display_slide_editor(slide_data, slide_index):
    slide = slide_data["slide"]
    st.write(f"**Slide {slide_index + 1}**")
    image_stream = BytesIO()
    slide.save(image_stream, format="png")
    image_stream.seek(0)
    st.image(Image.open(image_stream), width=200)
    with st.expander(f"Edit Slide {slide_index + 1} Content", expanded=False):
        for shape_index, shape in enumerate(slide.shapes):
            if shape.has_text_frame:
                current_text = shape.text_frame.text
                new_text = st.text_area(f"Edit text (currently: {current_text}):", value=current_text, key=f"text_{slide_index}_{shape_index}")
                shape.text_frame.text = new_text
            elif shape.has_table:
                st.write("Table:")
                for row_idx, row in enumerate(shape.table.rows):
                    cols = st.columns(len(row.cells))
                    for col_idx, cell in enumerate(row.cells):
                        with cols[col_idx]:
                            current_text = cell.text_frame.text
                            new_text = st.text_input(f"Cell ({row_idx}, {col_idx})", value=current_text, key=f"table_{slide_index}_{shape_index}_{row_idx}_{col_idx}")
                            cell.text_frame.text = new_text
            elif shape.shape_type == 13:
                st.write(f"Picture {shape_index + 1}")
                uploaded_image = st.file_uploader("Replace this picture:", type=["png", "jpg", "jpeg"], key=f"image_upload_{slide_index}_{shape_index}")
                if uploaded_image is not None:
                    picture_placeholder = shape.parent.placeholders[shape_index]
                    picture_placeholder.insert_picture(uploaded_image)
                st.write("Resize Picture:")
                col1, col2 = st.columns(2)
                with col1:
                    width = st.number_input("Width (inches):", value=shape.width.inches, key=f"pic_width_{slide_index}_{shape_index}")
                with col2:
                    height = st.number_input("Height (inches):", value=shape.height.inches, key=f"pic_height_{slide_index}_{shape_index}")
                shape.width = Inches(width)
                shape.height = Inches(height)

    st.write("**Voiceover:**")
    slide_data["voiceover"] = st.text_area(f"Enter/Edit voiceover for Slide {slide_index + 1}:", key=f"voiceover_{slide_index}", value=slide_data["voiceover"])
    return slide_data


def display_tts_options(slide_index, slide_data):
    with st.expander("Voiceover Settings", expanded=False):
        st.write("**Select TTS Engine:**")
        tts_engine = st.radio("", ["gTTS", "Google Cloud", "OpenAI"], key=f"tts_engine_dialog_{slide_index}", horizontal=True)
        voice_name = None
        language_code = "en-US"
        credentials_content = None
        speaking_rate = 1.0
        pitch = 0.0
        model = "tts-1-hd"
        if tts_engine == "gTTS":
            language_options = list(gtts.tts_langs().keys())
            language_code = st.selectbox("Select Language:", options=language_options, key=f"gtts_language_{slide_index}")
            st.write(f"Language: {gtts.tts_langs().get(language_code)}")
        if tts_engine == "Google Cloud":
            google_credentials = st.text_area("Paste Google Cloud Credentials JSON:", key=f"google_creds_{slide_index}")
            if google_credentials:
                try:
                    with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
                        creds_file.write(google_credentials)
                        creds_file.close()
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
                        texttospeech.TextToSpeechClient()
                        os.remove(creds_file.name)
                    st.success("Google Cloud credentials validated!")
                    language_options = get_language_options(google_credentials)
                    language_code = st.selectbox("Select Language:", options=language_options, key=f"google_language_{slide_index}")
                    language_name = get_language_name_from_code(language_code)
                    st.write(f"Language: {language_name}")
                    voice_options = get_google_tts_voices(google_credentials, language_code)
                    if voice_options:
                        selected_voice = st.selectbox("Select a voice:", [voice[0] for voice in voice_options], key=f"google_voice_{slide_index}")
                        voice_name = dict(voice_options)[selected_voice]
                        credentials_content = google_credentials
                        speaking_rate = st.slider("Speaking Rate:", min_value=0.25, max_value=4.0, value=1.0, step=0.25, key=f"speaking_rate_{slide_index}")
                        pitch = st.slider("Pitch:", min_value=-20.0, max_value=20.0, value=0.0, step=1.0, key=f"pitch_{slide_index}")
                    else:
                        st.warning("No voices found. Try different credentials or language.")
                except Exception as e:
                    st.warning("Invalid Google Cloud credentials. Please check your input.")
                    st.write(e)
        elif tts_engine == "OpenAI":
            openai_api_key = st.text_input("Enter your OpenAI API Key:", key=f"openai_key_{slide_index}")
            if openai_api_key:
                try:
                    openai.api_key = openai_api_key
                    openai.Engine.list()
                    st.success("OpenAI API key validated!")
                    voice_name = st.selectbox(
                        "Select a voice:",
                        [
                            "alloy",
                            "echo",
                            "fable",
                            "onyx",
                            "nova",
                            "shimmer",
                        ],
                        key=f"openai_voice_{slide_index}",
                    )
                    credentials_content = openai_api_key
                    model = st.selectbox("Select Model:", ["tts-1", "tts-1-hd"], key=f"openai_model_{slide_index}")
                except openai.error.AuthenticationError:
                    st.warning("Invalid OpenAI API key.")
                except Exception as e:
                    st.warning("An error occurred while validating your API key.")
                    st.write(e)
        if st.button(f"Generate Voiceover {slide_index + 1}"):
            with st.spinner("Generating voiceover..."):
                try:
                    audio_path = create_audio(slide_data["voiceover"], voice_name, "temp", slide_index, tts_engine, credentials_content, language_code, speaking_rate, pitch, model)
                    slide_data["audio_path"] = audio_path
                    st.success("Voiceover generated!")
                    st.audio(audio_path, format="audio/mp3")
                except Exception as e:
                    st.error(f"Error generating voiceover: {e}")


@st.cache_data
def create_audio(text, voice_name, temp_dir, slide_index, tts_engine, credentials_content=None, language_code="en-US", speaking_rate=1.0, pitch=0.0, model="tts-1-hd"):
    if text:
        if tts_engine == "gTTS":
            audio_path = synthesize_speech_gtts(text, temp_dir, slide_index, language_code)
        elif tts_engine == "Google Cloud":
            audio_path = synthesize_speech_google(text, voice_name, language_code, speaking_rate, pitch, temp_dir, slide_index, credentials_content)
        elif tts_engine == "OpenAI":
            audio_path = synthesize_speech_openai(text, voice_name, credentials_content, model)
        else:
            st.error("Invalid TTS engine selected.")
            return None
    else:
        audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")
        AudioFileClip(make_chunks(1, 0.1)[0]).write_audiofile(audio_path)
    return audio_path


# --- Main Streamlit App ---
def main():
    st.set_page_config(
        page_title="PowerPoint to Video Converter",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("PowerPoint to Video Converter")

    # --- Project Management (Save/Load) ---
    project_name = st.text_input("Project Name:", value="MyProject")
    st.session_state["project_name"] = project_name
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Project"):
            save_project(project_name)
    with col2:
        if st.button("Load Project"):
            load_project(project_name)

    # --- PowerPoint Upload ---
    uploaded_pptx = st.file_uploader("Upload your PowerPoint presentation", type=["pptx"])
    if uploaded_pptx:
        try:
            prs = Presentation(uploaded_pptx)

            # --- Initialize Slide Data ---
            if "slides_data" not in st.session_state:
                st.session_state["slides_data"] = []
                for i, slide in enumerate(prs.slides):
                    st.session_state["slides_data"].append(
                        {
                            "slide": slide,
                            "voiceover": "",
                            "audio_path": None,
                        }
                    )

            # --- Sidebar: Global Settings ---
            st.sidebar.header("Global Settings")
            st.session_state["slide_duration"] = st.sidebar.number_input(
                "Minimum Slide Duration (seconds)",
                min_value=1,
                value=DEFAULT_SLIDE_DURATION,
            )
            st.session_state["gap_duration"] = st.sidebar.number_input(
                "Gap Between Slides (seconds)",
                min_value=0,
                value=DEFAULT_GAP_BETWEEN_SLIDES,
            )
            st.session_state["output_filename"] = st.sidebar.text_input("Output Video Filename", value=DEFAULT_OUTPUT_FILENAME)

            # --- Main Content Area ---
            st.header("Edit Slides")

            # --- Tabs for Edit/Preview ---
            tab1, tab2 = st.tabs(["Edit Slides", "Preview"])
            with tab1:

                # --- Auto Preview Toggle ---
                auto_preview = st.checkbox("Enable Auto-Preview", value=False)

                # Display Slide Editors
                for i, slide_data in enumerate(st.session_state["slides_data"]):
                    st.session_state["slides_data"][i] = display_slide_editor(slide_data, i)
                    display_tts_options(i, slide_data)

                    # Auto-Preview
                    if auto_preview and "audio_path" in slide_data and slide_data["audio_path"]:
                        with st.spinner("Rendering slide preview..."):
                            render_and_display_video(
                                prs,
                                st.session_state["slide_duration"],
                                st.session_state["gap_duration"],
                                st.session_state["output_filename"],
                                st.session_state.get("selected_voice_name"),
                                st.session_state.get("credentials_content"),
                                i,
                            )

                # --- Add Slide Button ---
                if st.button("Add Slide"):
                    prs.slides.add_slide(prs.slide_layouts[6])  # Add a blank slide
                    st.session_state["slides_data"].append(
                        {
                            "slide": prs.slides[-1],
                            "voiceover": "",
                            "audio_path": "",
                        }
                    )

                    st.experimental_rerun()

                # --- Delete Slide Button ---
                if len(st.session_state["slides_data"]) > 1:
                    if st.button("Delete Last Slide"):
                        del st.session_state["slides_data"][-1]
                        del prs.slides[-1]
                        st.experimental_rerun()
            with tab2:

                # --- Display Slide Previews ---
                for i, slide_data in enumerate(st.session_state["slides_data"]):
                    display_slide_preview(slide_data["slide"], i)

            # --- Video Generation ---
            st.header("Create Full Video")
            if st.button("Generate Video"):
                with st.spinner("Creating video..."):
                    video_path = generate_video(
                        st.session_state["slides_data"],
                        st.session_state["slide_duration"],
                        st.session_state["gap_duration"],
                        st.session_state["output_filename"],
                        st.session_state.get("selected_voice_name"),
                        st.session_state.get("credentials_content"),
                        st.session_state.get("tts_engine", "gTTS"),
                    )

                    if video_path:
                        st.success("Video created successfully!")
                        st.balloons()
                        st.video(video_path)

            # --- Download and Conversion ---
            st.header("Download and Convert")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Download PPTX"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as temp_pptx:
                        prs.save(temp_pptx.name)
                        st.download_button(
                            "Download",
                            data=open(temp_pptx.name, "rb").read(),
                            file_name=f"{uploaded_pptx.name}",
                            mime="application/pptx",
                        )

            with col2:
                if st.button("Convert to PDF"):
                    with st.spinner("Converting to PDF..."):
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as temp_pptx:
                                prs.save(temp_pptx.name)
                                pdf_path = convert_pptx_to_pdf(Path(temp_pptx.name))
                            if pdf_path and Path(pdf_path).exists():
                                st.success("PDF created successfully!")
                                with open(pdf_path, "rb") as pdf_file:
                                    st.download_button(
                                        label="Download PDF",
                                        data=pdf_file,
                                        file_name=f"{Path(pdf_path).name}",
                                        mime="application/pdf",
                                    )
                            else:
                                st.error("PDF conversion failed. Please check the console for errors.")
                        except Exception as e:
                            st.error(f"An error occurred during PDF conversion: {e}")
        except Exception as e:
            st.error(f"An error occurred: {e}")


# --- Project Save/Load Logic ---
def save_project(project_name):
    project_data = {
        "slides_data": [
            {
                "slide_id": slide["slide"].slide_id,
                "voiceover": slide["voiceover"],
                "audio_path": slide["audio_path"],
            }
            for slide in st.session_state["slides_data"]
        ],
        "slide_duration": st.session_state["slide_duration"],
        "gap_duration": st.session_state["gap_duration"],
        "output_filename": st.session_state["output_filename"],
        "tts_engine": st.session_state["tts_engine"],
        "selected_voice_name": st.session_state.get("selected_voice_name", None),
        "credentials_content": st.session_state.get("credentials_content", None),
        "audio_files": {},
    }

    # Save audio files as base64 encoded strings
    for i, slide_data in enumerate(st.session_state["slides_data"]):
        audio_path = slide_data.get("audio_path")
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, "rb") as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode("utf-8")
                project_data["audio_files"][f"audio_{i}"] = audio_base64
    try:
        with open(f"{project_name}.json", "w") as f:
            json.dump(project_data, f)
        st.success(f"Project '{project_name}' saved successfully!")
    except Exception as e:
        st.error(f"Error saving project: {e}")


def load_project(project_name):
    try:
        with open(f"{project_name}.json", "r") as f:
            project_data = json.load(f)

        # --- Load presentation from uploaded file again ---
        uploaded_pptx = st.file_uploader(
            "Upload the PowerPoint file associated with this project:",
            type=["pptx"],
            key="project_upload",
        )
        if uploaded_pptx:
            prs = Presentation(uploaded_pptx)
            st.session_state["slides_data"] = []

            # Match slides based on slide_id
            for i, saved_slide_data in enumerate(project_data["slides_data"]):
                slide_id = saved_slide_data["slide_id"]
                matching_slide = next((s for s in prs.slides if s.slide_id == slide_id), None)
                if matching_slide:
                    audio_path = ""
                    if f"audio_{i}" in project_data["audio_files"]:
                        audio_base64 = project_data["audio_files"][f"audio_{i}"]
                        audio_data = base64.b64decode(audio_base64)

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                            temp_audio.write(audio_data)
                            audio_path = temp_audio.name

                    st.session_state["slides_data"].append(
                        {
                            "slide": matching_slide,
                            "voiceover": saved_slide_data["voiceover"],
                            "audio_path": audio_path,
                        }
                    )

                else:
                    st.warning(f"Slide with ID {slide_id} not found in the uploaded file.")

            st.session_state["slide_duration"] = project_data["slide_duration"]
            st.session_state["gap_duration"] = project_data.get("gap_duration", 1)
            st.session_state["output_filename"] = project_data["output_filename"]
            st.session_state["tts_engine"] = project_data["tts_engine"]
            st.session_state["selected_voice_name"] = project_data.get("selected_voice_name", None)
            st.session_state["credentials_content"] = project_data.get("credentials_content", None)
            st.success(f"Project '{project_name}' loaded successfully!")
            st.experimental_rerun()

        else:
            st.info("Please upload the associated PowerPoint file.")

    except FileNotFoundError:
        st.error(f"Project '{project_name}' not found.")
    except Exception as e:
        st.error(f"Error loading project: {e}")


# --- Render and Display Video ---
def render_and_display_video(prs, slide_duration, gap_duration, output_filename, tts_engine, voice_name, credentials_content, end_slide_index):
    video_path = generate_video(
        st.session_state["slides_data"],
        slide_duration,
        gap_duration,
        output_filename,
        voice_name,
        credentials_content,
        tts_engine,
        end_slide_index,
    )

    if video_path:
        st.video(video_path)


# --- Run the App ---
if __name__ == "__main__":
    main()
