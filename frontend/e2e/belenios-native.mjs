// Explicit native-booth laboratory votes. Not collected by the mocked UI suite.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const directory=path.join(root,'.runtime/adr-live');
const stateFile=path.join(directory,'state.json');
const state=JSON.parse(fs.readFileSync(stateFile));
assert.equal(state.phase,'open','Existing/uncertain native vote state requires manual reconciliation');
const journalFile=path.join(directory,'native-votes.json');
const journal=fs.existsSync(journalFile)?JSON.parse(fs.readFileSync(journalFile)):{};
const save=()=>fs.writeFileSync(journalFile,JSON.stringify(journal,null,2));
const credentials=JSON.parse(fs.readFileSync(state.private_credentials_file));
const browser=await chromium.launch({headless:true});
const origin='http://127.0.0.1:18002';
try {
  for(const [id,index,selection,expected] of [['vote-0',0,0,'Ok'],['vote-1',1,1,'Ok'],['revote-0',0,1,'Error']]) {
    if(journal[id]?.phase==='confirmed')continue;
    if(journal[id])throw new Error('Uncertain native attempt: do not repeat');
    journal[id]={phase:'attempt_started'};save();
    const context=await browser.newContext({locale:'en-US',serviceWorkers:'block'});
    await context.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
    const page=await context.newPage();let result;
    page.on('response',async response=>{
      if(response.url().startsWith(origin+'/api/cast-result/')&&response.status()===200){const body=await response.json();result=body[0]==='Ok'?{kind:'Ok',hash:body[1].hash}:{kind:'Error',error:body[1]};}
    });
    await page.goto(origin+'/election#'+state.uuid);await page.locator('#start').click();
    await page.locator('#credential').fill(credentials[state.voters[index]]);await page.locator('.input-credential-section__button').click();
    await page.locator(`label[for="question_0__choice_${selection}"]`).click();await page.locator('.vote-navigation__next-button').click();
    await page.locator('.review-encrypt-section').getByRole('button',{name:'Next',exact:true}).click();
    await page.locator('input[type=text]').waitFor();
    if(await page.locator('#username').isVisible()){
      await page.locator('#username').fill(state.voters[index]);await page.locator('input[type=submit]').click();
      await page.waitForFunction(()=>!document.querySelector('#username'));
    }
    const mail=execFileSync('docker',['exec','theogen-belenios33-poc-single-1','cat','/home/belenios/poc-data/private/mail.txt'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
    assert.ok(mail.includes(state.voters[index]));
    const otp=[...mail.matchAll(/^  (\d{6})\r?$/gm)].at(-1)[1];
    await page.locator('input[type=text]').fill(otp);await page.locator('input[type=submit]').click();
    for(let i=0;i<60&&!result;i++)await new Promise(r=>setTimeout(r,250));
    assert.equal(result?.kind,expected);if(expected==='Error')assert.equal(result.error,'RevoteNotAllowed');
    journal[id]={phase:'confirmed',result};save();await context.close();
    console.log(JSON.stringify({native_scenario:id,result:result.kind,error:result.error}));
  }
  const response=await fetch(origin+'/api/elections/'+state.uuid+'/ballots');
  assert.equal(Object.keys(await response.json()).length,2);
  state.phase='votes_confirmed';fs.writeFileSync(stateFile,JSON.stringify(state));
}catch(error){fs.writeFileSync(path.join(directory,'native-failure.txt'),error.stack);console.error('Native test stopped; reconcile the private journal before continuing.');process.exitCode=1;}
finally{await browser.close();}
