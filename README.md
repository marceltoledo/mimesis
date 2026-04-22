# mimesis

Mimesis — learns a storyteller's writing style and voice from YouTube videos, then generates and narrates new stories from current news using the same voice.

## Operations

### Refreshing YouTube cookies

YouTube's bot-detection blocks requests from Azure datacenter IPs. To bypass this, Mimesis reads a Netscape-format `cookies.txt` from a logged-in YouTube session stored in Key Vault as the `youtube-cookies` secret.

Cookies expire over time (typically within weeks). Follow these steps to refresh them:

#### 1. Export cookies from Firefox

Use [firefox_cookie_exporter_cli](https://github.com/marceltoledo/firefox_cookie_exporter_cli) while logged into YouTube in Firefox:

```bash
# Install
pip install fcookex

# Export ALL youtube.com cookies in one shot (no interactive prompt)
fcookex --search youtube.com --all --output youtube-cookies
# Writes export/youtube-cookies.txt
```

> Alternatively, export interactively (omit `--all`) to hand-pick individual cookies.

#### 2. Upload to Key Vault

```bash
az keyvault secret set \
  --vault-name mimesis-dev-kv \
  --name youtube-cookies \
  --file export/youtube-cookies.txt
```

For production:

```bash
az keyvault secret set \
  --vault-name mimesis-prod-kv \
  --name youtube-cookies \
  --file export/youtube-cookies.txt
```

#### 3. Verify

The `VideoIngestion` function loads the secret on cold-start. Trigger a fresh invocation and confirm success in App Insights — no `Sign in to confirm you're not a bot` errors should appear.

> The `youtube-cookies` secret is managed out-of-band (not via Terraform) because cookies rotate frequently. The Terraform state does not contain cookie values.
