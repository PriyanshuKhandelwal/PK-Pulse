# importing important libraries
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from docx import Document
import gradio as gr
import requests
import json

load_dotenv(override=True)
openai = OpenAI()
llama = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')

pushover_user = os.getenv('PUSHOVER_USER')
pushover_token = os.getenv('PUSHOVER_TOKEN')
pushover_url = 'https://api.pushover.net/1/messages.json'

use_ollama = False
use_ollama_for_evaluation = False
include_history = True
ollama = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')


def push(message):
    print(f"Pushover message: {message}")
    payload = {
        'user': pushover_user,
        'token': pushover_token,
        'message': message,
    }
    response = requests.post(pushover_url, data=payload)
    if response.status_code == 200:
        print("Pushover message sent successfully.")
    else:
        print(f"Failed to send Pushover message. Status code: {response.status_code}, Response: {response.text}")


# create two tool functions: record_user_details and record_unknown_question
def record_user_details(email, name='Not Provided', phone='Not Provided', notes='Not Provided'):
    """
    Records user details and returns a confirmation message.
    """
    # Here you can implement the logic to store the user details in a database or file
    push(f"User Details Recorded: Email: {email}, Name: {name}, Phone: {phone}, Notes: {notes}")
    return f"User details recorded for {name} with email {email}: OKAY"


def record_unknown_question(question, use_ollama=use_ollama):
    """
    Records an unknown question and returns a confirmation message.
    """
    # Here you can implement the logic to store the unknown question in a database or file
    if use_ollama:
        # push(f"Unknown question recorded: {question}")
        pass
    else:
        push(f"Unknown question recorded: {question}")
    return f"Unknown question recorded: {question}: OKAY"


# creating json tool for llm
tools_dict = {
    "tool_record_user_details_json": {
        "name": "record_user_details",
        "description": "Use this tool to record user details like email, name, phone, and notes, if user wants to get in touch",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address of the user"
                },
                "name": {
                    "type": "string",
                    "description": "The name of the user, if provided"
                },
                "phone": {
                    "type": "string",
                    "description": "The phone number of the user, if provided"
                },
                "notes": {
                    "type": "string",
                    "description": "Any additional notes or information about the user"
                }
            },
            "required": ["email"],
            "additionalProperties": False
        }
    },
    'tool_record_unknown_question_json': {
        "name": "record_unknown_question",
        "description": "ONLY use this tool when you definitively cannot answer a question about Priyanshu based on the provided information. Do NOT use this tool if you can provide any relevant answer, even if partial.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The unknown question that the user has asked"
                }
            },
            "required": ["question"],
            "additionalProperties": False
        }
    }
}

tools = [
    {"type": "function", "function": tools_dict["tool_record_user_details_json"]},
    {"type": "function", "function": tools_dict["tool_record_unknown_question_json"]}
]


# now the if else logic for the tools (behind the scenes of llm :p)
def tool_call_handler(tool_calls):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        print(f"Tool called: {tool_name}, Arguments: {tool_args}", flush=True)
        tool = globals().get(tool_name)
        result = tool(**tool_args) if tool else f"Tool {tool_name} not found."
        results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
    return results


about_me_folder_path = './about_me'
# above folder contains the about me files
about_me_files = os.listdir(about_me_folder_path)
# filter the files to only include pdf and docx
about_me_files = [file for file in about_me_files if file.endswith('.pdf') or file.endswith('.docx')]
# join the folder path with the file name to get the full path of the file
about_me_files = [os.path.join(about_me_folder_path, file) for file in about_me_files]


def read_pdf(file_path):
    reader = PdfReader(file_path)
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text


def read_docx(file_path):
    doc = Document(file_path)
    text = ''
    for para in doc.paragraphs:
        text += para.text + '\n'
    return text


def read_about_me_files():
    about_me_text = ''
    for file in about_me_files:
        if file.endswith('.pdf'):
            about_me_text += read_pdf(file) + '\n'
        elif file.endswith('.docx'):
            about_me_text += read_docx(file) + '\n'
    contact_info_file = os.path.join(about_me_folder_path, 'contact_info.txt')
    if os.path.exists(contact_info_file):
        with open(contact_info_file, 'r') as f:
            contact_info = f.read()
            about_me_text += contact_info + '\n'
    return about_me_text


about_me_text = read_about_me_files()

name = 'Priyanshu Khandelwal '
system_prompt = f"""You are representing {name}. {name} is a senior data scientist with over 8.5 years of experience. He loves learning about tech. Currently he is is learning French and focusing on fitness. 
You are answering all the question on {name}'s behalf on {name}'s website. For your response , first add response in very short form in bold, then add in detail (if required).
You know all about {name}'s career, background, education, skills and interests. You are responsible to represent {name} on 
the interactions as faithfully as possible. You are not allowed to make up any information about {name}.You are given a summary
seperately about {name} which you can use to answer the questions. You have to be proficient and professional and engaging, as you
may be talking to potential employers, clients, or collaborators.. Be faithful, if you don't know the answer to a question, strictly say that you don't know this information about {name}. Don't misrepresent {name} in any way.
You are not allowed to make up any information about {name}. If you are not sure about the answer, say that you are not sure. If you don't know something surely, then don't share it. ITS VERY IMPORTANT.
"""

system_prompt += f"\n\nHere is the summary about {name}:\n{about_me_text}\n\n"
system_prompt += "You are a helpful assistant. You are answering all the questions as {name}.\n\n"
system_prompt += """
IMPORTANT TOOL USAGE RULES:
- ONLY use 'record_unknown_question' when you absolutely cannot provide ANY information about the topic asked
- If you can answer even partially based on the provided information, DO NOT use the tool
- Always try to answer first before considering the question "unknown"
- Questions about general topics (not specific to Priyanshu) should be answered normally without using tools
"""

system_prompt += f"""
If some question you don't know the answer then share {name}'s email address to them to reachout to {name} directly.
IF they ask for contact information, you can share the email address.
IF they ask for whatsapp number, you can share the phone number.
If they ask for job location preferences, you can say that {name} is open to relocate for the right opportunity.
"""

system_prompt += f"""IF you want to highlight something about {name} then you can make that specifc word/text bold"""

def chat(message, history=[], use_ollama=use_ollama, include_history=include_history):
    # Convert Gradio history format to OpenAI message format
    messages = [{"role": "system", "content": system_prompt}]
    
    if include_history:
        # Convert history from Gradio format [user_msg, assistant_msg] to OpenAI format
        for user_msg, assistant_msg in history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
    
    # Add current user message
    messages.append({"role": "user", "content": message})
    
    print(f"User: {message}")
    print(f"Messages: {messages}", flush=True)
    
    done = False
    while not done:
        if use_ollama:
            print('Using Ollama model')
            response = ollama.chat.completions.create(
                model='llama3.2', 
                messages=messages, 
                temperature=0.1, 
                max_tokens=1000,
                top_p=0.9,
                frequency_penalty=1.0,
                presence_penalty=0.5,
                tools=tools,
            )
        else:
            print('Using OpenAI model')
            response = openai.chat.completions.create(
                model='gpt-4o-mini', 
                messages=messages, 
                tools=tools,
            )
        
        reply = response.choices[0].message.content
        finish_reasoning = response.choices[0].finish_reason
        
        print(response)
        print(f"Finish Reasoning: {finish_reasoning}", flush=True)
        
        if finish_reasoning == 'tool_calls':
            message_obj = response.choices[0].message
            tool_calls = message_obj.tool_calls
            results = tool_call_handler(tool_calls)
            messages.append(message_obj)
            messages.extend(results)
        else:
            done = True
    
    return reply

custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue - your existing color */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Only hide specific footer elements */
footer a[href*="gradio"], 
.footer a[href*="gradio"],
a[href*="github.com/gradio-app/gradio"],
.footer-links,
.versions {
    display: none !important;
}

/* Hide the "Built with Gradio" text specifically */
footer > div:last-child, 
div[class*="footer-links"],
div:has(> a[href*="gradio"]) {
    display: none !important;
}

/* Hide "Use via API" button and related elements */
a[id*="api"], 
a[class*="api"],
button[id*="api"],
button[class*="api"],
div[id*="api"],
div[class*="api"],
.api-btn {
    display: none !important;
}

/* Hide View API specifically */
a:has(span:contains("View API")),
button:has(span:contains("View API")),
div:has(span:contains("View API")) {
    display: none !important;
}

/* Ensure all API elements are hidden */
[data-testid*="api"] {
    display: none !important;
}

/* Body styling */
body {
    padding-bottom: 10px !important;
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--light-color) !important;
    color: var(--dark-color) !important;
}

/* Container styling */
.gradio-container {
    min-height: 450px !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow) !important;
    background-color: white !important;
}

/* Chat area styling */
.chat-container, .message-container {
    border-radius: 8px !important;
    background-color: white !important;
}

/* User messages */
.user-message, .message-user {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 12px 12px 2px 12px !important;
    padding: 10px 14px !important;
}

/* Bot messages */
.bot-message, .message-bot, .message-assistant {
    background-color: #f0f2f5 !important;
    color: var(--dark-color) !important;
    border-radius: 12px 12px 12px 2px !important;
    border-left: 3px solid var(--primary-color) !important;
    padding: 10px 14px !important;
}

/* Chat input area */
textarea, input[type="text"] {
    border-radius: 8px !important;
    border: 1px solid var(--border-color) !important;
    padding: 12px !important;
    transition: all 0.3s ease !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--primary-color) !important;
    box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2) !important;
    outline: none !important;
}

/* Make the submit button stand out more */
button[data-testid="submit"] {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    transition: all 0.2s ease !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

button[data-testid="submit"]:hover {
    background-color: #005b8c !important; /* Darker shade on hover */
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(0, 119, 181, 0.4) !important;
}

/* Title styling */
h1, h2, h3, .title {
    color: var(--primary-color) !important;
    font-weight: 600 !important;
}

/* Enhanced example buttons styling */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 6px !important;
    margin: 5px !important;
    transition: all 0.2s ease !important;
    padding: 8px 14px !important;
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: var(--primary-color) !important;
    color: white !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* Keep examples section visible with better styling */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 20px !important;
    padding: 15px !important;
    border-top: 1px solid var(--border-color) !important;
    background-color: #f9fafc !important;
    border-radius: 8px !important;
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px !important;
}

::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb {
    background: var(--primary-color) !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb:hover {
    background: #005b8c !important;
}

/* Custom copyright footer */
body::after {
    content: "© Priyanshu Khandelwal 2025. All rights reserved.";
    display: block;
    text-align: center;
    padding: 15px 0;
    color: var(--dark-color);
    font-size: 14px;
    border-top: 1px solid var(--border-color);
    margin-top: 20px;
    background: linear-gradient(to right, rgba(0, 119, 181, 0.05), rgba(0, 119, 181, 0.1), rgba(0, 119, 181, 0.05));
}

/* Animation for messages */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
}

.message {
    animation: fadeIn 0.3s ease-out forwards !important;
}

/* Responsive design improvements */
@media (max-width: 768px) {
    .gradio-container {
        border-radius: 0 !important;
    }
    
    .examples button {
        width: 100% !important;
        margin: 5px 0 !important;
    }
}
"""

custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue - your existing color */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Only hide specific footer elements */
footer a[href*="gradio"], 
.footer a[href*="gradio"],
a[href*="github.com/gradio-app/gradio"],
.footer-links,
.versions {
    display: none !important;
}

/* Hide the "Built with Gradio" text specifically */
footer > div:last-child, 
div[class*="footer-links"],
div:has(> a[href*="gradio"]) {
    display: none !important;
}

/* Hide "Use via API" button and related elements */
a[id*="api"], 
a[class*="api"],
button[id*="api"],
button[class*="api"],
div[id*="api"],
div[class*="api"],
.api-btn {
    display: none !important;
}

/* Hide View API specifically */
a:has(span:contains("View API")),
button:has(span:contains("View API")),
div:has(span:contains("View API")) {
    display: none !important;
}

/* Ensure all API elements are hidden */
[data-testid*="api"] {
    display: none !important;
}

/* Body styling */
body {
    padding-bottom: 10px !important;
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--light-color) !important;
    color: var(--dark-color) !important;
}

/* Container styling */
.gradio-container {
    min-height: 450px !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow) !important;
    background-color: white !important;
}

/* ===== CRITICAL: INCREASE CHAT AREA HEIGHT ===== */
/* Target the chat area and make it much taller */
.gradio-chatbot {
    height: 500px !important; /* Fixed height */
    min-height: 500px !important;
    max-height: 70vh !important; /* Or use viewport height for responsive sizing */
}

/* Make the message container scrollable and taller */
.message-container, .messages, .chatbot, .chat-area, [class*="message-container"] {
    height: 450px !important;
    min-height: 450px !important;
    overflow-y: auto !important;
}

/* Force all containers to respect the height */
.gradio-container [class*="chatbot"] > div {
    height: auto !important;
    min-height: 450px !important;
}

/* Chat area styling */
.chat-container, .message-container {
    border-radius: 8px !important;
    background-color: white !important;
}

/* User messages */
.user-message, .message-user {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 12px 12px 2px 12px !important;
    padding: 10px 14px !important;
}

/* Bot messages */
.bot-message, .message-bot, .message-assistant {
    background-color: #f0f2f5 !important;
    color: var(--dark-color) !important;
    border-radius: 12px 12px 12px 2px !important;
    border-left: 3px solid var(--primary-color) !important;
    padding: 10px 14px !important;
}

/* Chat input area */
textarea, input[type="text"] {
    border-radius: 8px !important;
    border: 1px solid var(--border-color) !important;
    padding: 12px !important;
    transition: all 0.3s ease !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--primary-color) !important;
    box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2) !important;
    outline: none !important;
}

/* Make the submit button stand out more */
button[data-testid="submit"] {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    transition: all 0.2s ease !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

button[data-testid="submit"]:hover {
    background-color: #005b8c !important; /* Darker shade on hover */
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(0, 119, 181, 0.4) !important;
}

/* Title styling */
h1, h2, h3, .title {
    color: var(--primary-color) !important;
    font-weight: 600 !important;
}

/* Enhanced example buttons styling */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 6px !important;
    margin: 5px !important;
    transition: all 0.2s ease !important;
    padding: 8px 14px !important;
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: var(--primary-color) !important;
    color: white !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* Keep examples section visible with better styling */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 20px !important;
    padding: 15px !important;
    border-top: 1px solid var(--border-color) !important;
    background-color: #f9fafc !important;
    border-radius: 8px !important;
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px !important;
}

::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb {
    background: var(--primary-color) !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb:hover {
    background: #005b8c !important;
}

/* Custom copyright footer */
body::after {
    content: "© Priyanshu Khandelwal 2025. All rights reserved.";
    display: block;
    text-align: center;
    padding: 15px 0;
    color: var(--dark-color);
    font-size: 14px;
    border-top: 1px solid var(--border-color);
    margin-top: 20px;
    background: linear-gradient(to right, rgba(0, 119, 181, 0.05), rgba(0, 119, 181, 0.1), rgba(0, 119, 181, 0.05));
}

/* Animation for messages */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
}

.message {
    animation: fadeIn 0.3s ease-out forwards !important;
}

/* Ensure proper scrolling */
.scrollable {
    overflow-y: auto !important;
}

/* Responsive design improvements */
@media (max-width: 768px) {
    .gradio-container {
        border-radius: 0 !important;
    }
    
    .examples button {
        width: 100% !important;
        margin: 5px 0 !important;
    }
    
    /* Adjust chat height for mobile */
    .gradio-chatbot {
        height: 60vh !important; /* Use viewport height on mobile */
    }
}
"""
custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue - your existing color */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Only hide specific footer elements */
footer a[href*="gradio"], 
.footer a[href*="gradio"],
a[href*="github.com/gradio-app/gradio"],
.footer-links,
.versions {
    display: none !important;
}

/* Hide the "Built with Gradio" text specifically */
footer > div:last-child, 
div[class*="footer-links"],
div:has(> a[href*="gradio"]) {
    display: none !important;
}

/* Hide "Use via API" button and related elements */
a[id*="api"], 
a[class*="api"],
button[id*="api"],
button[class*="api"],
div[id*="api"],
div[class*="api"],
.api-btn {
    display: none !important;
}

/* Hide View API specifically */
a:has(span:contains("View API")),
button:has(span:contains("View API")),
div:has(span:contains("View API")) {
    display: none !important;
}

/* Ensure all API elements are hidden */
[data-testid*="api"] {
    display: none !important;
}

/* Body styling with reduced font size */
body {
    padding-bottom: 10px !important;
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--light-color) !important;
    color: var(--dark-color) !important;
    font-size: 14px !important; /* Reduced base font size */
}

/* Container styling */
.gradio-container {
    min-height: 450px !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow) !important;
    background-color: white !important;
}

/* ===== CRITICAL: INCREASE CHAT AREA HEIGHT ===== */
/* Target the chat area and make it much taller */
.gradio-chatbot {
    height: 500px !important; /* Fixed height */
    min-height: 500px !important;
    max-height: 70vh !important; /* Or use viewport height for responsive sizing */
}

/* Make the message container scrollable and taller */
.message-container, .messages, .chatbot, .chat-area, [class*="message-container"] {
    height: 450px !important;
    min-height: 450px !important;
    overflow-y: auto !important;
}

/* Force all containers to respect the height */
.gradio-container [class*="chatbot"] > div {
    height: auto !important;
    min-height: 450px !important;
}

/* Chat area styling */
.chat-container, .message-container {
    border-radius: 8px !important;
    background-color: white !important;
}

/* User messages with reduced font size */
.user-message, .message-user {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 12px 12px 2px 12px !important;
    padding: 8px 12px !important; /* Reduced padding */
    font-size: 14px !important; /* Reduced font size */
    margin-bottom: 6px !important; /* Reduced margin */
}

/* Bot messages with reduced font size */
.bot-message, .message-bot, .message-assistant {
    background-color: #f0f2f5 !important;
    color: var(--dark-color) !important;
    border-radius: 12px 12px 12px 2px !important;
    border-left: 3px solid var(--primary-color) !important;
    padding: 8px 12px !important; /* Reduced padding */
    font-size: 14px !important; /* Reduced font size */
    margin-bottom: 6px !important; /* Reduced margin */
}

/* Make the message spacing more compact */
.message {
    margin-bottom: 6px !important;
}

/* Chat input area with reduced size */
textarea, input[type="text"] {
    border-radius: 8px !important;
    border: 1px solid var(--border-color) !important;
    padding: 10px !important; /* Reduced padding */
    transition: all 0.3s ease !important;
    font-size: 14px !important; /* Reduced font size */
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--primary-color) !important;
    box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2) !important;
    outline: none !important;
}

/* Make the submit button stand out more but smaller */
button[data-testid="submit"] {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 14px !important; /* Reduced padding */
    transition: all 0.2s ease !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
    font-size: 14px !important; /* Reduced font size */
}

button[data-testid="submit"]:hover {
    background-color: #005b8c !important; /* Darker shade on hover */
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(0, 119, 181, 0.4) !important;
}

/* Title styling with smaller size */
h1, h2, h3, .title {
    color: var(--primary-color) !important;
    font-weight: 600 !important;
    font-size: 18px !important; /* Reduced title size */
}

/* More compact buttons */
button {
    padding: 6px 12px !important;
    font-size: 13px !important;
}

/* Enhanced example buttons styling with smaller size */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 6px !important;
    margin: 4px !important; /* Reduced margin */
    transition: all 0.2s ease !important;
    padding: 6px 12px !important; /* Reduced padding */
    font-size: 13px !important; /* Reduced font size */
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: var(--primary-color) !important;
    color: white !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* More compact examples section */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 15px !important; /* Reduced margin */
    padding: 10px !important; /* Reduced padding */
    border-top: 1px solid var(--border-color) !important;
    background-color: #f9fafc !important;
    border-radius: 8px !important;
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 6px !important; /* Narrower scrollbar */
}

::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb {
    background: var(--primary-color) !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb:hover {
    background: #005b8c !important;
}

/* Custom copyright footer with smaller font */
body::after {
    content: "© Priyanshu Khandelwal 2025. All rights reserved.";
    display: block;
    text-align: center;
    padding: 10px 0; /* Reduced padding */
    color: var(--dark-color);
    font-size: 12px !important; /* Reduced font size */
    border-top: 1px solid var(--border-color);
    margin-top: 15px; /* Reduced margin */
    background: linear-gradient(to right, rgba(0, 119, 181, 0.05), rgba(0, 119, 181, 0.1), rgba(0, 119, 181, 0.05));
}

/* Animation for messages */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
}

.message {
    animation: fadeIn 0.3s ease-out forwards !important;
}

/* Ensure proper scrolling */
.scrollable {
    overflow-y: auto !important;
}

/* Responsive design improvements */
@media (max-width: 768px) {
    .gradio-container {
        border-radius: 0 !important;
    }
    
    .examples button {
        width: 100% !important;
        margin: 3px 0 !important; /* Even smaller margins on mobile */
    }
    
    /* Adjust chat height for mobile */
    .gradio-chatbot {
        height: 60vh !important; /* Use viewport height on mobile */
    }
    
    /* Slightly larger font on mobile for readability */
    .user-message, .message-user, .bot-message, .message-bot, .message-assistant {
        font-size: 14px !important; 
    }
}
"""
custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue - your existing color */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Only hide specific footer elements */
footer a[href*="gradio"], 
.footer a[href*="gradio"],
a[href*="github.com/gradio-app/gradio"],
.footer-links,
.versions {
    display: none !important;
}

/* Hide the "Built with Gradio" text specifically */
footer > div:last-child, 
div[class*="footer-links"],
div:has(> a[href*="gradio"]) {
    display: none !important;
}

/* Hide "Use via API" button and related elements */
a[id*="api"], 
a[class*="api"],
button[id*="api"],
button[class*="api"],
div[id*="api"],
div[class*="api"],
.api-btn {
    display: none !important;
}

/* Hide View API specifically */
a:has(span:contains("View API")),
button:has(span:contains("View API")),
div:has(span:contains("View API")) {
    display: none !important;
}

/* Ensure all API elements are hidden */
[data-testid*="api"] {
    display: none !important;
}

/* Body styling with reduced font size */
body {
    padding-bottom: 10px !important;
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--light-color) !important;
    color: var(--dark-color) !important;
    font-size: 14px !important; /* Reduced base font size */
}

/* Container styling */
.gradio-container {
    min-height: 450px !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow) !important;
    background-color: white !important;
}

/* ===== CRITICAL: INCREASE CHAT AREA HEIGHT ===== */
/* Target the chat area and make it much taller */
.gradio-chatbot {
    height: 600px !important; /* Increased fixed height */
    min-height: 600px !important;
    max-height: 75vh !important; /* Or use viewport height for responsive sizing */
}

/* Make the message container scrollable and taller */
.message-container, .messages, .chatbot, .chat-area, [class*="message-container"] {
    height: 550px !important;
    min-height: 550px !important;
    overflow-y: auto !important;
}

/* Force all containers to respect the height */
.gradio-container [class*="chatbot"] > div {
    height: auto !important;
    min-height: 550px !important;
}

/* Chat area styling */
.chat-container, .message-container {
    border-radius: 8px !important;
    background-color: white !important;
}

/* User messages with reduced font size */
.user-message, .message-user {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 12px 12px 2px 12px !important;
    padding: 8px 12px !important; /* Reduced padding */
    font-size: 13px !important; /* Further reduced font size */
    margin-bottom: 6px !important; /* Reduced margin */
}

/* Bot messages with reduced font size */
.bot-message, .message-bot, .message-assistant {
    background-color: #f0f2f5 !important;
    color: var(--dark-color) !important;
    border-radius: 12px 12px 12px 2px !important;
    border-left: 3px solid var(--primary-color) !important;
    padding: 8px 12px !important; /* Reduced padding */
    font-size: 13px !important; /* Further reduced font size */
    margin-bottom: 6px !important; /* Reduced margin */
}

/* Make the message spacing more compact */
.message {
    margin-bottom: 6px !important;
}

/* ===== HIDE CONTROL BUTTONS (Retry, Undo, Clear) ===== */
.controls-container, 
[class*="btn-container"],
[id*="component-4"], 
.retry-btn, 
.undo-btn, 
.clear-btn,
button[aria-label="Retry"],
button[aria-label="Undo"],
button[aria-label="Clear"],
div:has(> button[aria-label="Retry"]),
div:has(> button[aria-label="Clear"]) {
    display: none !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    visibility: hidden !important;
}

/* Chat input area with reduced size */
textarea, input[type="text"] {
    border-radius: 8px !important;
    border: 1px solid var(--border-color) !important;
    padding: 10px !important; /* Reduced padding */
    transition: all 0.3s ease !important;
    font-size: 14px !important; /* Reduced font size */
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--primary-color) !important;
    box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2) !important;
    outline: none !important;
}

/* Make the submit button stand out more but smaller */
button[data-testid="submit"] {
    background-color: var(--primary-color) !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 14px !important; /* Reduced padding */
    transition: all 0.2s ease !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
    font-size: 14px !important; /* Reduced font size */
}

button[data-testid="submit"]:hover {
    background-color: #005b8c !important; /* Darker shade on hover */
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(0, 119, 181, 0.4) !important;
}

/* Title styling with smaller size */
h1, h2, h3, .title {
    color: var(--primary-color) !important;
    font-weight: 600 !important;
    font-size: 18px !important; /* Reduced title size */
}

/* More compact buttons */
button {
    padding: 6px 12px !important;
    font-size: 13px !important;
}

/* Enhanced example buttons styling with smaller size */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 6px !important;
    margin: 4px !important; /* Reduced margin */
    transition: all 0.2s ease !important;
    padding: 6px 12px !important; /* Reduced padding */
    font-size: 13px !important; /* Reduced font size */
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: var(--primary-color) !important;
    color: white !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(0, 119, 181, 0.3) !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* More compact examples section */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 15px !important; /* Reduced margin */
    padding: 10px !important; /* Reduced padding */
    border-top: 1px solid var(--border-color) !important;
    background-color: #f9fafc !important;
    border-radius: 8px !important;
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 6px !important; /* Narrower scrollbar */
}

::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb {
    background: var(--primary-color) !important;
    border-radius: 10px !important;
}

::-webkit-scrollbar-thumb:hover {
    background: #005b8c !important;
}

/* Custom copyright footer with smaller font */
body::after {
    content: "© Priyanshu Khandelwal 2025. All rights reserved.";
    display: block;
    text-align: center;
    padding: 10px 0; /* Reduced padding */
    color: var(--dark-color);
    font-size: 12px !important; /* Reduced font size */
    border-top: 1px solid var(--border-color);
    margin-top: 15px; /* Reduced margin */
    background: linear-gradient(to right, rgba(0, 119, 181, 0.05), rgba(0, 119, 181, 0.1), rgba(0, 119, 181, 0.05));
}

/* Animation for messages */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
}

.message {
    animation: fadeIn 0.3s ease-out forwards !important;
}

/* Ensure proper scrolling */
.scrollable {
    overflow-y: auto !important;
}

/* Responsive design improvements */
@media (max-width: 768px) {
    .gradio-container {
        border-radius: 0 !important;
    }
    
    .examples button {
        width: 100% !important;
        margin: 3px 0 !important; /* Even smaller margins on mobile */
    }
    
    /* Adjust chat height for mobile */
    .gradio-chatbot {
        height: 70vh !important; /* Use viewport height on mobile */
    }
    
    /* Slightly larger font on mobile for readability */
    .user-message, .message-user, .bot-message, .message-bot, .message-assistant {
        font-size: 10px !important; 
    }
}
"""

# gr.ChatInterface(
#     fn=chat,
#     title="PK's Bot",
#     description="Ask anything about Priyanshu Khandelwal.",
#     examples=[
#         # ["What are your hobbies?"],
#         # ['What is your contact information?'],
#         # ["What is your summary?"],
#         ["What is your LinkedIn profile?"],
#         # ["What is your GitHub profile?"],
#         # ["What is your experience?"],
#         # ["What is your education background?"],
#         # ["What are your skills?"],
#         # ["What are your interests?"]
#     ],
#     # theme=gr.themes.Base(
#     #     primary_hue="blue",
#     #     secondary_hue="green",
#     #     font="Verdana",
#     # ),
#     css=custom_css,
    
# ).launch(share=False)

custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Body styling with reduced font size */
body {
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 14px !important;
}

/* Center the container and maintain proper spacing */
.gradio-container {
    margin: 0 auto !important;
    padding: 10px !important;
    max-width: 100% !important;
}

/* COMPACT EXAMPLES SECTION - properly centered */
div[id*="component-examples"],
div[class*="examples"],
.examples,
div[data-testid="examples"] {
    margin: 10px auto 5px auto !important;
    padding: 5px !important;
    border-top: 1px solid var(--border-color) !important;
    background-color: transparent !important;
    text-align: center !important;
    width: 100% !important;
}

/* Make example buttons smaller and properly spaced */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button,
div[data-testid="examples"] button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 4px !important;
    margin: 3px !important;
    transition: all 0.2s ease !important;
    padding: 4px 10px !important;
    font-size: 12px !important;
    height: auto !important;
    min-height: 28px !important;
    line-height: 1.2 !important;
    display: inline-block !important;
}

/* Examples heading - centered */
div[id*="component-examples"] h3,
div[class*="examples"] h3,
.examples h3,
div[data-testid="examples"] h3 {
    font-size: 13px !important;
    margin: 0 0 5px 0 !important;
    padding: 3px 0 !important;
    color: #666 !important;
    text-align: center !important;
    width: 100% !important;
}

/* Center the button container */
div[id*="component-examples"] > div,
div[class*="examples"] > div,
.examples > div,
div[data-testid="examples"] > div {
    margin: 0 auto !important;
    padding: 0 !important;
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 5px !important;
    justify-content: center !important; /* Center buttons */
    width: 100% !important;
}

/* Make the textbox/submit area properly aligned */
.input-container, 
.input-row, 
.submit-container,
div[data-testid="textbox"] {
    margin: 5px auto !important;
    padding: 0 !important;
    width: 100% !important;
}

/* Format the input area */
.input-row {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
}

textarea, input[type="text"] {
    border-radius: 6px !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px 12px !important;
    min-height: auto !important;
    font-size: 14px !important;
    width: 100% !important;
}

/* Make submit button match screenshot */
button[data-testid="submit"] {
    background-color: #FBD38D !important; /* Match your screenshot color */
    color: #E67E22 !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 8px 15px !important;
    height: auto !important;
    min-height: 38px !important;
    font-size: 14px !important;
    width: auto !important;
    text-align: center !important;
}

/* Fix chat container */
.gradio-chatbot {
    margin: 0 auto !important;
    width: 100% !important;
}

/* Hide footer */
footer, .footer {
    display: none !important;
}

/* Hide API elements */
[id*="api"], [class*="api"] {
    display: none !important;
}
"""
custom_css = """
/* Theme colors */
:root {
    --primary-color: #0077B5;       /* LinkedIn blue */
    --secondary-color: #4caf50;     /* Green accent */
    --dark-color: #333333;          /* Dark text */
    --light-color: #f5f5f5;         /* Light background */
    --border-color: #e0e0e0;        /* Border color */
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);  /* Subtle shadow */
}

/* Body styling with reduced font size */
body {
    font-family: 'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 14px !important;
}

/* Center the container and maintain proper spacing */
.gradio-container {
    margin: 0 auto !important;
    padding: 10px !important;
    max-width: 100% !important;
}

/* MAKE CHATBOT TALLER - key change */
.gradio-chatbot, 
.wrap, 
[data-testid="chatbot"],
[class*="chatbot"] {
    height: 500px !important; /* Increased height */
    min-height: 500px !important;
    overflow-y: auto !important;
}

/* Style the message container to be taller */
.message-container,
.messages,
.chatbox-messages,
[class*="message-container"] {
    height: auto !important;
    min-height: 450px !important;
    max-height: none !important;
}

/* COMPACT EXAMPLES SECTION - properly centered */
div[id*="component-examples"],
div[class*="examples"],
.examples,
div[data-testid="examples"] {
    margin: 10px auto 5px auto !important;
    padding: 5px !important;
    border-top: 1px solid var(--border-color) !important;
    background-color: transparent !important;
    text-align: center !important;
    width: 100% !important;
}

/* Make example buttons smaller and properly spaced */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button,
div[data-testid="examples"] button {
    border: 1px solid var(--primary-color) !important;
    color: var(--primary-color) !important;
    background-color: white !important;
    border-radius: 4px !important;
    margin: 3px !important;
    transition: all 0.2s ease !important;
    padding: 4px 10px !important;
    font-size: 12px !important;
    height: auto !important;
    min-height: 28px !important;
    line-height: 1.2 !important;
    display: inline-block !important;
}

/* Examples heading - centered */
div[id*="component-examples"] h3,
div[class*="examples"] h3,
.examples h3,
div[data-testid="examples"] h3 {
    font-size: 13px !important;
    margin: 0 0 5px 0 !important;
    padding: 3px 0 !important;
    color: #666 !important;
    text-align: center !important;
    width: 100% !important;
}

/* Center the button container */
div[id*="component-examples"] > div,
div[class*="examples"] > div,
.examples > div,
div[data-testid="examples"] > div {
    margin: 0 auto !important;
    padding: 0 !important;
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 5px !important;
    justify-content: center !important; /* Center buttons */
    width: 100% !important;
}

/* Make the textbox/submit area properly aligned */
.input-container, 
.input-row, 
.submit-container,
div[data-testid="textbox"] {
    margin: 5px auto !important;
    padding: 0 !important;
    width: 100% !important;
}

/* Format the input area */
.input-row {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
}

textarea, input[type="text"] {
    border-radius: 6px !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px 12px !important;
    min-height: auto !important;
    font-size: 14px !important;
    width: 100% !important;
}

/* Make submit button match screenshot */
button[data-testid="submit"] {
    background-color: #FBD38D !important; /* Match your screenshot color */
    color: #E67E22 !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 8px 15px !important;
    height: auto !important;
    min-height: 38px !important;
    font-size: 14px !important;
    width: auto !important;
    text-align: center !important;
}

/* Style chat messages to be more readable */
.user-message, .message-user {
    background-color: #FFF8E6 !important; /* Light orange background for user messages */
    padding: 10px 15px !important;
    border-radius: 10px !important;
    margin: 5px 0 !important;
    border: 1px solid #FBD38D !important;
}

.bot-message, .message-bot, .message-assistant {
    background-color: #F8F9FA !important; /* Light gray background for bot messages */
    padding: 10px 15px !important;
    border-radius: 10px !important;
    margin: 5px 0 !important;
    border: 1px solid #E0E0E0 !important;
}

/* Fix chat container */
.gradio-chatbot {
    margin: 0 auto !important;
    width: 100% !important;
}

/* Hide footer */
footer, .footer {
    display: none !important;
}

/* Hide API elements */
[id*="api"], [class*="api"] {
    display: none !important;
}

/* Better scrollbar */
::-webkit-scrollbar {
    width: 6px !important;
}

::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
}

::-webkit-scrollbar-thumb {
    background: #c1c1c1 !important;
    border-radius: 10px !important;
}
"""

gr.ChatInterface(
    fn=chat,
    title="PK's Bot",
    description="Ask anything about Priyanshu Khandelwal.",
    examples=[
        ["What is your LinkedIn/Github profile?"],
        ["What is your experience summary?"],
    ],
    css=custom_css,
).launch(share=False)

# gr.ChatInterface(
#     fn=chat,
#     title="PK's Bot",
#     description="Ask anything about Priyanshu Khandelwal.",
#     examples=[
#         ["What is your LinkedIn profile?"],
#     ],
#     css=custom_css,
# ).launch(share=False)


