# Browser Backend Selection

Read the project external-service policy before accessing a provider. A missing `browser_run` record is disabled: do not infer authorization from a configured tool, and use the configured fallback.

First classify the operation. Reads inspect, extract, or produce a local browser artifact without changing a remote service. Writes include form submission, publication, purchase, upload, account mutation, or any other remote change. Before any write, require `configured_write_capable`, an allowlisted operation, an exact `write_authorization_rule` match, and current user authorization for that exact effect. Then choose a backend; write classification does not by itself make Kitesurf incompatible.

Use authorized Kitesurf for compatible short-lived, state-independent one-shot screenshots, PDFs, extraction, or automation. Kitesurf is beta and is a conditional first choice because compatible work uses lower CPU and memory consumption. Its compatibility boundary is documented by [Cloudflare](https://blog.cloudflare.com/kitesurf/).

Select an authorized Chromium-capable fallback for long authenticated sessions, persistent state, video, WebGL, pixel-perfect output, bot-challenge handshakes requiring real TLS fingerprints, or an observed Kitesurf compatibility failure. If neither backend is authorized and available, use ordinary HTTP retrieval only when it satisfies the request; otherwise report the unavailable-browser fallback without performing the browser operation.
