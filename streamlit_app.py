from readme_coder import *
import sys

import streamlit as st
from PIL import Image

st.set_page_config(page_title="Phanes", layout="wide", initial_sidebar_state="expanded", page_icon="res/logo.jpeg")

logo_image = Image.open('res/logo.jpeg')

col1, col2, col3 = st.columns([12,10,10])
with col1:
    st.title('PHANES-V1')

with col2:
    st.write("")

with col3:
    st.image(logo_image, width=200)

command_str = './readme_coder.py main.py python3 main.py "a-doering" -s 100 -a 10000 -n 1000 '
sys.argv = command_str.split()
# st.write(sys.argv)



# example sidebar
st.sidebar.title("About this app")
st.sidebar.info(
    "This is a demo web application written in Python using "
    "the [Streamlit](https://streamlit.io/) library. "
    "The app demonstrates how to use various data types "
    "and features of Streamlit, including text, widgets, "
    "data frame display, and so on."
)

st.sidebar.slider("How old are you?", 0, 100, 25)

# example header
st.header("This is a header")

st.subheader("This is a subheader")

st.text("This is a text region. "
        "Add text hereto describe your "
        "web app, its goals, and its "
        "approach.")

st.code("import numpy as np")

st.markdown("#### This is a Markdown title")
st.markdown("##### This is a Markdown sub-title")
st.markdown("###### This is a Markdown sub-sub-title")


args = get_args()
queues = create_queues()
# Start the main program in the background
main_process = Process(target=main, args=(queues, args))
main_process.start()


col11, col12 = st.columns([10,10])
with col11:
    st.write("")


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
        print("code_blocks:", code_blocks)
        len_code_blocks = len(code_blocks)
        print("len_code_blocks:", len_code_blocks)
        for code_block in code_blocks:
            filename = code_block.strip().split('\n')[0][2:-3]
            code = '\n'.join(code_block.split('\n')[1:])
            code_blocks_list.append((filename, code))

        print("code_blocks_list:", code_blocks_list)
        return code_blocks_list

    def reset_code_view(self):
        st.write('reset_code_view')
        for filename_box, code_box in self.components_all:
            filename_box.empty()
            code_box.empty()

    def update_code_view(self, code):
        code_blocks_list = self.get_code_splits(code)
        if self.last_num_code_blocks < len(code_blocks_list):
            self.reset_code_view()

        self.last_num_code_blocks = len(code_blocks_list)

        for i, code_block in enumerate(code_blocks_list):
            filename, code = code_block
            filename_box, code_box = self.components_all[i]
            filename_box.markdown(f'`{filename}`')
            code_box.code(code)






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


while True:
    code_viewer.refresh_code_view()




main_process.terminate()
main_process.join()
sys.exit(0)
