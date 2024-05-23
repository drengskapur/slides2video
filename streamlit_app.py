import base64
import copy
import json
import os
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from abc import ABC, abstractmethod

import openai
import pdf2image
import pycountry
import streamlit as st
from google.cloud import texttospeech
from gtts import gTTS
from moviepy.editor import (AudioFileClip, CompositeAudioClip, ImageClip,
                           concatenate_videoclips)
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

# --- Constants ---
DEFAULT_OUTPUT_FILENAME = "output_video.mp4"
DEFAULT_GAP_BETWEEN_SLIDES = 1  # seconds

# --- Abstract Base Class for TTS Engines ---
class TTS(ABC):
    @abstractmethod
    def synthesize_speech(self, text, temp_dir, slide_index, **kwargs):
        pass

    @abstractmethod
    def display_settings(self, slide_index):
        """Displays UI settings specific to the TTS engine."""
        pass

    @staticmethod
    def get_language_code_from_name(language_name):
        try:
            return pycountry.languages.get(name=language_name).alpha_2 + "-" + pycountry.countries.get(name=language_name.split(" (")[0]).alpha_2
        except KeyError:
            return None

    @staticmethod
    def get_language_name_from_code(language_code):
        try:
            return pycountry.languages.get(alpha_2=language_code.split("-")[0]).name
        except KeyError:
            return "Unknown Language"

# --- TTS Engine Implementations ---
class GTTS_Engine(TTS):
    def synthesize_speech(self, text, temp_dir, slide_index, language="en"):
        tts = gTTS(text=text, lang=language)
        audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")
        tts.save(audio_path)
        return audio_path

    def display_settings(self, slide_index):
        language_options = list(gTTS.tts_langs().keys())
        language_code = st.selectbox("Select Language:", options=language_options, key=f"gtts_language_{slide_index}")
        st.write(f"Language: {gTTS.tts_langs().get(language_code)}")
        return {"language": language_code}  # Return settings as a dictionary


class GoogleCloud_Engine(TTS):
    def __init__(self):
        self.credentials_content = None

    def _set_credentials(self, credentials_content):
        """Sets the Google Cloud credentials."""
        self.credentials_content = credentials_content
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
            creds_file.write(self.credentials_content)
            creds_file.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
            try:
                texttospeech.TextToSpeechClient()
                os.remove(creds_file.name)
            except Exception as e:
                st.warning("Invalid Google Cloud credentials. Please check your input.")
                st.write(e)
                return False  # Indicate failure
            return True  # Indicate success

    def synthesize_speech(self, text, temp_dir, slide_index, voice_name, language_code, speaking_rate, pitch):
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(name=voice_name, language_code=language_code)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=speaking_rate, pitch=pitch
        )
        client = texttospeech.TextToSpeechClient.from_service_account_json(self.credentials_content)
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")

        with open(audio_path, "wb") as out:
            out.write(response.audio_content)
        return audio_path

    def _get_language_options(self):
        """Gets available language codes from Google Cloud TTS."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
            creds_file.write(self.credentials_content)
            creds_file.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
            try:
                client = texttospeech.TextToSpeechClient()
                voices = client.list_voices().voices
                language_codes = sorted({voice.language_codes[0] for voice in voices})
                os.remove(creds_file.name)
                return language_codes
            except Exception as e:
                st.error(f"Error fetching languages: {e}")
                return []

    @st.cache_data(show_spinner=False)  # Cache but don't show spinner
    def _get_google_tts_voices(self, language_code="en-US"):
        """Gets available voices for a specific language code."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as creds_file:
            creds_file.write(self.credentials_content)
            creds_file.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name
            try:
                client = texttospeech.TextToSpeechClient()
                voices = client.list_voices().voices
                voice_options = [
                    (
                        f"{voice.name} ({self.get_language_name_from_code(voice.language_codes[0])}, {texttospeech.SsmlVoiceGender(voice.ssml_gender).name})",
                        voice.name,
                    )
                    for voice in voices
                    if voice.language_codes
                    and voice.name
                    and voice.ssml_gender
                    and voice.language_codes[0] == language_code
                ]
                os.remove(creds_file.name)
                return voice_options
            except Exception as e:
                st.error(f"Error initializing Google TTS: {e}")
                return []

    def display_settings(self, slide_index):
        def update_google_credentials():
            if self._set_credentials(st.session_state["google_credentials"]):
                st.session_state["google_credentials_content"] = st.session_state["google_credentials"]
                st.success("Google Cloud credentials validated!")

        google_credentials = st.text_area(
            "Paste Google Cloud Credentials JSON:", key=f"google_credentials", on_change=update_google_credentials
        )

        # Retrieve credentials from session state if they exist
        if "google_credentials_content" in st.session_state:
            self.credentials_content = st.session_state["google_credentials_content"]
            language_options = self._get_language_options()
            language_code = st.selectbox(
                "Select Language:", options=language_options, key=f"google_language_{slide_index}"
            )
            language_name = self.get_language_name_from_code(language_code)
            st.write(f"Language: {language_name}")

            voice_options = self._get_google_tts_voices(language_code)
            if voice_options:
                selected_voice = st.selectbox(
                    "Select a voice:", [voice[0] for voice in voice_options], key=f"google_voice_{slide_index}"
                )
                voice_name = dict(voice_options)[selected_voice]
                st.session_state["selected_voice_name"] = voice_name
                speaking_rate = st.slider(
                    "Speaking Rate:", min_value=0.25, max_value=4.0, value=1.0, step=0.25, key=f"speaking_rate_{slide_index}"
                )
                pitch = st.slider(
                    "Pitch:", min_value=-20.0, max_value=20.0, value=0.0, step=1.0, key=f"pitch_{slide_index}"
                )

                # Update settings dictionary
                return {"voice_name": voice_name, "language_code": language_code, "speaking_rate": speaking_rate, "pitch": pitch}
            else:
                st.warning("No voices found. Try different credentials or language.")
        return {}


class OpenAI_Engine(TTS):
    def synthesize_speech(self, text, temp_dir, slide_index, voice_name, api_key, model="tts-1-hd"):
        openai.api_key = api_key  # Use API key from settings
        response = openai.audio.speech.create(input=text, voice=voice_name, model=model)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(response.content)
        return temp_file.name

    def display_settings(self, slide_index):
        def update_openai_api_key():
            api_key = st.session_state["openai_api_key_input"]
            if api_key:
                try:
                    openai.api_key = api_key
                    openai.Engine.list()
                    st.session_state["openai_api_key"] = api_key
                    st.success("OpenAI API key validated!")

                except openai.error.AuthenticationError:
                    st.warning("Invalid OpenAI API key.")
                except Exception as e:
                    st.warning("An error occurred while validating your API key.")
                    st.write(e)

        openai_api_key = st.text_input(
            "Enter your OpenAI API Key:", key=f"openai_api_key_input", on_change=update_openai_api_key
        )

        # Only display voice options if the API key is valid
        if "openai_api_key" in st.session_state:
            voice_name = st.selectbox(
                "Select a voice:",
                ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                key=f"openai_voice_{slide_index}",
            )
            st.session_state["selected_voice_name"] = voice_name
            model = st.selectbox("Select Model:", ["tts-1", "tts-1-hd"], key=f"openai_model_{slide_index}")
            return {"voice_name": voice_name, "api_key": openai_api_key, "model": model}
        return {}


# --- UI Components ---
class Project:
    def __init__(self, project_name="MyProject"):
        self.project_name = project_name
        self.slides_data = []  # Initialize as a list of dictionaries
        self.gap_duration = DEFAULT_GAP_BETWEEN_SLIDES
        self.output_filename = DEFAULT_OUTPUT_FILENAME

    def load_from_file(self, project_data):
        """Loads project data from a dictionary."""
        self.slides_data = project_data.get("slides_data", [])
        self.gap_duration = project_data.get("gap_duration", DEFAULT_GAP_BETWEEN_SLIDES)
        self.output_filename = project_data.get("output_filename", DEFAULT_OUTPUT_FILENAME)

    def save_to_file(self):
        """Saves project data to a JSON file."""
        project_data = {
            "slides_data": self.slides_data,
            "gap_duration": self.gap_duration,
            "output_filename": self.output_filename,
            "audio_files": {},  # Store base64 encoded audio here
        }

        # Save audio files as base64 encoded strings
        for i, slide_data in enumerate(self.slides_data):
            if slide_data.get("audio_path") and os.path.exists(slide_data["audio_path"]):
                with open(slide_data["audio_path"], "rb") as audio_file:
                    audio_base64 = base64.b64encode(audio_file.read()).decode("utf-8")
                    project_data["audio_files"][f"audio_{i}"] = audio_base64

        try:
            with open(f"{self.project_name}.json", "w") as f:
                json.dump(project_data, f)
            st.success(f"Project '{self.project_name}' saved successfully!")
        except Exception as e:
            st.error(f"Error saving project: {e}")


class Slide:
    def __init__(self, pptx_slide=None):
        self.pptx_slide = pptx_slide or self._create_new_slide()

    def _create_new_slide(self, layout_index=6):  # Default to Blank layout
        """Creates a new slide with the specified layout index."""
        prs = Presentation()
        slide_layout = prs.slide_layouts[layout_index]
        return prs.slides.add_slide(slide_layout)


class Gallery:
    def __init__(self, project):
        self.project = project

    def display(self):
        """Displays the slide gallery and handles new slide creation."""
        self.display_slides()

        # --- Add Slide Section ---
        st.header("Add New Slide")
        layout_names = [
            "Title Slide",
            "Title and Content",
            "Section Header",
            "Two Content",
            "Comparison",
            "Title Only",
            "Blank",
            "Content with Caption",
            "Picture with Caption",
        ]
        selected_layout_name = st.selectbox("Select Slide Layout:", layout_names)
        selected_layout_index = layout_names.index(selected_layout_name)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Add Slide to End"):
                self.add_new_slide(selected_layout_index, len(self.project.slides_data))
                st.experimental_rerun()
        with col2:
            insert_index = st.number_input(
                "Insert Slide Before Index (Starts at 1):",
                min_value=1,
                max_value=len(self.project.slides_data) + 1,
                step=1,
            )
            if st.button("Insert Slide"):
                self.add_new_slide(selected_layout_index, insert_index - 1)  # Adjust for zero-based indexing
                st.experimental_rerun()

    def display_slides(self):
        """Displays each slide with preview, voiceover input, and audio controls."""
        for i, slide_data in enumerate(self.project.slides_data):
            self.display_slide(i, slide_data)

    def display_slide(self, slide_index, slide_data):
        """Displays a single slide with its controls."""
        st.subheader(f"Slide {slide_index + 1}")

        col1, col2, col3 = st.columns([2, 3, 1])  # Adjust column ratios as needed

        with col1:
            # Slide Preview
            st.image(self.get_slide_preview(slide_data, slide_index), use_column_width=True)

        with col2:
            # Voiceover Textbox
            slide_data["voiceover"] = st.text_area("Enter voiceover:", value=slide_data.get("voiceover", ""), key=f"voiceover_{slide_index}")

            # Play/Stop Audio Buttons
            if st.button("Play Audio", key=f"play_audio_{slide_index}"):
                if slide_data.get("audio_path"):
                    st.audio(slide_data["audio_path"], format="audio/mp3")
                else:
                    st.warning("No audio generated yet!")

        with col3:
            # Voiceover Configuration and Generation
            if st.button(f"Configure Voiceover", key=f"configure_voiceover_{slide_index}"):
                self.configure_voiceover(slide_index)
            # Delete Slide Button
            if st.button("Delete Slide", key=f"delete_slide_{slide_index}"):
                del self.project.slides_data[slide_index]
                st.experimental_rerun()

        st.markdown("---")  # Add a separator between slides

    def configure_voiceover(self, slide_index):
        """Handles voiceover configuration and generation."""
        slide_data = self.project.slides_data[slide_index]
        with st.expander("Voiceover Settings", expanded=True):  # Use expander to hide settings by default

            # --- Access Selected Engine ---
            selected_tts_engine = None
            if st.session_state["tts_engine"] == "gTTS":
                selected_tts_engine = GTTS_Engine()
            elif st.session_state["tts_engine"] == "Google Cloud":
                selected_tts_engine = GoogleCloud_Engine()
            elif st.session_state["tts_engine"] == "OpenAI":
                selected_tts_engine = OpenAI_Engine()

            # --- Display Engine Settings ---
            if selected_tts_engine:
                settings = selected_tts_engine.display_settings(slide_index)

                if st.button(f"Generate Voiceover", key=f"generate_voiceover_{slide_index}"):
                    with st.spinner("Generating voiceover..."):
                        try:
                            if st.session_state["tts_engine"] == "Google Cloud":
                                settings["credentials_content"] = st.session_state.get("google_credentials_content")
                            elif st.session_state["tts_engine"] == "OpenAI":
                                settings["api_key"] = st.session_state.get("openai_api_key")  # Pass API key

                            audio_path = selected_tts_engine.synthesize_speech(
                                text=slide_data["voiceover"], temp_dir="temp", slide_index=slide_index, **settings
                            )

                            slide_data["audio_path"] = audio_path
                            st.success("Voiceover generated!")
                            st.audio(audio_path, format="audio/mp3")
                        except Exception as e:
                            st.error(f"Error generating voiceover: {e}")

    def get_slide_preview(self, slide_data, slide_index):
        """Returns an image preview of the slide."""
        slide = Slide()
        slide.pptx_slide = slide_data.get("slide")
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = self.slide_to_image(slide, slide_index, temp_dir)
            return Image.open(image_path)

    def add_new_slide(self, layout_index, index):
        """Adds a new slide to the project data at the specified index."""
        new_slide = Slide()
        new_slide._create_new_slide(layout_index=layout_index)
        new_slide_data = {
            "slide": new_slide.pptx_slide,
            "voiceover": "",
            "audio_path": None,
            "tts_settings": {},
        }
        self.project.slides_data.insert(index, new_slide_data)

    def slide_to_image(self, slide, slide_index, temp_dir):
        """Saves a slide as an image."""
        prs = Presentation()
        new_slide_layout = prs.slide_layouts.get_by_name(slide.pptx_slide.slide_layout.name)
        new_slide = prs.slides.add_slide(new_slide_layout)

        # Copy shapes from the original slide to the new slide
        for shape in slide.pptx_slide.shapes:
            el = shape.element
            newel = copy.deepcopy(el)
            new_slide.shapes._spTree.insert_element_before(newel, 'p:extLst')

        temp_pptx_path = os.path.join(temp_dir, f"temp_slide_{slide_index}.pptx")
        prs.save(temp_pptx_path)
        temp_pdf_path = os.path.join(temp_dir, f"temp_slide_{slide_index}.pdf")
        self.convert_pptx_to_pdf(Path(temp_pptx_path), Path(temp_pdf_path))
        temp_png_path = os.path.join(temp_dir, f"temp_slide_{slide_index}.png")
        self.pdf_to_png(temp_pdf_path, temp_png_path)
        return temp_png_path

    def make_chunks(self, size, chunk_size):
        """Splits a sequence into chunks."""
        return [size[i : i + chunk_size] for i in range(0, len(size), chunk_size)]

    def convert_pdf_to_png(self, pdf_path, png_path, dpi=300):
        """Converts a PDF to a PNG image."""
        images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
        resized_image = self.resize_image_to_even_dimensions(images[0])
        resized_image.save(png_path, "PNG")

    def convert_pptx_to_pdf(self, input_pptx: Path):
        """Converts a PPTX file to PDF using LibreOffice."""
        output_pdf_path: Path = Path("downloads") / f"{input_pptx.stem}.pdf"  # Construct output path here
        try:
            Path("downloads").mkdir(parents=True, exist_ok=True)
            if shutil.which("libreoffice") is None:
                raise FileNotFoundError("LibreOffice is not installed or not in the PATH. Please install LibreOffice.")

            cmd = [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                str(input_pptx),
                "--outdir",
                str(output_pdf_path.parent),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_pdf_path

        except Exception as e:
            raise RuntimeError(f"Error converting {input_pptx} to PDF: {e}") from e

    def resize_image_to_even_dimensions(self, image):
        width, height = image.size
        even_width = width if width % 2 == 0 else width + 1
        even_height = height if height % 2 == 0 else height + 1
        return image.resize((even_width, even_height))


# --- Cached function to create audio ---
@st.cache_data
def create_audio(text, voice_name, temp_dir, slide_index, tts_engine, credentials_content=None, api_key=None, language="en", speaking_rate=1.0, pitch=0.0, model="tts-1-hd", **kwargs):
    if text:
        if tts_engine == "gTTS":
            audio_path = GTTS_Engine().synthesize_speech(text, temp_dir, slide_index, language=language)
        elif tts_engine == "Google Cloud":
            audio_path = GoogleCloud_Engine().synthesize_speech(text, temp_dir, slide_index, voice_name, language, speaking_rate, pitch, credentials_content)
        elif tts_engine == "OpenAI":
            audio_path = OpenAI_Engine().synthesize_speech(text, temp_dir, slide_index, voice_name, api_key, model)
        else:
            st.error("Invalid TTS engine selected.")
            return None
    else:
        audio_path = os.path.join(temp_dir, f"temp_audio_{slide_index}.mp3")
        try:
            AudioFileClip(Gallery.make_chunks(size=[1], chunk_size=0.1)[0]).write_audiofile(audio_path)
        except Exception as e:
            st.error(f"Error creating silent audio: {e}")
            return None
    return audio_path


# --- Cached Video Generation Function ---
@st.cache_data
def generate_video(slides_data, gap_duration, output_filename, voice_name, credentials_content, tts_engine, end_slide_index=None):
    try:
        gap_duration = int(gap_duration)
    except ValueError:
        st.error("Gap duration must be a valid number.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        return _create_video_from_data(
            slides_data, gap_duration, output_filename, voice_name, temp_dir, tts_engine, credentials_content, end_slide_index
        )


def _create_video_from_data(slides_data, gap_duration, output_filename, voice_name, temp_dir, tts_engine, credentials_content, end_slide_index=None):
    image_clips = []
    audio_clips = []
    slides_to_process = slides_data if end_slide_index is None else slides_data[: end_slide_index + 1]
    for i, slide_data in enumerate(slides_to_process):
        image_path = Gallery.slide_to_image(slide_data["slide"], i, temp_dir)
        image_clips.append(ImageClip(image_path))

        text = slide_data.get("voiceover", "")
        audio_path = create_audio(text, voice_name, temp_dir, i, tts_engine, credentials_content, **slide_data.get("tts_settings", {}))

        if audio_path is None:
            return None  # Handle potential error in create_audio
        audio_clip = AudioFileClip(audio_path)
        audio_clips.append(audio_clip)
        image_clips[-1] = image_clips[-1].set_duration(audio_clip.duration)
        if i < len(slides_to_process) - 1:
            image_clips.append(ImageClip(image_path).set_duration(gap_duration))

    combined_audio = CompositeAudioClip(audio_clips)
    final_clips = [img.set_audio(combined_audio) for img in image_clips]
    final_video = concatenate_videoclips(final_clips)

    video_path = os.path.join(temp_dir, output_filename)
    final_video.write_videofile(video_path, fps=24)
    return video_path

# --- Main Streamlit App ---
def main():
    # --- Page Configuration ---
    st.set_page_config(page_title="Slides2Video", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

    # --- Project Management ---
    if "project" not in st.session_state:
        st.session_state["project"] = Project()
    project = st.session_state["project"]

    # --- Project Settings ---
    project.project_name = st.text_input("Project Name:", value=project.project_name)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Project"):
            project.save_to_file()
    with col2:
        if st.button("Load Project"):
            try:
                with open(f"{project.project_name}.json", "r") as f:
                    project_data = json.load(f)
                    # Load audio files from base64 if they exist
                    if "audio_files" in project_data:
                        for i, audio_base64 in project_data["audio_files"].items():
                            audio_data = base64.b64decode(audio_base64)
                            with open(f"temp/{i}.mp3", "wb") as f:
                                f.write(audio_data)
                            project_data["slides_data"][int(i[6:])]["audio_path"] = f"temp/{i}.mp3"

                project.load_from_file(project_data)
                st.success(f"Project '{project.project_name}' loaded successfully!")
                st.experimental_rerun()  # Rerun to reflect loaded data
            except FileNotFoundError:
                st.error(f"Project '{project.project_name}' not found.")

    # --- TTS Engine Selection ---
    if "tts_engine" not in st.session_state:
        st.session_state["tts_engine"] = "gTTS"

    def update_tts_engine():
        st.session_state["tts_engine"] = st.session_state["tts_engine_selection"]

    tts_engine_name = st.radio(
        "Select TTS Engine:", ["gTTS", "Google Cloud", "OpenAI"], key="tts_engine_selection", horizontal=True, on_change=update_tts_engine
    )

    # --- PowerPoint Upload OR New Presentation ---
    uploaded_pptx = st.file_uploader("Upload your PowerPoint presentation (optional)", type=["pptx"])
    create_new = st.checkbox("Create a new presentation", value=True if not uploaded_pptx else False)

    # --- Presentation Logic ---
    if create_new and not uploaded_pptx:
        prs = Presentation()
        prs.slides.add_slide(prs.slide_layouts[6])  # Default layout
        project.slides_data = [
            {"slide": slide, "voiceover": "", "audio_path": None, "tts_settings": {}} for slide in prs.slides
        ]
    elif uploaded_pptx:
        prs = Presentation(uploaded_pptx)
        project.slides_data = [
            {"slide": slide, "voiceover": "", "audio_path": None, "tts_settings": {}} for slide in prs.slides
        ]

    # --- Global Settings ---
    st.header("Global Settings")
    project.gap_duration = st.number_input("Gap Between Slides (seconds)", min_value=0, value=project.gap_duration)
    project.output_filename = st.text_input("Output Video Filename", value=project.output_filename)

    # --- Slide Gallery ---
    gallery = Gallery(project)
    gallery.display()

    # --- Video Generation ---
    st.header("Create Full Video")
    if st.button("Generate Video"):
        voice_name = st.session_state.get("selected_voice_name")
        credentials_content = st.session_state.get("google_credentials_content")  # For Google Cloud
        api_key = st.session_state.get("openai_api_key")  # For OpenAI
        tts_engine = st.session_state.get("tts_engine", "gTTS")

        with st.spinner("Creating video..."):
            video_path = generate_video(
                project.slides_data,
                project.gap_duration,
                project.output_filename,
                voice_name,
                credentials_content,
                tts_engine,
            )
            if video_path:
                st.success("Video created successfully!")
                st.balloons()
                st.video(video_path)

    # --- Download ---
    st.header("Download")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Download PPTX"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as temp_pptx:
                prs = Presentation()
                for slide_data in project.slides_data:
                    prs.slides.add_slide(slide_data["slide"])
                prs.save(temp_pptx.name)
                st.download_button("Download PPTX", data=open(temp_pptx.name, "rb").read(), file_name=f"{project.project_name}.pptx", mime="application/pptx")
    with col2:
       if st.button("Download PDF"):
            with st.spinner("Generating PDF..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as temp_pptx:
                        prs = Presentation()
                        for slide_data in project.slides_data:
                            prs.slides.add_slide(slide_data["slide"])
                        prs.save(temp_pptx.name)
                        pdf_path = gallery.convert_pptx_to_pdf(Path(temp_pptx.name))
                    if pdf_path and Path(pdf_path).exists():
                        st.success("PDF generated successfully!")
                        with open(pdf_path, "rb") as pdf_file:
                            st.download_button(
                                label="Download PDF",
                                data=pdf_file,
                                file_name=f"{Path(pdf_path).name}",
                                mime="application/pdf",
                            )
                    else:
                        st.error("PDF generation failed. Please check the console for errors.")
                except Exception as e:
                    st.error(f"An error occurred during PDF generation: {e}")


# --- Run the App ---
if __name__ == "__main__":
    main()
