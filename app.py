from flask import Flask, url_for, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import sqlite3
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import praw
from datetime import datetime
from functools import wraps
import re
import csv
from collections import defaultdict
import os
import json
from openai import OpenAI
import datetime
import shutil

app = Flask(__name__)

#variables set by user
app.secret_key = '<<app.secret_key>>' 
app.config['MAIL_USERNAME'] = '<<email>>' 
app.config['MAIL_PASSWORD'] = '<<mail password>>' 
api_key = '<<api key>>' 
reddit_client_id='<<reddit client id>>'
reddit_client_secret='<<reddit client secret>>'
reddit_user_agent='<<reddit user_agent>>'


# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_DEFAULT_SENDER'] = 'llmprofiles@gmail.com'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
app.config['UPLOAD_EXTENSIONS'] = ['.txt', '.csv']

mail = Mail(app)

s = URLSafeTimedSerializer(app.secret_key)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db_name = 'ladder.db'
files = 'storage/files'

valid_emails = [
    "@gmail.com",
    "@yahoo.com",
    "@outlook.com",
    "@hotmail.com",
    "@icloud.com"
]

statuses = [
    "Name Created",
    "Data Gathered",
    "Uploading Files",
    "Fine-tuning",
    "Success",
    "Cancelled",
    "Failed"
]

llm_model = "gpt-3.5-turbo-1106"  # Model to be fine-tuned

client = OpenAI(api_key=api_key)
system_message = 'You are a converstional chatbot whoose name is '
output_dir = 'storage/jsonl/'

def check(username):
    reddit = praw.Reddit(
        client_id='cENPvSaGI90lM---PzSAQA',
        client_secret='S-nvvEqsAzhwKomQyMFChVui2O-Xzw',
        user_agent='redditcptest',
    )
    try: 
        redditor = reddit.redditor(username)
        id = redditor.id
        return False
    except:
        return True

def WhatsApp_data(file_name):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Load the chat file
    with open(file_name, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Define regex patterns
    message_pattern = re.compile(r'^\[(\d{1,2}/\d{1,2}/\d{2,4}), \d{1,2}:\d{2}:\d{2} ?[AP]M\] (.*?): (.*)')
    link_pattern = re.compile(r'(https?://\S+)')

    user_data = defaultdict(set)

    # Process the lines
    for line in lines:
        match = message_pattern.match(line)
        if match:
            _, username, message = match.groups()
            username = username.replace("~", "").replace(" ", "_").replace(":", "").replace("/", "_")
            if not link_pattern.search(message) and '‎' not in message:
                user_data[username].add(message)

    # Output messages to JSONL files
    return(user_data)

def Discord_data(path):
    for root, dirs, files in os.walk(path):
        # Skip the "avatar" directory
        if "avatar" in dirs:
            dirs.remove("avatar")

        for file in files:
            file_name = os.path.join(root, file)
            try:
                # Ensure the output directory exists
                os.makedirs(output_dir, exist_ok=True)

                # Define regex patterns
                link_pattern = re.compile(r'(https?://\S+)')  # Identify links
                timestamp_pattern = re.compile(r'\[\d{1,2}:\d{2} [AP]M\]')  # Identify timestamps in messages

                user_data = defaultdict(set)  # Use a list to store messages for easier splitting

                # Process the CSV file
                with open(file_name, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        username = row.get('author.global_name')
                        content = row.get('content')

                        if username and content and content.strip():  # Check if content is not null or empty
                            if not link_pattern.search(content):
                                # Split content by timestamp if any
                                split_messages = timestamp_pattern.split(content)
                                for message in split_messages:
                                    message = message.strip()
                                    if message:  # Add only non-empty messages
                                        user_data[username].add(message)
            except:
                pass
        return(user_data)
                                        

def get_user_llms(user_id):
    conn = sqlite3.connect(f'{db_name}')
    cursor = conn.cursor()
    table_name = 'llm_data'

    cursor.execute(f'SELECT name FROM {table_name} WHERE user_id = ?', (user_id,))
    llms = [row[0] for row in cursor.fetchall()]
    conn.close()
    return llms


def reddit_data(username, name, sys_name):
    reddit = praw.Reddit(
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent=reddit_user_agent,
    )
    
    user_data = defaultdict(set)
    
    # Fetch the Redditor object
    redditor = reddit.redditor(username)
    
    # Gather all submissions (posts)
    for submission in redditor.submissions.new(limit=None):
        user_data[name].add(submission.title + ": " + submission.selftext)
    
    # Gather all comments
    for comment in redditor.comments.new(limit=None):
        user_data[name].add(comment.body)
    
    if user_data[name] == set():
        return "no data"
    else:
        name is None
        user = 'reddit'
        compile(user_data, name, user, sys_name)

def compile(user_data, name, user, sys_name): #compiles user_data into jsonl file
    if user != 'reddit':
        new_user_data = defaultdict(set)
        new_user_data[user] = user_data[user]
    else:
        new_user_data = user_data
        
    for username, messages in new_user_data.items():
        
        if name:
            filename = (f'{name}.jsonl')
        else:
            filename = f'{username.replace("~", "").replace(" ", "_").replace(":", "").replace("/", "_")}.jsonl'
        
        file_path = os.path.join(output_dir, filename)
        
        # Load existing messages if the file exists
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    existing_message = json.loads(line).get("message")
                    try:
                        messages.add(existing_message)
                    except:
                        messages.append(existing_message)

        
        # Write all unique messages back to the file
        sys_message = "Simulate the prevous line in this conversation with the same tone and style."
        with open(file_path, 'a', encoding='utf-8') as file:
            for message in messages:
                if message is None:
                    continue
                # Manually escaping any characters if needed
                completion = client.chat.completions.create(
                    model="ft:gpt-3.5-turbo-1106:personal::A3wNB2Mj",
                    messages=[
                        {"role": "system", "content": sys_message},
                        {"role": "user", "content": message}
                    ]
                )
                previous = completion.choices[0].message.content
                
                new_system_message = system_message + sys_name
                
                # This is where we serialize the larger structure
                message_json = json.dumps({
                    "messages": [
                        {"role": "system", "content": new_system_message},
                        {"role": "user", "content": previous},
                        {"role": "assistant", "content": message}
                    ]
                }, ensure_ascii=False)

                file.write(message_json + '\n')
    return(filename)

def apology(message, code=400):
    """Render message as an apology to user."""
    return render_template("apology.html", code=code, message=message), code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def create_llm(user_id, name):
    status = statuses[0]
    conn = sqlite3.connect(f'{db_name}')
    cursor = conn.cursor()
    table_name = 'llm_data'
    cursor.execute(f'SELECT name FROM {table_name} WHERE user_id = ?', (user_id,))
    names = cursor.fetchall()

    for name_tuple in names:
        n = name_tuple[0]  # Correctly extract the name from the tuple
        if n == name or n.lower() == name.lower():
            cursor.execute(f'SELECT id FROM {table_name} WHERE name = ?', (name,))
            row = cursor.fetchone()
            id = row[0]
            log = ['duplicate']
            return id, log

    # Insert new user into the database
    sql_insert = f'''
    INSERT INTO {table_name} (user_id, name, job_status)
    VALUES (?, ?, ?)
    '''
    cursor.execute(sql_insert, (user_id, name, status)) 
    id = cursor.lastrowid
    conn.commit()
    conn.close()
    log = ['']
    return id, log   


@app.route('/delete', methods=["GET", "POST"])
@login_required
def delete():
    if request.method == "POST":
        table_name = 'llm_data'
        id = request.form.get('id')
        
        if id in chat_histories:
            chat_histories[id] = []
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute(f'SELECT name, storage FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchall()
        name = row[0][0]
        storage = row[0][1]
        cursor.execute(f'DELETE FROM {table_name} WHERE id = ?', (id,))
        
        if storage != '' and storage is not None:   
            directory = 'storage/files/'

            # Go through all the files and folders in the directory
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                
                # Check if the file or folder starts with the specified 'id' prefix
                if filename.startswith(id):
                    # If it's a directory, remove the directory and all its contents
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    # If it's a file, remove the file
                    else:
                        os.remove(file_path)

        jsonl_path = (f'storage/jsonl/{name}_{id}.jsonl')
        if os.path.exists(jsonl_path):
            os.remove(jsonl_path)
        # Execute a query to get all rows from your table
        conn.commit()
        conn.close()

        return redirect('/')


@app.route('/info', methods=["GET", "POST"])
@login_required
def info():
    if request.method == "POST":
        table_name = 'llm_data'
        id = request.form.get('id')
        conn = sqlite3.connect(db_name)
        conn.row_factory = sqlite3.Row  # allows access to columns by name
        cursor = conn.cursor()
        
        # Execute a query to get all rows from your table
        cursor.execute(f'SELECT * FROM {table_name} WHERE id = ?', (id,))
        
        # Fetch all rows as a list of dictionaries
        llm_data = cursor.fetchone()
        logs = llm_data[10]
        if logs is None:
            logs = ""
        log = logs.split(',')
        log.reverse()
        name = llm_data[6]
        if name:
            cursor.execute(f'UPDATE {table_name} SET deployable = 1 WHERE id = ?', (id,))
        
        dataset_file_name = llm_data[2]
        if dataset_file_name:
            dataset_file_path = (f'storage/jsonl/{dataset_file_name}.jsonl')
            
            if dataset_file_path.endswith('.jsonl.jsonl'):
                dataset_file_path = dataset_file_path.removesuffix('.jsonl')
            
            with open(dataset_file_path, 'r', encoding='utf-8') as file:
                line_count = sum(1 for _ in file)
        else:
            line_count = 0

        try:
            job_name = llm_data[6]
        except:
            try:
                model_id = llm_data[5]
                if model_id:
                    fine_tune_info = client.fine_tuning.jobs.retrieve(model_id)
                    model_name = fine_tune_info.fine_tuned_model
                    status = fine_tune_info.status
                    if model_name:
                        status = statuses[4]
                        created = fine_tune_info.created_at
                        timestamp = datetime.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
                        cursor.execute(f'UPDATE {table_name} SET job_status = ?, job_name = ?, created = ? WHERE id = ?', (status, model_name, timestamp, id))
                    else:
                        if status == 'failed':
                            status == statuses[6]
                            cursor.execute(f'UPDATE {table_name} SET job_status = ? WHERE id = ?', (status, id))
            except:
                pass
        conn.commit() 
        # Commit any remaining updates (if there are any) and close the connection after the loop
        conn.commit()  # Ensure all pending updates are committed
        conn.close()  # Close the connection after all operations are complete
            
        return render_template("info.html", info = llm_data, log = log, line_count=line_count)


@app.route('/select', methods=["GET", "POST"])
@login_required
def select():
    if request.method == "POST":
        user_id = session["user_id"]
        name = request.form.get("name")
        id, log = create_llm(user_id, name)
        if log == ['duplicate']:
            return apology("This LLM is Already in Use")
        else:
            return render_template('create.html', id=id, name=name, log=log, line_count = 0, fine_tuning = False)
    else:
        return render_template("select.html")


@app.route('/create<id><name>', methods=["GET", "POST"])
@login_required
def create(id, name):
    if request.method == "POST":
        if id:
            id = request.form.get('id')
        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'
        cursor.execute(f'SELECT name, log, jsonl_file_path, job_status FROM {table_name} WHERE id = ?', (id,))
        rows = cursor.fetchone()
        name = rows[0]
        logs = rows[1]
        conn.close()
        
        dataset_file_name = rows[2]
        if dataset_file_name:
            dataset_file_path = (f'storage/jsonl/{dataset_file_name}.jsonl')
            
            if dataset_file_path.endswith('.jsonl.jsonl'):
                dataset_file_path = dataset_file_path.removesuffix('.jsonl')
            
        
            with open(dataset_file_path, 'r', encoding='utf-8') as file:
                line_count = sum(1 for _ in file)
        else:
            line_count = 0
        
        if logs is None:
            logs = ""
        log = logs.split(',')
        log.reverse()
        
        status = rows[3]
        if status == statuses[3]:
            fine_tuning = True
        else:
            fine_tuning = False
        
        return render_template("create.html", id=id, name=name, log=log, line_count=line_count, fine_tuning=fine_tuning)


@app.route('/reddit', methods=["GET", "POST"])
@login_required
def reddit():
    if request.method == "POST":
        id = request.form.get('id')
        username = request.form.get('username')
        if not username:
            return apology("Username required")
        
        if check(username):
            return apology(f'{username} is not a valid usernmae.')
        
        # Format to exclude seconds
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        new = (f'Reddit: {username} - {time}')
        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'
        
        cursor.execute(f'SELECT log, name FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchone()
        
        sys_name = row[1]
        name = (f'{sys_name}_{id}')
        
        # Ensure log is always initialized
        log = ''
        if row and row[0] is not None:
            log = row[0]
        
        log += new + ','
        
        success = reddit_data(username, name, sys_name)
        if success == "no data":
            return apology(f'No data found for {username}')
        
        cursor.execute(f'SELECT jsonl_file_path, job_status FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchone()

        dataset_file_path = (f'storage/jsonl/{name}.jsonl')
            
        with open(dataset_file_path, 'r', encoding='utf-8') as file:
            line_count = sum(1 for _ in file)
        
        status = statuses[1]
        cursor.execute(f'UPDATE {table_name} SET log = ?, job_status = ?, jsonl_file_path = ? WHERE id = ?', (log, status, name, id))
        conn.commit()
        conn.close()
        str_log = log
        return redirect(url_for('reddit', log=str_log, id=id, line_count=line_count, status=status))
    else:
        id = request.args.get('id')
        log = request.args.get('log')
        line_count = int(request.args.get('line_count'))
        status = request.args.get('status')

        if log:
            log = log.split(",")
            log = [entry for entry in log if entry]  # Remove any empty strings
        else:
            log = []  # Ensure log is always initialized
            
        if status == statuses[3]:
            fine_tuning = True
        else:
            fine_tuning = False
        log.reverse()
        
        return render_template("create.html", id=id, log=log, line_count=line_count, fine_tuning=fine_tuning)

    
@app.route('/preview', methods=["GET", "POST"])
@login_required
def preview():
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            return apology("Username Required")
        url = (f'https://www.reddit.com/user/{username}/')
        return redirect(url)
    else:
        return redirect('/reddit')
    

@app.route('/r', methods=["GET", "POST"])
@login_required
def r():
    id = request.form.get("id")
    return render_template('reddit.html', id=id)

@app.route('/discord', methods=["GET", "POST"])
@login_required
def d():
    id = request.form.get("id")
    message = '''
        <p>1. Get the <a href="https://chromewebstore.google.com/detail/discrub/plhdclenpaecffbcefjmpkkbdpkmhhbj?hl=en-US">Discrub</a> chrome extenstion</p>
        <p>2. Open Discord in a browser.</p>
        <p>3. At the top right, click the Discrub icon .</p>
        <p>4. Select the serve and channel name or click the menu button at the top for direct messages.</p>
        <p>5. Click export and export as a CSV file.</p>
        <p>6. Downlaod and extract the folder.</p>
        <p>7. Drag and drop the extracted folder or select from your computer.</p>
    '''
    return render_template('texts.html', id=id, message = message, service_name='Discord')

@app.route('/whatsapp', methods=["GET", "POST"])
@login_required
def w():
    id = request.form.get("id")
    message = '''
        <p>1. Open WhatsApp and go to the chat you want to extract data from.</p>
        <p>2. Go down to export chat and select  the "Without media" option.</p>
        <p>3. Downlaod and extract the file.</p>
        <p>4. Drag and drop the extracted file or select from your computer.</p>
    '''
    return render_template('texts.html', id=id, message = message, service_name='WhatsApp')


@app.route('/cancell', methods=["GET", "POST"])
@login_required
def cancell():
    id = request.form.get("id")
    conn = sqlite3.connect(f'{db_name}')
    cursor = conn.cursor()
    table_name = 'llm_data'
    cursor.execute(f'SELECT name, job_id FROM {table_name} WHERE id = ?', (id,))
    row = cursor.fetchone()
    name = row[0]
    job_id = row[1]
    client.fine_tuning.jobs.cancel(job_id)
    status = statuses[5]
    cursor.execute(f'UPDATE {table_name} SET job_status = ? WHERE id = ?', (status, id))
    conn.commit()
    conn.close()
    flash(f'Fine-tuing Cancelled for {name}', 'success')
    return redirect(url_for('index'))


@app.route('/deploy', methods=["GET", "POST"])
@login_required
def deploy():
    id = request.form.get('id')
    conn = sqlite3.connect(f'{db_name}')
    cursor = conn.cursor()
    table_name = 'llm_data'
    status = statuses[3]
    cursor.execute(f'Select jsonl_file_path FROM {table_name} WHERE id = ?', (id,))
    rows = cursor.fetchone()
    dataset_file_name = rows[0]
    dataset_file_path = (f'storage/jsonl/{dataset_file_name}.jsonl')
            
    if dataset_file_path.endswith('.jsonl.jsonl'):
        dataset_file_path = dataset_file_path.removesuffix('.jsonl')
    
    with open(dataset_file_path, 'r', encoding='utf-8') as file:
        line_count = sum(1 for _ in file)
        
    if line_count < 10:
        return apology(f'Not Enough Data Provided. There must be at least 10 lines and you have {line_count}.')
    
    cursor.execute(f'UPDATE {table_name} SET job_status = ? WHERE id = ?', (status, id))
    files = client.files.list()
    jobs = client.fine_tuning.jobs.list()

    # Initialize variables for file ID model name
    model_name = None
    file_id = None
    
    # Check if the dataset file is already uploaded
    for file in files.data:
        if file.filename == dataset_file_name:
            file_id = file.id
            break

    # If the file is not found, upload it
    if file_id is None:
        response = client.files.create(
            file=open(dataset_file_path, "rb"),
            purpose="fine-tune"
        )
        file_id = response.id

    # Check if a fine-tuned model already exists for the dataset
    for job in jobs.data:
        if job.training_file == file_id and job.fine_tuned_model is not None:
            model_name = job.fine_tuned_model
            model_id = job.id
            cursor.execute(f'UPDATE {table_name} SET job_name = ?, job_id = ? WHERE id = ?', (model_name, model_id, id))
            conn.commit()
            conn.close()
            flash('LLM is already Fine-tuned', 'success')
            return redirect(url_for('index'))

    # If no fine-tuned model is found, start a new fine-tuning job
    if model_name is None:
        
        #if the dataset name is too long to be a suffix, short to 18 characters
        if len(dataset_file_name) > 18:
            dataset_file_name = dataset_file_name[:18]
        
        fine_tune_response = client.fine_tuning.jobs.create(
            training_file=file_id,
            model=llm_model,
            suffix=dataset_file_name
        )
        model_id = fine_tune_response.id
        cursor.execute(f'UPDATE {table_name} SET job_id = ? WHERE id = ?', (model_id, id))
        conn.commit()
        conn.close()
        flash('Started Fine-tuning LLM', 'success')
        return redirect(url_for('index'))
    else:
        conn.commit()
        conn.close()
        flash('Started Fine-tuning LLM', 'success')
        return redirect(url_for('index'))


@app.route('/texts', methods=["GET", "POST"])
@login_required
def texts():
    if request.method == "POST":
        id = request.form.get('id')
        service = request.form.get('service_name')
        
        if service not in ['WhatsApp', 'Discord']:
            return apology("Invalid service name")

        files = request.files.getlist('file')
        if not files or files[0].filename == '':
            return apology("No selected file(s)")

        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'

        cursor.execute(f'SELECT storage, name FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchone()
        
        if not row:
            return apology("Invalid ID")

        sys_name, storage = row[1], row[0] or ''

        uploaded_files = []

        if service == 'WhatsApp':
            if len(files) != 1:
                return apology("Please upload a single file for WhatsApp")
            file = files[0]
            if os.path.splitext(file.filename)[1].lower() != '.txt':
                return apology("Invalid file type for WhatsApp. Please upload a .txt file.")
            filename = secure_filename(f'{id}_{file.filename}')
            file_path = os.path.join('storage/files/', filename)
            file.save(file_path)
            uploaded_files.append(filename)

        elif service == 'Discord':
            
            file_path = files[0].filename  # Access the filename of the first file in the list
            folder_name = file_path.split('/')[0]  # Split the string at '/' and get the first part
            
            folder = secure_filename(f'{id}_{folder_name}')
            folder_path = os.path.join('storage/files/', folder)
            
            if os.path.exists(folder_path):
                counter = 1
                while os.path.exists(folder_path):
                    folder_path = (f'{folder_path}({counter})')
                    counter += 1
            
            os.makedirs(folder_path, exist_ok=True)
            
            for file in files:
                file_path = os.path.join(folder_path, secure_filename(file.filename))
                file.save(file_path)
                uploaded_files.append(os.path.relpath(file_path, 'storage/files/'))
        
        # Update storage with new files
        storage += ','.join(uploaded_files) + ','
        
        cursor.execute(f'UPDATE {table_name} SET storage = ? WHERE id = ?', (storage, id))
        conn.commit()
        conn.close()

        if service == 'WhatsApp':
            user_data = WhatsApp_data(f'storage/files/{filename}')
        elif service == 'Discord':
            user_data = Discord_data(folder_path)
        if len(user_data) > 1:
            # Fetch the user's current LLMs to pass to the template
            llms = get_user_llms(session["user_id"])
            user_data_dict = {key: list(value) for key, value in user_data.items()}
            user_data_json = json.dumps(user_data_dict)
            return render_template("select_user.html", user_data=user_data, user_data_json=user_data_json, llms=llms, id=id, service = service)
        elif len(user_data) == 1:
            conn = sqlite3.connect(f'{db_name}')
            cursor = conn.cursor()
            table_name = 'llm_data'

            cursor.execute(f'SELECT log, name FROM {table_name} WHERE id = ?', (id,))
            row = cursor.fetchone()
                
            if row is None:
                return apology(f"No record found with id: {id}")
                
            name = row[1]
            name += (f'_{id}')
            user = next(iter(user_data))
            
            filename = compile(user_data, name, user, sys_name)
                
            # Ensure log is always initialized
            log = ''
            if row and row[0] is not None:
                log = row[0]
                
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            username = next(iter(user_data))
            
            new = (f'{service}: {username} - {time}')
                
            log += new + ','
                
            status = statuses[1]
            cursor.execute(f'UPDATE {table_name} SET log = ?, job_status = ?, jsonl_file_path = ? WHERE id = ?', (log, status, filename, id))
            conn.commit()
            conn.close()
            
            return redirect(url_for('whatsapp', log=log, id=id))
        else:
            return apology(f'{filename} is empty')  
    else:
        id = request.args.get('id')
        log = request.args.get('log')
        if log:
            log = log.split(",")
            log = [entry for entry in log if entry]  # Remove any empty strings
        else:
            log = []  # Ensure log is always initialized
        return render_template("create.html", id=id, name=name, log=log)


@app.route('/select_user', methods=["GET", "POST"])
@login_required
def select_user():
    if request.method == "POST":
        user_data_json = request.form.get('user_data')

        if user_data_json:
            user_data_dict = json.loads(user_data_json)
            user_data = defaultdict(set, user_data_dict)
        else:
            user_data = defaultdict(set)

        user_id = session["user_id"]
        id = request.form.get('id')
        service = request.form.get('service')
        return_id = id

        action_data = {}
        
        for key in request.form.keys():
            if key.startswith('action_'):
                user = key.split('_', 1)[1]  # Split only at the first underscore
                action = request.form.get(key)
                
                # Initialize the action data for the user
                action_data[user] = {'action': action}
                
                if action == "add_to_another_llm":
                    llm_selection = request.form.get(f'llm_selection_{user}')
                    action_data[user]['llm_selection'] = llm_selection
                    
                    if llm_selection != 'new_llm' and llm_selection != 'current_llm':
                        return apology("All Input Feilds Must Be Filled Out")
                    
                    # Handle the case for selecting a new LLM
                    if llm_selection == 'new_llm':
                        new_llm_name = request.form.get(f'new_llm_name_{user}')
                        if new_llm_name:
                            action_data[user]['new_llm_name'] = new_llm_name
                        else:
                            return apology("All Input Feilds Must Be Filled Out")
                    
                    # Handle the case for selecting an existing LLM
                    elif llm_selection == 'current_llm':
                        current_llm = request.form.get(f'current_llm_{user}')
                        if current_llm:
                            action_data[user]['current_llm'] = current_llm
                        else:
                            return apology("All Input Feilds Must Be Filled Out")
                elif action == "discard" or action == "add_to_this_llm":
                    pass
                else:
                    return apology("All Input Feilds Must Be Filled Out")
                
        # Now you can process user_data as needed
        # Example: Loop through the data and compile or add to LLMs
        for user, data in action_data.items():
            if data['action'] == "add_to_this_llm":
                conn = sqlite3.connect(f'{db_name}')
                cursor = conn.cursor()
                table_name = 'llm_data'
                
                cursor.execute(f'SELECT log, name FROM {table_name} WHERE id = ?', (id,))
                row = cursor.fetchone()
                
                if row is None:
                    return apology(f"No record found with id: {id}")
                
                sys_name = row[1]
                name = (f'{sys_name}_{id}')

                filename = compile(user_data, name, user, sys_name)
                
                # Ensure log is always initialized
                log = ''
                if row and row[0] is not None:
                    log = row[0]
                
                time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
                new = (f'{service}: {user} - {time}')
                
                log += new + ','
                
                status = statuses[1]
                cursor.execute(f'UPDATE {table_name} SET log = ?, job_status = ?, jsonl_file_path = ? WHERE id = ?', (log, status, filename, id))
                conn.commit()
                conn.close()
            elif data['action'] == "add_to_another_llm":
                if data['llm_selection'] == "new_llm":
                    new_llm_name = data['new_llm_name']
                    id, log = create_llm(user_id, new_llm_name)
                    
                    conn = sqlite3.connect(f'{db_name}')
                    cursor = conn.cursor()
                    table_name = 'llm_data'

                    cursor.execute(f'SELECT log, name FROM {table_name} WHERE id = ?', (id,))
                    row = cursor.fetchone()
                    
                    if row is None:
                        return apology(f"No record found with id: {id}")
                    
                    name = row[1]
                    name += (f'_{id}')
                    
                    filename = compile(user_data, name, user, sys_name)
                    
                    # Ensure log is always initialized
                    log = ''
                    if row and row[0] is not None:
                        log = row[0]
                    
                    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                
                    new = (f'{service}: {user} - {time}')
                    
                    log += new + ','
                    
                    status = statuses[1]
                    cursor.execute(f'UPDATE {table_name} SET log = ?, job_status = ?, jsonl_file_path = ? WHERE id = ?', (log, status, filename, id))
                    conn.commit()
                    conn.close()
                    
                elif data['llm_selection'] == "current_llm":
                    # Logic for adding user to an existing LLM
                    current_llm = data['current_llm']
                    conn = sqlite3.connect(f'{db_name}')
                    cursor = conn.cursor()
                    table_name = 'llm_data'

                    cursor.execute(f'SELECT log, id FROM {table_name} WHERE name = ?', (current_llm,))
                    row = cursor.fetchone()
                    
                    if row is None:
                        return apology(f"No record found with id: {id}")
                    
                    id = row[1]
                    name = (f'{current_llm}_{id}')

                    filename = compile(user_data, name, user, sys_name)
                    
                    log = ''
                    if row and row[0] is not None:
                        log = row[0]
                    
                    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                
                    new = (f'{service}: {user} - {time}')
                    
                    log += new + ','
                    
                    status = statuses[1]
                    cursor.execute(f'UPDATE {table_name} SET log = ?, job_status = ?, jsonl_file_path = ? WHERE id = ?', (log, status, filename, id))
                    conn.commit()
                    conn.close()
        try:
            print(log)
        except:
            conn = sqlite3.connect(f'{db_name}')
            cursor = conn.cursor()
            table_name = 'llm_data'
            cursor.execute(f'SELECT log FROM {table_name} WHERE id = ?', (id,))
            row = cursor.fetchone() 
            if row is None:
                return apology(f"No record found with id: {id}")
            # Ensure log is always initialized
            log = ''
            if row and row[0] is not None:
                log = row[0]
            conn.close()
        return redirect(url_for('select_user', log=log, id=return_id))
    else:
        id = request.args.get('id')
        
        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'

        cursor.execute(f'SELECT name, log, job_status, jsonl_file_path FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchone()
        name = row[0]
        logs = row[1]
        if logs == "" or logs is None:
            log = []
        else:
            log = logs.split(',')
            log.reverse()
            
        status = row[2]
        if status == statuses[3]:
            fine_tuning = True
        else:
            fine_tuning = False
        
        dataset_file_name = row[3]
        if dataset_file_name:
            dataset_file_path = (f'storage/jsonl/{dataset_file_name}.jsonl')
            
            if dataset_file_path.endswith('.jsonl.jsonl'):
                dataset_file_path = dataset_file_path.removesuffix('.jsonl')
        
            with open(dataset_file_path, 'r', encoding='utf-8') as file:
                line_count = sum(1 for _ in file)
        else:
            line_count = 0
        
        return render_template("create.html", id=id, name=name, log=log, line_count=line_count, fine_tuning=fine_tuning)
    
    
@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            if not any(email.endswith(ending) for ending in valid_emails):
                return apology("Valid Email Required")
        else:
            return apology("Email Required")
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            token = s.dumps(email, salt='email-confirm-salt')
            link = url_for('new_password', token=token, _external=True)
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Please click the link to reset your password: {link}. This link is only valid for 5 minutes and will then redirect you back to the login page.'
            mail.send(msg)
        else:
            return apology("Email not found")
        
        return redirect(url_for('reset_password_confirmation', email=email))
    else:
        return render_template("forgot_password.html")

@app.route('/reset_password_confirmation/<email>')
def reset_password_confirmation(email):
    return render_template('reset_password_confirmation.html', email=email)

@app.route('/new_password/<token>', methods=['GET', 'POST'])
def new_password(token):
    try:
        # Load the email from the token
        email = s.loads(token, salt='email-confirm-salt', max_age=300)
    except:
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form['password']
        confirmation = request.form['confirmation']

        # Validate the form inputs
        if not password:
            return apology("Password Required")
        if not confirmation:
            return apology("Confirmation Required")
        if password != confirmation:
            return apology("Passwords do not match")

        # Generate the new password hash
        hash = generate_password_hash(password)

        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Check if the email exists and fetch the current password
        cursor.execute('SELECT password FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()

        # Ensure the email is found
        if row is None:
            return apology("User not found")

        old_password = row[0]
        if check_password_hash(old_password, password):
            return apology("Your new password can't be the same as your old password")

        # Update the user's password
        cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hash, email))
        conn.commit()
        conn.close()

        flash('Password Changed Successfully', 'success')
        return redirect(url_for('index'))

    return render_template('new_password.html', token=token)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # gets id
    user_id = session["user_id"]
    table_name = 'llm_data'
    
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row  # allows access to columns by name
    cursor = conn.cursor()
    
    # Execute a query to get all rows from your table
    cursor.execute(f'SELECT * FROM {table_name} WHERE user_id = ?', (user_id,))
    
    # Fetch all rows as a list of dictionaries
    llm_data = cursor.fetchall()
    for row in llm_data:
        job_name = row[6]
        if not job_name:
            model_id = row[5]
            if model_id:
                fine_tune_info = client.fine_tuning.jobs.retrieve(model_id)
                model_name = fine_tune_info.fine_tuned_model
                status = fine_tune_info.status
                id = row['id']
                if model_name:
                    status = statuses[4]
                    created = fine_tune_info.created_at
                    timestamp = datetime.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
                    cursor.execute(f'UPDATE {table_name} SET job_status = ?, job_name = ?, created = ? WHERE id = ?', (status, model_name, timestamp, id))
                else:
                    if status == 'failed':
                        status == statuses[6]
                        cursor.execute(f'UPDATE {table_name} SET job_status = ? WHERE id = ?', (status, id))
        conn.commit() 
    
    # Commit any remaining updates (if there are any) and close the connection after the loop
    conn.commit()  # Ensure all pending updates are committed
    conn.close()  # Close the connection after all operations are complete
    
    return render_template("index.html", database = llm_data)

chat_histories = {}  # Store chat history

@app.route('/exit', methods=['GET', 'POST'])
def exit():
    if request.method == "POST":
        id = request.form.get('id')
        current_time = datetime.datetime.now()
        time = current_time.strftime('%Y-%m-%d %H:%M')
        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'
        
        cursor.execute(f'UPDATE {table_name} SET last_used = ? WHERE id = ?', (time, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

@app.route('/use', methods=['GET', 'POST'])
def use():
    if request.method == 'POST':
        id = request.form.get('id')
        name = request.form.get('name')
        
        if id not in chat_histories:
            chat_histories[id] = []
        
        conn = sqlite3.connect(f'{db_name}')
        cursor = conn.cursor()
        table_name = 'llm_data'
        cursor.execute(f'SELECT * FROM {table_name} WHERE id = ?', (id,))
        row = cursor.fetchone()
        model_name = row[6]
        conn.close()
        new_system_message = system_message + name
        
        if 'message' in request.form and request.form['message'].strip():
            user_message = request.form['message']
            
            # Generate a response using the fine-tuned model
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": new_system_message},
                    {"role": "user", "content": user_message}
                ]
            )
            time = datetime.datetime.now()
            time = time.strftime('%I:%M %p')  # Format the current time
            response = completion.choices[0].message.content
            
            # Insert the new message and response into the chat history
            chat_histories[id].insert(0, {'user': user_message, 'response': response, 'time': time})
            
            # Redirect to the 'use' route with id and name as query parameters
            return redirect(url_for('use', id=id, name=name))
        return redirect(url_for('use', id=id, name=name))
    else:
        # Handle GET request, keep id and name from the query parameters
        id = request.args.get('id')
        name = request.args.get('name')
        chat = chat_histories.get(id, [])
        return render_template('chat.html', chat_history=chat, id=id, name=name)

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        email = (request.form.get("email")).lower()
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if not username:
            return apology("Username Required")
        if email:
            if not any(email.endswith(ending) for ending in valid_emails):
                return apology("Valid Email Required")
        else:
            return apology("Email Required")
        if not password:
            return apology("Password Required")
        if not confirmation:
            return apology("Confirmation Requried")
        if password != confirmation:
            return apology("PASSWORDS DO NOT MATCH")

        hash = generate_password_hash(password)
        
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            table_name = 'users'
            
            # Insert new user into the database
            sql_insert = f'''
            INSERT INTO {table_name} (username, email, password)
            VALUES (?, ?, ?)
            '''
            cursor.execute(sql_insert, (username, email, hash))
            
            # Get the ID of the new user
            user_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
        except:
            return apology("Username or Email Already Exists")

        session["user_id"] = user_id

        return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        
        # Connect to SQLite database
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        table_name = 'users'

        # Check if the username already exists in the database
        cursor.execute(f'SELECT * FROM {table_name} WHERE username = ?', (request.form.get("username"),))
        rows = cursor.fetchall()
        conn.commit()
        conn.close()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][3], request.form.get("password")):
            return apology("Invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        user_id = session["user_id"]
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        table_name = 'users'

        # Check if the username already exists in the database
        cursor.execute(f'SELECT * FROM {table_name} WHERE id = ?', (user_id,))
        rows = cursor.fetchall()
        conn.commit()
        conn.close()
        
        current_password_hash = rows[0][3]

        if not check_password_hash(current_password_hash, request.form.get("old")):
            return apology("Current Password Is Incorrect", 403)

        new = request.form.get("new")
        confirmation = request.form.get("confirmation")
        if not new or new != confirmation:
            return apology("New passwords do not match", 400)

        new_password_hash = generate_password_hash(new)
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_password_hash, user_id))
        conn.commit()
        conn.close()

        flash("Password Canged Successfully!")
        return redirect("/")

    else:
        return render_template("change_password.html")
    
if __name__ == '__main__':
    app.run(debug=True)