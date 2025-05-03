#!/usr/bin/env node
/**
 * Usage: node product-de.js <htmlInputPath> <pdfOutputPath> [<imageUrl>]
 */

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');
const { DefaultAzureCredential } = require('@azure/identity');
const { BlobServiceClient }   = require('@azure/storage-blob');

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
    const blobClient = client
      .getContainerClient(container)
      .getBlobClient(blobName);
    const download = await blobClient.download();
    return await new Promise((resolve, reject) => {
      const chunks = [];
      download.readableStreamBody.on('data', d => chunks.push(d));
      download.readableStreamBody.on('end', () => {
        resolve(Buffer.concat(chunks).toString('base64'));
      });
      download.readableStreamBody.on('error', reject);
    });
  } else {
    return fs.readFileSync(source).toString('base64');
  }
}

/**
 * Scans the HTML for any <img src="https://.../*.svg"> and
 * replaces each with a data URI via Managed Identity.
 */
async function inlineSvgs(html) {
  const urls = new Set(
    [...html.matchAll(/<img[^>]+src="(https?:\/\/[^"]+\.svg)"/g)].map(m => m[1])
  );
  for (const url of urls) {
    try {
      const b64 = await getImageBase64(url);
      const dataUri = `data:image/svg+xml;base64,${b64}`;
      const re = new RegExp(url.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'g');
      html = html.replace(re, dataUri);
    } catch (err) {
      console.warn(`⚠️ Failed to inline SVG ${url}:`, err.message);
    }
  }
  return html;
}

/**
 * Builds the PDF header HTML, inlining the logo and date.
 */
function headerTemplate(img64) {
  const dt = new Date();
  const d = [
    dt.getDate().toString().padStart(2,'0'),
    (dt.getMonth()+1).toString().padStart(2,'0'),
    dt.getFullYear()
  ].join('.');
  return `
    <div style="display:flex;justify-content:space-between;
                width:85.8%;font-size:10px;
                padding-left:7.2%;padding-top:20px;">
      <img src="data:image/svg+xml;base64,${img64}" style="width:90px;" />
      <span style="font-size:7px;color:lightgrey;">Produktreport, ${d}</span>
    </div>`;
}

/**
 * Builds the PDF footer HTML.
 */
function footerTemplate() {
  return `
    <div style="display:flex;justify-content:space-between;
                align-items:center;width:93%;font-size:7px;
                color:lightgrey;padding-bottom:20px;">
      <div style="flex-shrink:0;text-align:left;padding-left:60px;">
        <span>XXXXX</span>
      </div>
      <div style="flex-grow:1;text-align:right;">
        <span><span class="pageNumber"></span>/<span class="totalPages"></span></span>
      </div>
    </div>`;
}

;(async () => {
  const [,, htmlPath, pdfPath, imageUrl] = process.argv;
  if (!htmlPath || !pdfPath) {
    console.error(
      'Usage: node product-de.js <htmlInputPath> <pdfOutputPath> [<imageUrl>]'
    );
    process.exit(1);
  }

  // 1) Read & inline any SVGs in the HTML template
  let html = fs.readFileSync(htmlPath, 'utf-8');
  html = await inlineSvgs(html);

  // 2) Launch Puppeteer and load HTML
  const browser = await puppeteer.launch({
    args: ['--no-sandbox','--disable-setuid-sandbox'],
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH
  });
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // 3) Prepare header/footer (fetch logo once)
  let header = '', footer = '';
  if (imageUrl) {
    const img64 = await getImageBase64(imageUrl);
    header = headerTemplate(img64);
    footer = footerTemplate();
  }

  // 4) Generate the PDF
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    scale: 1,
    printBackground: false,
    preferCSSPageSize: true,
    displayHeaderFooter: Boolean(header || footer),
    headerTemplate: header,
    footerTemplate: footer
  });

  await browser.close();
})();
