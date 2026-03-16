import express from "express";

const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/run", async (req, res) => {
  const { code, timeoutMs = 5000 } = req.body || {};
  console.log("RUN REQUEST RECEIVED");

  if (typeof code !== "string") {
    return res.status(400).json({ error: "code must be a string" });
  }

  try {
    const response = await fetch("https://ce.judge0.com/submissions?wait=true", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        language_id: 109,
        source_code: code,
        stdin: "",
        cpu_time_limit: Math.max(1, Math.ceil(timeoutMs / 1000))
      })
    });

    const result = await response.json();
    console.log("JUDGE0 RESPONSE:", result);

    res.json({
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? result.compile_output ?? result.message ?? "",
      exitCode: result.status?.id === 3 ? 0 : 1
    });
  } catch (err) {
    console.error("RUN ERROR:", err);
    res.status(500).json({ error: "Execution service temporarily unavailable." });
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Runner listening on ${port}`);
});