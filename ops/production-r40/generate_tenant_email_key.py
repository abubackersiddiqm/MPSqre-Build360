from __future__ import annotations
import argparse
from pathlib import Path
from cryptography.fernet import Fernet

PLACEHOLDERS=('replace-with','replace-me','changeme','<','>')
def main():
    p=argparse.ArgumentParser(); p.add_argument('target'); a=p.parse_args(); root=Path(a.target).resolve(); env=root/'backend/.env.production'
    if not env.is_file(): raise SystemExit('[ERROR] backend/.env.production is missing. Run Prepare-Production-R38.bat first.')
    text=env.read_text(encoding='utf-8'); lines=text.splitlines(); key='TENANT_EMAIL_CREDENTIAL_KEYS'; found=False; changed=False
    for i,line in enumerate(lines):
        if line.startswith(key+'='):
            found=True; value=line.split('=',1)[1].strip()
            if value and not any(x in value.lower() for x in PLACEHOLDERS):
                print('[OK] TENANT_EMAIL_CREDENTIAL_KEYS is already configured. No change made.'); return
            lines[i]=key+'='+Fernet.generate_key().decode('ascii'); changed=True; break
    if not found:
        insert_at=next((i+1 for i,l in enumerate(lines) if l.startswith('CRM_PROTECTED_DATA_KEYS=')),len(lines))
        lines.insert(insert_at,key+'='+Fernet.generate_key().decode('ascii')); changed=True
    if changed:
        env.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print('[OK] Dedicated tenant-email Fernet key generated in backend/.env.production.')
        print('     The key was not printed to the console.')
if __name__=='__main__': main()
