#!/usr/bin/env python3

import jupyter_client
import argparse

CODE_FILE = 'generated_code_interactive'

def get_output_ipython(msg):
    if 'data' in msg['content']:
        out_text = msg['content']['data']['text/plain']
        print(f'{out_text}')

def run_code_ipython(code, kernel_id):
    cf=jupyter_client.find_connection_file(kernel_id)
    km=jupyter_client.BlockingKernelClient(connection_file=cf)
    km.load_connection_file()

    km.execute_interactive(code, output_hook=get_output_ipython)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run code in an IPython kernel')
    parser.add_argument('--code', help='Python code to run,', default=None)
    parser.add_argument('--kernel-id', help='Kernel ID', default='python3')
    args = parser.parse_args()

    if args.code:
        code = args.code
    else:
        with open(CODE_FILE, 'r') as f:
            # read the last line
            code = f.readlines()[-1]



    run_code_ipython(code, args.kernel_id)
