#!/usr/bin/env node
/**
 * Usage: node template.js <htmlInputPath> <pdfOutputPath> [<imageUrl>]
 */

const fs = require('fs');
const { DefaultAzureCredential } = require('@azure/identity');
const { BlobServiceClient }   = require('@azure/storage-blob');
const puppeteer = require('puppeteer');

/**
 * Fetches a blob or local file and returns its Base64‑encoded contents.
 */
async function getImageBase64(source) {
  if (source.startsWith('http')) {
    const url = new URL(source);
    const [, container, ...parts] = url.pathname.split('/');
    const blobName = parts.join('/');
    const cred = new DefaultAzureCredential();
    const client = new BlobServiceClient(`${url.protocol}//${url.host}`, cred);
    const blobClient = client.getContainerClient(container).getBlobClient(blobName);
    const download = await blobClient.download();
    const buffer = await new Promise((resolve, reject) => {
      const chunks = [];
      download.readableStreamBody.on('data', d => chunks.push(d));
      download.readableStreamBody.on('end', () => resolve(Buffer.concat(chunks)));
      download.readableStreamBody.on('error', reject);
    });
    return buffer.toString('base64');
  } else {
    // local file
    return fs.readFileSync(source).toString('base64');
  }
}

/**
 * Scans the HTML for any <img src="...*.svg"> URLs and inlines them as data URIs.
 */
async function inlineSvgs(html) {
  // gather unique SVG URLs from img tags
  const urls = new Set();
  for (const [, url] of html.matchAll(/<img[^>]+src="(https?:\/\/[^"]+\.svg)"/g)) {
    urls.add(url);
  }

  // replace each with its data URI
  for (const url of urls) {
    try {
      const b64 = await getImageBase64(url);
      const dataUri = `data:image/svg+xml;base64,${b64}`;
      // escape regex
      const re = new RegExp(url.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'g');
      html = html.replace(re, dataUri);
    } catch (e) {
      console.warn(`⚠️  Could not inline SVG ${url}:`, e.message);
    }
  }
  return html;
}

/**
 * Example header template — you can adjust styling as needed.
 */
function headerTemplate(data, img64) {
  const date = new Date();
  const d = [
    date.getDate().toString().padStart(2,'0'),
    (date.getMonth()+1).toString().padStart(2,'0'),
    date.getFullYear()
  ].join('.');
  return `
    <div style="display:flex;justify-content:space-between;width:85.8%;font-size:10px;
                padding-left:7.2%;padding-top:20px;">
      <img src="data:image/svg+xml;base64,${img64}" style="width:90px;" />
      <span style="font-size:7px;color:lightgrey;">Report, ${d}</span>
    </div>`;
}

/**
 * Example footer template.
 */
function footerTemplate() {
  return `
    <div style="font-size:7px;text-align:right;width:93%;color:lightgrey;
                padding-bottom:20px;">
      Page <span class="pageNumber"></span> of <span class="totalPages"></span>
    </div>`;
}

;(async () => {
  const [,, htmlPath, pdfPath, imageUrl] = process.argv;
  if (!htmlPath || !pdfPath) {
    console.error('Usage: node template.js <htmlInputPath> <pdfOutputPath> [<imageUrl>]');
    process.exit(1);
  }

  // 1) Read & inline any SVGs in the HTML
  let html = fs.readFileSync(htmlPath, 'utf-8');
  html = await inlineSvgs(html);

  // 2) Launch Puppeteer
  const browser = await puppeteer.launch({
    args: ['--no-sandbox','--disable-setuid-sandbox'],
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH
  });
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // 3) Prepare header/footer if an imageUrl was provided
  let header = '', footer = '';
  if (imageUrl) {
    const img64 = await getImageBase64(imageUrl);
    header = headerTemplate(null, img64);  // you can pass data into headerTemplate if needed
    footer = footerTemplate();
  }

  // 4) Generate the PDF
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: false,
    preferCSSPageSize: true,
    displayHeaderFooter: Boolean(header || footer),
    headerTemplate: header,
    footerTemplate: footer
  });

  await browser.close();
})();
