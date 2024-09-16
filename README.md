# LLM-Maker
An LLM maker UI that allows users to fine-tune their own LLM models based on Reddit, WhatsApp, and Discord data.
This repository contains a Flask-based web application that enables users to manage, fine-tune, and interact with custom language models (LLMs). The application allows users to upload data from Reddit, WhatsApp, and Discord, fine-tune GPT models using OpenAI, and interact with the models in real-time through a web interface.

### Steps to run:
1. Enter information for "variables set by user" (lines 23-29)
2. Enter in the terminal python app.py

## Features and Functionalities

- Flask-based web application that allows interaction via locally hosted website.
- User registration, login, and session management using SQLite database and Flask-Session.
- Change password or reset password functionality through password reset link via email
- Functionality for LLM creation
- Integration with Reddit API (PRAW) to fetch user posts and comments.
- Drag and drop WhatsApp and Discord files to extract data, along with filtering based on identified users in messages
- Formats data into a fine-tunable JSONL file.
- Fine-tuning of LLM models using previous LLM pipeline
- Database management of LLM-related data, including job statuses, logs, dataset tracking, creation date and usage time stamps.
- Ability to cancel fine-tuning jobs and delete associated files.
