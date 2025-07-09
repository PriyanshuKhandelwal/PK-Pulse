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
You are answering all the question on {name}'s behalf on {name}'s website. For your response , first add response in very short form in upper caps, then add in detail (if required).
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


# Define custom CSS to hide unwanted elements and style the chat
# Define custom CSS to hide unwanted elements but keep examples
custom_css = """
/* Hide footer elements */
footer, .footer, footer *, .footer-links, .versions {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Hide "Use via API" button and related elements */
[id*="api"], [class*="api"], #component-0 > div.mb-12 {
    display: none !important;
}

/* Remove extra padding at the bottom */
body {
    padding-bottom: 0 !important;
}

/* Make the chat area take more vertical space */
.gradio-container {
    min-height: 450px !important;
}

/* Improve the chat container */
.gr-chatbot {
    min-height: 400px !important;
}

/* Remove Gradio branding and "Built with Gradio" */
.gr-footer, .gr-footer-attribution {
    display: none !important;
}

/* Hide all API-related buttons */
button[id*="api"], a[id*="api"] {
    display: none !important;
}

/* Make chat interface cleaner */
.gradio-container {
    max-width: 100% !important;
}

/* Make the submit button stand out more */
.submit-btn {
    background-color: #0077B5 !important;
}

/* Add a professional look and feel */
.chatbot-header {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Style the examples section nicely */
.examples {
    margin-top: 10px !important;
    border-top: 1px solid #eaeaea !important;
    padding-top: 15px !important;
}

/* Style example buttons */
.examples button {
    border-radius: 5px !important;
    transition: all 0.2s ease !important;
    border: 1px solid #0077B5 !important;
    color: #0077B5 !important;
}

.examples button:hover {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Hide only the bottom parts of the page that have API info */
#component-0 > div:last-child:not(.examples) {
    display: none !important;
}
"""
# Define custom CSS to hide unwanted elements but keep examples
custom_css = """
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
a[id*="api-btn"], 
button[id*="api-btn"],
div[id*="api-btn"],
div.mt-12 {
    display: none !important;
}

/* Remove extra padding at the bottom */
body {
    padding-bottom: 10px !important;
}

/* Make the chat area take more vertical space */
.gradio-container {
    min-height: 450px !important;
}

/* Make the submit button stand out more */
button[data-testid="submit"] {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Enhanced example buttons styling */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid #0077B5 !important;
    color: #0077B5 !important;
    border-radius: 4px !important;
    margin: 5px !important;
    transition: all 0.2s ease !important;
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* Keep examples section visible */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 15px !important;
    padding-top: 15px !important;
    border-top: 1px solid #eaeaea !important;
}
"""
# Define custom CSS to hide unwanted elements but keep examples and add custom copyright
custom_css = """
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

/* Remove extra padding at the bottom */
body {
    padding-bottom: 10px !important;
}

/* Make the chat area take more vertical space */
.gradio-container {
    min-height: 450px !important;
}

/* Make the submit button stand out more */
button[data-testid="submit"] {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Enhanced example buttons styling */
div[id*="component-examples"] button,
div[class*="examples"] button,
.examples button {
    border: 1px solid #0077B5 !important;
    color: #0077B5 !important;
    border-radius: 4px !important;
    margin: 5px !important;
    transition: all 0.2s ease !important;
}

div[id*="component-examples"] button:hover,
div[class*="examples"] button:hover,
.examples button:hover {
    background-color: #0077B5 !important;
    color: white !important;
}

/* Hide any other footer or attribution elements */
[class*="footer-attribution"],
[id*="footer-attribution"] {
    display: none !important;
}

/* Keep examples section visible */
div[id*="component-examples"],
div[class*="examples"],
.examples {
    display: block !important;
    visibility: visible !important;
    margin-top: 15px !important;
    padding-top: 15px !important;
    border-top: 1px solid #eaeaea !important;
}

/* Custom copyright footer */
body::after {
    content: "© Priyanshu Khandelwal 2025. All rights reserved.";
    display: block;
    text-align: center;
    padding: 15px 0;
    color: #666;
    font-size: 14px;
    border-top: 1px solid #eaeaea;
    margin-top: 20px;
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

# Create the Gradio chat interface with custom CSS
interface = gr.ChatInterface(
    fn=chat,
    title="PK's Bot",
    description="Ask anything about Priyanshu Khandelwal.",
    examples=[
        ['What is your contact information?'],
        ["What is your summary?"],
        ["What is your LinkedIn profile?"],
    ],
    theme="compact",
    css=custom_css,  # Add the custom CSS here
)

# Launch the interface
interface.launch(share=False)