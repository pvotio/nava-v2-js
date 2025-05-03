import { ServiceBusClient } from "@azure/service-bus";
import { DefaultAzureCredential } from "@azure/identity";
import { BlobClient, BlobServiceClient } from "@azure/storage-blob";
import pLimit from "p-limit";
import zlib from "zlib";
import { generatePdf } from "./pdf.js";

/* -------------------------------------------------------------------------- */
/* ENV & CLIENT INITIALISATION                                                */
/* -------------------------------------------------------------------------- */
const {
  SB_NAMESPACE,
  SB_QUEUE,
  PDF_CONTAINER,
  WORKER_CONCURRENCY = 3
} = process.env;

if (!SB_NAMESPACE || !SB_QUEUE || !PDF_CONTAINER) {
  throw new Error("SB_NAMESPACE, SB_QUEUE and PDF_CONTAINER environment variables are required");
}

const sbClient = new ServiceBusClient(
  `${SB_NAMESPACE}.servicebus.windows.net`,
  new DefaultAzureCredential()
);
const receiver = sbClient.createReceiver(SB_QUEUE);

const blobService = new BlobServiceClient(
  process.env.STORAGE_URL,
  new DefaultAzureCredential()
);
const pdfContainer = blobService.getContainerClient(PDF_CONTAINER);

const limit = pLimit(Number(WORKER_CONCURRENCY));

/* -------------------------------------------------------------------------- */
/* HELPERS                                                                    */
/* -------------------------------------------------------------------------- */
async function downloadHtml(blobUrl, compressed) {
  const blobClient = new BlobClient(blobUrl);
  const data       = await blobClient.downloadToBuffer();
  return compressed ? zlib.gunzipSync(data).toString("utf8") : data.toString("utf8");
}

/* -------------------------------------------------------------------------- */
/* MESSAGE HANDLER                                                            */
/* -------------------------------------------------------------------------- */
receiver.subscribe({
  processMessage: async (msg) => {
    await limit(async () => {
      try {
        const {
          jobId,
          template,
          blobUrl,
          compressed = false,
          userId,
          fileName = `${template}.pdf`
        } = msg.body;

        if (!jobId || !template || !blobUrl || !userId) {
          throw new Error("Invalid message payload – missing jobId/template/blobUrl/userId");
        }

        // Download HTML payload
        const html = await downloadHtml(blobUrl, compressed);

        // Generate PDF buffer
        const pdfBuffer = await generatePdf(template, html);

        // Upload PDF to storage with metadata
        const blockBlob = pdfContainer.getBlockBlobClient(`${jobId}.pdf`);
        await blockBlob.uploadData(pdfBuffer, {
          blobHTTPHeaders: { blobContentType: "application/pdf" },
          metadata: {
            owner: userId,
            filename: fileName,
            downloaded: "false"
          }
        });

        await receiver.completeMessage(msg);
        console.log(`✔ processed job ${jobId}`);
      } catch (err) {
        console.error("✖ job failed", err);
        await receiver.abandonMessage(msg, { deadLetterErrorDescription: err.message });
      }
    });
  },
  processError: (err) => console.error("Receiver error", err)
});

/* -------------------------------------------------------------------------- */
/* Graceful shutdown                                                           */
/* -------------------------------------------------------------------------- */
process.on("SIGTERM", async () => {
  console.log("Shutting down worker…");
  await receiver.close();
  await sbClient.close();
  process.exit(0);
});
