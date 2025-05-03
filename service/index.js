
"use strict";

/* -------------------------------------------------------------------------- */
/* Imports                                                                     */
/* -------------------------------------------------------------------------- */
const express                   = require("express");
const helmet                    = require("helmet");
const { expressjwt: jwt }       = require("express-jwt");
const jwksRsa                   = require("jwks-rsa");
const { DefaultAzureCredential }= require("@azure/identity");
const { ServiceBusClient }      = require("@azure/service-bus");
const { BlobServiceClient,
        generateBlobSASQueryParameters,
        BlobSASPermissions,
        SASProtocol }           = require("@azure/storage-blob");
const { v4: uuidv4 }            = require("uuid");
const zlib                      = require("zlib");
const sql                       = require("mssql");
const { execFile }              = require("child_process");
const path                      = require("path");
const fs                        = require("fs");
const NodeCache                 = require("node-cache");
const puppeteer                 = require("puppeteer");
const jwtSign                   = require("jsonwebtoken");          // NEW

/* -------------------------------------------------------------------------- */
/* Basic app config                                                            */
/* -------------------------------------------------------------------------- */
const app  = express();
app.use(helmet());
const port = process.env.PORT || 3000;
app.use(express.json());

/* ConfigMap mount path for template assets */
const SCRIPTS = process.env.SCRIPTS_DIR || path.join(__dirname, "../scripts");

/* -------------------------------------------------------------------------- */
/* Storage setup (payload + generated-pdfs containers)                         */
/* -------------------------------------------------------------------------- */
const storageUrl            = process.env.STORAGE_URL;
const payloadContainerName  = process.env.PAYLOAD_CONTAINER || "pdfpayloads";
const pdfContainerName      = process.env.PDF_CONTAINER     || "generated-pdfs";

if (!storageUrl) {
  console.error("Missing STORAGE_URL environment variable");
  process.exit(1);
}

const blobSvc          = new BlobServiceClient(storageUrl, new DefaultAzureCredential());
const payloadContainer = blobSvc.getContainerClient(payloadContainerName);
const pdfContainer     = blobSvc.getContainerClient(pdfContainerName);

/* -------------------------------------------------------------------------- */
/* JWT / JWKS SETUP (Azure AD + Auth0)                                         */
/* -------------------------------------------------------------------------- */
const azureTenantId = process.env.AZURE_TENANT_ID;
const azureAudience = process.env.AZURE_AD_AUDIENCE;
const auth0Domain   = process.env.AUTH0_DOMAIN;
const auth0Audience = process.env.AUTH0_API_AUDIENCE;

const azureJwksClient = jwksRsa({
  cache: true, rateLimit: true,
  jwksUri: `https://login.microsoftonline.com/${azureTenantId}/discovery/v2.0/keys`
});
const auth0JwksClient = jwksRsa({
  cache: true, rateLimit: true,
  jwksUri: `https://${auth0Domain}/.well-known/jwks.json`
});

const allowedIssuers = {
  [`https://login.microsoftonline.com/${azureTenantId}/v2.0`]: azureJwksClient,
  [`https://${auth0Domain}/`]: auth0JwksClient
};

app.use(jwt({
  secret: (req, token, done) => {
    const client = allowedIssuers[token.payload.iss];
    if (!client) return done(new Error("Untrusted issuer"));
    client.getSigningKey(token.header.kid, (err, key) => {
      if (err) return done(err);
      done(null, key.getPublicKey());
    });
  },
  audience: [azureAudience, auth0Audience],
  issuer: Object.keys(allowedIssuers),
  algorithms: ["RS256"]
}));

/* -------------------------------------------------------------------------- */
/* Azure Service Bus setup                                                     */
/* -------------------------------------------------------------------------- */
const sbClient = new ServiceBusClient(
  `${process.env.SB_NAMESPACE}.servicebus.windows.net`,
  new DefaultAzureCredential()
);
const sbSender = sbClient.createSender(process.env.SB_QUEUE || "pdf-jobs");

/* -------------------------------------------------------------------------- */
/* Azure SQL Connection & Logging                                              */
/* -------------------------------------------------------------------------- */
// getSqlPool() and log() unchanged from your original file

/* -------------------------------------------------------------------------- */
/* CACHE & TEMPLATE REGISTRY                                                   */
/* -------------------------------------------------------------------------- */
const pdfCache = new NodeCache({ stdTTL: 60, checkperiod: 30 });
const TEMPLATES = {
  "crm-trade-invoice": { script: "crm-trade-invoice.py", params: ["tradeid"] },
  "product-de":        { script: "product-de.py",        params: ["isin", "date"] }
};

/* Helper renderHtml remains unchanged from your original file */

/* -------------------------------------------------------------------------- */
/* ONE-TIME GENERATION TICKET (60s TTL)                                        */
/* -------------------------------------------------------------------------- */
const TICKET_TTL = 60;
if (!process.env.TICKET_SECRET) {
  console.error("TICKET_SECRET env var missing");
  process.exit(1);
}
const ticketCache = new NodeCache({ stdTTL: TICKET_TTL + 5 });

app.post("/pdf-tickets", (req, res) => {
  const payload = {
    sub: req.auth.sub,
    jti: uuidv4(),
    exp: Math.floor(Date.now() / 1000) + TICKET_TTL
  };
  const ticket = jwtSign.sign(payload, process.env.TICKET_SECRET);
  res.json({ ticket, ttl: TICKET_TTL });
});

function verifyTicket(tok, user) {
  try {
    const t = jwtSign.verify(tok, process.env.TICKET_SECRET);
    if (t.sub !== user) throw new Error("wrong-user");
    if (ticketCache.get(t.jti)) throw new Error("reused");
    ticketCache.set(t.jti, true);
    return true;
  } catch {
    return false;
  }
}

/* -------------------------------------------------------------------------- */
/* REQUEST-PDF endpoint with deduplication (60s)                               */
/* -------------------------------------------------------------------------- */
const jobCache = new NodeCache({ stdTTL: 60, checkperiod: 30 });

app.post("/request-pdf/:template(*)", async (req, res) => {
  const ticket = req.headers["x-pdf-ticket"] || req.body.ticket;
  if (!verifyTicket(ticket, req.auth.sub)) {
    return res.status(410).send("ticket missing / invalid / reused");
  }

  const template = req.params.template;
  const entry = TEMPLATES[template];
  if (!entry) return res.status(404).send("Unknown template");

  const params = { ...req.query, ...req.body };
  const missing = entry.params.filter(p => !params[p]);
  if (missing.length) return res.status(400).send(`Missing required parameters: ${missing.join(",")}`);

  const key = template + "|" + entry.params.map(p => `${p}=${params[p]}`).join("&");
  const cachedJob = jobCache.get(key);
  if (cachedJob) {
    await log("info", "PDF_REUSED", { template, jobId: cachedJob, user: req.auth.sub });
    return res.status(202).json({ status: "queued", jobId: cachedJob });
  }

  try {
    const html = await renderHtml(template, params);
    await payloadContainer.createIfNotExists();

    const jobId = uuidv4();
    const blob = payloadContainer.getBlockBlobClient(`${jobId}.html.gz`);
    const gz = zlib.gzipSync(Buffer.from(html, "utf8"));
    await blob.uploadData(gz, {
      blobHTTPHeaders: { blobContentType: "text/html", blobContentEncoding: "gzip" }
    });

    await sbSender.sendMessages({
      body: {
        jobId, template, blobUrl: blob.url, compressed: true,
        userId: req.auth.sub, fileName: `${template}.pdf`
      },
      contentType: "application/json"
    });

    jobCache.set(key, jobId);
    await log("info", "PDF_QUEUED", { template, jobId, user: req.auth.sub });
    res.status(202).json({ status: "queued", jobId });
  } catch (err) {
    console.error("Claim-check enqueue error", err);
    res.status(502).send("Queue unavailable");
  }
});

/* -------------------------------------------------------------------------- */
/* Sync /generate-pdf endpoint (unchanged)                                     */
/* -------------------------------------------------------------------------- */
app.get("/generate-pdf/:template(*)", async (req, res) => {
  const template = req.params.template;
  const entry = TEMPLATES[template];
  if (!entry) return res.status(404).send("Unknown template");
  const missing = entry.params.filter(p => !req.query[p]);
  if (missing.length)
    return res.status(400).send(`Missing required parameters: ${missing.join(",")}`);
  try {
    await log("info", "PDF_REQUEST", {
      template, params: req.query, user: req.auth?.sub || "anonymous"
    });
  } catch {}
  const key = [
    template,
    ...entry.params.map(p => req.query[p]),
    req.query.imageUrl || ""
  ].join("|");
  const cached = pdfCache.get(key);
  if (cached) {
    res.type("application/pdf").send(cached);
    return;
  }
  let html;
  try {
    html = await renderHtml(template, req.query);
  } catch (err) {
    console.error("Render error", err);
    return res.status(500).send("Template error");
  }
  try {
    const browser = await puppeteer.launch({
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH
    });
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });
    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: false,
      preferCSSPageSize: true
    });
    await browser.close();
    pdfCache.set(key, pdfBuffer);
    res.type("application/pdf").send(pdfBuffer);
  } catch (err) {
    console.error("Puppeteer error", err);
    res.status(500).send("PDF generation error");
  }
});

/* -------------------------------------------------------------------------- */
/* STREAM-ONCE DOWNLOAD                                                        */
/* -------------------------------------------------------------------------- */
app.get("/download-pdf/:id", async (req, res) => {
  const pdfBlob = pdfContainer.getBlobClient(`${req.params.id}.pdf`);
  if (!(await pdfBlob.exists())) return res.sendStatus(404);

  const props = await pdfBlob.getProperties();
  if (props.metadata?.owner !== req.auth.sub) return res.sendStatus(403);
  if (props.metadata?.downloaded === "true") return res.sendStatus(410);

  await pdfBlob.setMetadata({ ...props.metadata, downloaded: "true" });

  const dl = await pdfBlob.download();
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader(
    "Content-Disposition",
    `attachment; filename="${props.metadata?.filename || "document.pdf"}"`
  );
  dl.readableStreamBody.pipe(res);
});

/* -------------------------------------------------------------------------- */
/* Global error handler + healthz + start                                      */
/* -------------------------------------------------------------------------- */
app.use((err, req, res, _next) =>
  err.name === "UnauthorizedError"
    ? res.status(401).send("Invalid or missing token")
    : (console.error(err), res.status(500).send("Unexpected error"))
);

app.get("/healthz", (_req, res) => res.status(200).send("ok"));
app.listen(port, () => console.log(`🚀 PDF service listening on port ${port}`));
