import express from "express";
import { compute } from "computesdk";

const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/run", async (req, res) => {
  const { code, timeoutMs = 5000 } = req.body || {};

  if (typeof code !== "string") {
    return res.status(400).json({ error: "code must be a string" });
  }

  let sandbox;

  try {
    sandbox = await compute.sandbox.create();

    const wrapped = `
import signal, sys

def _timeout(signum, frame):
    print("Time limit exceeded (timeout).", file=sys.stderr)
    sys.exit(124)

signal.signal(signal.SIGALRM, _timeout)
signal.alarm(${Math.max(1, Math.ceil(timeoutMs / 1000))})

${code}
`;

    const result = await sandbox.runCode(wrapped, "python");

    res.json({
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
      exitCode: result.exitCode ?? 0
    });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  } finally {
    if (sandbox) {
      try {
        await sandbox.destroy();
      } catch (_) {}
    }
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Runner listening on ${port}`);
});