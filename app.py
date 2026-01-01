import streamlit as st
import json
import boto3
import os
from pydub import AudioSegment
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import base64
from PIL import Image
from botocore.config import Config
import io
import re
import random
import time
from PyPDF2 import PdfReader
import docx
import requests
from bs4 import BeautifulSoup

# Initialize the Bedrock client
client = boto3.client("bedrock-runtime")

# Initialize Polly client
polly_client = boto3.client('polly', region_name='us-east-1')

# modelId="anthropic.claude-3-sonnet-20240229-v1:0"
# modelId="anthropic.claude-3-5-sonnet-20240620-v1:0"
# modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
modelId="us.amazon.nova-lite-v1:0"
# modelId="us.meta.llama3-2-90b-instruct-v1:0"
# modelId="meta.llama3-2-3b-instruct-v1:0"

model_ids = ['us.amazon.nova-lite-v1:0', 'us.amazon.nova-lite-v1:0', 'us.meta.llama3-2-90b-instruct-v1:0', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0', 'anthropic.claude-3-sonnet-20240229-v1:0']

# Define ImageError exception
class ImageError(Exception):
    """Custom exception for image generation errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def fetch_and_display_url_content(url):
    try:
        # Fetch the content of the URL
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Initialize formatted_text
        formatted_text = ""

        # Extract the title
        title = None
        if 'wikipedia.org' in url:
            title = soup.find(id='firstHeading').get_text()
        else:
            # Try different methods to get the title
            title_candidates = [
                soup.find('meta', property='og:title'),
                soup.find('meta', {'name': 'twitter:title'}),
                soup.find('h1', {'class': lambda x: x and any(word in str(x).lower() for word in ['title', 'headline', 'post-title'])}),
                soup.find('title'),
            ]

            for candidate in title_candidates:
                if candidate:
                    if candidate.name == 'meta':
                        title = candidate.get('content')
                    else:
                        title = candidate.get_text()
                    if title:
                        title = title.strip()
                        break

        # Add title to formatted_text
        if title:
            formatted_text += f"{title.upper()}\n{'='*len(title)}\n\n"

        # Special handling for Wikipedia
        if 'wikipedia.org' in url:
            # Remove unwanted sections
            unwanted_sections = [
                'Navigation menu',
                'References',
                'External links',
                'Contents',
                'See also',
                'Notes',
                'Citations',
                'Bibliography'
            ]
            
            # Remove reference numbers [1], [2], etc.
            for ref in soup.find_all('sup', {'class': 'reference'}):
                ref.decompose()

            # Remove reference links
            for ref in soup.find_all('a', {'class': 'reference'}):
                ref.decompose()

            # Remove edit links
            for edit in soup.find_all('span', {'class': 'mw-editsection'}):
                edit.decompose()

            # Get the main content div
            content = soup.find('div', {'id': 'mw-content-text'})
            
            if content:
                # Process each section
                for section in content.find_all(['h2', 'h3', 'p', 'ul', 'ol']):
                    # Skip unwanted sections
                    section_text = section.get_text().strip()
                    if any(unwanted in section_text for unwanted in unwanted_sections):
                        continue

                    if section.name in ['h2', 'h3']:
                        formatted_text += f"\n{section_text.upper()}\n{'='*len(section_text)}\n\n"
                    elif section.name == 'p' and len(section_text) > 20:
                        formatted_text += f"{section_text}\n\n"
                    elif section.name in ['ul', 'ol']:
                        for li in section.find_all('li'):
                            li_text = li.get_text().strip()
                            if li_text:
                                formatted_text += f"  • {li_text}\n"
                        formatted_text += "\n"

        else:
            # Handle non-Wikipedia sites
            # Remove unwanted elements
            unwanted_elements = [
                'header', 'footer', 'nav', 'aside', 'script', 'style', 
                'noscript', 'iframe', 'ad', 'advertisement', 'comments',
                'sidebar', 'menu', 'social-links', 'related-posts'
            ]
            
            for element in soup.find_all(class_=lambda x: x and any(word in str(x).lower() for word in unwanted_elements)):
                element.decompose()
            
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            # Try to find the main content container
            main_content = None
            possible_content_elements = [
                soup.find('article'),
                soup.find('main'),
                soup.find(class_=lambda x: x and 'content' in str(x).lower()),
                soup.find(id=lambda x: x and 'content' in str(x).lower()),
                soup.find('div', class_=lambda x: x and ('post' in str(x).lower() or 'article' in str(x).lower()))
            ]

            for element in possible_content_elements:
                if element:
                    main_content = element
                    break

            if not main_content:
                main_content = soup.find('body')

            if main_content:
                # Process headings
                for heading in main_content.find_all(['h1', 'h2', 'h3']):
                    text = heading.get_text().strip()
                    if text and text != title:  # Skip if heading is same as title
                        formatted_text += f"\n{text.upper()}\n{'='*len(text)}\n\n"

                # Process paragraphs and lists
                for element in main_content.find_all(['p', 'ul', 'ol']):
                    if element.name == 'p':
                        text = element.get_text().strip()
                        if text and len(text) > 20:  # Filter out very short paragraphs
                            formatted_text += f"{text}\n\n"
                    elif element.name in ['ul', 'ol']:
                        for li in element.find_all('li'):
                            text = li.get_text().strip()
                            if text:
                                formatted_text += f"  • {text}\n"
                        formatted_text += "\n"

        # Clean up the text
        formatted_text = re.sub(r'$$[\d\s,]+$$', '', formatted_text)  # Remove reference numbers
        formatted_text = re.sub(r'\n\s*\n', '\n\n', formatted_text)   # Fix spacing
        formatted_text = re.sub(r'\s+', ' ', formatted_text)          # Replace multiple spaces
        formatted_text = '\n'.join(line.strip() for line in formatted_text.splitlines() if line.strip())

        # Display content in an expander with text area
        with st.expander("Webpage Content", expanded=True):
            st.text_area(
                label="",
                value=formatted_text,
                height=300
            )

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching the URL: {e}")
    except Exception as e:
        st.error(f"Error parsing the webpage content: {e}")

def text_to_image_invoke_model(model_id, body):
    """
    Generate an image using Amazon Nova Canvas model on demand.
    Args:
        model_id (str): The model ID to use.
        body (str): The request body to use.
    Returns:
        image_bytes (bytes): The image generated by the model.
    """

    # logger.info("Generating image with Amazon Nova Canvas model", model_id)

    bedrock = boto3.client(
        service_name='bedrock-runtime',
        config=Config(read_timeout=300)
    )

    accept = "application/json"
    content_type = "application/json"

    response = bedrock.invoke_model(
        body=body, modelId=model_id, accept=accept, contentType=content_type
    )
    response_body = json.loads(response.get("body").read())

    base64_image = response_body.get("images")[0]
    base64_bytes = base64_image.encode('ascii')
    image_bytes = base64.b64decode(base64_bytes)

    finish_reason = response_body.get("error")

    if finish_reason is not None:
        raise ImageError(f"Image generation error. Error is {finish_reason}")

    return image_bytes

def generate_image(prompt, i, max_retries=5, backoff_factor=2):
    print("Inside...")
    model_id = 'amazon.nova-canvas-v1:0'
    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt},
        "imageGenerationConfig": {"numberOfImages": 1, "height": 1024, "width": 1024, "cfgScale": 8.0, "seed": random.randint(0, 2147483646)}
    })

    retries = 0
    while retries < max_retries:
        try:
            # Try to generate the image
            image_bytes = text_to_image_invoke_model(model_id=model_id, body=body)
            image = Image.open(io.BytesIO(image_bytes))
            image.save(f"generated_image_{i}.png")

            if i == 0:
                st.image(image, caption=" ", use_column_width=True)
            
            response = "Image has been generated."
            return response  # Exit early if successful

        except Exception as e:
            # Check if the exception is related to throttling (Rate-limited or 429 errors)
            if "throttling" in str(e).lower() or "429" in str(e):
                retries += 1
                wait_time = backoff_factor ** retries + random.uniform(0, 1)  # Exponential backoff with jitter
                print(f"Rate-limited. Retrying in {wait_time:.2f} seconds (attempt {retries}/{max_retries})...")
                time.sleep(wait_time)  # Wait before retrying
            else:
                # If the error is not throttling-related, raise the exception
                print(f"Error occurred while generating image: {str(e)}")
                response = "Error occurred while generating image."
                body = json.dumps({
                    "taskType": "TEXT_IMAGE",
                    "textToImageParams": {"text": "Generate an image for a podcast without any human"},
                    "imageGenerationConfig": {"numberOfImages": 1, "height": 1024, "width": 1024, "cfgScale": 8.0, "seed": 0}
                })
                image_bytes = text_to_image_invoke_model(model_id=model_id, body=body)
                image = Image.open(io.BytesIO(image_bytes))
                st.image(image, caption=" ", use_column_width=True)
                break  # Exit if a non-throttling error occurs

def synthesize_speech(text, voice_id, output_filename):
    """Synthesizes speech for a given text and saves the result to a file"""
    try:
        response = polly_client.synthesize_speech(
            Engine='generative',
            LanguageCode='en-US',
            Text=text,
            TextType='text',  # Text input (no SSML tags)
            OutputFormat='mp3',
            VoiceId=voice_id
        )

        # Write the audio stream to a file
        with open(output_filename, 'wb') as audio_file:
            audio_file.write(response['AudioStream'].read())
            print(f"Audio for {voice_id} saved to {output_filename}")

    except Exception as e:
        print(f"An error occurred while synthesizing speech: {e}")

def clean_script(script_lines):
    """Cleans the input script lines to remove unwanted characters or formatting issues."""
    cleaned_lines = []
    for line in script_lines:
        # Remove unwanted characters (like leading/trailing spaces or unexpected symbols)
        line = line.strip()
        
        # Remove '**' or other symbols from speaker names, if present
        line = line.replace("**", "").strip()  # Remove '**' symbols if they exist
        
        if line:
            cleaned_lines.append(line)
    return cleaned_lines

def process_script(script_lines):
    """Process the script line by line and synthesize speech based on the speaker"""
    # Mapping speakers to their voices
    speaker_map = {
        "Speaker 1": "Ruth",  # Voice for Speaker 1
        "Speaker 2": "Stephen",  # Voice for Speaker 2
        "Host 1": "Ruth",  # Voice for Host 1
        "Host 2": "Stephen",  # Voice for Host 2
    }
    
    audio_files = []  # List to keep track of the generated audio files
    
    # Clean the script lines to remove extra spaces, special characters, etc.
    cleaned_script = clean_script(script_lines)

    for i, line in enumerate(cleaned_script):
        # Ensure the line is in the correct format: "Speaker X: Text"
        if ":" not in line:
            print(f"Skipping invalid line: {line}")
            continue
        
        # Split the line by speaker and text
        speaker, text = line.split(":", 1)
        
        # Clean speaker name and text
        speaker = speaker.strip()  # Remove extra spaces around the speaker label
        text = text.strip()  # Remove extra spaces around the text
        
        # Check if the speaker is in the map (supports both "Speaker X" and "Host X")
        if speaker in speaker_map:
            voice = speaker_map[speaker]
        else:
            # If speaker isn't found, log and default to 'Ruth'
            print(f"Warning: Speaker '{speaker}' not found. Defaulting to 'Ruth'.")
            voice = "Ruth"  # Default to 'Ruth' if speaker is unknown

        # Output filename based on speaker and line number
        output_filename = f"output_{speaker.replace(' ', '_')}_{i+1}.mp3"
        
        # Synthesize speech and save to file
        synthesize_speech(text, voice, output_filename)
        
        # Add the generated file to the list for merging later
        audio_files.append(output_filename)
    
    return audio_files

def get_title(script):
    # Regular expression to find the title
    title_pattern = r"Title:\s*(.*)"

    # Search for the title using regex
    match = re.search(title_pattern, script)

    if match:
        # Extract the title and clean it
        title = match.group(1).strip()
        
        # Remove any leading/trailing markdown-style formatting
        title = title.lstrip('**').rstrip('**')
        
        # Remove all double quotes
        title = title.replace('"', '')
        
        print(f"Title extracted: {title}")
    else:
        title = None
        print("No title found in the response text.")

    return title

def merge_audio_files(audio_files, output_filename="final_podcast.mp3"):
    """Merge multiple MP3 files into one"""
    # Load the first audio file
    final_audio = AudioSegment.from_mp3(audio_files[0])
    
    # Append each subsequent audio file to the final audio
    for audio_file in audio_files[1:]:
        audio_segment = AudioSegment.from_mp3(audio_file)
        final_audio += audio_segment  # Append to the final audio

    # Export the final merged audio file
    final_audio.export(output_filename, format="mp3")
    print(f"Final podcast saved as {output_filename}")

    # Clean up temporary audio files
    for audio_file in audio_files:
        os.remove(audio_file)

    st.subheader("Dive into the DocTalk Podcast")
    st.audio(output_filename, format="audio/mp3")

def summarize_and_generate_images(source, document_bytes, uploaded_file, system_prompt, user_prompt):
    # Append any additional user input as a custom prompt
    if user_prompt:
        system_prompt += f"\n\nAdditional Prompt: {user_prompt}"

    # Prepare messages depending on whether the source is a URL or document
    if source == "URL":
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": system_prompt
                    }
                ]
            }
        ]
    else:
        # Extract the document name without the extension and the file extension
        document_name_without_extension, file_extension = os.path.splitext(uploaded_file.name)
        file_extension = file_extension.lstrip('.')
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "name": document_name_without_extension,
                            "format": file_extension,
                            "source": {
                                "bytes": document_bytes
                            }
                        }
                    },
                    {
                        "text": system_prompt
                    }
                ]
            }
        ]

    # Make the API call
    response = client.converse(
        modelId=modelId,
        messages=messages
    )

    # Extract and display the title
    title = get_title(response['output']['message']['content'][0]['text'])
    st.subheader(f"Title: {title}")

    # Generate the image(s)
    generate_image_prompt = f"Generate an image for: {title}"
    
    if media_option == "Video":
        for i in range(1):
            j = i % 5
            # Select the modelId for this iteration
            # modelId1 = model_ids[j]
            
            # messages = [
            #     {
            #         "role": "user",
            #         "content": [
            #             {
            #                 "text": f"Summarize the article in one sentence - {response['output']['message']['content'][0]['text']}"
            #             }
            #         ]
            #     }
            # ]

            # time.sleep(10)

            # response1 = client.converse(
            #     modelId=modelId1,
            #     messages=messages
            # )
            # generate_image_prompt = f"Generate an image for: {response1['output']['message']['content'][0]['text']}"
            generate_image(generate_image_prompt[:1024], i)
    else:
        generate_image(generate_image_prompt[:1024], 0)

    # Return the summarized text
    return response["output"]["message"]["content"][0]["text"]

def generate_video_from_images_and_audio(image_paths, audio_path, output_video_path):
    try:
        # Load the audio file
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration  # Get the audio's duration
        
        clips = []
        total_duration = 0  # Keep track of the total duration of the video

        # Set the target resolution for full-screen (1920x1080)
        target_width = 1920
        target_height = 1080
        
        # Repeat the image sequence until the total duration exceeds the audio duration
        while total_duration < audio_duration:
            for image_path in image_paths:
                # Load the image as a video clip
                image_clip = ImageClip(image_path)
                
                # Generate a random duration for the image to be displayed
                duration = random.uniform(20, 25)  # Random duration between 20 and 25 seconds
                
                # Resize the image to full screen (1920x1080) while maintaining aspect ratio
                image_clip = image_clip.resize(newsize=(target_width, target_height))  # Resize to fit the screen
                            
                # Set the duration of the image clip
                image_clip = image_clip.set_duration(duration)
                
                # Add this clip to the list
                clips.append(image_clip)
                
                # Update the total duration of the video
                total_duration += duration
                
                # Stop once the total duration exceeds the audio length
                if total_duration >= audio_duration:
                    break
        
        # Concatenate all the image clips into one video
        video_clip = concatenate_videoclips(clips, method="compose")
        
        # Set the audio to the video
        video_clip = video_clip.set_audio(audio_clip)
        
        # Write the result to a video file
        video_clip.write_videofile(output_video_path, fps=24, codec='libx264', audio_codec='aac')

        st.subheader("Catch the latest DocTalk visuals")
        st.video(output_video_path)
    except Exception as e:
        # Catch any general exceptions
        print(f"An error occurred: {e}")
        st.error(f"An unexpected error occurred: {e}")

def generate_audio(source, document_bytes, uploaded_file, url):
    if source == "URL":
        prompt0 = f"Convert the provided article contents from {url} "
    elif source == "Document":
        prompt0 = "Convert the provided document content "
    else:
        prompt0 = ""
    
    system_prompt = prompt0 + """
        into a natural, engaging, and extensive podcast script featuring a conversation between **two hosts**. 
        Go through each page of the document and extract the insights to create the podcast script. Do not miss any pages while creating the podcast script.
        The dialogue should flow naturally, with dynamic interaction between the hosts, including pauses, gaps, and natural breaks,
        to make the conversation feel lively and authentic—perfect for an audio format.
        The conversation should be lively, dynamic, and keep the listener's attention, with smooth transitions and natural pauses.

        ### Key Instructions:
        1. **Summarize the article in one sentence** and make that the podcast **title**.
        2. **Introduction** Always have the first line of the Podcast script as "Welcome to the DocTalk show! I’m Rachel, and my co-host Tom, here to dive into the fascinating world of documents and articles, bringing them to life as engaging DocTalk conversations."
        2. **Mention the podcast title** at the beginning of the script and throughout the conversation where appropriate. Make sure it feels integrated naturally, not forced.
        3. **Ensure that the core message and essence** of the original content are preserved while adapting it into a dialogue. Every important point in the document must be covered, with a balance between thoroughness and natural conversation flow.
        4. **Format**: Use dialogue between **Speaker 1** and **Speaker 2**. Don't mention the speaker names in the script. Alternate between them in a way that keeps the conversation dynamic and engaging.
        5. **Pacing**: Include natural pauses, slight pauses, and breaks to make the conversation sound authentic and suited for an audio format.
        6. Avoid using words like 'pause,' 'wrapping up,' 'interjecting,' 'enthusiastically,' or any other terms that describe actions or tones

        ### Example Format:
        **Title:** [Podcast Title]  
        **Speaker 1:** Welcome back to [Podcast Title].  
        **Speaker 2:** Thanks for joining us. Today, we’ll be discussing [main point of the document].  
        **Speaker 1:** That's right. We'll explore [main point] in more detail here on [Podcast Title].  
        **Speaker 2:** This is an important topic to explore. Let’s dive in.

        Feel free to adapt the tone based on the subject matter, whether it’s more casual and friendly or informative and serious. Ensure the script reads as a natural conversation, with both hosts actively engaging with each other and maintaining a lively flow.
        """
    
    # Add custom CSS
    st.markdown(
        """
        <style>
        /* Container for the columns */
        [data-testid="stHorizontalBlock"] {
            position: fixed;
            bottom: 0;
            left: 54%;
            transform: translateX(-50%);
            width: 900px;  /* Adjust total width of the container */
            background-color: white;
            padding: 20px;
            z-index: 999;
        }

        /* Chat input specific styling */
        .stChatInput {
            width: 600px !important;  /* Adjust this value to make input smaller */
            margin: 0 auto !important;
        }

        /* Optional: Style the button to align with the smaller width */
        .stButton {
            margin-left: 30px !important;
        }
        </style>
        """, 
        unsafe_allow_html=True
    )

    # Your existing columns code
    col1, col2 = st.columns([2, 1])

    with col1:
        user_prompt = st.chat_input("Enter an optional prompt to customize and curate your DocTalk episode:", key="user_prompt_input")

    with col2:
        create_doctalk = st.button("Launch DocTalk")
    
    if user_prompt:
        update_chat_history(user_prompt)

    # Summarize the document
    # if st.button("Summarize Document"):
    if user_prompt or create_doctalk:
        with st.spinner(text="Curating the DocTalk Episode..."):
            
            if source == "URL":
                # summary = summarize_from_url("video", url, system_prompt, user_prompt)
                summary = summarize_and_generate_images("URL", None, None, system_prompt, user_prompt)
            elif source == "Document":
                # summary = summarize_from_document("video", document_bytes, uploaded_file, system_prompt, user_prompt)
                summary = summarize_and_generate_images("Document", document_bytes, uploaded_file, system_prompt, user_prompt)
            elif source == "Existing Script":
                title = get_title(document_bytes.decode('utf-8'))
                st.subheader(f"Title: {title}")

                if media_option == "Video":
                    for i in range(1):
                        j = i % 5
                        generate_image(title, i)
                else:
                    generate_image(title, 0)
                summary = document_bytes.decode('utf-8')

            # st.subheader("Summary:")
            # st.write(summary)

            # Split the script by lines and process
            script_lines = summary.strip().split("\n")

        # Process the script and generate audio files for each speaker
        with st.spinner(text="Bringing DocTalk to Life..."):
            audio_files = process_script(script_lines)

            # Merge all audio files into a final podcast file
            merge_audio_files(audio_files)

        if media_option == "Video":
            # Process the audio & image files to generate video
            with st.spinner(text="Bringing DocTalk’s Vision to Life..."):
                # image_paths = ["generated_image0.png", "generated_image1.png", "generated_image2.png", "generated_image3.png", "generated_image4.png"]
                # Custom prefix or pattern for image names
                prefix = "generated_image_"

                # Number of images to generate
                num_images = 1

                # Dynamically generate the image paths
                image_paths = [f"{prefix}{i}.png" for i in range(num_images)]
                generate_video_from_images_and_audio(image_paths, "final_podcast.mp3", "random_video.mp4")

# Streamlit UI
st.title("DocTalk")

# Radio button to choose between document or URL
# option = st.radio("Choose the input type", ["Attach Document", "Website URL"])

# options = ["Curate DocTalk Episodes from Documents", "Curate DocTalk Episodes from Articles"]
# option = st.radio("", options, horizontal=True)

options = ["Curate DocTalk Episodes from Documents", 
           "Curate DocTalk Episodes from Articles", 
           "Curate DocTalk Episodes from Existing Script"]

# Use st.selectbox for a combo box (dropdown)
option = st.selectbox("Choose the source for DocTalk Episodes", options)

# Options for the second combo box (Audio/Video)
media_options = ["Audio", "Video"]

media_option = st.selectbox("Choose the media type", media_options)

# List to store user inputs (chat-like)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Function to update chat history
def update_chat_history(user_input):
    st.session_state.chat_history.append(user_input)

# Display chat history
for chat in st.session_state.chat_history:
    st.write(f"**User:** {chat}")

# Process based on user's choice
if option == "Curate DocTalk Episodes from Documents":
    # File upload for document
    uploaded_file = st.file_uploader("Upload your document", type=["pdf", "docx", "txt"])
    
    if uploaded_file:
        # Read the file as bytes
        document_bytes = uploaded_file.read()

        # Display file details
        st.write(f"Uploaded document: {uploaded_file.name}")

        # Get file size in KB
        file_size_kb = len(uploaded_file.getvalue()) / 1024  # Convert bytes to KB

        # Check if file size is greater than 250KB
        if file_size_kb > 2500:
            st.warning("The file is over 250KB and too large to display, but it can still be processed for DocTalk.")
        else:
            # Create an expander for the text display
            with st.expander("Document Content", expanded=True):

                # Handle TXT files
                if uploaded_file.type == "text/plain":
                    try:
                        document_text = document_bytes.decode('utf-8')  # Attempt to decode as UTF-8
                        # st.text(document_text)
                        st.text_area("", value=document_text, height=300)
                    except UnicodeDecodeError:
                        st.error("Error decoding the TXT file. Try uploading a UTF-8 encoded file.")
                
                # Handle PDF files
                elif uploaded_file.type == "application/pdf":
                    try:
                        # Convert bytes to file-like object
                        pdf_file = io.BytesIO(document_bytes)
                        
                        # Use PyPDF2 to extract text from PDF
                        pdf_reader = PdfReader(pdf_file)
                        pdf_text = ""
                        for page in pdf_reader.pages:
                            pdf_text += page.extract_text()
                        # st.text(pdf_text)
                        st.text_area("", value=pdf_text, height=300)
                    except Exception as e:
                        st.error(f"Error extracting text from PDF: {e}")
                
                # Handle DOCX files
                elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    try:
                        # Use python-docx to extract text from DOCX
                        doc = docx.Document(io.BytesIO(document_bytes))
                        doc_text = "\n".join([para.text for para in doc.paragraphs])
                        # st.text(doc_text)
                        st.text_area("", value=doc_text, height=300)
                    except Exception as e:
                        st.error(f"Error extracting text from DOCX: {e}")

        generate_audio("Document", document_bytes, uploaded_file, None)

elif option == "Curate DocTalk Episodes from Articles":
    # Text input for URL
    url = st.text_input("Enter the Article URL")
    
    if url:
        fetch_and_display_url_content(url)
        generate_audio("URL", None, None, url)

# Process based on user's choice
elif option == "Curate DocTalk Episodes from Existing Script":
    # File upload for document
    uploaded_file = st.file_uploader("Upload your document", type=["txt"])
    
    if uploaded_file:
        # Read the file as bytes
        document_bytes = uploaded_file.read()

        # Display file details
        st.write(f"Uploaded document: {uploaded_file.name}")

        document_text = document_bytes.decode('utf-8')  # Attempt to decode as UTF-8
        st.text_area("", value=document_text, height=300)

        generate_audio("Existing Script", document_bytes, uploaded_file, None)