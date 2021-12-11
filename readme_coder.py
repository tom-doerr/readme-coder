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
import subprocess
from termcolor import colored
import random
import string
from pathlib import Path
import re
import jupyter_client
import traceback
import multiprocessing
from multiprocessing import Queue, Process

from textual.app import App
from textual.widgets import Placeholder
from textual.widget import Widget
from textual.reactive import Reactive
from rich.panel import Panel

import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter

import datetime
import shutil

cur_dir_not_full_path = os.getcwd().split('/')[-1]

# Get config dir from environment or default to ~/.config
CONFIG_DIR = os.getenv('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
API_KEYS_LOCATION = os.path.join(CONFIG_DIR, 'openaiapirc')

GENERATED_PROJECTS_DIR = 'generated_projects'
GENERATED_PROJECTS_DIR_LOCAL = os.path.join('mounted/', GENERATED_PROJECTS_DIR)
SUCCESS_LINKS_DIR = 'success_links'
SUCCESS_LINKS_ALL_DIR = 'success_links_all'
SUCCESS_LINKS_OLD_DIR = 'success_links_old'
DUMMY_DIR = 'dummy/'
DUMMY_DIR_LOCAL = os.path.join('mounted/', DUMMY_DIR)
BASE_DIRS_DIR = 'base_dirs'

DOCKER_EXEC_COMMAND = 'docker exec readme_coder_container bash -c'

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

Copyright <YEAR> <COPYRIGHT HOLDER>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

============================================================
**README.md:**

'''

PYTHON_INTERACTIVE_PROMPT = \
'''
Python 3.8.10 (default, Sep 28 2021, 16:10:42) 
[GCC 9.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
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



def create_input_prompt(main_file, base_dir, length=3000, interactive=False):
    input_prompt = PROMPT_BEGINNING
    # Read the readme file.
    with open(os.path.join(base_dir, 'README.md'), 'r') as f:
        readme_text = f.read()

    # Add the readme text to the input prompt.
    input_prompt = input_prompt + readme_text
    if interactive:
        input_prompt += f'# Above program written in interactive mode\n```\n'
        input_prompt += PYTHON_INTERACTIVE_PROMPT
    else:
        input_prompt += f'============================================================\n**{main_file}:**'
    return input_prompt


def generate_completion(input_prompt, num_tokens, model, stop=None, stream=True):
    args = {'prompt': input_prompt, 'engine': model, 'temperature': 0.5, 'max_tokens': num_tokens, 'stream': stream, 'stop': stop, 'logprobs': 1}
    response = openai.Completion.create(**args)
    # save args to file
    with open('args.csv', 'a') as f:
        f.write(f'{time.time()}, {args}\n')
    return response


def clear_screen_and_display_generated_files_with_animation(response, print_delay=0.001):
    generated_text = ''
    while True:
        try:
            next_response = next(response)
        except openai.error.APIError:
            print('Error: API returned an error')
            break
        with open('responses.csv', 'a') as f:
            f.write(f'{time.time()}, {next_response}\n')
        completion = next_response['choices'][0]['text']
        for e in completion:
            print(e, end='', flush=True)
            time.sleep(print_delay)

        generated_text = generated_text + completion
        if next_response['choices'][0]['finish_reason'] != None: break


    return generated_text


def get_logprobs_sum(logprobs_dicts):
    logprobs_dict_values = [e.values() for e in logprobs_dicts]
    sum_logprobs = [sum(e) for e in logprobs_dict_values]
    sum_all_logprobs = sum(sum_logprobs)
    return sum_all_logprobs


def filter_tokens(completion, tokens):
    # print("tokens:", tokens)
    tokens_filtered = []
    for token in tokens[::-1]:
        if token == completion[-len(token):]:
            # print("completion[-len(tokens[-i]):]:", completion[-len(token):])
            tokens_filtered.append(token)
            # print("tokens_filtered:", tokens_filtered)
            completion = completion[:-len(token)]
            # print("completion:", completion)

    tokens_filtered_inverse = tokens_filtered[::-1]
    # print("tokens_filtered_inverse:", tokens_filtered_inverse)
    # if len(tokens_filtered) != len(tokens):
        # time.sleep(10)
    return tokens_filtered_inverse

def clear_screen_and_display_generated_files_with_animation_backtracking(args, input_prompt, queues, print_delay=0.001):
    text_all = input_prompt
    top_logprobs = []
    num_tokens_generated = 0
    # num_sub_tokens = 20
    if args.backtrack:
        num_sub_tokens = 20
    else:
        num_sub_tokens = args.num_tokens
    tokens = []
    print_response = False
    while  True:
        while True:
            response = generate_completion(text_all, num_sub_tokens, args.model)
            while True:
                try:
                    next_response = next(response)
                    queues['model'].put(next_response['model'])
                except openai.error.APIError:
                    print('Error: API returned an error')
                    break
                with open('responses.csv', 'a') as f:
                    f.write(f'{time.time()}, {next_response}\n')
                completion = next_response['choices'][0]['text']
                top_logprobs_current = next_response['choices'][0]['logprobs']['top_logprobs']
                top_logprobs.extend(top_logprobs_current)
                tokens_filtered = filter_tokens(completion, next_response['choices'][0]['logprobs']['tokens'])
                tokens.extend(tokens_filtered)
                completion_char_by_char = ''
                if print_response:
                    # print("completion:", completion)
                    # print("next_response['choices'][0]['logprobs']['tokens']:", next_response['choices'][0]['logprobs']['tokens'])
                    # time.sleep(10)
                    print_response = False

                for e in completion:
                    # print(e, end='', flush=True)
                    completion_char_by_char += e
                    generated_up_until_now = (text_all + completion_char_by_char).replace(input_prompt, '')
                    queues['generated_code'].put(generated_up_until_now)
                    time.sleep(print_delay)

                num_tokens_generated += len(top_logprobs_current)
                # text_all = text_all + completion
                generated_code = ''.join(tokens)
                text_all = input_prompt + generated_code
                if next_response['choices'][0]['finish_reason'] != None: break



            if args.backtrack:
                NUM_TOKENS_BACKTRACKING_CHECK = 1 * num_sub_tokens
                logprobs_sum = get_logprobs_sum(top_logprobs[-NUM_TOKENS_BACKTRACKING_CHECK:])
                if logprobs_sum > -8.0:
                    break
                else:
                    # print logprobs sum in blue
                    if False:
                        print(f'\033[1;34m{logprobs_sum}\033[0m')
                    top_logprobs = top_logprobs[:-NUM_TOKENS_BACKTRACKING_CHECK]
                    tokens = tokens[:-NUM_TOKENS_BACKTRACKING_CHECK]
                    generated_code = ''.join(tokens)
                    text_all = input_prompt + generated_code
                    # print("tokens:", tokens)
                    # for token in tokens:
                        # print('token: ', token, flush=True)
                    # print("text_all:", text_all)
                    print_response = True
            else:
                break
                # pass



        if num_tokens_generated >= args.num_tokens:
            break




    text_all = text_all.replace(input_prompt, '')
    return text_all

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

def save_files(files, base_dir):
    # Save files to disk.
    project_root_dir = str(time.time()).replace('.', '_')
    dir_name = os.path.join(GENERATED_PROJECTS_DIR, project_root_dir)
    dir_name_local = os.path.join('mounted/', dir_name)
    # os.makedirs(dir_name_local)


    # copy all files and directories from the base_dir to the new directory except for files matching 'test*secret*'
    shutil.copytree(base_dir, dir_name_local, ignore=shutil.ignore_patterns('test*secret*'))

    # if os.path.exists(os.path.join(base_dir, 'test*secret*')):
    # os.system(f'cp -r {base_dir}/* {dir_name_local}')
    

    for file_name, file_text in files.items():
        file_path = dir_name_local + '/' + file_name
        # Create directories if needed.
        try:
            if '/' in file_name:
                dirname = os.path.dirname(file_path)
                dirname_path = Path(dirname)
                try:
                    dirname_path.mkdir(parents=True, exist_ok=True)
                except NotADirectoryError:
                    print('Not a directory: {}'.format(dirname))
                    print('Skipping file: {}'.format(file_name))
                    continue
                # os.makedirs(dirname, exist_ok=True)    r
            with open(file_path, 'w') as f:
                f.write(file_text + '\n')
        except FileExistsError:
            print('File already exists: {}'.format(file_path))
            print('Skipping file...')
            continue
        except IsADirectoryError:
            print('File is a directory: {}'.format(file_path))
            print('Skipping file...')
            continue
        except OSError:
            print('OSError: {}'.format(file_path))
            print('Skipping file...')
            continue

    return dir_name, dir_name_local


def get_args():
    # Get the number of tokens as positional argument.
    parser = argparse.ArgumentParser()
    parser.add_argument("main_file", help="The file to execute")
    parser.add_argument("command", nargs='*', help="The command to execute")
    parser.add_argument('-n', "--num_tokens", type=int, default=1000)
    parser.add_argument('-a', "--num_attempts", type=int, default=100, help="The number of attempts to generate the code")
    parser.add_argument('-s', "--num_solutions", type=int, default=1, help="The number of solutions to generate")
    parser.add_argument('-o', '--output', type=str, default=None, help='The expected output of the code')
    parser.add_argument('-t', '--timeout', type=int, default=1, help='The timeout for the code to run')
    parser.add_argument('-w', '--wait', type=int, default=0, help='The time to wait between attempts')
    parser.add_argument('-m', '--model', type=str, default='davinci-codex', help='The model to use')
    parser.add_argument('-b', '--backtrack', action='store_true', help='Whether to backtrack or not')
    parser.add_argument('-i', '--interactive', action='store_true', help='Whether to run in interactive mode')
    parser.add_argument('-d', '--base_dir', type=str, default=None, help='Directory the generated project is based on')
    args = parser.parse_args()
    return args


def get_base_dir(base_dir_arg):
    if base_dir_arg:
        base_dir = base_dir_arg
    else:
        # Get the newest directory in BASE_DIRS_DIR.
        base_dirs_dir = BASE_DIRS_DIR
        base_dirs = [os.path.join(base_dirs_dir, d) for d in os.listdir(base_dirs_dir)]
        base_dirs_dir_time = [os.path.getmtime(d) for d in base_dirs]
        base_dir = base_dirs[base_dirs_dir_time.index(max(base_dirs_dir_time))]

    return base_dir


def get_output(program, timeout):
    stderr = None
    stdout = None
    success = False

    # Run the program and capture its output
    with open(os.devnull, 'w') as devnull:
        try:
            # Get the stderr and the stdout of the program program.
            stdout = subprocess.check_output(program,  stderr=subprocess.STDOUT, shell=True, timeout=timeout).decode('utf-8')
            success = True
        except subprocess.TimeoutExpired:
            stderr =  "Timeout"
        except subprocess.CalledProcessError as e:
            stderr =  e.output.decode('utf-8')

    # save all values to file
    values = {'program': program, 'stdout': stdout, 'stderr': stderr, 'success': success}
    with open('outputs.csv', 'a') as f:
        f.write(f'{time.time()}, {values}\n')

    return stdout, stderr, success

def generate_success_id():
    # generate a random success id consisting of letters
    while True:
        suc_id = ''.join(random.choices(string.ascii_letters, k=5)).lower()
        # check if the id exists
        if not os.path.exists(os.path.join(SUCCESS_LINKS_DIR, suc_id)):
            break

    return suc_id

def write_output_suc_id_file(output, suc_id):
    # write the output to a file
    with open(os.path.join(SUCCESS_LINKS_DIR, f'{suc_id}.txt'), 'w') as f:
        f.write(output)

def start_docker_container():
    docker_start_command = f'docker run --ulimit nofile=10000:10000 --rm --name readme_coder_container -v $PWD/mounted:/mounted -dt readme_coder_image' 
    # Check if the container is running, stop it and wait for it to stop
    if subprocess.run(['docker', 'ps', '-a'], stdout=subprocess.PIPE).stdout.decode('utf-8').count('readme_coder_container') != 0:
        # Stop the container
        subprocess.run(['docker', 'stop', 'readme_coder_container'])
        # Wait for the container to stop
        while subprocess.run(['docker', 'ps', '-a'], stdout=subprocess.PIPE).stdout.decode('utf-8').count('readme_coder_container') != 0:
            time.sleep(0.1)

    subprocess.check_output(docker_start_command, shell=True)


def extract_module_name(text):
    word = re.findall(r'(?<=No module named \')\w+', text)[0]
    return word

def write_module_name_to_file(module_name):
    # Check if dir dummy exists and create it if not
    if not os.path.exists(DUMMY_DIR_LOCAL):
        os.mkdir(DUMMY_DIR_LOCAL)
    with open(os.path.join(DUMMY_DIR_LOCAL, 'dummy.py'), 'w') as f:
        f.write(f'import {module_name}')

def run_pipreqs():
    subprocess.run(['pipreqs', DUMMY_DIR_LOCAL, '--force'])

def install_requirements():
    print('= requirements.txt =')
    with open(os.path.join(DUMMY_DIR, 'requirements.txt'), 'r') as f:
        print(f.read())

    print('= running pip3 install')
    requirements_path = os.path.join(DUMMY_DIR, 'requirements.txt')
    pip_command = f'pip3 install -r {requirements_path}'
    print(f'$ {pip_command}')
    subprocess.run([f'{DOCKER_EXEC_COMMAND} "cd /mounted; {pip_command}"'], shell=True)
    print('= pip3 install done')


def start_ipython_kernel():
    log_file = '.ipython_kernel_ouput'
    unix_timestamp_last_mod = os.path.getmtime(log_file)
    subprocess.run([f'{DOCKER_EXEC_COMMAND} "cd /mounted; ipython kernel > .ipython_kernel_ouput" &'], shell=True)
    wait_counter = 0
    while True:
        time.sleep(0.001)
        unix_timestamp_current_mod = os.path.getmtime(log_file)
        if unix_timestamp_current_mod > unix_timestamp_last_mod:
            # Extract the kernel id from the output:
            # '''To connect another client to this kernel, use:
            # --existing kernel-3105870.json'''
            output = ''
            with open(log_file, 'r') as f:
                output = f.read()

            if 'kernel-' not in output:
                wait_counter += 1
                if wait_counter > 1000:
                    print('Could not start the kernel')
                    break
                continue

            kernel_id = output.split('kernel-')[1].split('.json')[0]
            break

    return kernel_id


def run_code_ipython_docker(kernel_id):
    # Run the code in the docker container
    command = f'{DOCKER_EXEC_COMMAND} "cd /mounted; ./run_ipython_kernel.py --kernel-id {kernel_id}"'
    output, stderr = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return output, stderr


def generate_code_interactive():
    CODE_FILE = 'generated_code_interactive'
    PROMPTS_ALL = 'prompts_interactive_all'
    kernel_id = start_ipython_kernel()
    prompt = PYTHON_INTERACTIVE_PROMPT
    # prompt += '>>> # Print the text of the newest blog entry on openai.com/blog/\n'
    # prompt += '>>> # Print the largest temperature from temps.csv'
    # prompt += '>>> # Print the largest temperature from temps.csv'
    # prompt += '>>> # Merge the file temps.csv with the file temperatures.csv'
    # prompt += '>>> # Steps:\n'
    for i in range(30):
        prompt += '>>> '
        # only use last 6k characters
        prompt = prompt[-6000:]
        try:
            response = generate_completion(prompt, 128, 'davinci-codex', stop=['>>>', '\n'], stream=False)
        except openai.error.InvalidRequestError:
            print('Invalid request error: {}'.format(prompt))
            # show stacktrace
            traceback.print_exc()
            print('Skipping prompt...')
            break

        completion = response['choices'][0]['text'] + '\n'
        # print("completion:", completion)
        with open(CODE_FILE, 'a') as f:
            # completion = 'abc\n'
            f.write(completion)
        prompt += completion
        # print("prompt:", prompt)

        queues['text_generated_interactively'].put(prompt)

        output, stderr = run_code_ipython_docker(kernel_id)
        prompt += output.decode('utf-8')

        # output in green color
        print(colored(output.decode('utf-8'), 'green'))

        # error in red color
        print(colored(stderr.decode('utf-8'), 'red'))

        # output, stderr = run_code_ipython_docker('a=3', kernel_id)
        # print("output:", output)
        # print("stderr:", stderr)
        # output, stderr = run_code_ipython_docker('a', kernel_id)
        # print("output:", output)
        # print("stderr:", stderr)
        # print("output.decode('utf-8'):", output.decode('utf-8'))
        # input()

        # output, stderr = run_code_ipython_docker('import os', kernel_id)
        # output, stderr = run_code_ipython_docker('os.getcwd()', kernel_id)
        # print("output:", output)
        # print("stderr:", stderr)
        # print("output.decode('utf-8'):", output.decode('utf-8'))
        # input()

    # write prompt
    with open(PROMPTS_ALL, 'a') as f:
        f.write('======================')
        f.write(prompt)



# def create_dirs_if_needed():
    # if not os.path.exists(GENERATED_PROJECTS_DIR_LOCAL):
        # os.makedirs(GENERATED_PROJECTS_DIR_LOCAL)


def run_pytest(dir_name, dir_name_local, base_dir):
    # Copy all files from base_dir to dir_name that match the 'test*secret*' pattern
    # Check if files {base_dir}/test*secret exist using glob
    import glob
    if len(glob.glob(f'{base_dir}/test*secret*')) > 0:
        # for file in glob.glob(f'{base_dir}/test*secret*'):
            # shutil.copy(file, dir
    # if os.path.exists(os.path.join(base_dir, 'test*secret*')):
        os.system(f'cp -r {base_dir}/test*secret* {dir_name_local}')
    command_with_docker = f'{DOCKER_EXEC_COMMAND} "cd /mounted/{dir_name}; pytest" '
    stdout, stderr, success = get_output(command_with_docker, args.timeout)
    if stderr:
        return False
    else:
        return True




def main(queues, args):
    move_old_symlinks()
    base_dir = get_base_dir(args.base_dir)
    # create_dirs_if_needed()
    # for i in range(1000):
        # # add random text to the generated_code
        # generated_code.put('Hellooooooo World!')
        # time.sleep(0.01)

    initialize_openai_api()
    # engines = openai.Engine.list()
    # print("engines:", engines)
    input_prompt = create_input_prompt(args.main_file, base_dir)
    num_solutions = 0
    start_time = time.time()
    start_docker_container()
    generated_enough_solutions = False
    for attempt in range(1, args.num_attempts + 1):
        block_char = '─'
        print(f'{block_char * 30}', end='')
        # print the attempt in bold
        print("\033[1m Attempt: " + str(attempt) + "\033[0m")
        queues['attempt'].put(attempt)

        if args.interactive:
            generate_code_interactive()
            continue



        print_delay = 0.005 if args.model == 'davinci-codex' else 0.001
        generated_text = clear_screen_and_display_generated_files_with_animation_backtracking(args, input_prompt, queues)
        if False:
            response = generate_completion(input_prompt, args.num_tokens, args.model)
            generated_text = clear_screen_and_display_generated_files_with_animation(response, print_delay)
        text_all = input_prompt + '\n' + generated_text
        files = split_text_into_files(text_all)
        dir_name, dir_name_local = save_files(files, base_dir)
        command_inside_docker = ' '.join(args.command)
        command_with_docker = f'{DOCKER_EXEC_COMMAND} "cd /mounted/{dir_name}; {command_inside_docker}" '

        for _ in range(2):
            output, stderr, execution_success = get_output(command_with_docker, args.timeout)
            if not stderr or not 'ModuleNotFoundError' in stderr:
                break
            
            module_name = extract_module_name(stderr)
            print(f'= Installing module {module_name}...')
            write_module_name_to_file(module_name)
            run_pipreqs()
            install_requirements()



        print()
        # print the stderr in red.
        if stderr:
            print(colored(stderr, 'red'))
            # os.system('cls' if os.name == 'nt' else 'clear')
        # print the output in green.
        if output:
            print(colored(output, 'green'))

        pytest_success = run_pytest(dir_name, dir_name_local, base_dir)

        success = execution_success and pytest_success
        if success:
            if args.output:
                if output.strip() != args.output.strip():
                    print(colored('Output doesn\'t match expected output', 'red'))
                    print(colored(f'Expected: {args.output.strip()}', 'red'))
                    print(colored(f'Got: {output.strip()}', 'red'))
                    continue

            # check if output is empty
            if not output.strip():
                print(colored('Output is empty', 'red'))
                continue

            suc_id = generate_success_id()
            create_symlinks(suc_id, dir_name_local)
            write_output_suc_id_file(output, suc_id)
            num_solutions += 1
            if num_solutions >= args.num_solutions:
                generated_enough_solutions = True
                break

        if args.wait > 0:
            print(f'Waiting {args.wait} seconds before next attempt')
            # count down
            for i in range(args.wait, 0, -1):
                print(f'  {i} s left', end='\r')
                time.sleep(1)

    # Show the time the script run for in HH:MM:SS format
    hh_mm_ss = str(datetime.timedelta(seconds=int(time.time() - start_time)))
    print(f'Ran for {hh_mm_ss}')

    if not generated_enough_solutions:
        print(colored(f'\n\n\nOnly generated {num_solutions}/{args.num_solutions} solutions.', 'red'))


def move_old_symlinks():
    dir_for_old_links = os.path.join(SUCCESS_LINKS_OLD_DIR, str(int(time.time())))
    os.makedirs(dir_for_old_links)
    # move all files in SUCCESS_LINKS_DIR to dir_for_old_links
    for file in os.listdir(SUCCESS_LINKS_DIR):
        os.rename(os.path.join(SUCCESS_LINKS_DIR, file), os.path.join(dir_for_old_links, file))
        # if the file is a symlink, change the link location to ../symlink. 
        if os.path.islink(os.path.join(dir_for_old_links, file)):
            link_destination = os.readlink(os.path.join(dir_for_old_links, file))
            os.remove(os.path.join(dir_for_old_links, file))
            os.symlink(os.path.join('..', link_destination), os.path.join(dir_for_old_links, file))


def create_symlinks(suc_id, dir_name_local):
    os.makedirs(SUCCESS_LINKS_ALL_DIR, exist_ok=True)
    os.symlink(os.path.join('..', dir_name_local), os.path.join(SUCCESS_LINKS_ALL_DIR, str(time.time())))
    os.symlink(os.path.join('..', dir_name_local), os.path.join(SUCCESS_LINKS_DIR, suc_id))
    if os.path.exists(os.path.join(SUCCESS_LINKS_DIR, 'success_latest')):
        os.remove(os.path.join(SUCCESS_LINKS_DIR, 'success_latest'))
    os.symlink(os.path.join('..', dir_name_local), os.path.join(SUCCESS_LINKS_DIR, 'success_latest'))


class InteractiveCodeWidget(Widget):

    mouse_over = Reactive(False)

    def on_mount(self) -> None:
        self.set_interval(0.001, self.refresh)
        self.last_text = ''

    def render(self) -> Panel:
        text = self.last_text
        while not queues['text_generated_interactively'].empty():
            try:
                text = queues['text_generated_interactively'].get_nowait()
                self.last_text = text
            except Exception as e:
                print(e)

        _, height = self.size
        text = '\n'.join(text.split('\n')[-height:])
        text += '\n'*1000

        # syntax = Syntax(
            # text,
            # 'python',
            # line_numbers=True,
            # word_wrap=True,
            # # indent_guides=True,
            # theme="monokai",
        # )

        # return syntax
        return Panel(text)


    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False


  

class CodeWidget(Widget):

    mouse_over = Reactive(False)

    def on_mount(self) -> None:
        self.set_interval(0.001, self.refresh)
        self.last_text = ''

    def render(self) -> Panel:
        # if not queues['generated_code'].empty():
            # text = queues['generated_code'].get()
            # self.last_text = text
        # else:
            # text = self.last_text

        
        text = self.last_text
        while not queues['generated_code'].empty():
            try:
                text = queues['generated_code'].get_nowait()
                self.last_text = text
            except Exception as e:
                print(e)


        # text = self.last_text
        # try:
            # text = queues['generated_code'].get(timeout=0.1)
        # except Exception as e:
            # text = ''


        # text = pygments.highlight(text.strip(), PythonLexer(), TerminalFormatter())

        # syntax = Syntax.from_path(
            # '/home/tom/test/zow.py',
            # line_numbers=True,
            # word_wrap=True,
            # indent_guides=True,
            # theme="monokai",
        # )

        _, height = self.size
        text = '\n'.join(text.split('\n')[-height:])
        text += '\n'*1000

        syntax = Syntax(
            text,
            'python',
            line_numbers=True,
            word_wrap=True,
            # indent_guides=True,
            theme="monokai",
        )

        return syntax
        # return Panel(text)

        # text = 'jkl siw jkff'
        # return Panel('\033[32m{}\033[0m'.format(text))

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False



class Custom1(Widget):

    mouse_over = Reactive(False)

    def on_mount(self) -> None:
        self.set_interval(0.001, self.refresh)

    def render(self) -> Panel:
        return Panel(str(time.time()))

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False

    # parser.add_argument("main_file", help="The file to execute")
    # parser.add_argument("command", nargs='*', help="The command to execute")
    # parser.add_argument('-n', "--num_tokens", type=int, default=1000)
    # parser.add_argument('-a', "--num_attempts", type=int, default=100, help="The number of attempts to generate the code")
    # parser.add_argument('-s', "--num_solutions", type=int, default=1, help="The number of solutions to generate")
    # parser.add_argument('-o', '--output', type=str, default=None, help='The expected output of the code')
    # parser.add_argument('-t', '--timeout', type=int, default=1, help='The timeout for the code to run')
    # parser.add_argument('-w', '--wait', type=int, default=0, help='The time to wait between attempts')
    # parser.add_argument('-m', '--model', type=str, default='davinci-codex', help='The model to use')
    # parser.add_argument('-b', '--backtrack', action='store_true', help='Whether to backtrack or not')

class Stats(Widget):

    mouse_over = Reactive(False)

    def on_mount(self) -> None:
        self.set_interval(0.01, self.refresh)
        self.last_attempt = ''
        self.last_model = ''

    def render(self) -> Panel:
        if not queues['attempt'].empty():
            attempt = queues['attempt'].get()
            self.last_attempt = attempt
        else:
            attempt = self.last_attempt

        if not queues['model'].empty():
            model = queues['model'].get()
            self.last_model = model
        else:
            model = self.last_model

        # attempt = self.last_attempt

        text = ''
        text += f'Main file: {args.main_file}\n'
        text += f'Command: {args.command}\n'
        text += f'Number of tokens: {args.num_tokens}\n'
        text += f'Number of attempts: {args.num_attempts}\n'
        text += f'Number of solutions: {args.num_solutions}\n'
        text += f'Expected output: {args.output}\n'
        text += f'Timeout: {args.timeout}\n'
        text += f'Wait: {args.wait}\n'
        text += f'Model: {args.model}\n'
        text += f'Backtrack: {args.backtrack}\n'
        text += f'\n'
        text += f'Model Version: {model}\n'
        text += f'Attempt: {attempt}'
        return Panel(text)

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False

from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree

# scroll_view = ScrollView(
    # children=[
        # DirectoryTree(
            # path='../../',
            # on_click=FileClick(
                # on_click=lambda path: print(path)
            # )
        # ),
        # Header(
            # children=[
                # CodeWidget(),
                # Custom1(),
                # Stats(),
            # ]
        # ),
        # Footer(
            # children=[
                # 'Made with ❤️ by ',
                # Link('test.de', 'https://test.de'),
            # ]
        # ),
    # ]
# )


class DirectoryTreeCustom(DirectoryTree):
    def on_mount(self) -> None:
        self.set_interval(0.001, self.refresh)


from rich.syntax import Syntax

class AutoCodingApp(App):

    def shutdown(self) -> None:
        main_process.terminate()
        main_process.join()
        sys.exit(0)


    async def on_load(self) -> None:
        await self.bind("q", "quit", "Quit")


    async def on_mount(self) -> None:
        # self.scroll_view = ScrollView()
        # self.scroll_view.update(Panel('jkljkljkljkl'))

        # syntax = Syntax.from_path(
            # '/home/tom/test/latest',
            # line_numbers=True,
            # word_wrap=True,
            # indent_guides=True,
            # theme="monokai",
        # )


        # self.scroll_view.update(syntax) 

        grid = await self.view.dock_grid(edge="left", name="left")
        grid.add_column(fraction=1, name="left")
        grid.add_column(fraction=2, name="right")
        grid.add_row(fraction=4, name="top", min_size=2)
        grid.add_row(fraction=1, name="middle", min_size=2)
        grid.add_row(fraction=1, name="bottom", min_size=2)

        grid.add_areas(
            area1="left",
            area2="right,top",
            area4="right,middle",
            area3="right,bottom",
        )

        grid.place(
            area1=Custom1(),
            area2=CodeWidget(),
            area3=Stats(),
            # area4=self.scroll_view,
            # area4=ScrollView(),
            # area4=DirectoryTree(os.getcwd(), 'code'),
            area4=DirectoryTreeCustom(os.getcwd(), 'code'),
        )


    # async def on_mount(self) -> None:
        # await self.view.dock(Stats(), edge="left", size=40)
        # await self.view.dock(Custom1(), Hover(), edge="top")


class InteractiveCodingApp(App):

    def shutdown(self) -> None:
        main_process.terminate()
        main_process.join()
        sys.exit(0)


    async def on_load(self) -> None:
        await self.bind("q", "quit", "Quit")


    async def on_mount(self) -> None:
        grid = await self.view.dock_grid(edge="left", name="left")
        grid.add_column(fraction=1, name="left")
        grid.add_column(fraction=2, name="right")
        grid.add_row(fraction=4, name="top", min_size=2)
        grid.add_row(fraction=1, name="middle", min_size=2)
        grid.add_row(fraction=1, name="bottom", min_size=2)

        grid.add_areas(
            area1="left",
            area2="right,top",
            area4="right,middle",
            area3="right,bottom",
        )

        grid.place(
            area1=Custom1(),
            area2=InteractiveCodeWidget(),
            area3=Stats(),
            area4=DirectoryTreeCustom(os.getcwd(), 'code'),
        )


def create_queues():
    queues = {}
    queues['generated_code'] = Queue()
    queues['attempt'] = Queue()
    queues['model'] = Queue()
    queues['text_generated_interactively'] = Queue()
    return queues



import signal

class GracefulExit(Exception):
    pass


def signal_handler(signum, frame):
    print('Signal handler called with signal', signum)
    # Kill the main_process process
    main_process.terminate()
    main_process.join()
    sys.exit(0)

    raise GracefulExit()


if __name__ == '__main__':
    # initialize_openai_api()
    # engines = openai.Engine.list()
    # print("engines:", engines)
    # input()
    args = get_args()
    queues = create_queues()
    # Start the main program in the background
    main_process = Process(target=main, args=(queues, args))
    main_process.start()

    if args.interactive:
        InteractiveCodingApp().run(log="textual.log")
    else:
        AutoCodingApp.run(log="textual.log")

    main_process.terminate()
    main_process.join()
    sys.exit(0)
