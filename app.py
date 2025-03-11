import streamlit as st
import requests
import json
import os
import uuid
import datetime
import tempfile
import base64

# Set page config
st.set_page_config(page_title="Document Assistant", layout="wide", initial_sidebar_state="expanded")

# Add custom CSS for modern chat UI styling and code block overrides
st.markdown("""
<style>
/* Main app background */
.main, .stApp {
    background-color: #0E0E0E;
    color: #FFFFFF;
}

/* Chat container with reduced width, centered horizontally, and vertical spacing */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 6px;                /* smaller gap between messages */
    margin: 120px auto 0;    /* 120px top margin to bring it down further */
    max-width: 400px;        /* narrower chat box */
    width: 100%;
}

/* Message styling */
.message {
    padding: 8px 10px;       /* smaller padding around text */
    border-radius: 6px;
    max-width: 100%;
    margin: 2px 0;           /* tighter spacing between messages */
    word-wrap: break-word;
    font-size: 14px;         /* smaller font size if desired */
}

/* User message styling */
.user-message {
    background-color: #1E1E1E;
}

/* Assistant message styling */
.assistant-message {
    background-color: #252525;
}

/* Input area styling */
.chat-input-area {
    background-color: #1E1E1E;
    border-radius: 8px;
    padding: 6px;
    margin-top: 10px;
}

/* Style text areas: set height to 70px (minimum required by Streamlit) */
.stTextArea textarea {
    background-color: #1E1E1E !important;
    color: white !important;
    border: none !important;
    padding: 10px !important;
    height: 70px !important; /* must be at least 68px to avoid Streamlit error */
    font-size: 14px !important;
}

/* Send button styling */
.send-button {
    background-color: #5046E5 !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
    margin-top: 6px !important;
    border: none !important;
    font-size: 14px !important;
}

/* Hide default Streamlit elements */
header {
    visibility: hidden;
}

/* For the sidebar */
.css-1d391kg, .css-1v3fvcr {
    background-color: #0E0E0E;
}

/* Download link styling */
.download-link {
    color: #5046E5 !important;
    text-decoration: none !important;
    display: inline-flex !important;
    align-items: center !important;
    margin-top: 10px !important;
    font-size: 14px !important;
}

/* Style the chat title input (if used) */
div[data-testid="stTextInput"] input {
    background-color: #1E1E1E !important;
    color: white !important;
    border-color: #333333 !important;
    border-radius: 6px !important;
}

/* Neutralize code-block styling in Streamlit */
[data-testid="stMarkdownContainer"] pre,
[data-testid="stMarkdownContainer"] pre code,
[data-testid="stMarkdownContainer"] code,
[data-testid="stMarkdownContainer"] .highlight {
    background-color: #0E0E0E !important; /* or transparent if you prefer */
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: inherit !important;
}
</style>
""", unsafe_allow_html=True)

# Directory setup for saving chats
CHATS_DIR = "archived_chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# Initialize session state variables
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "anthropic/claude-3-5-sonnet-20240620"
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'chat_id' not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if 'chat_title' not in st.session_state:
    st.session_state.chat_title = "New Chat " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
if 'document_context' not in st.session_state:
    st.session_state.document_context = ""
if 'archived_chats' not in st.session_state:
    st.session_state.archived_chats = []
if 'enable_web_search' not in st.session_state:
    st.session_state.enable_web_search = True
if 'submitted' not in st.session_state:
    st.session_state.submitted = False

# Models available in OpenRouter
MODELS = {
    "OpenAI GPT-4o": "openai/gpt-4o",
    "GPT-4 Turbo": "openai/gpt-4-turbo",
}

# Helper function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        st.error("PyPDF2 is not installed. Installing now...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2"])
        from PyPDF2 import PdfReader
    
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

# Helper function to extract text from DOCX
def extract_text_from_docx(docx_file):
    try:
        import docx
    except ImportError:
        st.error("python-docx is not installed. Installing now...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
        import docx
    
    try:
        doc = docx.Document(docx_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        return f"Error extracting text from DOCX: {str(e)}"

# Helper function to extract text from txt
def extract_text_from_txt(file):
    try:
        return file.read().decode("utf-8")
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# Enhanced web search functionality
def perform_web_search(query):
    try:
        duckduckgo_url = f"https://api.duckduckgo.com/?q={query}&format=json"
        response = requests.get(duckduckgo_url)
        
        if response.status_code == 200:
            results = response.json()
            formatted_results = "Web search results:\n\n"
            
            if "AbstractText" in results and results["AbstractText"]:
                formatted_results += f"Summary: {results['AbstractText']}\n"
                if "AbstractSource" in results:
                    formatted_results += f"Source: {results['AbstractSource']}\n\n"
            
            if "RelatedTopics" in results and results["RelatedTopics"]:
                formatted_results += "Related Information:\n"
                for i, topic in enumerate(results["RelatedTopics"][:5]):
                    if "Text" in topic:
                        formatted_results += f"- {topic['Text']}\n"
                
            return formatted_results
        
        return f"Web search results for '{query}' (simulation fallback)"
    
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return f"Unable to perform web search. Error: {str(e)}"

# OpenRouter API function
def openrouter_chat_completion(messages, model):
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "Document Assistant App",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": messages
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(data)
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                st.error(f"API Error: {response.status_code} - {error_message}")
                if "not a valid model ID" in error_message:
                    st.warning("Please select a different model from the sidebar.")
            except:
                st.error(f"API Error: {response.status_code} - {response.text}")
            
            return None
    except Exception as e:
        st.error(f"Request error: {str(e)}")
        return None

# Send message function
def send_message(user_input):
    if not st.session_state.api_key:
        st.error("Please enter your OpenRouter API key in the sidebar.")
        return False
    
    if not user_input.strip():
        return False
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    messages_for_api = []
    
    system_message = "You are a helpful document assistant. You can analyze documents, answer questions, and help with creative writing tasks."
    if st.session_state.document_context:
        system_message += "\n\nBelow is relevant information from the user's documents:"
        context_limit = 75000
        if len(st.session_state.document_context) > context_limit:
            system_message += f"\n\n{st.session_state.document_context[:context_limit]} [Truncated...]"
        else:
            system_message += f"\n\n{st.session_state.document_context}"
    
    messages_for_api.append({"role": "system", "content": system_message})
    
    # Simple check for search triggers
    if st.session_state.enable_web_search and any(term in user_input.lower() for term in ["search", "find", "look up", "google", "information about"]):
        with st.spinner("Searching the web..."):
            search_results = perform_web_search(user_input)
            if search_results:
                messages_for_api.append({"role": "system", "content": search_results})
    
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            messages_for_api.append(msg)
    
    with st.spinner("Thinking..."):
        response = openrouter_chat_completion(messages_for_api, st.session_state.selected_model)
        if response and "choices" in response and len(response["choices"]) > 0:
            full_response = response["choices"][0]["message"]["content"]
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_chat()
            return True
        else:
            st.error("Failed to get a response. Please try again.")
            return False

# Save chat function
def save_chat():
    chat_data = {
        "id": st.session_state.chat_id,
        "title": st.session_state.chat_title,
        "messages": st.session_state.messages,
        "timestamp": datetime.datetime.now().isoformat(),
        "model": st.session_state.selected_model,
        "document_context": st.session_state.document_context
    }
    
    filename = f"{CHATS_DIR}/{st.session_state.chat_id}.json"
    with open(filename, "w") as f:
        json.dump(chat_data, f)
    
    st.session_state.archived_chats = [c for c in st.session_state.archived_chats if c["id"] != chat_data["id"]]
    st.session_state.archived_chats.append(chat_data)
    return filename

# Load chat function
def load_chat(chat_id):
    filename = f"{CHATS_DIR}/{chat_id}.json"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            chat_data = json.load(f)
        st.session_state.messages = chat_data["messages"]
        st.session_state.chat_id = chat_data["id"]
        st.session_state.chat_title = chat_data["title"]
        if "model" in chat_data:
            st.session_state.selected_model = chat_data["model"]
        if "document_context" in chat_data:
            st.session_state.document_context = chat_data["document_context"]
        return True
    else:
        st.error(f"Chat with ID {chat_id} not found.")
        return False

# Load archived chats
def load_archived_chats():
    chats = []
    if os.path.exists(CHATS_DIR):
        for filename in os.listdir(CHATS_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(CHATS_DIR, filename), "r") as f:
                        chat_data = json.load(f)
                        chats.append(chat_data)
                except Exception as e:
                    st.error(f"Error loading chat {filename}: {e}")
    chats.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    st.session_state.archived_chats = chats

# Start new chat
def start_new_chat():
    st.session_state.messages = []
    st.session_state.chat_id = str(uuid.uuid4())
    st.session_state.chat_title = "New Chat " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.document_context = ""

def process_document(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_file_path = temp_file.name
    
    try:
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        
        if file_extension == ".pdf":
            with open(temp_file_path, "rb") as f:
                text = extract_text_from_pdf(f)
        elif file_extension == ".docx":
            with open(temp_file_path, "rb") as f:
                text = extract_text_from_docx(f)
        elif file_extension == ".txt":
            with open(temp_file_path, "rb") as f:
                text = extract_text_from_txt(f)
        else:
            return f"Unsupported file format: {file_extension}"
        
        return text
    finally:
        os.unlink(temp_file_path)

def handle_submit():
    st.session_state.submitted = True

# Main App Layout
st.title("")

# Sidebar
with st.sidebar:
    st.title("Settings")
    api_key = st.text_input("OpenRouter API Key", value=st.session_state.api_key, type="password")
    if api_key != st.session_state.api_key:
        st.session_state.api_key = api_key

    st.subheader("Model Selection")
    selected_model_name = st.selectbox(
        "Choose a model",
        list(MODELS.keys()),
        index=0
    )
    st.session_state.selected_model = MODELS[selected_model_name]

    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader("Upload documents", accept_multiple_files=True, type=["txt", "pdf", "docx"])
    if uploaded_files:
        process_button = st.button("Process Documents")
        if process_button:
            progress_bar = st.progress(0)
            all_text = ""
            for i, uploaded_file in enumerate(uploaded_files):
                progress_percent = int((i / len(uploaded_files)) * 100)
                progress_bar.progress(progress_percent)
                st.text(f"Processing {uploaded_file.name}...")
                text = process_document(uploaded_file)
                if not text.startswith("Error"):
                    all_text += f"\n\n--- Document: {uploaded_file.name} ---\n\n" + text
                    st.success(f"Processed {uploaded_file.name}")
                else:
                    st.error(f"Failed to process {uploaded_file.name}: {text}")
            progress_bar.progress(100)
            if all_text.strip():
                st.session_state.document_context = all_text
                st.success("All documents processed!")
            progress_bar.empty()

    if st.session_state.document_context:
        if st.checkbox("Show Document Preview"):
            preview_text = (st.session_state.document_context[:1000] + "...") \
                if len(st.session_state.document_context) > 1000 else st.session_state.document_context
            st.text_area("Document Preview", preview_text, height=150)
        
        if st.button("Clear Document Context"):
            st.session_state.document_context = ""
            st.success("Document context cleared!")

    st.subheader("Web Search")
    enable_web_search = st.checkbox("Enable Web Search", value=st.session_state.enable_web_search)
    if enable_web_search != st.session_state.enable_web_search:
        st.session_state.enable_web_search = enable_web_search

    st.markdown("---")

    st.subheader("Archived Chats")
    if not st.session_state.archived_chats:
        load_archived_chats()

    if st.session_state.archived_chats:
        for chat in st.session_state.archived_chats:
            if st.button(f"📝 {chat['title']}", key=f"btn_{chat['id']}"):
                load_chat(chat['id'])
                st.rerun()
    else:
        st.text("No archived chats found.")

    if st.button("➕ New Chat", key="new_chat_btn"):
        start_new_chat()
        st.rerun()

# Main chat area wrapped in a centered container
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""<div class="message user-message">
                        {message['content']}
                        </div>""", unsafe_allow_html=True)
        elif message["role"] == "assistant":
            st.markdown(f"""<div class="message assistant-message">
                        {message['content']}
                        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.form(key="message_form", clear_on_submit=True):
        user_input = st.text_area(
            "What can I help with?",
            placeholder="Type your message here...",
            label_visibility="collapsed",
            height=70  # Must be >=68 to avoid Streamlit error
        )
        submit_button = st.form_submit_button("Send", on_click=handle_submit, use_container_width=True)
        if submit_button and user_input:
            if send_message(user_input):
                st.rerun()

    if st.session_state.messages:
        chat_json = json.dumps(st.session_state.messages, indent=2)
        b64 = base64.b64encode(chat_json.encode()).decode()
        download_filename = f"chat_{st.session_state.chat_id[:8]}.json"
        st.markdown(
            f'<a href="data:file/json;base64,{b64}" download="{download_filename}" '
            f'class="download-link">'
            f'<span style="margin-right: 5px;">⬇️</span> Download Chat History</a>',
            unsafe_allow_html=True
        )
