# Setting up the BreakNWipe APT repository — step by step

This is the one-time setup that turns `sudo apt install breaknwipe` into a real thing. You run
every command below yourself, on your own machine (you need `gh` authenticated and push access
to the repo, which this assistant doesn't have). I'll explain what each step does and why, and
check the result with you before moving to the next one — nothing here is meant to be a black box.

**What's already done (by the assistant, in code, no secrets involved):**
- `scripts/build_packages.sh` — builds a self-contained `.deb` (vendors BreakNWipe + all its
  Python dependencies into a `uv`-managed virtual environment, so the package doesn't depend on
  system Python packaging at all). Verified locally end-to-end in a clean Ubuntu 24.04 container:
  build → install → run all work.
- `.github/workflows/apt-repo.yml` — a GitHub Actions workflow that builds that `.deb`, assembles
  a proper signed APT repository tree, and publishes it to the `gh-pages` branch. Verified locally
  (outside of GitHub) that the exact same `dpkg-scanpackages`/`apt-ftparchive`/`gpg` commands it
  runs produce a repo that `apt-get update && apt-get install` actually accepts and installs from.

**What's left — five steps, all below:**

---

## Step 1 — Generate the GPG signing key

This key is what makes the repo trustworthy: `apt` refuses to install from an unsigned repo (or
warns loudly), so every package needs to be signed by a key `apt` has been told to trust. We
generate it once; the *private* half goes into a GitHub secret (only GitHub Actions can use it to
sign new releases), and the *public* half gets committed to the repo (so anyone's `apt` can verify
signatures against it).

Run this on your own machine, in a scratch directory (not inside the repo):

```bash
mkdir -p ~/breaknwipe-gpg-setup && cd ~/breaknwipe-gpg-setup

gpg --batch --gen-key <<'EOF'
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: BreakNWipe APT Repo
Name-Email: codebreakers@gmail.com
Expire-Date: 2y
EOF
```

- `%no-protection` — no passphrase on the key. This is intentional: GitHub Actions needs to use
  this key non-interactively during CI, and there's no good way to type a passphrase there. The
  key only ever lives in a GitHub secret (encrypted at rest, never shown in logs) and on your
  machine briefly during this setup, so the usual "no passphrase = weak" concern doesn't really
  apply here the way it would for, say, your personal email key.
- `Expire-Date: 2y` — the key auto-expires in 2 years as a safety net; you'll just repeat this
  whole setup to rotate it when that comes due.

**Tell me what output you get** (it should end with something like `gpg: key ABCD1234EFGH5678
marked as ultimately trusted` / a `revocation certificate stored` line) and I'll help you interpret
it if anything looks off before continuing.

---

## Step 2 — Export both halves of the key

```bash
gpg --armor --export codebreakers@gmail.com > pubkey.gpg
gpg --armor --export-secret-keys codebreakers@gmail.com > private.key
```

- `pubkey.gpg` — the **public** key. Safe to share/commit; it's what lets anyone's `apt` verify
  that a package really came from this key, not forge signatures.
- `private.key` — the **private** key. This is the sensitive one — anyone with it can sign
  packages that your users' `apt` will trust and auto-install as root. It goes into a GitHub
  secret in Step 3 and then gets deleted from your disk. Don't commit it, don't paste its contents
  anywhere else.

Check both files exist and `pubkey.gpg` looks like a normal PGP armored block:

```bash
head -3 pubkey.gpg
```

You should see `-----BEGIN PGP PUBLIC KEY BLOCK-----` followed by base64-looking text. **Paste me
that first line (just the header, not the key material) to confirm it's the right format.**

---

## Step 3 — Commit the public key, add the private key as a GitHub secret

```bash
# From inside your BreakNWipe repo checkout:
mkdir -p docs/apt
cp ~/breaknwipe-gpg-setup/pubkey.gpg docs/apt/pubkey.gpg
git add docs/apt/pubkey.gpg
git commit -m "Add APT repository signing public key"
git push
```

This is why the workflow's "Verify public key is committed" step exists — it refuses to run
until `docs/apt/pubkey.gpg` is present, so a half-finished setup fails loudly instead of silently
publishing an unsigned/broken repo.

Now add the private key as a repo secret (this uploads it encrypted; GitHub never displays it
again after this, not even to you):

```bash
gh secret set APT_GPG_PRIVATE_KEY < ~/breaknwipe-gpg-setup/private.key
```

If that succeeds you'll see `✓ Set secret APT_GPG_PRIVATE_KEY for 41vi4p/BreakNWipe`. Confirm it's
listed (this only shows the name, never the value):

```bash
gh secret list
```

**Now delete the private key from disk — it has no further reason to exist there:**

```bash
rm ~/breaknwipe-gpg-setup/private.key
```

**Tell me once `gh secret list` shows `APT_GPG_PRIVATE_KEY`** and I'll confirm we're good to move on.

---

## Step 4 — Trigger the workflow (this also creates the `gh-pages` branch)

Push a version tag — this is what `.github/workflows/apt-repo.yml` listens for:

```bash
git tag v2.6.1   # match whatever version is currently in breaknwipe/__init__.py
git push origin v2.6.1
```

(You can also trigger it manually without tagging anything yet, to test: go to the repo's
**Actions** tab → "Build and publish APT repository" → **Run workflow**.)

Watch it run:

```bash
gh run watch
```

or just open the **Actions** tab in the browser. This single run does everything: builds the
`.deb` inside a clean Ubuntu container, assembles the signed repo tree, and pushes it to the
`gh-pages` branch (creating that branch automatically if it doesn't exist yet — which is exactly
why we do this *before* enabling Pages in the next step, not after).

**Paste me the run's result (pass/fail) and, if it fails, the name of whichever step failed** —
I'll help debug from there.

---

## Step 5 — Enable GitHub Pages, then verify the real install

Now that `gh-pages` exists (from Step 4), point Pages at it:

```bash
gh api repos/41vi4p/BreakNWipe/pages -X POST -f "source[branch]=gh-pages" -f "source[path]=/" 2>&1 || \
gh api repos/41vi4p/BreakNWipe/pages -X PUT -f "source[branch]=gh-pages" -f "source[path]=/"
```

(The two-command fallback is because the API uses POST the very first time Pages is enabled for a
repo, PUT to update it afterward — running the POST first and falling back to PUT handles either
case without you needing to check which applies.) Or do it via the web UI: repo **Settings** →
**Pages** → Source: **Deploy from a branch** → Branch: `gh-pages` / `/ (root)` → **Save**.

Give it a minute or two to actually publish, then test the real thing — ideally on a spare/VM
Ubuntu or Debian machine (not your main dev machine, since this installs a package system-wide):

```bash
curl -fsSL https://41vi4p.github.io/BreakNWipe/apt/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/breaknwipe.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/breaknwipe.gpg] https://41vi4p.github.io/BreakNWipe/apt stable main" | sudo tee /etc/apt/sources.list.d/breaknwipe.list
sudo apt update
sudo apt install breaknwipe
breaknwipe --help
```

**Tell me what happens at `sudo apt update`** (it should show `Get: ... 41vi4p.github.io ... InRelease` with no GPG/signature warnings) **and at `sudo apt install breaknwipe`.** If `apt update` complains about the signature, it usually means Pages hasn't finished publishing yet — worth waiting a couple of minutes and retrying before assuming something's actually wrong.

---

## After this is all working

Every future release is just:

```bash
# bump breaknwipe/__init__.py + pyproject.toml versions, commit as usual, then:
git tag v<new-version>
git push origin v<new-version>
```

...and every machine that's added the repo gets it via a plain `sudo apt update && sudo apt upgrade` —
no more re-running installer scripts by hand.
