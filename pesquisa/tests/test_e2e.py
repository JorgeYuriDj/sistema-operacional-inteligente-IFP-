import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyotp
import pytest
import requests
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect, TimeoutError as BrowserTimeout

from manage import provision, erasures_path
from storage import connect, backup

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8791"
SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
PASSWORD = "browser-test-password-32-characters"


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_browser_desktop_mobile_security_persistence_and_load(tmp_path, engine):
    key=Fernet.generate_key().decode()
    database=tmp_path/"e2e.sqlite3"
    provision(database,key,"admin",PASSWORD,SECRET)
    erasures_path(database).touch()
    env={**os.environ,"IFP_DATABASE":str(database),"IFP_ENCRYPTION_KEY":key,
         "IFP_SECRET_KEY":"browser-test-signing-key-long-enough-32", "IFP_ORIGIN":BASE}
    log=(tmp_path/"server.log").open("w",encoding="utf-8")
    def start():
        proc=subprocess.Popen([sys.executable,str(ROOT/"tests/serve_test.py")],cwd=ROOT,env=env,stdout=log,stderr=log)
        for _ in range(80):
            if proc.poll() is not None:raise AssertionError("Servidor de teste encerrou.")
            try:
                if requests.get(BASE+"/healthz",timeout=.5).status_code==200:return proc
            except requests.RequestException:pass
            time.sleep(.1)
        raise AssertionError("Servidor de teste não respondeu.")
    proc=start()
    screenshots=ROOT/"artifacts";screenshots.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel="chrome") if engine == "chromium" else p.webkit.launch(headless=True)
            desktop=browser.new_context(viewport={"width":1440,"height":1080},locale="pt-BR",accept_downloads=True)
            page=desktop.new_page();errors=[];csp=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.on("console",lambda message:csp.append(message.text) if "violat" in message.text.lower() and "policy" in message.text.lower() else None)
            page.goto(BASE)
            expect(page.get_by_role("heading",name="Sua formação tem voz.")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(screenshots/"public-desktop.png"),full_page=True)
            page.locator('#next').click()
            expect(page.locator('#step-label')).to_have_text("01 / 03")
            page.locator('[name=stage][value=s12]').check()
            page.locator('[name=area][value=personal]').check()
            page.locator('#next').click()
            for gap in ("training","sales"):page.locator(f'[name=gaps][value={gap}]').check()
            page.locator('[name=gaps][value=service]').click()
            expect(page.locator('[name=gaps]:checked')).to_have_count(2)
            expect(page.locator('#form-error')).to_contain_text("até duas")
            page.locator('[name=gaps][value=all]').check()
            expect(page.locator('[name=gaps]:checked')).to_have_count(1)
            page.locator('[name=gaps][value=training]').check()
            expect(page.locator('[name=gaps][value=all]')).not_to_be_checked()
            page.locator('[name=gaps][value=sales]').check()
            page.locator('[name=format][value=short]').check()
            page.locator('#next').click()
            page.locator('#open-privacy').click();expect(page.locator('dialog')).to_be_visible();page.keyboard.press('Escape')
            malicious='<img src=x onerror="window.injected=true"> Formação com prática.'
            page.locator('[name=wish]').fill(malicious)
            page.locator('[name=name]').fill("Participante fictício E2E")
            page.locator('[name=email]').fill("e2e@example.com")
            page.locator('[name=phone]').fill("61999999999")
            page.locator('[name=contact_consent]').check()
            page.locator('[name=research_consent]').check()
            page.locator('#submit').click();expect(page.locator('#success')).to_be_visible()
            receipt=page.locator('#receipt').inner_text();assert uuid.UUID(receipt)
            page.screenshot(path=str(screenshots/"receipt.png"),full_page=True)
            device=p.devices["Pixel 7"] if engine == "chromium" else p.devices["iPhone 13"]
            mobile=browser.new_context(**device,locale="pt-BR")
            mp=mobile.new_page();mp.goto(BASE)
            assert mp.evaluate("document.documentElement.scrollWidth <= innerWidth")
            mp.screenshot(path=str(screenshots/"public-mobile.png"),full_page=True)
            mp.locator('[name=stage][value=s34]').check();mp.locator('[name=area][value=group]').check();mp.locator('#next').click()
            mp.locator('[name=gaps][value=classes]').check();mp.locator('[name=format][value=workshops]').check();mp.locator('#next').click()
            mp.locator('[name=wish]').fill("Ter mais oportunidades de prática supervisionada.")
            mp.locator('[name=research_consent]').check()
            mp.route('**/api/responses',lambda route:route.abort())
            mp.locator('#submit').click();expect(mp.locator('#form-error')).to_contain_text("conexão falhou")
            expect(mp.locator('[name=wish]')).to_have_value("Ter mais oportunidades de prática supervisionada.")
            mp.unroute('**/api/responses');mp.locator('#submit').click();expect(mp.locator('#success')).to_be_visible()
            page.goto(BASE+'/admin');expect(page).to_have_url(BASE+'/login')
            page.locator('[name=username]').fill('admin');page.locator('[name=password]').fill(PASSWORD);page.locator('[name=code]').fill(pyotp.TOTP(SECRET).now());page.get_by_role('button',name='Entrar no painel').click()
            expect(page.locator('#total')).to_have_text('2');expect(page.locator('#contacts')).to_have_text('1')
            page.locator('#records details').last.get_by_text('Ler resposta e detalhes').click()
            expect(page.locator('#records')).to_contain_text(malicious)
            assert not page.evaluate('Boolean(window.injected)')
            assert page.locator('#records img').count()==0
            page.screenshot(path=str(screenshots/'admin-desktop.png'),full_page=True)
            export_responses=[]
            page.on('response',lambda response:export_responses.append({"status":response.status,"disposition":response.headers.get('content-disposition')}) if '/api/admin/export.csv' in response.url else None)
            try:
                with page.expect_download() as info:page.locator('#export').click()
            except BrowserTimeout as error:
                raise AssertionError({"download_timeout":True,"url":page.url,"responses":export_responses,"javascript":errors,"csp":csp}) from error
            download=info.value;download.save_as(str(tmp_path/'export.csv'))
            exported=list(csv.reader(io.StringIO((tmp_path/'export.csv').read_text(encoding='utf-8-sig')),delimiter=';'))
            assert len(exported)==3 and 'E-mail' in exported[0]
            page.locator('select[name=stage]').select_option('s12');page.get_by_role('button',name='Aplicar').click();expect(page.locator('#total')).to_have_text('1')
            page.locator('#clear').click();expect(page.locator('#total')).to_have_text('2')
            page.set_viewport_size({"width":390,"height":844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(screenshots/'admin-mobile.png'),full_page=True)
            proc.terminate();proc.wait(timeout=10);proc=start()
            page.reload();expect(page.locator('#total')).to_have_text('2')
            page.get_by_role('button',name='Sair').click();expect(page).to_have_url(BASE+'/login')
            assert requests.get(BASE+'/api/admin/responses').status_code==401
            assert not errors and not csp, (errors,csp)
            browser.close()
        # Escritas reais concorrentes pela rede; dados sintéticos no banco temporário.
        def send(index):
            s=requests.Session();html=s.get(BASE).text
            token=re.search(r'name="csrf-token" content="([^"]+)"',html)[1]
            body={"submission_key":str(uuid.uuid4()),"form_token":re.search(r'data-token="([^"]+)"',html)[1],"stage":"s56","area":"gym","gaps":["training"],"format":"online","wish":f"Resposta sintética concorrente {index}","research_consent":True}
            started=time.perf_counter();response=s.post(BASE+'/api/responses',json=body,headers={"X-CSRFToken":token,"Origin":BASE},timeout=20)
            return response.status_code,round((time.perf_counter()-started)*1000,1)
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(send,range(30)))
        assert all(code==201 for code,_ in results),results
        durations=sorted(ms for _,ms in results)
        with connect(database) as db:
            assert db.execute('SELECT COUNT(*) FROM responses').fetchone()[0]==32
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        snapshot=backup(database,tmp_path/'snapshot.sqlite3')
        with connect(snapshot) as db:assert db.execute('SELECT COUNT(*) FROM responses').fetchone()[0]==32
        (screenshots/f'e2e-summary-{engine}.json').write_text(json.dumps({"browser":engine,"device":"Pixel 7" if engine=="chromium" else "iPhone 13","responses":32,"concurrent_requests":30,"concurrency":12,"p95_ms":durations[28],"max_ms":max(durations),"restart_persistence":True,"backup_integrity":"ok","javascript_errors":errors,"csp_errors":csp},indent=2),encoding='utf-8')
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
