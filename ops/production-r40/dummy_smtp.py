from __future__ import annotations
import argparse, asyncio, re
from datetime import datetime
from pathlib import Path

async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, out: Path):
    peer=writer.get_extra_info('peername')
    writer.write(b'220 build360-r40.local ESMTP Dummy SMTP\r\n'); await writer.drain()
    data_mode=False; lines=[]; mail_from=''; rcpts=[]
    while True:
        raw=await reader.readline()
        if not raw: break
        line=raw.decode('utf-8','replace').rstrip('\r\n')
        if data_mode:
            if line=='.':
                stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                path=out/f'message_{stamp}.eml'
                path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
                subject=next((x[8:].strip() for x in lines if x.lower().startswith('subject:')), '(no subject)')
                print(f'[CAPTURED] {path} | to={rcpts} | subject={subject}', flush=True)
                lines=[]; data_mode=False
                writer.write(b'250 2.0.0 message accepted\r\n'); await writer.drain(); continue
            lines.append(line[1:] if line.startswith('..') else line); continue
        upper=line.upper()
        if upper.startswith('EHLO'):
            writer.write(b'250-build360-r40.local\r\n250 SIZE 26214400\r\n')
        elif upper.startswith('HELO'):
            writer.write(b'250 build360-r40.local\r\n')
        elif upper.startswith('MAIL FROM:'):
            mail_from=line[10:].strip(); rcpts=[]; writer.write(b'250 2.1.0 OK\r\n')
        elif upper.startswith('RCPT TO:'):
            rcpts.append(line[8:].strip()); writer.write(b'250 2.1.5 OK\r\n')
        elif upper=='DATA':
            data_mode=True; lines=[]; writer.write(b'354 End data with <CR><LF>.<CR><LF>\r\n')
        elif upper=='RSET':
            lines=[]; rcpts=[]; mail_from=''; writer.write(b'250 2.0.0 reset\r\n')
        elif upper=='NOOP': writer.write(b'250 2.0.0 OK\r\n')
        elif upper=='QUIT':
            writer.write(b'221 2.0.0 bye\r\n'); await writer.drain(); break
        else: writer.write(b'250 2.0.0 OK\r\n')
        await writer.drain()
    writer.close(); await writer.wait_closed()

async def main_async(host:str,port:int,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    server=await asyncio.start_server(lambda r,w: handle(r,w,out),host,port)
    print('Build360 R40 DEMO Dummy SMTP')
    print(f'Listening: {host}:{port}')
    print(f'Captured emails: {out}')
    print('Use only in DEMO. TLS/SSL must be OFF in the company SMTP form.')
    async with server: await server.serve_forever()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=1025); p.add_argument('--out',required=True); a=p.parse_args()
    try: asyncio.run(main_async(a.host,a.port,Path(a.out)))
    except KeyboardInterrupt: print('\nDummy SMTP stopped.')
if __name__=='__main__': main()
