from readme_coder import *
import sys

import streamlit as st
from PIL import Image
import os
# from streamlit_ace import st_ace


# sidebar_state = 'expanded'
sidebar_state = 'collapsed'
# sidebar_state = 'auto'
st.set_page_config(page_title="Phanes", layout="wide", initial_sidebar_state=sidebar_state, page_icon="res/logo.jpeg")
time_last_refreshed = st.sidebar.empty()



        # if not queues['attempt'].empty():
            # attempt = queues['attempt'].get()
            # self.last_attempt = attempt
        # else:
           # attempt = self.last_attempt

        # if not queues['model'].empty():
            # model = queues['model'].get()
            # self.last_model = model
        # else:
            # model = self.last_model

        # # attempt = self.last_attempt

        # text = ''
        # text += f'Main file: {args.main_file}\n'
        # text += f'Command: {args.command}\n'
        # text += f'Number of tokens: {args.num_tokens}\n'
        # text += f'Number of attempts: {args.num_attempts}\n'
        # text += f'Number of solutions: {args.num_solutions}\n'
        # text += f'Expected output: {args.output}\n'
        # text += f'Timeout: {args.timeout}\n'
        # text += f'Wait: {args.wait}\n'
        # text += f'Model: {args.model}\n'
        # text += f'Backtrack: {args.backtrack}\n'
        # text += f'\n'
        # text += f'Model Version: {model}\n'
        # text += f'Attempt: {attempt}'









logo_image = Image.open('res/logo.jpeg')

col1, col2, col3 = st.columns([5,10,10])
with col1:
    # st.image(logo_image, width=200)
    st.title('PHANES-V1')
    pass

with col2:
    st.write("")
    st.write("")
    st.write("")
    # st.title('PHANES-V1')

with col3:
    st.image(logo_image, width=200)

command_str = './readme_coder.py main.py python3 main.py "a-doering" -s 100 -a 10000 -n 1000 '
sys.argv = command_str.split()
# st.write(sys.argv)


args = get_args()
num_tokens = st.sidebar.slider("Maximum number of tokens", 0, 4000, args.num_tokens)
args.num_tokens = num_tokens

st.sidebar.markdown(f'### Main file: `{args.main_file}`')
st.sidebar.markdown(f'### Command: `{args.command}`')
st.sidebar.markdown(f'### Maximum number of tokens: `{args.num_tokens}`')
st.sidebar.markdown(f'### Maximum number of attempts: `{args.num_attempts}`')
st.sidebar.markdown(f'### Maximum number of solutions: `{args.num_solutions}`')
st.sidebar.markdown(f'### Expected output: `{args.output}`')
st.sidebar.markdown(f'### Timeout: `{args.timeout}`')
st.sidebar.markdown(f'### Wait: `{args.wait}`')
st.sidebar.markdown(f'### Model: `{args.model}`')
st.sidebar.markdown(f'### Backtrack: `{args.backtrack}`')

# Same information, but in a table in the sidebar
st.sidebar.table(
    [
        [f"Main file", f"{args.main_file}"],
        [f"Command", f"{args.command}"],
        [f"Maximum number of tokens", f"{args.num_tokens}"],
        [f"Maximum number of attempts", f"{args.num_attempts}"],
        [f"Maximum number of solutions", f"{args.num_solutions}"],
        [f"Expected output", f"{args.output}"],
        [f"Timeout", f"{args.timeout}"],
        [f"Wait", f"{args.wait}"],
        [f"Model", f"{args.model}"],
        [f"Backtrack", f"{args.backtrack}"],
    ]
)







base_dir = get_base_dir(args.base_dir)
readme_path = os.path.join(base_dir, 'README.md')
with open(readme_path, 'r') as f:
    readme_text = f.read()


queues = create_queues()
# Start the main program in the background
main_process = Process(target=main, args=(queues, args))
main_process.start()


col11, col12, col13 = st.columns([10,10,10])
with col11:
    # st.write("")
    st.header('Input')
    readme_text_box = st.empty()
    markdown_box = st.empty()
    running_button = st.button("Start")


with col12:
    # st.write("")
    st.header('Output')

with col13:
    # st.write("")
    st.header('Test')
    script_output = st.empty()
    execution_shell = st.empty()
    pytest_shell = st.empty()
    pytest_output = st.empty()



# with col11:
    # readme_text = st.text_area('README.md', value=readme_text, height=500)
    # st.markdown(readme_text)



class CodeView():
    def __init__(self):
        with col12:
            # st.markdown('`main.py`')
            self.code_view = st.empty()

        self.components_all = []
        self.create_empty_component()
        self.last_num_code_blocks = 0


    def create_empty_component(self, num_components=100):
        components = []
        with col12:
            for i in range(num_components):
                components.append((st.empty(), st.empty()))

        # reverse the list
        self.components_all = components[::-1]

    def get_code_splits(self, code):
        code_blocks_list = []
        code_blocks = code.split(SEPERATION_LINE)
        # len_code_blocks = len(code_blocks)
        for code_block in code_blocks:
            filename = code_block.strip().split('\n')[0][2:-3]
            code = '\n'.join(code_block.strip().split('\n')[1:])
            code_blocks_list.append((filename, code))

        return code_blocks_list

    def reset_code_view(self):
        # st.write('reset_code_view')
        for filename_box, code_box in self.components_all:
            filename_box.empty()
            code_box.empty()

    def update_code_view(self, code):
        code_blocks_list = self.get_code_splits(code)
        if len(code_blocks_list) < self.last_num_code_blocks:
            self.reset_code_view()

        self.last_num_code_blocks = len(code_blocks_list)

        for i, code_block in enumerate(code_blocks_list):
            filename, code = code_block
            filename_box, code_box = self.components_all[i]
            filename_box.markdown(f'`{filename}`')
            code_box.code(code)
            # st_ace(code)






    def refresh_code_view(self):
        # text = self.last_text
        # print("text:", text)
        while not queues['generated_code'].empty():
            try:
                text = queues['generated_code'].get_nowait()
                # self.last_text = text
            except Exception as e:
                print(e)

            # self.code_view.code(text)
            self.update_code_view(text)




code_viewer = CodeView()
# queues['pytest_output'].put('test')
# queues['script_output'].put('test o')

# with col11:
    # pytest_output = st.empty()



while True:
    readme_text = readme_text_box.text_area('README.md', value=readme_text, height=200, key=time.time())
    markdown_box.markdown(readme_text)

    # if False:
    if True:
        if not running_button:
            time.sleep(0.1)
            continue

    code_viewer.refresh_code_view()
    try:
        if not queues['pytest_output'].empty():
            text = queues['pytest_output'].get_nowait()
            # pytest_output.info(text)
            pytest_shell.code(f'$ pytest\n{text}', language='bash')
    except Exception as e:
        print(e)
        pass

    if not queues['script_output'].empty():
        command_output = queues['script_output'].get_nowait()
        # script_output.success(command_output)

        if not queues['script_command'].empty():
            command_str = queues['script_command'].get_nowait()

            execution_shell.code(f'$ {command_str}\n{command_output}', language='bash')

    time_last_refreshed.text(f'Last refreshed: {time.asctime()}')



# main()

# 






main_process.terminate()
main_process.join()
sys.exit(0)
