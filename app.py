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

# Add custom CSS for modern chat UI styling
st.markdown("""
<style>
/* Main app background */
.main, .stApp {
    background-color: #0E0E0E;
    color: #FFFFFF;
}

/* Chat container */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 20px;
}

/* Message styling */
.message {
    padding: 12px 16px;
    border-radius: 8px;
    max-width: 100%;
    margin: 4px 0;
    word-wrap: break-word;
}

/* User message styling */
.user-message {
    background-color: #1E1E1E;
    margin-right: 0;
}

/* Assistant message styling */
.assistant-message {
    background-color: #252525;
    margin-left: 0;
}

/* Input area styling */
.chat-input-area {
    background-color: #1E1E1E;
    border-radius: 12px;
    padding: 8px;
    margin-top: 20px;
}

/* Style text areas */
.stTextArea textarea {
    background-color: #1E1E1E !important;
    color: white !important;
    border: none !important;
    padding: 12px !important;
    height: 60px !important;
    font-size: 16px !important;
}

/* Send button styling */
.send-button {
    background-color: #5046E5 !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    margin-top: 10px !important;
    border: none !important;
}

/* Hide default Streamlit elements */
header {
    visibility: hidden;
}

/* Conversation title styling */
h1, h2, h3 {
    color: white !important;
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
    margin-top: 20px !important;
}

/* Style the chat title input */
div[data-testid="stTextInput"] input {
    background-color: #1E1E1E !important;
    color: white !important;
    border-color: #333333 !important;
    border-radius: 8px !important;
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

# Models available in OpenRouter - Updated with requested order
MODELS = {
    "OpenAI GPT-4o": "openai/gpt-4o",
    "GPT-4 Turbo": "openai/gpt-4-turbo",
}

# Helper function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        # Install PyPDF2 if not already installed
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            st.error("PyPDF2 is not installed. Installing now...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2"])
            from PyPDF2 import PdfReader
        
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
        # Install python-docx if not already installed
        try:
            import docx
        except ImportError:
            st.error("python-docx is not installed. Installing now...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
            import docx
        
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
        # Try DuckDuckGo first
        duckduckgo_url = f"https://api.duckduckgo.com/?q={query}&format=json"
        response = requests.get(duckduckgo_url)
        
        if response.status_code == 200:
            results = response.json()
            
            # Format search results
            formatted_results = "Web search results:\n\n"
            
            # Add abstract if available
            if "AbstractText" in results and results["AbstractText"]:
                formatted_results += f"Summary: {results['AbstractText']}\n"
                if "AbstractSource" in results:
                    formatted_results += f"Source: {results['AbstractSource']}\n\n"
            
            # Add related topics
            if "RelatedTopics" in results and results["RelatedTopics"]:
                formatted_results += "Related Information:\n"
                for i, topic in enumerate(results["RelatedTopics"][:5]):  # Limit to 5 topics
                    if "Text" in topic:
                        formatted_results += f"- {topic['Text']}\n"
                
            return formatted_results
        
        # Fallback to a simplified search simulation if DuckDuckGo fails
        return f"Web search results for '{query}' (Note: This is simulated since direct web search requires additional API integration)"
    
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
                
                # Specific handling for invalid model ID
                if "not a valid model ID" in error_message:
                    st.warning("Please select a different model from the sidebar.")
            except:
                st.error(f"API Error: {response.status_code} - {response.text}")
            
            return None
    except Exception as e:
        st.error(f"Request error: {str(e)}")
        return None

# Function to send a message and get a response
def send_message(user_input):
    if not st.session_state.api_key:
        st.error("Please enter your OpenRouter API key in the sidebar.")
        return False
    
    if not user_input.strip():
        return False
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Prepare message history for API
    messages_for_api = []
    
    # Add initial system message with document context if available
    system_message = "You are a helpful document assistant. You can analyze documents, answer questions, and help with creative writing tasks."
    
    if st.session_state.document_context:
        system_message += "\n\nBelow is relevant information from the user's documents that may help answering their query:"
        # Limit context length to avoid token limits
        context_limit = 75000
        if len(st.session_state.document_context) > context_limit:
            system_message += f"\n\n{st.session_state.document_context[:context_limit]} [Document truncated due to length...]"
        else:
            system_message += f"\n\n{st.session_state.document_context}"
    
    messages_for_api.append({"role": "system", "content": system_message})
    
    # Web search if enabled and requested
    if st.session_state.enable_web_search and any(term in user_input.lower() for term in ["search", "find", "look up", "google", "information about"]):
        with st.spinner("Searching the web..."):
            search_results = perform_web_search(user_input)
            if search_results:
                messages_for_api.append({
                    "role": "system", 
                    "content": search_results
                })
    
    # Add conversation history (exclude system messages)
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            messages_for_api.append(msg)
    
    # Make API request
    with st.spinner("Thinking..."):
        response = openrouter_chat_completion(messages_for_api, st.session_state.selected_model)
        
        if response and "choices" in response and len(response["choices"]) > 0:
            full_response = response["choices"][0]["message"]["content"]
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Auto-save chat
            save_chat()
            return True
        else:
            st.error("Failed to get a response from the model. Please try again.")
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
    
    # Save to file
    filename = f"{CHATS_DIR}/{st.session_state.chat_id}.json"
    with open(filename, "w") as f:
        json.dump(chat_data, f)
    
    # Update archived chats list
    st.session_state.archived_chats = [chat for chat in st.session_state.archived_chats if chat["id"] != chat_data["id"]]
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
    
    # Sort by timestamp, newest first
    chats.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    st.session_state.archived_chats = chats

# Start new chat
def start_new_chat():
    st.session_state.messages = []
    st.session_state.chat_id = str(uuid.uuid4())
    st.session_state.chat_title = "New Chat " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.document_context = ""

# Process document function
def process_document(uploaded_file):
    # Create a temporary file
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
        # Clean up the temp file
        os.unlink(temp_file_path)

# Function to handle the form submission
def handle_submit():
    # Set the submitted flag
    st.session_state.submitted = True

# Main App Layout
st.title("Document Assistant")

# Sidebar
with st.sidebar:
    st.title("Settings")

    # API Key input
    api_key = st.text_input("OpenRouter API Key", value=st.session_state.api_key, type="password")
    if api_key != st.session_state.api_key:
        st.session_state.api_key = api_key

    # Model selection
    st.subheader("Model Selection")
    selected_model_name = st.selectbox(
        "Choose a model",
        list(MODELS.keys()),
        index=0  # Default to first model (Claude 3.5 Sonnet)
    )
    st.session_state.selected_model = MODELS[selected_model_name]

    # Document upload
    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload documents", 
        accept_multiple_files=True,
        type=["txt", "pdf", "docx"]
    )

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
            
            # Hide progress bar after completion
            progress_bar.empty()

    # Show document context preview
    if st.session_state.document_context:
        if st.checkbox("Show Document Preview"):
            preview_text = st.session_state.document_context[:1000] + "..." if len(st.session_state.document_context) > 1000 else st.session_state.document_context
            st.text_area("Document Preview", preview_text, height=200)
        
        # Option to clear document context
        if st.button("Clear Document Context"):
            st.session_state.document_context = ""
            st.success("Document context cleared!")

    # Web search option
    st.subheader("Web Search")
    enable_web_search = st.checkbox("Enable Web Search", value=st.session_state.enable_web_search)
    if enable_web_search != st.session_state.enable_web_search:
        st.session_state.enable_web_search = enable_web_search

    # Separator
    st.markdown("---")

    # Archived chats
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

    # New Chat button
    if st.button("➕ New Chat", key="new_chat_btn"):
        start_new_chat()
        st.rerun()

# Main chat area
st.header(st.session_state.chat_title)

# Edit chat title
new_title = st.text_input("Chat Title", value=st.session_state.chat_title)
if new_title != st.session_state.chat_title:
    st.session_state.chat_title = new_title

# Display conversation history with modern styling
st.subheader("Conversation")
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""<div class="message user-message">
                    <b>You:</b> {message['content']}
                    </div>""", unsafe_allow_html=True)
    elif message["role"] == "assistant":
        st.markdown(f"""<div class="message assistant-message">
                    <b>Assistant:</b> {message['content']}
                    </div>""", unsafe_allow_html=True)

# Message input form with clear functionality
with st.form(key="message_form", clear_on_submit=True):
    user_input = st.text_area(
        "Your message", 
        height=100,
        placeholder="Type your message here...",
        label_visibility="collapsed"
    )
    
    # Add a submit button
    submit_button = st.form_submit_button("Send", on_click=handle_submit, use_container_width=True)
    
    # Process the form submission
    if submit_button and user_input:
        # Process the message
        if send_message(user_input):
            st.rerun()

# Download chat history button
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
