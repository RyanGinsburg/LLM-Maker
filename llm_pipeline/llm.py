from flask import Flask, render_template, request, redirect, url_for
from openai import OpenAI
from datetime import datetime
import json
import os
import signal
import time

# Variables set by the user
api_key = '<<api key>>'
dataset_file_name = 'shakespeare.jsonl' #Name of the dataset used for fine-tuning in the datasets folder
llm_model = "gpt-3.5-turbo-1106"  # Model to be fine-tuned

client = OpenAI(api_key=api_key)

# Retrieve the list of files and fine-tuning jobs
files = client.files.list()
jobs = client.fine_tuning.jobs.list()

dataset_file_path = f"datasets/samples/{dataset_file_name}"

# Gets system message from dataset
with open(dataset_file_path, 'r') as file:
    first_line = file.readline()
    # Parse the first line as a JSON object
    data = json.loads(first_line)
    
    # Extract the system message
    system_message = None
    for message in data['messages']:
        if message['role'] == 'system':
            system_message = message['content']
            break  # No need to continue since we only need the first one

# Print the system message
print("System Message:", system_message)

# Initialize variables for file ID model name
model_name = None
file_id = None

# Check if the dataset file is already uploaded
for file in files.data:
    if file.filename == dataset_file_name:
        print("File found")
        file_id = file.id
        print("File ID: " + str(file_id))
        print("ID gathered")
        break

# If the file is not found, upload it
if file_id is None:
    print("Dataset file not found")
    response = client.files.create(
        file=open(dataset_file_path, "rb"),
        purpose="fine-tune"
    )
    file_id = response.id
    print("Dataset file uploaded and ID now gathered")

# Check if a fine-tuned model already exists for the dataset
for job in jobs.data:
    if job.training_file == file_id and job.fine_tuned_model is not None:
        print("Fine-tuned model found")
        model_name = job.fine_tuned_model
        print("Model name: " + str(model_name))
        exit = False
        break

# If no fine-tuned model is found, start a new fine-tuning job
if model_name is None:
    print("Fine-tuned model not found")
    
    #if the dataset name is too long to be a suffix, short to 18 characters
    if len(dataset_file_name) > 18:
        dataset_file_name = dataset_file_name[:18]
    
    fine_tune_response = client.fine_tuning.jobs.create(
        training_file=file_id,
        model=llm_model,
        suffix=dataset_file_name
    )
    model_id = fine_tune_response.id
    print("Started fine-tuning job")

    # Monitor the fine-tuning process
    while True:
        # Fetch the status of the fine-tuning job
        fine_tune_status = client.fine_tuning.jobs.retrieve(model_id)
        
        # Check the status
        status = fine_tune_status.status
        print(f"Current fine-tuning status: {status}")
        
        if status == "succeeded":
            model_name = client.fine_tuning.jobs.retrieve(model_id).fine_tuned_model
            print("used model_name: " + str(model_name))
            exit = False
            break
        
        elif status == "failed" or status == "cancelled":
            exit = True
            break
        
        # Wait for a short period before checking the status again
        time.sleep(30)

# If the fine-tuning process was successful or a model was found, proceed to use the model
if not exit:
    print("Ready to use fine-tuned model")
    # Prompt the user to choose between terminal and local web interface
    while True:
        user_input = input("Use fine-tuned model in terminal (T) or local site (L) (T or L): ").strip().lower()
        if user_input == 't':
            terminal = True
            break
        elif user_input == 'l':
            terminal = False
            break
        else:
            print("That's not a valid answer. Try again.")
            
    #terminal interface
    if terminal:
        print("Enter the word 'exit' to stop chatting")
        while True:
            message = input('User: ')
            if message.strip().lower() == 'exit':
                print("Program exited")
                break
            else:
            
                # Generate a response using the fine-tuned model
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": message}
                    ]
                )
                print(f"Assistant: {completion.choices[0].message.content}")
                print("______________________________________________________________________________________")
                
    #local web interface
    else:
        # Create a Flask web application for local use
        app = Flask(__name__, static_folder='frontend/static', template_folder='frontend/templates')

        chat_history = []  # Store chat history

        @app.route('/', methods=['GET', 'POST'])
        def index():
            global chat_history
            if request.method == 'POST':
                if 'exit' in request.form:
                    os.kill(os.getpid(), signal.SIGINT)  # Stops the Flask server and exits the program
                if 'message' in request.form and request.form['message'].strip():
                    user_message = request.form['message']
                    # Generate a response using the fine-tuned model
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ]
                    )
                    time = datetime.now().strftime('%I:%M %p')  # Format the current time
                    response = completion.choices[0].message.content
                    chat_history.insert(0, {'user': user_message, 'response': response, 'time': time})
                    return redirect(url_for('index'))  # Prevents the most recent message from duplicating after refreshing the page
            return render_template('index.html', chat_history=chat_history)

        if __name__ == '__main__':
            app.run(debug=True, use_reloader=False)  # Prevents code from executing twice
