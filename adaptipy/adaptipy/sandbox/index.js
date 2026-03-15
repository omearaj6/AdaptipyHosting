import express from "express";

if (process.env.TARGET_RAILWAY_PROJECT_ID) {
  process.env.RAILWAY_PROJECT_ID = process.env.TARGET_RAILWAY_PROJECT_ID;
}

if (process.env.TARGET_RAILWAY_ENVIRONMENT_ID) {
  process.env.RAILWAY_ENVIRONMENT_ID = process.env.TARGET_RAILWAY_ENVIRONMENT_ID;
}

const { compute } = await import("computesdk");

const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/run", async (req, res) => {
  const { code, timeoutMs = 5000 } = req.body || {};

  console.log("RUN REQUEST RECEIVED");

  if (typeof code !== "string") {
    console.log("INVALID CODE PAYLOAD");
    return res.status(400).json({ error: "code must be a string" });
  }

  let sandbox;

  try {
    console.log("ABOUT TO CREATE SANDBOX");
    sandbox = await compute.sandbox.create();
    console.log("SANDBOX CREATED");

    const wrapped = `
import signal, sys

def _timeout(signum, frame):
    print("Time limit exceeded (timeout).", file=sys.stderr)
    sys.exit(124)

signal.signal(signal.SIGALRM, _timeout)
signal.alarm(${Math.max(1, Math.ceil(timeoutMs / 1000))})

${code}
`;

    console.log("ABOUT TO RUN CODE");
    const result = await sandbox.runCode(wrapped, "python");
    console.log("CODE EXECUTED", result);

    res.json({
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
      exitCode: result.exitCode ?? 0
    });
  } catch (err) {
    console.error("RUN ERROR:", err);
    res.status(500).json({ error: String(err) });
  } finally {
    if (sandbox) {
      try {
        console.log("ABOUT TO DESTROY SANDBOX");
        await sandbox.destroy();
        console.log("SANDBOX DESTROYED");
      } catch (destroyErr) {
        console.error("DESTROY ERROR:", destroyErr);
      }
    }
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Runner listening on ${port}`);
});