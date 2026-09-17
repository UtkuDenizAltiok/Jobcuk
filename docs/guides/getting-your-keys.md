# Getting your keys

Jobcu needs a few **keys** to work. A key is a long code, like a password, that lets Jobcu use a
service on your behalf. You need:

1. **A key from an AI provider of your choice.** Jobcu uses it to read your CV and job ads and to
   score the jobs.
2. **Two free Adzuna codes** and **one free Reed key**, from two job sites that let apps search
   their job ads.

> ⚠️ **Keep your keys private.** Never send them to anyone, post them, or paste them into an AI
> chat. Anyone with your AI key can use your account and run up costs.
>
> Save each key in a password manager (see the end of this guide). Then enter them in Jobcu's
> **Settings**, as shown in [Your first search](first-search.md).

---

## 1. Your AI key

Jobcu works with many AI providers, and **it doesn't recommend any of them**. The choice is
yours, and you can switch later in Jobcu's settings.

**Before choosing, compare:**

- **Price.** Providers charge for what Jobcu uses, and the price depends on the model you pick.
  Some include a small free allowance.
- **Payment.** Most providers need a payment card or prepaid credit for regular use. You enter it
  on the provider's website, never in Jobcu.
- **Privacy.** Jobcu sends your CV and cover letter to the provider. Some providers' free plans
  allow them to use what you send to improve their AI, and the rules can differ by country. Read
  the provider's terms before choosing.
- **Live web search.** Jobcu can use the AI to search the web for extra jobs. Providers without
  this still work, but Jobcu then skips that one extra source.
- **Spending limit.** Most providers let you set a monthly limit on their website. Setting one is
  a good idea.

Instructions for three common providers follow, in alphabetical order. Jobcu connects to these
directly, and each has built-in web search. Websites change often, so if a button looks
different, look for a similarly named one.

### Anthropic (Claude)

1. Go to [platform.claude.com](https://platform.claude.com) and sign in, or create an account.
2. Open **Settings → API keys**.
3. Click **Create key**, give it a name such as `Jobcu`, and confirm.
4. **Copy the key right away.** It starts with `sk-ant-` and is shown only once.
5. API use is paid: look under **Settings → Billing** to add credit. Your usage limits are shown
   there and under **Settings → Limits**.

### Google (Gemini)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with a Google
   account.
2. If Google shows its terms of service, read them and accept if you agree.
3. Click **Create API key**. First-time users may find a key already created for them.
4. Copy the key.
5. Without billing, you use Google's free allowance, which has daily limits. For paid use, click
   **Set up billing**. You can then set a monthly spend cap on the **Spend** page.

### OpenAI

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and sign in, or create
   an account.
2. Click **Create new secret key**, give it a name such as `Jobcu`, and confirm.
3. **Copy the key right away.** It's shown only once.
4. Regular use needs credit: look under **Settings → Billing**. You can set usage limits in the
   settings too.

### Other providers

Many other providers, including ones you can run on your own computer, offer an
"**OpenAI-compatible**" connection. For these, Jobcu will ask for three things, all listed in the
provider's own documentation: the **base URL** (a web address), the **API key** and the **model
name**.

---

## 2. Adzuna (free)

Adzuna gives you two codes: an **Application ID** and an **Application Key**.

1. Go to [developer.adzuna.com/signup](https://developer.adzuna.com/signup).
2. Fill in the form:
   - **Username, Email, Password, Password confirmation:** your choice
   - **Organisation/Group Name:** for example `Jobcu (personal use)`
   - **Organisation/Group website:** any website of yours, for example your GitHub profile page
   - **Your application of the Adzuna API:** *Personal or academic research*
   - **Average Monthly Visitors:** *N/A*
   - **Primary Market:** *Europe*
   - **Primary Industry:** *Career Services*
3. Read Adzuna's terms. If you agree, tick the box and click **Register for an API key now**.
4. If Adzuna sends a confirmation email, click the link in it.
5. Sign in at developer.adzuna.com and open **API Access Details**. Copy the **Application ID**
   and the **Application Key**.

## 3. Reed (free)

Reed gives you one **API key**.

1. Go to [reed.co.uk/developers/jobseeker](https://www.reed.co.uk/developers/jobseeker).
2. Click the blue **Sign up for a reed.co.uk API Key** button near the top.
3. Fill in **First name**, **Last name** and **Email**, then click **Register**.
4. Your key appears on screen or arrives by email (check spam too). It's a long code with dashes.

---

## Keeping your keys safe until you enter them

Save each key in a password manager.

**On a Mac**, use the built-in **Passwords** app:

1. Press **Command + Space**, type `Passwords`, and press **Return**.
2. Click **+**.
3. Fill in:
   - **Title:** for example `Adzuna API`
   - **User Name:** your email address, or for Adzuna, the Application ID
   - **Password:** paste the key
   - **Website:** the site's full address, for example `developer.adzuna.com`. A name like
     "Adzuna API" won't work here, and the app will ask for a complete address.
4. Click **Save**.

**On Windows**, use any password manager you trust.

Once a key is saved, delete it from any email, note or document where you copied it on the way.
