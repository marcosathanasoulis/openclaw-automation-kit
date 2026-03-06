# Credential Setup for `credential_refs`

The `openclaw-automation-kit` is designed to handle sensitive credentials securely using `credential_refs`. This means your actual usernames and passwords are never hardcoded in scripts or committed to source control. Instead, automations reference named entries in your operating system's secure secret store.

Here's how to set up credentials for use with `credential_refs` on different platforms:

## General Principles

*   **Store Locally:** Always store your credentials in your local, secure secret store (e.g., OS keychain).
*   **Reference by Name:** In your automation inputs, you will pass a reference like `{"airline_username": "openclaw/united/username"}`. The OpenClaw engine will then retrieve the actual value associated with `openclaw/united/username` from your secret store.
*   **Never Hardcode:** Do not put raw usernames or passwords directly into your automation scripts or input JSONs.

## Platform-Specific Setup

### 1. macOS Keychain Access

macOS provides a secure and user-friendly Keychain Access application to manage your passwords and certificates.

**To add a credential:**

1.  Open **Keychain Access** (Applications > Utilities > Keychain Access).
2.  From the "File" menu, select **New Password Item...**.
3.  Fill in the details:
    *   **Keychain Item Name:** This should be the full `credential_ref` string used by your automation (e.g., `openclaw/united/username`).
    *   **Account Name:** Your actual username for the service.
    *   **Password:** Your actual password for the service.
4.  Click **Add**.

**Example:**
For an automation expecting `{"airline_username": "openclaw/united/username"}`, you would create a new password item with:
*   Keychain Item Name: `openclaw/united/username`
*   Account Name: `your_united_username`
*   Password: `your_united_password`

### 2. Linux Keyring (e.g., `secret-tool` or `pass`)

On Linux, you can use tools like `secret-tool` (part of `libsecret`) or `pass` (the standard Unix password manager) to manage secrets.

#### Using `secret-tool` (GNOME Keyring)

1.  **Install `secret-tool`** if you don't have it:
    ```bash
    sudo apt-get install libsecret-tools # Debian/Ubuntu
    sudo yum install libsecret-tools # Fedora/CentOS
    ```
2.  **To add a credential:**
    ```bash
    secret-tool store --label="OpenClaw Automation Credential" openclaw_ref "openclaw/united/username"
    # It will then prompt you for the value (your username).
    secret-tool store --label="OpenClaw Automation Credential" openclaw_ref "openclaw/united/password"
    # It will then prompt you for the value (your password).
    ```
    Replace `"openclaw/united/username"` with your actual `credential_ref` name.

#### Using `pass`

1.  **Install `pass`** and initialize your GnuPG key if you haven't already.
2.  **To add a credential:**
    ```bash
    pass insert openclaw/united/username
    pass insert openclaw/united/password
    ```
    Follow the prompts to enter the password. The path `openclaw/united/username` will correspond to your `credential_ref`.

### 3. Environment Variables (for Development/Testing)

For local development or testing, you can expose credentials directly as environment variables. **This method is generally less secure and NOT recommended for production or sensitive credentials.**

1.  **Set Environment Variables:**
    ```bash
    export OPENCLAW_CREDENTIAL_openclaw_united_username="your_united_username"
    export OPENCLAW_CREDENTIAL_openclaw_united_password="your_united_password"
    ```
    The format is `OPENCLAW_CREDENTIAL_<credential_ref_path_with_underscores>`.

**Example:**
If your `credential_ref` is `openclaw/united/username`, the environment variable should be `OPENCLAW_CREDENTIAL_openclaw_united_username`.

## Referencing in Automations

In your automation's input JSON, you would then simply reference these names:

```json
{
  "from": "SFO",
  "to": ["AMS"],
  "credential_refs": {
    "airline_username": "openclaw/united/username",
    "airline_password": "openclaw/united/password"
  }
}
```
The OpenClaw engine will automatically resolve these references to the actual values stored in your configured secret manager.