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


gr.ChatInterface(
    fn=chat,
    title="PK Pulse",
    description="A chat interface for PK Pulse. Ask anything about Priyanshu Khandelwal.",
    examples=[
        ["What are your hobbies?"],
        ['What is your contact information?'],
        ["What is your summary?"],
        ["What is your LinkedIn profile?"],
        ["What is your GitHub profile?"],
        ["What is your experience?"],
        ["What is your education background?"],
        ["What are your skills?"],
        ["What are your interests?"]
    ],
    theme="compact",
).launch(share=True)


