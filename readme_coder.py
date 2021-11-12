#!/usr/bin/env python3

'''
This script generates the project based on the README.md file.
'''

import sys
import openai
import os
import argparse
import configparser
import time

FILES_NOT_TO_INCLUDE = ['LICENSE', 'README.md']
STREAM = True
cur_dir_not_full_path = os.getcwd().split('/')[-1]

# Get config dir from environment or default to ~/.config
CONFIG_DIR = os.getenv('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
API_KEYS_LOCATION = os.path.join(CONFIG_DIR, 'openaiapirc')

GENERATED_PROJECTS_DIR = 'generated_projects'

PROMPT_BEGINNING = \
'''
============================================================
**.gitignore:**

__pycache__/
.env
.venv
env/
venv/

============================================================
**LICENSE:**

MIT License

Copyright (c) 2018 Ondřej Masopust; Gymnázium Praha 6, Nad Alejí 1952

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

============================================================
**README.md:**

'''

def create_template_ini_file():
    """
    If the ini file does not exist create it and add the organization_id and
    secret_key
    """
    if not os.path.isfile(API_KEYS_LOCATION):
        with open(API_KEYS_LOCATION, 'w') as f:
            f.write('[openai]\n')
            f.write('organization_id=\n')
            f.write('secret_key=\n')

        print('OpenAI API config file created at {}'.format(API_KEYS_LOCATION))
        print('Please edit it and add your organization ID and secret key')
        print('If you do not yet have an organization ID and secret key, you\n'
               'need to register for OpenAI Codex: \n'
                'https://openai.com/blog/openai-codex/')
        sys.exit(1)


def initialize_openai_api():
    """
    Initialize the OpenAI API
    """
    # Check if file at API_KEYS_LOCATION exists
    create_template_ini_file()
    config = configparser.ConfigParser()
    config.read(API_KEYS_LOCATION)

    openai.organization_id = config['openai']['organization_id'].strip('"').strip("'")
    openai.api_key = config['openai']['secret_key'].strip('"').strip("'")



def create_input_prompt(file_to_execute, length=3000):
    input_prompt = PROMPT_BEGINNING
    # Read the readme file.
    with open('README.md', 'r') as f:
        readme_text = f.read()

    # Add the readme text to the input prompt.
    input_prompt = input_prompt + readme_text
    input_prompt += f'============================================================\n**{file_to_execute}:**'
    # input_prompt += '============================================================\n**'
    return input_prompt


def generate_completion(input_prompt, num_tokens):
    response = openai.Completion.create(engine='davinci-codex', prompt=input_prompt, temperature=0.5, max_tokens=num_tokens, stream=STREAM, stop=None)
    return response



def clear_screen_and_display_generated_files(response):
    # Clear screen.
    os.system('cls' if os.name == 'nt' else 'clear')
    generated_text = '**'
    while True:
        next_response = next(response)
        completion = next_response['choices'][0]['text']
        # print("completion:", completion)
        # print(next(response))
        print(completion, end='')
        generated_text = generated_text + completion
        if next_response['choices'][0]['finish_reason'] != None: break

    return generated_text

def split_text_into_files(text):
    # Split text into files.
    files = {}
    items = text.split('============================================================')
    items = [items.strip() for items in items]
    for item in items:
        # print("item:", item)
        # print("item.startswith('**'):", item.startswith('**'))
        if item.startswith('**'):
            file_name = item.split('**')[1].split(':')[0].strip()
            # print("file_name:", file_name)
            # input()
            files[file_name] = '**'.join(item.split('**')[2:]).strip()

    return files

def save_files(files):
    # Save files to disk.
    dir_name = os.path.join(GENERATED_PROJECTS_DIR, str(time.time()))
    # make all dirs
    os.makedirs(dir_name)
    # os.mkdir(dir_name)
    for file_name, file_text in files.items():
        if file_name and file_name not in FILES_NOT_TO_INCLUDE:
            file_path = dir_name + '/' + file_name
            # Create directories if needed.
            if '/' in file_name:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(file_text)


def get_args():
    # Get the number of tokens as positional argument.
    parser = argparse.ArgumentParser()
    parser.add_argument("file_to_execute", help="The file to execute")
    # arguments for the file
    parser.add_argument("arguments", nargs='*', help="Arguments to pass to the file")
    parser.add_argument("--tokens", type=int, default=256)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = get_args()
    initialize_openai_api()
    input_prompt = create_input_prompt(args.file_to_execute)
    # print("input_prompt:", input_prompt)
    # sys.exit(0)
    response = generate_completion(input_prompt, args.tokens)
    generated_text = clear_screen_and_display_generated_files(response)
    text_all = input_prompt + '\n' + generated_text
    files = split_text_into_files(text_all)
    save_files(files)


  
