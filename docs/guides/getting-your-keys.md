# Get your keys

A key is a long code that lets Jobcu use a service on your account. You need one: an **AI key**.
The free **Adzuna** and **Reed** keys are optional and add two more job sites; everything else
Jobcu searches needs no key. A **Google Maps** key is optional too: it gives real travel times. **Never share keys or paste them into a chat**; save them in a
password manager, then enter them in Jobcu's **Settings**.

## AI key (your choice of provider)

Jobcu works with many providers and doesn't recommend one. Compare price, free allowance and how
they treat your data, then create a key:

- **Anthropic (Claude):** [platform.claude.com](https://platform.claude.com) → Settings → API keys →
  **Create key**
- **Google (Gemini):** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) →
  **Create API key**
- **OpenAI:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys) →
  **Create new secret key**
- **Others:** choose "Other (OpenAI-compatible)" in Jobcu and enter the address, key and model from
  the provider's documentation.

Copy the key right away (it's often shown only once). If you add payment details at the provider,
set a monthly spending limit there.

## Adzuna (free)

1. Sign up at [developer.adzuna.com/signup](https://developer.adzuna.com/signup). For the form,
   use e.g. *Personal or academic research*, *N/A* visitors, *Europe*, *Career Services*.
2. Sign in → **API Access Details** → copy the **Application ID** and **Application Key**.

## Reed (free)

1. Go to [reed.co.uk/developers/jobseeker](https://www.reed.co.uk/developers/jobseeker) → **Sign up
   for a reed.co.uk API Key** → fill in name and email → **Register**.
2. Copy the key shown on screen or sent by email.

## Google Maps (optional, for travel times)

Only needed if you write things like *"at most 50 minutes by public transport to a big city"*.
Without it, the AI estimates travel times. Google asks for a card, but gives a free allowance
every month, and Jobcu stops below it.

1. Open [console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate),
   name the project *Jobcu* → **Create**.
2. Add a billing account when Google asks. Then set a small budget alert (for example €1) at
   [console.cloud.google.com/billing/budgets](https://console.cloud.google.com/billing/budgets).
3. Turn on the [Routes API](https://console.cloud.google.com/apis/library/routes.googleapis.com)
   and the [Places API (New)](https://console.cloud.google.com/apis/library/places.googleapis.com)
   (**Enable** on each page).
4. [Credentials](https://console.cloud.google.com/apis/credentials) → **Create credentials** →
   **API key**. Under **API restrictions**, allow only those two APIs → **Save**.
5. In Jobcu: **Settings → Travel times** → paste the key → **Save** → **Test Google Maps**.

➡️ Next: [Your first search](first-search.md)
