import {createRequire} from 'node:module';
import {existsSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const base=process.env.PLAYWRIGHT_BASE_URL||'http://localhost:3000';
const output=fileURLToPath(new URL('../docs/screenshots/',import.meta.url));
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||(existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),args:['--no-sandbox','--disable-dev-shm-usage']});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1100},reducedMotion:'reduce'});
 await page.goto(base);await page.getByRole('heading',{name:/One idea/}).waitFor();
 await page.waitForFunction(() => [...document.querySelectorAll('.landing-hero > div')].every(element => getComputedStyle(element).opacity === '1'));
 await page.screenshot({path:output+'landing.png'});
 await page.getByRole('button',{name:'Explore the live demo'}).click();
 await page.getByRole('button',{name:'Review content',exact:true}).waitFor({timeout:60000});
 const runId=page.url().split('/').at(-1);
 await page.getByTestId('agent-fact_checker').click();
 await page.screenshot({path:output+'control-center.png',fullPage:true});
 await page.goto(`${base}/evidence/${runId}`);
 await page.getByTestId('claim-highlight').filter({hasText:'Battery electric vehicles produce no tailpipe emissions.'}).click();
 await page.screenshot({path:output+'evidence-studio.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.goto(`${base}/control/${runId}`);
 await page.getByRole('heading',{name:/Agent control center/}).waitFor();
 await page.screenshot({path:output+'mobile.png',fullPage:true});
 console.log('Captured four screenshots from the running demonstration.');
} finally {await browser.close();}
