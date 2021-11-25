#!/usr/bin/env python3


import jupyter_client

cf=jupyter_client.find_connection_file('985658')
km=jupyter_client.BlockingKernelClient(connection_file=cf)
km.load_connection_file()



def print_out(msg):
    if 'data' in msg['content']:
        out_text = msg['content']['data']['text/plain']
        print(f'=== {out_text} ===')

km.execute_interactive('jkl=543')
km.execute_interactive('jkl', output_hook=print_out)

